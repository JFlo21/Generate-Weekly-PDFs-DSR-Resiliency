"""pipeline.reporting_corrections -- opt-in, owner-approved reporting
corrections for already-billed (WR, week ending) cases.

A *correction* re-credits specific source rows (matched by their exact
Smartsheet ``(sheet_id, row_id)``) to an approved owner and reporting
workday, without touching a single raw Smartsheet cell value. It exists
for the rare case where the field data is right but the reporting
assignment (who earned a unit, on which day) was entered wrong and the
owner has approved a row-by-row allocation.

Activation is opt-in through ``REPORTING_CORRECTIONS_FILE`` (a path to a
JSON file, see ``docs/templates/reporting_corrections.template.json``).
Unset -> every public hook in this module is an identity no-op and the
pipeline is byte-identical to a run without this module.

Seams (each is a small, additive call from the owning module):

* ``pipeline.fetch``          -- ``recovery_for_row``: pre-admission
  recovery of explicitly listed rows whose two date cells are blank.
* ``pipeline.orchestrate``    -- ``prepare_run``: validate every
  correction against the admitted rows, stamp applied rows, block
  mismatched cases, compute displaced group keys, count audit findings.
* ``pipeline.grouping``       -- ``apply_credit_overrides``: exclusive
  credit for stamped rows, after the frozen-claimer maps are built.
* ``pipeline.excel``          -- ``reporting_workday``: day placement.
* ``pipeline.change_detection`` -- ``group_correction_token``: the
  ``CORR=`` hash token.

This module never imports a ``pipeline_memory`` or ``billing_audit``
writer and performs no I/O except reading the configured JSON file, so
the ``preview`` / ``validate`` CLI below makes zero external writes::

    python -m pipeline.reporting_corrections validate --file F
    python -m pipeline.reporting_corrections preview --file F \
        --rows-json ROWS [--memory-json MEM]

Logging rule: log lines carry correction ids, WR numbers, row ids and
counts only -- never a person's name (Sentry breadcrumbs inherit them).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import logging
import sys
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable, Mapping, cast

from pipeline import config as _cfg
from pipeline.pricing import parse_price
from pipeline.types import normalize_helper_value
from pipeline.utils import excel_serial_to_date, is_checked

SCHEMA_VERSION = 1
VARIANTS = ('primary', 'helper', 'helper2')
EXPECT_KEYS = (
    'pole', 'cu', 'work_type', 'quantity', 'units_total_price',
    'snapshot_date', 'weekly_reference_logged_date', 'units_completed',
)
_CENT = Decimal('0.01')
_JOB_ALIASES = (
    'Job #', 'Job#', 'Job Number', 'JobNumber', 'Job_Number',
    'JOB #', 'JOB#', 'job #', 'job#',
)
# Row keys this module stamps; all are "__"-prefixed so excel.py's
# column sampler and calculate_data_hash()'s named-field reads never
# see them (same convention as __row_modified_at / __mem_*).
STAMP_KEYS = (
    '__corr_id', '__corr_revision', '__corr_credit', '__corr_workday',
    '__corr_week_ending', '__corr_recovered',
)


class CorrectionError(ValueError):
    """The corrections file is invalid; ``problems`` lists every issue."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__('; '.join(problems))
        self.problems = problems


@dataclass(frozen=True)
class CorrectionRow:
    sheet_id: int
    row_id: int
    name: str
    variant: str
    dept: str
    job: str
    workday: datetime.date
    expect: Mapping[str, Any]
    recover_missing_dates: bool = False

    @property
    def key(self) -> tuple[int, int]:
        return (self.sheet_id, self.row_id)


@dataclass(frozen=True)
class Correction:
    correction_id: str
    revision: int
    wr: str
    week_ending: datetime.date
    rows: tuple[CorrectionRow, ...]
    expected_subtotals: Mapping[str, Mapping[str, str]] | None = None

    @property
    def pair(self) -> tuple[str, datetime.date]:
        return (self.wr, self.week_ending)


@dataclass(frozen=True)
class CorrectionSet:
    corrections: tuple[Correction, ...]
    by_row: Mapping[tuple[int, int], tuple[Correction, CorrectionRow]] = (
        field(default_factory=dict)
    )


@dataclass
class CorrectionResult:
    correction: Correction
    status: str = 'applied'
    reasons: list[str] = field(default_factory=list)
    matched: list[CorrectionRow] = field(default_factory=list)
    missing: list[CorrectionRow] = field(default_factory=list)
    mismatched: list[tuple[CorrectionRow, list[str]]] = field(
        default_factory=list)
    subtotals: dict[tuple[str, str], Decimal] = field(default_factory=dict)
    subtotal_rows: dict[tuple[str, str], int] = field(default_factory=dict)
    observed_totals: dict[str, Decimal] = field(default_factory=dict)
    credited_totals: dict[str, Decimal] = field(default_factory=dict)
    blank_date_rows: list[CorrectionRow] = field(default_factory=list)
    reassigned_rows: list[CorrectionRow] = field(default_factory=list)


# ---------------------------------------------------------------- loader

def _iso_date(value: Any) -> datetime.date | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.date.fromisoformat(value.strip())
    except ValueError:
        return None


def _text(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _parse_row(raw: Any, where: str, week_ending: datetime.date,
               scope_days: set[datetime.date] | None,
               problems: list[str]) -> CorrectionRow | None:
    if not isinstance(raw, dict):
        problems.append(f'{where}: row entry must be an object')
        return None
    before = len(problems)
    sid, rid = raw.get('sheet_id'), raw.get('row_id')
    for label, val in (('sheet_id', sid), ('row_id', rid)):
        if not isinstance(val, int) or isinstance(val, bool) or val <= 0:
            problems.append(f'{where}: {label} must be a positive integer')
    credit = raw.get('credit')
    if not isinstance(credit, dict):
        problems.append(f'{where}: credit must be an object')
        credit = {}
    name = _text(credit.get('name'))
    variant = credit.get('variant')
    dept = _text(credit.get('dept'))
    job = _text(credit.get('job'))
    if not name:
        problems.append(f'{where}: credit.name is required')
    if variant not in VARIANTS:
        problems.append(
            f'{where}: credit.variant must be one of {list(VARIANTS)}')
    elif variant in ('helper', 'helper2') and not dept:
        problems.append(f'{where}: credit.dept is required for {variant}')
    workday = _iso_date(raw.get('workday'))
    if workday is None:
        problems.append(f'{where}: workday must be an ISO date')
    elif not (week_ending - datetime.timedelta(days=6)
              <= workday <= week_ending):
        problems.append(
            f'{where}: workday {workday} is outside the reporting week '
            f'ending {week_ending}')
    elif scope_days is not None and workday not in scope_days:
        problems.append(f'{where}: workday {workday} not in scope_days')
    expect = raw.get('expect')
    if not isinstance(expect, dict):
        problems.append(f'{where}: expect must be an object')
        expect = {}
    missing = [k for k in EXPECT_KEYS if k not in expect]
    if missing:
        problems.append(f'{where}: expect is missing {missing}')
    recover = raw.get('recover_missing_dates', False)
    if not isinstance(recover, bool):
        problems.append(f'{where}: recover_missing_dates must be boolean')
        recover = False
    if recover and (expect.get('snapshot_date') is not None
                    or expect.get('weekly_reference_logged_date')
                    is not None):
        problems.append(
            f'{where}: recover_missing_dates requires both expected '
            'dates to be null')
    for dkey in ('snapshot_date', 'weekly_reference_logged_date'):
        dval = expect.get(dkey)
        if dval is not None and _iso_date(dval) is None:
            problems.append(f'{where}: expect.{dkey} must be ISO or null')
    if len(problems) != before or workday is None:
        return None
    return CorrectionRow(
        sheet_id=cast(int, sid), row_id=cast(int, rid), name=name,
        variant=str(variant), dept=dept,
        job=job, workday=workday, expect=dict(expect),
        recover_missing_dates=recover,
    )


def _parse_correction(raw: Any, idx: int,
                      problems: list[str]) -> Correction | None:
    where = f'corrections[{idx}]'
    if not isinstance(raw, dict):
        problems.append(f'{where}: must be an object')
        return None
    before = len(problems)
    cid = _text(raw.get('id'))
    if not cid:
        problems.append(f'{where}: id is required')
    revision = raw.get('revision')
    if (not isinstance(revision, int) or isinstance(revision, bool)
            or revision < 1):
        problems.append(f'{where}: revision must be an integer >= 1')
    wr = _text(raw.get('wr')).split('.')[0]
    if not wr:
        problems.append(f'{where}: wr is required')
    week_ending = _iso_date(raw.get('week_ending'))
    if week_ending is None:
        problems.append(f'{where}: week_ending must be an ISO date')
        return None
    scope_days: set[datetime.date] | None = None
    if raw.get('scope_days') is not None:
        days = raw.get('scope_days')
        parsed = [_iso_date(d) for d in days] if isinstance(
            days, list) else [None]
        if None in parsed:
            problems.append(f'{where}: scope_days must be ISO dates')
        else:
            scope_days = {d for d in parsed if d is not None}
    subtotals = raw.get('expected_subtotals')
    if subtotals is not None:
        ok = isinstance(subtotals, dict) and all(
            isinstance(v, dict) and all(
                _iso_date(d) is not None and _decimal(a) is not None
                for d, a in v.items())
            for v in subtotals.values())
        if not ok:
            problems.append(
                f'{where}: expected_subtotals must map name -> '
                '{ISO day: amount}')
    rows_raw = raw.get('rows')
    if not isinstance(rows_raw, list) or not rows_raw:
        problems.append(f'{where}: rows must be a non-empty list')
        rows_raw = []
    rows = []
    for j, row in enumerate(rows_raw):
        parsed_row = _parse_row(
            row, f'{where}.rows[{j}]', week_ending, scope_days, problems)
        if parsed_row is not None:
            rows.append(parsed_row)
    if len(problems) != before:
        return None
    return Correction(
        correction_id=cid, revision=cast(int, revision), wr=wr,
        week_ending=week_ending, rows=tuple(rows),
        expected_subtotals=subtotals,
    )


def parse_corrections(data: Any) -> CorrectionSet:
    """Validate a decoded corrections document; raise ``CorrectionError``
    listing every problem, or return the effective ``CorrectionSet``.

    Supersession: two entries for one ``(wr, week_ending)`` are allowed
    only when they share an ``id`` and differ in ``revision``; the
    highest revision is effective and the rest are ignored.
    """
    problems: list[str] = []
    if not isinstance(data, dict):
        raise CorrectionError(['document must be a JSON object'])
    if data.get('schema') != SCHEMA_VERSION:
        problems.append(f'schema must be {SCHEMA_VERSION}')
    raw_list = data.get('corrections')
    if not isinstance(raw_list, list) or not raw_list:
        problems.append('corrections must be a non-empty list')
        raw_list = []
    parsed = [_parse_correction(c, i, problems)
              for i, c in enumerate(raw_list)]
    if problems:
        raise CorrectionError(problems)
    by_pair: dict[tuple[str, datetime.date], list[Correction]] = {}
    ids: dict[str, tuple[str, datetime.date]] = {}
    for corr in parsed:
        assert corr is not None
        if ids.setdefault(corr.correction_id, corr.pair) != corr.pair:
            problems.append(
                f'id {corr.correction_id} is reused for a different '
                'wr/week_ending')
        by_pair.setdefault(corr.pair, []).append(corr)
    effective: list[Correction] = []
    for pair, group in by_pair.items():
        if len({c.correction_id for c in group}) > 1:
            problems.append(
                f'overlapping corrections for WR {pair[0]} week '
                f'{pair[1]} (only a superseding revision of the same id '
                'may share a wr/week)')
            continue
        revisions = [c.revision for c in group]
        if len(set(revisions)) != len(revisions):
            problems.append(
                f'duplicate revision for correction {group[0].correction_id}')
            continue
        effective.append(max(group, key=lambda c: c.revision))
    by_row: dict[tuple[int, int], tuple[Correction, CorrectionRow]] = {}
    for corr in effective:
        for row in corr.rows:
            if row.key in by_row:
                problems.append(
                    f'row {row.sheet_id}/{row.row_id} appears more than '
                    'once across corrections')
            by_row[row.key] = (corr, row)
    if problems:
        raise CorrectionError(problems)
    return CorrectionSet(corrections=tuple(effective), by_row=by_row)


def load_corrections(path: str) -> CorrectionSet:
    """Read and validate the JSON file at *path*."""
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise CorrectionError(
            [f'cannot read corrections file: {type(exc).__name__}'])
    return parse_corrections(data)


_ACTIVE_CACHE: dict[str, CorrectionSet | None] = {}


def get_active_set() -> CorrectionSet | None:
    """The configured correction set, or ``None`` (feature off).

    An invalid file is logged at ERROR (no names) and treated as "no
    corrections": the pipeline then behaves exactly as without the file,
    which is today's output -- never a partially applied correction.
    """
    path = getattr(_cfg, 'REPORTING_CORRECTIONS_FILE', None)
    if not path:
        return None
    if path not in _ACTIVE_CACHE:
        try:
            _ACTIVE_CACHE[path] = load_corrections(path)
        except CorrectionError as exc:
            logging.error(
                '🚫 Reporting corrections file is invalid; NO correction '
                f'will be applied this run ({len(exc.problems)} '
                f'problem(s)): {exc.problems[:5]}')
            _ACTIVE_CACHE[path] = None
    return _ACTIVE_CACHE[path]


def reset_state() -> None:
    """Forget the cached file and this run's registries."""
    _ACTIVE_CACHE.clear()
    _DISPLACED.clear()
    _RUN_COUNTS.clear()


reset_for_tests = reset_state


# ------------------------------------------------------------- matching

def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value)).quantize(_CENT)
    except (InvalidOperation, ValueError, TypeError):
        return None


def row_key(row: Mapping[str, Any]) -> tuple[int, int] | None:
    sid = row.get('__source_sheet_id', row.get('__sheet_id'))
    rid = row.get('__row_id')
    if isinstance(sid, int) and isinstance(rid, int):
        return (sid, rid)
    return None


def _row_wr(row: Mapping[str, Any]) -> str:
    raw = row.get('Work Request #')
    return str(raw).split('.')[0].strip() if raw else ''


def _row_date_iso(row: Mapping[str, Any], col: str) -> str | None:
    parsed = excel_serial_to_date(row.get(col))
    return parsed.date().isoformat() if parsed is not None else None


def row_amount(row: Mapping[str, Any]) -> Decimal:
    """The row's billed amount, as the pipeline prices it."""
    return Decimal(str(parse_price(row.get('Units Total Price')))).quantize(
        _CENT)


def _row_job(row: Mapping[str, Any]) -> str:
    for key in _JOB_ALIASES:
        value = row.get(key)
        if value:
            return _text(value)
    return ''


def _same_number_or_text(a: str, b: str) -> bool:
    if a == b:
        return True
    try:
        return Decimal(a) == Decimal(b)
    except (InvalidOperation, ValueError):
        return False


def row_differences(entry: CorrectionRow, corr: Correction,
                    row: Mapping[str, Any]) -> list[str]:
    """Every way *row* differs from the approved expectation (pure)."""
    exp = entry.expect
    diffs: list[str] = []
    if _row_wr(row) != corr.wr:
        diffs.append('work request differs')
    checks = (
        ('pole', _text(row.get('Pole #') or row.get('Point #')
                       or row.get('Point Number')),
         _text(exp.get('pole'))),
        ('cu', _text(row.get('CU') or row.get('Billable Unit Code')),
         _text(exp.get('cu'))),
        ('work_type', _text(row.get('Work Type')),
         _text(exp.get('work_type'))),
    )
    for label, got, want in checks:
        if got != want:
            diffs.append(f'{label}: {got!r} != expected {want!r}')
    got_qty = _decimal(row.get('Quantity'))
    if got_qty is None or got_qty != _decimal(exp.get('quantity')):
        diffs.append(
            f"quantity: {row.get('Quantity')!r} != expected "
            f"{exp.get('quantity')!r}")
    got_price = row_amount(row)
    if got_price != _decimal(exp.get('units_total_price')):
        diffs.append(
            f'units_total_price: {got_price} != expected '
            f"{exp.get('units_total_price')}")
    for dkey, col in (('snapshot_date', 'Snapshot Date'),
                      ('weekly_reference_logged_date',
                       'Weekly Reference Logged Date')):
        got_d = _row_date_iso(row, col)
        if got_d != exp.get(dkey):
            diffs.append(f'{dkey}: {got_d} != expected {exp.get(dkey)}')
    if is_checked(row.get('Units Completed?')) != bool(
            exp.get('units_completed')):
        diffs.append('units_completed differs')
    if row.get('__is_vac_crew') or row.get('__is_subcontractor'):
        diffs.append('unsupported row type (VAC crew / subcontractor)')
    if entry.variant == 'primary':
        dept = _text(row.get('Dept #'))
        if entry.dept and not _same_number_or_text(dept, entry.dept):
            diffs.append(
                'primary credit dept differs from the row Dept # '
                '(a primary dept override is not supported)')
        if entry.job and not _same_number_or_text(_row_job(row),
                                                  entry.job):
            diffs.append(
                'primary credit job differs from the row Job # '
                '(a primary job override is not supported)')
    return diffs


def observed_owner(row: Mapping[str, Any]) -> str:
    """Who the current sheet data credits for *row* (helper #2 > helper
    > primary), from pipeline flags when present, else raw cells."""
    if '__effective_user' in row or '__is_helper_row' in row:
        if row.get('__is_helper2_row') and row.get('__helper2_foreman'):
            return str(row['__helper2_foreman'])
        if row.get('__is_helper_row') and row.get('__helper_foreman'):
            return str(row['__helper_foreman'])
        return str(row.get('__effective_user') or '')
    done = is_checked(row.get('Units Completed?'))
    h2 = normalize_helper_value(row.get('Foreman Helping? #2'))
    if done and h2 and is_checked(
            row.get('Helping Foreman #2 Completed Unit?')):
        return h2
    h1 = _text(row.get('Foreman Helping?'))
    if done and h1 and is_checked(row.get('Helping Foreman Completed Unit?')):
        return h1
    return _text(row.get('Foreman Assigned?') or row.get('Foreman'))


def evaluate(cset: CorrectionSet,
             rows: Iterable[Mapping[str, Any]]) -> list[CorrectionResult]:
    """Match every correction against *rows* by exact (sheet, row) id.

    A correction is ``blocked`` when any of its rows is missing, differs
    from its expectation, or its subtotals disagree with
    ``expected_subtotals``; a blocked correction applies nothing.
    """
    index: dict[tuple[int, int], Mapping[str, Any]] = {}
    for row in rows:
        key = row_key(row)
        if key is not None and key in cset.by_row:
            index[key] = row
    results = []
    for corr in cset.corrections:
        res = CorrectionResult(correction=corr)
        for entry in corr.rows:
            hit_row = index.get(entry.key)
            if hit_row is None:
                res.missing.append(entry)
                continue
            row = hit_row
            diffs = row_differences(entry, corr, row)
            if diffs:
                res.mismatched.append((entry, diffs))
                continue
            res.matched.append(entry)
            amount = row_amount(row)
            sub_key = (entry.name, entry.workday.isoformat())
            res.subtotals[sub_key] = res.subtotals.get(
                sub_key, Decimal('0.00')) + amount
            res.subtotal_rows[sub_key] = res.subtotal_rows.get(
                sub_key, 0) + 1
            owner = observed_owner(row) or '<unassigned>'
            res.observed_totals[owner] = res.observed_totals.get(
                owner, Decimal('0.00')) + amount
            res.credited_totals[entry.name] = res.credited_totals.get(
                entry.name, Decimal('0.00')) + amount
            if (_row_date_iso(row, 'Snapshot Date') is None
                    or _row_date_iso(row, 'Weekly Reference Logged Date')
                    is None):
                res.blank_date_rows.append(entry)
            if owner != entry.name:
                res.reassigned_rows.append(entry)
        if res.missing:
            res.reasons.append(f'{len(res.missing)} row(s) not found')
        if res.mismatched:
            res.reasons.append(
                f'{len(res.mismatched)} row(s) differ from expectation')
        if corr.expected_subtotals is not None and not (
                res.missing or res.mismatched):
            want = {
                (name, day): _decimal(amount)
                for name, days in corr.expected_subtotals.items()
                for day, amount in days.items()
            }
            if want != res.subtotals:
                res.reasons.append('subtotals differ from expected')
        if res.reasons:
            res.status = 'blocked'
        results.append(res)
    return results


def memory_differences(
    rows: Iterable[Mapping[str, Any]],
    memory_images: Mapping[Any, Mapping[str, Any]],
    *,
    price_tolerance: Decimal = Decimal('0.01'),
) -> list[dict[str, Any]]:
    """Material source-vs-memory differences for the given rows (pure).

    *memory_images* maps ``row_id`` (int or str) to the last stored
    run-memory image with optional ``units_total_price``,
    ``snapshot_date`` and ``week_ending`` keys. A difference is listed,
    never resolved: the current source value stays authoritative unless
    the owner decides otherwise.
    """
    found = []
    for row in rows:
        rid = row.get('__row_id')
        image = memory_images.get(rid, memory_images.get(str(rid)))
        if not image:
            continue
        diffs: list[tuple[str, Any, Any]] = []
        mem_price = _decimal(image.get('units_total_price'))
        if mem_price is not None and abs(
                mem_price - row_amount(row)) >= price_tolerance:
            diffs.append(('units_total_price', str(mem_price),
                          str(row_amount(row))))
        for mkey, col in (('snapshot_date', 'Snapshot Date'),
                          ('week_ending', 'Weekly Reference Logged Date')):
            if mkey in image and image.get(mkey) != _row_date_iso(row, col):
                diffs.append((mkey, image.get(mkey), _row_date_iso(row, col)))
        if diffs:
            found.append({'row_id': rid, 'differences': diffs})
    return found


# ------------------------------------------------------- pipeline seams

def recovery_for_row(row_data: Mapping[str, Any],
                     sheet_id: Any, row_id: Any) -> dict[str, Any] | None:
    """fetch.py seam: reporting-only fields for an explicitly listed row
    whose Weekly Reference Logged Date / Snapshot Date are blank, or None.

    Only rows flagged ``recover_missing_dates`` qualify, and only when the
    row still satisfies every ``expect`` value (blank dates included).
    Raw cells are never changed; the returned keys are ``__``-prefixed.
    """
    cset = get_active_set()
    if cset is None:
        return None
    hit = cset.by_row.get((sheet_id, row_id))
    if hit is None:
        return None
    corr, entry = hit
    if not entry.recover_missing_dates:
        return None
    if row_differences(entry, corr, row_data):
        return None
    return {
        '__corr_week_ending': corr.week_ending.isoformat(),
        '__corr_workday': entry.workday.isoformat(),
        '__corr_id': corr.correction_id,
        '__corr_recovered': True,
    }


def _strip(row: dict[str, Any]) -> None:
    for key in STAMP_KEYS:
        row.pop(key, None)


def _entry_tuple(entry: CorrectionRow, revision: int) -> tuple:
    return (entry.sheet_id, entry.row_id, entry.name, entry.variant,
            entry.dept, entry.job, entry.workday.isoformat(), revision)


# group key -> frozenset of correction tuples displaced from that group;
# group key -> uncorrected rows (for identity of now-empty groups).
_DISPLACED: dict[str, Any] = {}
_RUN_COUNTS: dict[str, int] = {}


def _uncorrected_copy(row: Mapping[str, Any]) -> dict[str, Any]:
    copy = dict(row)
    _strip(copy)
    return copy


def prepare_run(
    rows: list[dict[str, Any]],
    *,
    group_fn: Callable[[list[dict[str, Any]]], Mapping[str, list]] | None,
    audit_summary: Any = None,
) -> dict[str, Any]:
    """orchestrate.py seam, after fetch and before grouping.

    Evaluates every active correction against *rows* (mutated in place):
    applied corrections stamp their rows; blocked corrections strip any
    stamp and drop their recovered rows (so today's blank-date safeguard
    holds). Displaced group keys -- the keys corrected rows would have
    had WITHOUT the correction -- are computed with *group_fn* over the
    uncorrected copies of the corrected (wr, week) pairs only, and
    registered for the ``CORR=`` token and empty-group cleanup.

    Returns a summary of counts (no names). Feature off -> ``{}`` and
    nothing is touched.
    """
    _DISPLACED.clear()
    _RUN_COUNTS.clear()
    cset = get_active_set()
    if cset is None:
        return {}
    results = evaluate(cset, rows)
    applied_rows: dict[tuple[int, int], tuple[Correction, CorrectionRow]] = {}
    blocked_ids: set[str] = set()
    for res in results:
        corr = res.correction
        if res.status == 'blocked':
            blocked_ids.add(corr.correction_id)
            logging.warning(
                f'⛔ Reporting correction {corr.correction_id} '
                f'(rev {corr.revision}) BLOCKED for WR {corr.wr} week '
                f'{corr.week_ending}: {"; ".join(res.reasons)} -- nothing '
                'applied; existing logic stays in force')
            for entry, diffs in res.mismatched[:10]:
                logging.warning(
                    f'   row {entry.row_id}: {"; ".join(diffs)[:300]}')
            continue
        for entry in res.matched:
            applied_rows[entry.key] = (corr, entry)
        logging.warning(
            f'✏️ Reporting correction {corr.correction_id} (rev '
            f'{corr.revision}) APPLIED to WR {corr.wr} week '
            f'{corr.week_ending}: {len(res.matched)} row(s), '
            f'{len(res.reassigned_rows)} re-credited, '
            f'{len(res.blank_date_rows)} with blank source dates')
    kept: list[dict[str, Any]] = []
    recovered = 0
    for row in rows:
        key = row_key(row)
        hit = applied_rows.get(key) if key is not None else None
        if hit is None:
            if row.get('__corr_recovered') or row.get('__corr_id'):
                if row.get('__corr_recovered'):
                    continue  # recovered row of a blocked correction
                _strip(row)
            kept.append(row)
            continue
        corr, entry = hit
        row['__corr_id'] = corr.correction_id
        row['__corr_revision'] = corr.revision
        row['__corr_credit'] = (entry.name, entry.variant, entry.dept,
                                entry.job)
        row['__corr_workday'] = entry.workday.isoformat()
        if row.get('__corr_recovered'):
            recovered += 1
        kept.append(row)
    rows[:] = kept
    displaced = 0
    if applied_rows and group_fn is not None:
        displaced = _register_displaced(rows, applied_rows, group_fn)
    findings = {
        'blank_source_dates': sum(
            len(r.blank_date_rows) for r in results
            if r.status == 'applied'),
        'credited_differs_from_observed': sum(
            len(r.reassigned_rows) for r in results
            if r.status == 'applied'),
        # Source-vs-memory differences need a row_state read this module
        # never performs; the preview CLI evaluates them (--memory-json).
        'source_memory_differences': None,
    }
    summary = {
        'corrections': len(results),
        'applied': len(results) - len(blocked_ids),
        'blocked': len(blocked_ids),
        'rows_applied': len(applied_rows),
        'rows_recovered': recovered,
        'displaced_groups': displaced,
        'findings': findings,
    }
    if isinstance(audit_summary, dict):
        audit_summary['reporting_corrections'] = summary
    if findings['blank_source_dates'] or blocked_ids:
        logging.warning(
            f'🔎 Reporting-correction audit: {summary} -- review the '
            'flagged rows; nothing is auto-resolved')
    return summary


def _register_displaced(
    rows: list[dict[str, Any]],
    applied_rows: Mapping[tuple[int, int], tuple[Correction,
                                                 CorrectionRow]],
    group_fn: Callable[[list[dict[str, Any]]], Mapping[str, list]],
) -> int:
    pairs = {corr.pair for corr, _ in applied_rows.values()}
    subset = []
    for row in rows:
        if row.get('__corr_recovered'):
            continue  # without the correction this row is not admitted
        week = excel_serial_to_date(row.get('Weekly Reference Logged Date'))
        if week is None or (_row_wr(row), week.date()) not in pairs:
            continue
        subset.append(_uncorrected_copy(row))
    try:
        groups = group_fn(subset) if subset else {}
    except Exception as exc:  # never block the run on a diagnostic pass
        logging.warning(
            '⚠️ Reporting corrections: displaced-group pass failed '
            f'({type(exc).__name__}); corrected groups still carry CORR=')
        return 0
    for gkey, grows in (groups or {}).items():
        tuples = set()
        for grow in grows:
            hit = applied_rows.get(row_key(grow) or (0, 0))
            if hit is not None:
                tuples.add(_entry_tuple(hit[1], hit[0].revision))
        if tuples:
            _DISPLACED[gkey] = {'tokens': frozenset(tuples),
                                'rows': list(grows)}
    return len(_DISPLACED)


def correction_pairs() -> set[tuple[str, str]]:
    """(wr, week ISO) pairs of every active correction (incremental
    mode's explicit, bounded fallback). Empty when the feature is off."""
    cset = get_active_set()
    if cset is None:
        return set()
    return {(c.wr, c.week_ending.isoformat()) for c in cset.corrections}


def correction_sheet_ids() -> set[int]:
    cset = get_active_set()
    if cset is None:
        return set()
    return {sid for sid, _ in cset.by_row}


def displaced_groups() -> dict[str, list[dict[str, Any]]]:
    """Displaced group key -> its uncorrected rows (copy)."""
    return {k: list(v['rows']) for k, v in _DISPLACED.items()}


def apply_credit_overrides(rows: list[dict[str, Any]],
                           *claimer_maps: dict) -> list[dict[str, Any]]:
    """grouping.py seam: exclusive credit for every stamped row.

    Returns *rows* itself when no row is stamped (feature off). Stamped
    rows are replaced by overridden COPIES (the shared row dicts are
    never mutated) and their entries are dropped from the frozen-claimer
    maps so a frozen claimer can never win over an approved correction.
    Unstamped rows keep the existing logic untouched.
    """
    if not any('__corr_credit' in r for r in rows):
        return rows
    known = _known_helper_reprs(rows)
    out = []
    frozen_overrides = 0
    for row in rows:
        credit = row.get('__corr_credit')
        if not credit:
            out.append(row)
            continue
        rid = row.get('__row_id')
        for cmap in claimer_maps:
            outcome = cmap.pop(rid, None)
            name = getattr(outcome, 'name', None)
            if getattr(outcome, 'action', None) == 'use' and name and (
                    name != credit[0]):
                frozen_overrides += 1
        out.append(_overridden(row, credit, known))
    _RUN_COUNTS['frozen_overrides'] = (
        _RUN_COUNTS.get('frozen_overrides', 0) + frozen_overrides)
    if frozen_overrides:
        logging.warning(
            f'✏️ Reporting corrections overrode {frozen_overrides} frozen '
            'claimer(s) for this grouping pass (attribution_snapshot is '
            'not modified)')
    return out


def _known_helper_reprs(
    rows: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str, str], list[str]]:
    """(wr, helper name, field) -> dept/job spellings today's pipeline
    already uses for that helper on UNcorrected rows of the run."""
    known: dict[tuple[str, str, str], list[str]] = {}
    for row in rows:
        if row.get('__corr_credit'):
            continue
        for flag, prefix in (('__is_helper_row', '__helper'),
                             ('__is_helper2_row', '__helper2')):
            name = row.get(f'{prefix}_foreman')
            if not (row.get(flag) and name):
                continue
            for part in ('dept', 'job'):
                value = row.get(f'{prefix}_{part}')
                if value:
                    known.setdefault(
                        (_row_wr(row), str(name), f'{prefix}_{part}'),
                        []).append(str(value))
    return known


def _helper_value(row: Mapping[str, Any], raw_col: str, credit_value: str,
                  helper2: bool, known: list[str]) -> str:
    """Keep today's spelling of an equal dept/job ('489.0' for '489') so
    the helper identity -- and therefore the file -- stays stable."""
    if not credit_value:
        return ''
    for value in known:
        if _same_number_or_text(value, credit_value):
            return value
    raw = row.get(raw_col)
    derived = normalize_helper_value(raw) if helper2 else (
        str(raw).strip() if raw else '')
    if derived and _same_number_or_text(derived, credit_value):
        return derived
    return credit_value


def _overridden(row: Mapping[str, Any], credit: tuple,
                known: Mapping[tuple[str, str, str], list[str]]
                ) -> dict[str, Any]:
    name, variant, dept, job = credit
    copy = dict(row)
    copy['__is_helper_row'] = False
    copy['__is_helper2_row'] = False
    wr = _row_wr(row)
    if variant == 'primary':
        copy['__effective_user'] = name
    elif variant == 'helper':
        copy['__is_helper_row'] = True
        copy['__helper_foreman'] = name
        copy['__helper_dept'] = _helper_value(
            row, 'Helper Dept #', dept, False,
            known.get((wr, name, '__helper_dept'), []))
        copy['__helper_job'] = _helper_value(
            row, 'Helper Job #', job, False,
            known.get((wr, name, '__helper_job'), []))
    else:
        copy['__is_helper2_row'] = True
        copy['__helper2_foreman'] = name
        copy['__helper2_dept'] = _helper_value(
            row, 'Helper #2 Dept #', dept, True,
            known.get((wr, name, '__helper2_dept'), []))
        copy['__helper2_job'] = _helper_value(
            row, 'Helper #2 Job #', job, True,
            known.get((wr, name, '__helper2_job'), []))
    return copy


def get_run_counts() -> dict[str, int]:
    return dict(_RUN_COUNTS)


def reporting_workday(row: Mapping[str, Any]) -> Any:
    """excel.py seam: the day a row is reported under."""
    return row.get('__corr_workday') or row.get('Snapshot Date')


def group_correction_token(sorted_rows: Iterable[Mapping[str, Any]],
                           group_key: str | None = None) -> str:
    """change_detection.py seam: the ``CORR=`` token, '' when the group
    holds no corrected row and lost none (byte-identical hash)."""
    tuples = set()
    for row in sorted_rows:
        credit = row.get('__corr_credit')
        if credit and isinstance(row.get('__row_id'), int):
            sid = row.get('__source_sheet_id', row.get('__sheet_id'))
            tuples.add((sid, row['__row_id'], credit[0], credit[1],
                        credit[2], credit[3], row.get('__corr_workday'),
                        row.get('__corr_revision')))
            if group_key is None:
                group_key = row.get('__grouping_key')
        elif group_key is None and row.get('__grouping_key'):
            group_key = row.get('__grouping_key')
    if group_key and group_key in _DISPLACED:
        tuples |= set(_DISPLACED[group_key]['tokens'])
    if not tuples:
        return ''
    payload = '\n'.join(repr(t) for t in sorted(tuples, key=repr))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]


# ------------------------------------------------------------------ CLI

def _rows_from_dump(data: Any) -> list[dict[str, Any]]:
    """Accept either a list of pipeline-shaped row dicts or a sheet dump
    ``{sheet: [{sheet_id, row_id, cells: {title: [value, display]}}]}``.
    """
    if isinstance(data, list):
        return [dict(r) for r in data if isinstance(r, dict)]
    rows = []
    for value in (data or {}).values():
        if not isinstance(value, list):
            continue
        for raw in value:
            if not isinstance(raw, dict) or 'cells' not in raw:
                continue
            row: dict[str, Any] = {}
            for title, cell in raw['cells'].items():
                if isinstance(cell, list) and len(cell) == 2:
                    row[title] = cell[0] if cell[0] is not None else cell[1]
                else:
                    row[title] = cell
            row['__sheet_id'] = row['__source_sheet_id'] = raw.get(
                'sheet_id')
            row['__row_id'] = raw.get('row_id')
            rows.append(row)
    return rows


def _money(value: Decimal) -> str:
    return f'{value:,.2f}'


def preview(cset: CorrectionSet, rows: list[dict[str, Any]],
            memory_images: Mapping[Any, Any] | None = None,
            out=None) -> int:
    """Print the dry-run report; return 0 when every correction would
    apply, 1 otherwise. Reads only its inputs, writes only to *out*."""
    out = out or sys.stdout
    results = evaluate(cset, rows)
    index = {row_key(r): r for r in rows}
    for res in results:
        corr = res.correction
        print(f'== {corr.correction_id} rev {corr.revision} WR {corr.wr} '
              f'week {corr.week_ending}: {res.status.upper()}', file=out)
        print(f'   matched {len(res.matched)} / unmatched '
              f'{len(res.missing)} / mismatched {len(res.mismatched)}',
              file=out)
        for reason in res.reasons:
            print(f'   reason: {reason}', file=out)
        for entry in res.missing[:20]:
            print(f'   missing row {entry.sheet_id}/{entry.row_id}',
                  file=out)
        for entry, diffs in res.mismatched[:20]:
            print(f'   row {entry.row_id}: {"; ".join(diffs)}', file=out)
        print('   subtotals (credited owner, workday):', file=out)
        total = Decimal('0.00')
        for (name, day), amount in sorted(res.subtotals.items()):
            total += amount
            print(f'     {name:<28} {day}  {res.subtotal_rows[(name, day)]:>4}'
                  f' rows  {_money(amount):>12}', file=out)
        print(f'     {"TOTAL":<28} {"":10}  {len(res.matched):>4} rows  '
              f'{_money(total):>12}', file=out)
        print('   monetary deltas (observed -> credited):', file=out)
        for name in sorted(set(res.observed_totals) | set(
                res.credited_totals)):
            before = res.observed_totals.get(name, Decimal('0.00'))
            after = res.credited_totals.get(name, Decimal('0.00'))
            print(f'     {name:<28} {_money(before):>12} -> '
                  f'{_money(after):>12}  delta {_money(after - before)}',
                  file=out)
        print(f'   findings: blank source dates {len(res.blank_date_rows)}'
              f', credited != observed {len(res.reassigned_rows)}',
              file=out)
        if memory_images is not None:
            mem = memory_differences(
                [index[e.key] for e in res.matched if e.key in index],
                memory_images)
            print(f'   findings: source vs memory differences {len(mem)}',
                  file=out)
            for item in mem[:20]:
                print(f"     row {item['row_id']}: {item['differences']}",
                      file=out)
    blocked = sum(1 for r in results if r.status == 'blocked')
    print(f'SUMMARY corrections={len(results)} blocked={blocked} '
          f'matched={sum(len(r.matched) for r in results)} '
          f'unmatched={sum(len(r.missing) for r in results)}', file=out)
    return 1 if blocked else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog='python -m pipeline.reporting_corrections')
    ap.add_argument('command', choices=('preview', 'validate'))
    ap.add_argument('--file', required=True)
    ap.add_argument('--rows-json')
    ap.add_argument('--memory-json')
    args = ap.parse_args(argv)
    try:
        cset = load_corrections(args.file)
    except CorrectionError as exc:
        for problem in exc.problems:
            print(f'INVALID: {problem}')
        return 2
    rows_total = sum(len(c.rows) for c in cset.corrections)
    print(f'VALID: {len(cset.corrections)} correction(s), {rows_total} '
          'row entr(ies)')
    if args.command == 'validate':
        return 0
    if not args.rows_json:
        print('preview needs --rows-json (a private row dump)')
        return 2
    with open(args.rows_json, encoding='utf-8') as fh:
        rows = _rows_from_dump(json.load(fh))
    memory = None
    if args.memory_json:
        with open(args.memory_json, encoding='utf-8') as fh:
            memory = json.load(fh)
    return preview(cset, rows, memory)


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
