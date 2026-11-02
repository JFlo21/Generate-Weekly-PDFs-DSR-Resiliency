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
* ``pipeline.orchestrate``    -- ``hold_recovered_rows`` right after the
  fetch (recovered rows never reach the memory write or the audits);
  ``prepare_run``: validate every correction against the admitted rows,
  stamp applied rows, block mismatched / skip retired cases, count audit
  findings; ``register_displaced`` + ``check_applied_placement`` after
  the main grouping (displaced keys, stale identities of retired /
  blocked cases and superseded revisions); ``drop_all_corrections`` is
  the fail-closed fallback.
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

    @property
    def reconcile_only(self) -> bool:
        """A $0.00 row: kept for the audit trail only. The pipeline never
        admits a zero-price row, so it is never credited or placed in a
        workbook, and its absence from the admitted rows is expected."""
        return _decimal(self.expect.get('units_total_price')) == Decimal(
            '0.00')


@dataclass(frozen=True)
class Correction:
    correction_id: str
    revision: int
    wr: str
    week_ending: datetime.date
    rows: tuple[CorrectionRow, ...]
    expected_subtotals: Mapping[str, Mapping[str, str]] | None = None
    # ``retired: true`` (owner rollback): the case applies nothing; its
    # correction-only files are removed and its groups regenerate.
    retired: bool = False

    @property
    def pair(self) -> tuple[str, datetime.date]:
        return (self.wr, self.week_ending)


@dataclass(frozen=True)
class CorrectionSet:
    corrections: tuple[Correction, ...]
    by_row: Mapping[tuple[int, int], tuple[Correction, CorrectionRow]] = (
        field(default_factory=dict)
    )
    # Every parsed entry, superseded revisions included: their credited
    # group identities are cleaned up when a revision moves the credit.
    history: tuple[Correction, ...] = ()


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
    reconcile_only: list[CorrectionRow] = field(default_factory=list)


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
    if recover and _decimal(expect.get('units_total_price')) == Decimal(
            '0.00'):
        problems.append(
            f'{where}: a $0.00 row is reconciliation-only and cannot use '
            'recover_missing_dates')
    if recover and (expect.get('snapshot_date') is not None
                    or expect.get('weekly_reference_logged_date')
                    is not None):
        problems.append(
            f'{where}: recover_missing_dates requires both expected '
            'dates to be null')
    expect = dict(expect)
    for dkey in ('snapshot_date', 'weekly_reference_logged_date'):
        dval = expect.get(dkey)
        if dval is None:
            continue
        parsed_d = _iso_date(dval)
        if parsed_d is None:
            problems.append(f'{where}: expect.{dkey} must be ISO or null')
        else:
            # '20260105' parses too: store the canonical spelling the
            # row-side comparison produces.
            expect[dkey] = parsed_d.isoformat()
    week_iso = week_ending.isoformat()
    if not recover and expect.get('weekly_reference_logged_date') != (
            week_iso):
        problems.append(
            f'{where}: expect.weekly_reference_logged_date must equal '
            f'week_ending {week_iso} (the row must belong to the week)')
    for nkey in ('quantity', 'units_total_price'):
        if nkey in expect and not _finite(expect.get(nkey)):
            problems.append(f'{where}: expect.{nkey} must be a finite number')
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
    elif not wr.isdigit():
        problems.append(f'{where}: wr must be a numeric work request')
    retired = raw.get('retired', False)
    if not isinstance(retired, bool):
        problems.append(f'{where}: retired must be boolean')
        retired = False
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
        expected_subtotals=subtotals, retired=retired,
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
    return CorrectionSet(
        corrections=tuple(effective), by_row=by_row,
        history=tuple(c for c in parsed if c is not None))


def load_corrections(path: str) -> CorrectionSet:
    """Read and validate the JSON file at *path* (a UTF-8 BOM is fine)."""
    try:
        with open(path, encoding='utf-8-sig') as fh:
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
        except Exception as exc:  # noqa: BLE001 -- any bug = feature off
            logging.error(
                '🚫 Reporting corrections could not be loaded '
                f'({type(exc).__name__}); NO correction will be applied '
                'this run')
            _ACTIVE_CACHE[path] = None
    return _ACTIVE_CACHE[path]


def reset_state() -> None:
    """Forget the cached file and this run's registries."""
    _ACTIVE_CACHE.clear()
    _DISPLACED.clear()
    _RUN_COUNTS.clear()
    _RUN_STATE.clear()
    _RECOVERED_SEEN.clear()


reset_for_tests = reset_state


# ------------------------------------------------------------- matching

def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value)).quantize(_CENT)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _finite(value: Any) -> bool:
    """A real, finite number (JSON NaN / Infinity and booleans are not)."""
    if isinstance(value, bool) or value is None:
        return False
    try:
        return Decimal(str(value).strip()).is_finite()
    except (InvalidOperation, ValueError, TypeError):
        return False


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
    # The row must belong to the correction's week: its live Weekly
    # Reference Logged Date (a recovered row: its reporting week; a
    # listed blank-date row can only ever be recovered into this week).
    row_week = _row_date_iso(row, 'Weekly Reference Logged Date') or (
        _iso_date(row.get('__corr_week_ending')))
    if row_week is None and entry.recover_missing_dates:
        row_week = corr.week_ending
    if row_week is None or str(row_week) != corr.week_ending.isoformat():
        diffs.append(
            f'week ending: {row_week} != correction week '
            f'{corr.week_ending}')
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

    Rows expected at $0.00 are reconciliation-only: absent (the normal
    case -- the admission gate drops zero-price rows) or present at $0.00
    they are listed in ``reconcile_only`` and never credited; present
    with any difference (e.g. a live non-zero price) they block the case.
    """
    index: dict[tuple[int, int], Mapping[str, Any]] = {}
    for row in rows:
        key = row_key(row)
        if key is not None and key in cset.by_row:
            index[key] = row
    results = []
    for corr in cset.corrections:
        res = CorrectionResult(correction=corr)
        if corr.retired:
            res.status = 'retired'
            res.reasons.append('retired by the owner (nothing applied)')
            results.append(res)
            continue
        for entry in corr.rows:
            hit_row = index.get(entry.key)
            if hit_row is None:
                if entry.reconcile_only:
                    res.reconcile_only.append(entry)
                else:
                    res.missing.append(entry)
                continue
            row = hit_row
            diffs = row_differences(entry, corr, row)
            if diffs:
                res.mismatched.append((entry, diffs))
                continue
            if entry.reconcile_only:
                res.reconcile_only.append(entry)
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
            # $0.00 entries carry no money: compare non-zero amounts only
            # (a reconcile-only row never enters res.subtotals).
            if ({k: v for k, v in want.items() if v}
                    != {k: v for k, v in res.subtotals.items() if v}):
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
    if (corr.retired or not entry.recover_missing_dates
            or entry.reconcile_only):
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


# group key -> {'tokens': set of correction tuples displaced from (or
# retired out of) that group, 'rows': rows for the group's identity}.
# Keys absent from today's grouping are stale identities whose old
# attachment is removed (orchestrate._remove_empty_displaced_attachments).
_DISPLACED: dict[str, Any] = {}
_RUN_COUNTS: dict[str, int] = {}
# This run's evaluation: 'applied' {row key: (corr, entry)} and
# 'status' {correction id: applied | blocked | retired}.
_RUN_STATE: dict[str, Any] = {}
# Recovered rows seen this run (copies), kept for identity computation
# after a blocked / retired case drops them from the row list.
_RECOVERED_SEEN: dict[tuple[int, int], dict[str, Any]] = {}


def _uncorrected_copy(row: Mapping[str, Any]) -> dict[str, Any]:
    copy = dict(row)
    _strip(copy)
    return copy


def _retired_token(corr: Correction) -> tuple:
    return ('retired', corr.correction_id, corr.revision)


def hold_recovered_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """orchestrate.py seam, right after the fetch.

    Recovered rows are reporting-only: they must never reach the memory
    write, the billing audit, the audit-memory or the drift phases.
    Every ``__corr_recovered`` row is removed from *rows* (in place);
    the ones whose case evaluates as applied NOW are returned so the
    caller can re-add them just before ``prepare_run`` (which stays the
    final authority). Recovered rows of a blocked / retired case are
    dropped here. Feature off -> nothing is recovered -> ``[]`` and
    *rows* is untouched.
    """
    if not any(r.get('__corr_recovered') for r in rows):
        return []
    cset = get_active_set()
    status: dict[str, str] = {}
    if cset is not None:
        status = {res.correction.correction_id: res.status
                  for res in evaluate(cset, rows)}
    held: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    dropped = 0
    for row in rows:
        if not row.get('__corr_recovered'):
            kept.append(row)
            continue
        key = row_key(row)
        if key is not None:
            _RECOVERED_SEEN[key] = dict(row)
        if status.get(str(row.get('__corr_id'))) == 'applied':
            held.append(row)
        else:
            dropped += 1
    rows[:] = kept
    logging.info(
        f'✏️ Reporting corrections: {len(held)} recovered row(s) held '
        f'out of memory/audit inputs, {dropped} dropped (case not '
        'applicable)')
    return held


def drop_all_corrections(rows: list[dict[str, Any]]) -> None:
    """Fail-closed fallback: drop every recovered row FIRST (the marker
    is one of the stamps), then strip every stamp, then forget state."""
    rows[:] = [r for r in rows if not r.get('__corr_recovered')]
    for row in rows:
        _strip(row)
    reset_state()


def prepare_run(
    rows: list[dict[str, Any]],
    *,
    group_fn: Callable[[list[dict[str, Any]]], Mapping[str, list]] | None,
    audit_summary: Any = None,
) -> dict[str, Any]:
    """orchestrate.py seam, after fetch and before grouping.

    Evaluates every active correction against *rows* (mutated in place):
    applied corrections stamp their rows; blocked / retired corrections
    strip any stamp and drop their recovered rows (so today's blank-date
    safeguard holds). With *group_fn* the displaced / stale group keys
    are registered right away (``register_displaced``); orchestrate
    passes ``None`` and registers them after its main grouping instead,
    reusing that pass's attribution prefetch (no second RPC).

    Returns a summary of counts (no names), also logged at INFO. Feature
    off -> ``{}`` and nothing is touched.
    """
    _DISPLACED.clear()
    _RUN_COUNTS.clear()
    _RUN_STATE.clear()
    cset = get_active_set()
    if cset is None:
        return {}
    results = evaluate(cset, rows)
    applied_rows: dict[tuple[int, int], tuple[Correction, CorrectionRow]] = {}
    status: dict[str, str] = {}
    for res in results:
        corr = res.correction
        status[corr.correction_id] = res.status
        if res.status == 'retired':
            logging.warning(
                f'↩️ Reporting correction {corr.correction_id} (rev '
                f'{corr.revision}) RETIRED for WR {corr.wr} week '
                f'{corr.week_ending}: nothing applied; its correction-only '
                'files are removed and its groups regenerate')
            continue
        if res.status == 'blocked':
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
            f'{len(res.blank_date_rows)} with blank source dates, '
            f'{len(res.reconcile_only)} $0.00 reconcile-only (not credited)')
    kept: list[dict[str, Any]] = []
    recovered = 0
    for row in rows:
        key = row_key(row)
        if key is not None and row.get('__corr_recovered'):
            _RECOVERED_SEEN[key] = dict(row)
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
    _RUN_STATE['applied'] = applied_rows
    _RUN_STATE['status'] = status
    displaced = 0
    if group_fn is not None:
        displaced = register_displaced(rows, group_fn)
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
    counts = {s: sum(1 for v in status.values() if v == s)
              for s in ('applied', 'blocked', 'retired')}
    summary = {
        'corrections': len(results),
        'applied': counts['applied'],
        'blocked': counts['blocked'],
        'retired': counts['retired'],
        'rows_applied': len(applied_rows),
        'rows_recovered': recovered,
        'rows_reconcile_only': sum(
            len(r.reconcile_only) for r in results
            if r.status == 'applied'),
        'displaced_groups': displaced,
        'findings': findings,
    }
    if isinstance(audit_summary, dict):
        audit_summary['reporting_corrections'] = summary
    # The audit sheet row is written before this seam runs, so the
    # summary is persisted here, in the run log (counts only).
    logging.info(f'✏️ Reporting corrections summary: {summary}')
    if findings['blank_source_dates'] or counts['blocked']:
        logging.warning(
            f'🔎 Reporting-correction audit: {summary} -- review the '
            'flagged rows; nothing is auto-resolved')
    return summary


def register_displaced(
    rows: list[dict[str, Any]],
    group_fn: Callable[[list[dict[str, Any]]], Mapping[str, list]],
) -> int:
    """Register this run's displaced / stale group keys (after
    ``prepare_run``). *group_fn* must be side-effect free (orchestrate
    passes ``group_source_rows(..., side_effects=False)``).

    * displaced: keys the applied rows would have had WITHOUT the
      correction (the ``CORR=`` token; an emptied one is cleaned up);
    * retired: every group holding a retired case's row gets a token
      (it regenerates once, distinct from any applied version);
    * stale: credited identities of a retired / blocked case and of
      superseded revisions -- absent from today's grouping, their old
      correction-only file is removed. Bounded to each case's WR/week.

    Returns the number of registered keys; never raises.
    """
    _DISPLACED.clear()
    cset = get_active_set()
    status = _RUN_STATE.get('status') or {}
    if cset is None or not status:
        return 0
    saved_counts = dict(_RUN_COUNTS)
    try:
        _register_uncorrected(rows, cset, status, group_fn)
        _register_credited(rows, cset, status, group_fn)
    except Exception as exc:  # never block the run on a diagnostic pass
        logging.warning(
            '⚠️ Reporting corrections: displaced-group pass failed '
            f'({type(exc).__name__}); corrected groups still carry CORR=')
    finally:
        # the side passes must not inflate this run's override counts
        _RUN_COUNTS.clear()
        _RUN_COUNTS.update(saved_counts)
    logging.info(
        f'✏️ Reporting corrections: {len(_DISPLACED)} displaced / stale '
        'group key(s) registered')
    return len(_DISPLACED)


def _add_displaced(gkey: str, grows: list, tokens: set) -> None:
    slot = _DISPLACED.setdefault(gkey, {'tokens': set(), 'rows': []})
    slot['tokens'] |= tokens
    if not slot['rows']:
        slot['rows'] = list(grows)


def _register_uncorrected(rows, cset: CorrectionSet,
                          status: Mapping[str, str], group_fn) -> None:
    applied = _RUN_STATE.get('applied') or {}
    retired_tokens = {
        entry.key: _retired_token(corr)
        for corr in cset.corrections if status.get(
            corr.correction_id) == 'retired'
        for entry in corr.rows
    }
    pairs = {corr.pair for corr, _ in applied.values()} | {
        corr.pair for corr in cset.corrections
        if status.get(corr.correction_id) == 'retired'}
    if not pairs:
        return
    subset = []
    for row in rows:
        if row.get('__corr_recovered'):
            continue  # without the correction this row is not admitted
        week = excel_serial_to_date(row.get('Weekly Reference Logged Date'))
        if week is None or (_row_wr(row), week.date()) not in pairs:
            continue
        subset.append(_uncorrected_copy(row))
    groups = group_fn(subset) if subset else {}
    for gkey, grows in (groups or {}).items():
        tokens = set()
        for grow in grows:
            key = row_key(grow) or (0, 0)
            hit = applied.get(key)
            if hit is not None:
                tokens.add(_entry_tuple(hit[1], hit[0].revision))
            if key in retired_tokens:
                tokens.add(retired_tokens[key])
        if tokens:
            _add_displaced(gkey, grows, tokens)


def _register_credited(rows, cset: CorrectionSet,
                       status: Mapping[str, str], group_fn) -> None:
    by_key: dict[tuple[int, int], Mapping[str, Any]] = {}
    for row in rows:
        key = row_key(row)
        if key is not None:
            by_key[key] = row
    for key, row in _RECOVERED_SEEN.items():
        by_key.setdefault(key, row)
    effective = {c.correction_id: c for c in cset.corrections}
    for corr in cset.history:
        eff = effective.get(corr.correction_id)
        state = status.get(corr.correction_id)
        if eff is None or (corr is eff and state == 'applied'):
            continue
        token = {_retired_token(eff)} if state == 'retired' else set()
        copies = []
        for entry in corr.rows:
            src = by_key.get(entry.key)
            if src is None or entry.reconcile_only:
                continue
            copy = _uncorrected_copy(src)
            if not copy.get('Weekly Reference Logged Date'):
                copy['__corr_week_ending'] = corr.week_ending.isoformat()
            copy['__corr_id'] = corr.correction_id
            copy['__corr_revision'] = corr.revision
            copy['__corr_credit'] = (entry.name, entry.variant,
                                     entry.dept, entry.job)
            copy['__corr_workday'] = entry.workday.isoformat()
            copies.append(copy)
        if not copies:
            continue
        week_key = corr.week_ending.strftime('%m%d%y')
        for gkey, grows in (group_fn(copies) or {}).items():
            if (not grows or gkey.split('_', 1)[0] != week_key
                    or _row_wr(grows[0]) != corr.wr):
                continue  # bounded to this case's WR / week
            _add_displaced(gkey, grows, token)


def check_applied_placement(groups: Mapping[Any, list]) -> int:
    """Post-grouping check: every applied row must land in exactly one
    group (e.g. a VAC claim elsewhere would leave it in none). Logs row
    ids and counts only; returns the number of misplaced rows."""
    applied = _RUN_STATE.get('applied') or {}
    if not applied:
        return 0
    seen: dict[tuple[int, int], int] = {}
    for grows in groups.values():
        for row in grows:
            key = row_key(row)
            if key is not None and key in applied and row.get(
                    '__corr_credit'):
                seen[key] = seen.get(key, 0) + 1
    bad = sorted(k for k in applied if seen.get(k, 0) != 1)
    _RUN_COUNTS['misplaced_rows'] = len(bad)
    if bad:
        logging.warning(
            f'⚠️ Reporting corrections: {len(bad)} applied row(s) are not '
            f'in exactly one group (row ids {[k[1] for k in bad[:10]]}) '
            '-- review before relying on the corrected files')
    return len(bad)


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
    """Displaced / stale group key -> rows for its identity (copy)."""
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
    holds no corrected row and lost none (byte-identical hash).

    Without an explicit *group_key* every distinct ``__grouping_key`` in
    the rows contributes its registered tokens, so an aggregated bucket
    spanning several groups carries all of them (not just the first's).
    """
    tuples = set()
    keys = {group_key} if group_key else set()
    for row in sorted_rows:
        credit = row.get('__corr_credit')
        if credit and isinstance(row.get('__row_id'), int):
            sid = row.get('__source_sheet_id', row.get('__sheet_id'))
            tuples.add((sid, row['__row_id'], credit[0], credit[1],
                        credit[2], credit[3], row.get('__corr_workday'),
                        row.get('__corr_revision')))
        if group_key is None and row.get('__grouping_key'):
            keys.add(row['__grouping_key'])
    for key in keys:
        if key in _DISPLACED:
            tuples |= set(_DISPLACED[key]['tokens'])
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
            if not isinstance(raw, dict) or not isinstance(
                    raw.get('cells'), dict):
                continue
            row: dict[str, Any] = {}
            for title, cell in raw['cells'].items():
                if isinstance(cell, list) and len(cell) == 2:
                    row[title] = cell[0] if cell[0] is not None else cell[1]
                else:
                    row[title] = cell
            row['__sheet_id'] = row['__source_sheet_id'] = _int_id(
                raw.get('sheet_id'))
            row['__row_id'] = _int_id(raw.get('row_id'))
            rows.append(row)
    return rows


def _int_id(value: Any) -> Any:
    """Dump ids may be strings ('7001'); match them as integers."""
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return value


def _read_json(path: str) -> Any:
    with open(path, encoding='utf-8-sig') as fh:
        return json.load(fh)


def _money(value: Decimal) -> str:
    return f'{value:,.2f}'


def _print_reconcile_only(res: CorrectionResult, out) -> None:
    """$0.00 rows: never admitted / credited, listed for the audit trail."""
    groups: dict[tuple[str, str], list[Decimal]] = {}
    for entry in res.reconcile_only:
        groups.setdefault((entry.name, entry.workday.isoformat()), []).append(
            _decimal(entry.expect.get('units_total_price')) or Decimal(
                '0.00'))
    total = sum((sum(v, Decimal('0.00')) for v in groups.values()),
                Decimal('0.00'))
    print(f'   reconcile-only $0.00 rows (never admitted, never credited): '
          f'{len(res.reconcile_only)} rows, total {_money(total)}', file=out)
    for (name, day), amounts in sorted(groups.items()):
        print(f'     {name:<28} {day}  {len(amounts):>4} rows  '
              f'{_money(sum(amounts, Decimal("0.00"))):>12}', file=out)


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
        print(f'   matched {len(res.matched)} billable / reconcile-only '
              f'{len(res.reconcile_only)} / unmatched {len(res.missing)} / '
              f'mismatched {len(res.mismatched)}', file=out)
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
        _print_reconcile_only(res, out)
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
          f'reconcile_only={sum(len(r.reconcile_only) for r in results)} '
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
    try:
        rows = _rows_from_dump(_read_json(args.rows_json))
        memory = (_read_json(args.memory_json) if args.memory_json
                  else None)
    except (OSError, ValueError) as exc:
        print(f'cannot read input JSON: {type(exc).__name__}')
        return 2
    if memory is not None and not isinstance(memory, dict):
        print('--memory-json must be an object keyed by row id')
        return 2
    return preview(cset, rows, memory)


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
