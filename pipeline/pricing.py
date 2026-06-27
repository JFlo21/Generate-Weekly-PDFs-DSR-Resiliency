"""pipeline.pricing -- rate loading, price resolution, and rate recalculation.

Pure calculator module relocated from ``generate_weekly_pdfs.py`` in Phase 09
Wave 2 (D-02/D-05, byte-for-byte). No Smartsheet API calls; the only side
effect is reading CSV rate tables at import. ``_SUBCONTRACTOR_RATES`` and
``_SUBCONTRACTOR_RATES_FINGERPRINT`` are computed once at module import.

The facade (``generate_weekly_pdfs``) re-exports every public name; consumers
keep accessing these via ``import generate_weekly_pdfs as gwp; gwp.NAME`` or
``from generate_weekly_pdfs import NAME`` unchanged.

Relocated symbols: parse_price, load_contract_rates, load_new_contract_rates,
build_cu_to_group_mapping, _compute_rates_fingerprint, _strip_csv_fieldnames,
load_subcontractor_rates, _compute_subcontractor_rates_fingerprint,
_subcontractor_rescue_price, _resolve_row_price, load_rate_versions,
_resolve_cu_code, recalculate_row_price, revert_subcontractor_price,
_SUBCONTRACTOR_RATES(_FINGERPRINT/_REQUIRED_HEADERS), ARROWHEAD_DISCOUNT,
NEW_RATES_CSV, OLD_RATES_CSV, SUBCONTRACTOR_RATES_CSV,
RATE_RECALC_WEEKLY_FALLBACK, RATE_RECALC_SKIP_ORIGINAL_CONTRACT.

NOTE: SUBCONTRACTOR_PPP_SHEET_ID stays facade-resident (a reload-recompute
characterization test reloads only the facade); pricing never references it.
"""
from __future__ import annotations

import csv
import hashlib
import logging
import os
from collections.abc import Sequence

from pipeline import config as _cfg
from pipeline.config import (
    SUBCONTRACTOR_RATE_VARIANTS_ENABLED,
    _RE_EXTRACT_NUMBERS,
    _sanitize_csv_path,
)
from pipeline.observability import (
    _redact_exception_message,
    sentry_add_breadcrumb,
    sentry_capture_with_context,
)

logger = logging.getLogger(__name__)


ARROWHEAD_DISCOUNT = 0.90  # 10% reduction for subcontractors (Arrowhead)


NEW_RATES_CSV = _sanitize_csv_path('NEW_RATES_CSV', 'New Contract Rates copy regenerated again.csv')


OLD_RATES_CSV = _sanitize_csv_path('OLD_RATES_CSV', 'CU List - Corpus North & South.csv')


# Weekly-Ref-Date fallback for pre-acceptance rate recalculation.
# Default-ON: when a row has a blank/unparseable Snapshot Date (common on
# current-week VAC crew / helper rows before Smartsheet's snapshot
# automation has fired), fall back to 'Weekly Reference Logged Date'
# for the cutoff comparison. Rows that DO have a Snapshot Date are
# unaffected — the snapshot-keyed business rule stays primary. Set
# RATE_RECALC_WEEKLY_FALLBACK=0 (or false/no/off) to disable.
RATE_RECALC_WEEKLY_FALLBACK = os.getenv(
    'RATE_RECALC_WEEKLY_FALLBACK', '1'
).lower() in ('1', 'true', 'yes', 'on')


# Smartsheet-native pricing guard for original-contract folders.
# Default-ON: sheets discovered via ORIGINAL_CONTRACT_FOLDER_IDS (folders
# whose Smartsheet formula already emits the correct post-cutoff
# Units Total Price for rows with Snapshot Date >= RATE_CUTOFF_DATE
# and Units Completed? = true) are excluded from Python-side recalc.
# Running recalc on top of Smartsheet's already-correct price risked
# overwriting the Smartsheet-authoritative value with a CSV-derived
# rate × qty that did not always match, producing over/under-billed
# rows. Set RATE_RECALC_SKIP_ORIGINAL_CONTRACT=0 (or false/no/off) to
# restore the pre-fix behaviour (run recalc on these folders too).
# Subcontractor sheets are excluded unconditionally regardless of this
# flag (same as before this guard existed).
RATE_RECALC_SKIP_ORIGINAL_CONTRACT = os.getenv(
    'RATE_RECALC_SKIP_ORIGINAL_CONTRACT', '1'
).lower() in ('1', 'true', 'yes', 'on')


SUBCONTRACTOR_RATES_CSV = _sanitize_csv_path(
    'SUBCONTRACTOR_RATES_CSV', 'data/subcontractor_rates.csv'
)


def parse_price(price_str: str | float | int | None) -> float:
    """Safely convert a price string to a float.
    
    Args:
        price_str: Price value as string, float, int, or None
    
    Returns:
        float: Parsed price value, or 0.0 if parsing fails
    """
    if not price_str:
        return 0.0
    try:
        return float(str(price_str).replace('$', '').replace(',', ''))
    except (ValueError, TypeError):
        return 0.0


def load_contract_rates(filepath):
    """Loads contract rates into a fast lookup dictionary."""
    rates = {}
    REQUIRED_HEADERS = {'CU', 'Install Price', 'Removal Price', 'Transfer Price'}
    if not os.path.isfile(filepath):
        # Optional/retired rate CSV absent (e.g. pinned-empty OLD_RATES_CSV
        # resolving to its uncommitted default 'CU List - Corpus North & South.csv').
        # Benign - skip cleanly. INFO (not error) so LoggingIntegration
        # (event_level=ERROR) does NOT fire a Sentry event every run.
        logging.info(f"Rate CSV not present, skipping load: {filepath}")
        sentry_add_breadcrumb(
            "rate_loading", "rate CSV absent - skipped",
            level="info", data={"path_present": False},
        )
        return rates
    try:
        with open(filepath, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or not REQUIRED_HEADERS.issubset(set(reader.fieldnames)):
                missing = REQUIRED_HEADERS - set(reader.fieldnames or [])
                logging.error(f"CSV {filepath} missing required headers: {missing}")
                return rates
            for row in reader:
                cu = str(row.get('CU', '')).strip().upper()
                if not cu:
                    continue

                rates[cu] = {
                    'install': parse_price(row.get('Install Price', 0)),
                    'removal': parse_price(row.get('Removal Price', 0)),
                    'transfer': parse_price(row.get('Transfer Price', 0))
                }
        logging.info(f"Loaded {len(rates)} CU rates from {filepath}")
    except Exception as e:
        logging.error(f"Failed to load rates from {filepath}: {e}")
        sentry_capture_with_context(
            e,
            context_name="rate_loading",
            context_data={
                "file_present": True,
                "error": _redact_exception_message(e),
            },
            tags={"phase": "rate_load"},
            fingerprint=["rate-csv-load-failure", "load_contract_rates"],
        )
    return rates


def load_new_contract_rates(filepath):
    """Load new contract rates from the 2026 format CSV (group-level codes).

    The new CSV has 3 metadata rows before data, with columns by position:
    [0]=Group Code, [1]=Description, [2]=UOM, [3]=Category, [4]=Region,
    [5]=Date, [6]=Install Price, [7]=Removal Price, [8]=Transfer Price.

    Returns:
        dict: {GROUP_CODE: {install: float, removal: float, transfer: float}}
    """
    rates = {}
    try:
        with open(filepath, mode='r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            # Skip 3 metadata/header rows
            for _ in range(3):
                next(reader, None)
            for row in reader:
                if len(row) < 9:
                    continue
                group_code = row[0].strip().upper()
                if not group_code:
                    continue
                rates[group_code] = {
                    'install': parse_price(row[6]),
                    'removal': parse_price(row[7]),
                    'transfer': parse_price(row[8]),
                }
        logging.info(f"Loaded {len(rates)} group-level rates from {filepath}")
    except Exception as e:
        logging.error(f"Failed to load new contract rates from {filepath}: {e}")
    return rates


def build_cu_to_group_mapping(old_csv_path):
    """Build a mapping from detailed CU codes to Compatible Unit Group codes.

    Reads the old-format CSV which has both 'CU' (detailed code) and
    'Compatible Unit Group' columns.

    Returns:
        dict: {DETAILED_CU_CODE: GROUP_CODE} e.g. {'ANC-DHM-10-84-D1': 'ANC-M'}
    """
    mapping = {}
    if not os.path.isfile(old_csv_path):
        # Optional/retired rate CSV absent (e.g. pinned-empty OLD_RATES_CSV
        # resolving to its uncommitted default 'CU List - Corpus North & South.csv').
        # Benign - skip cleanly. INFO (not error) so LoggingIntegration
        # (event_level=ERROR) does NOT fire a Sentry event every run.
        logging.info(f"Rate CSV not present, skipping load: {old_csv_path}")
        sentry_add_breadcrumb(
            "rate_loading", "rate CSV absent - skipped",
            level="info", data={"path_present": False},
        )
        return mapping
    try:
        with open(old_csv_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or 'CU' not in reader.fieldnames or 'Compatible Unit Group' not in reader.fieldnames:
                logging.error(f"CSV {old_csv_path} missing 'CU' or 'Compatible Unit Group' columns for mapping")
                return mapping
            for row in reader:
                cu = str(row.get('CU', '')).strip().upper()
                group = str(row.get('Compatible Unit Group', '')).strip().upper()
                if cu and group:
                    mapping[cu] = group
        logging.info(f"Built CU-to-group mapping: {len(mapping)} CU codes -> groups")
    except Exception as e:
        logging.error(f"Failed to build CU-to-group mapping from {old_csv_path}: {e}")
        sentry_capture_with_context(
            e,
            context_name="rate_loading",
            context_data={
                "file_present": True,
                "error": _redact_exception_message(e),
            },
            tags={"phase": "rate_load"},
            fingerprint=["rate-csv-load-failure", "build_cu_to_group_mapping"],
        )
    return mapping


def _compute_rates_fingerprint(rates_dict):
    """Compute a short SHA256 fingerprint of a rates dictionary for hash invalidation."""
    h = hashlib.sha256()
    for code in sorted(rates_dict.keys()):
        r = rates_dict[code]
        h.update(f"{code}:{r['install']:.2f},{r['removal']:.2f},{r['transfer']:.2f}\n".encode())
    return h.hexdigest()[:12]


# Headers the subcontractor-rates loader must see in the CSV. Defined
# at module scope so the column-shape contract is documented in one
# place — Plan 2 (parser extension) and Plan 3 (variant emission)
# both read the same nine fields per row.
_SUBCONTRACTOR_RATES_REQUIRED_HEADERS: frozenset[str] = frozenset({
    'CU',
    'Install Price (Subcontractor Rates)',
    'Removal Price (Subcontractor Rates)',
    'Transfer Price (Subcontractor Rates)',
    'Install Price (New Rates)',
    'Removal Price (New Rates)',
    'Transfer Price (New Rates)',
})


def _strip_csv_fieldnames(fieldnames: Sequence[str] | None) -> dict[str, str]:
    """Map stripped header → original header for an operator CSV.

    The operator-supplied subcontractor rates CSV uses space-padded
    column headers (e.g. ``' CU                       '``) so a
    ``csv.DictReader``'s ``row.get('CU')`` would miss every value. This
    helper produces a stripped-form → raw-form mapping so the loader
    can ``row.get(raw)`` after looking up the desired header by its
    stripped form. Returns ``{}`` if ``fieldnames`` is falsy.
    """
    if not fieldnames:
        return {}
    return {(name or '').strip(): name for name in fieldnames}


def load_subcontractor_rates(filepath: str) -> dict[str, dict]:
    """Load the subcontractor rates CSV into a CU-keyed dict.

    Per Phase 1 decisions D-04..D-07 + D-20 (see
    ``.planning/phases/01-subcontractor-rate-logic-modification/
    01-CONTEXT.md``):

    - ``encoding='utf-8-sig'`` tolerates a UTF-8 BOM at file start.
    - Header matching strips whitespace so the operator-padded
      headers in the supplied CSV (``' CU                       '``)
      match the canonical ``CU`` key.
    - Price cells go through :func:`parse_price` which strips ``$``
      and thousands-comma. ``N/A`` and other non-numeric values
      coerce to ``0.0``.
    - Rows whose all six priced columns are zero are skipped
      (placeholder / inactive CUs — 1058 of 4848 in the supplied
      file). They are NOT counted as missing-CU telemetry.
    - Literal values are read for every priced field; the loader does
      NOT compute ``reduced = new × 0.87`` or ``new = old × 1.03``
      shortcuts (per-CU variance is real per ``contract-schema.md``).
    - ``Old-Rates`` columns (12-14) and ``Hours`` columns (6-8) are
      NOT loaded — the operator file retains them for human audit
      only; carrying them in memory would invite accidental code
      reuse and create a 3rd source of truth.

    Returns a CU-keyed dict shaped:

    .. code-block:: python

       {
           'cu_code': str,                  # uppercased
           'cu_wbs': str,                   # audit-only
           'compatible_unit_group': str,    # audit-only
           'reduced_install_price': float,
           'reduced_remove_price': float,
           'reduced_transfer_price': float,
           'new_install_price': float,
           'new_remove_price': float,
           'new_transfer_price': float,
       }

    Returns ``{}`` on any failure (fail-safe contract). Never raises
    into the caller — every Phase 1 plan downstream depends on this
    helper degrading gracefully.
    """
    rates: dict[str, dict] = {}
    try:
        with open(filepath, mode='r', encoding='utf-8-sig', newline='') as f:
            # ``skipinitialspace=True`` is mandatory for the operator-
            # supplied CSV: every field is left-padded with spaces
            # (``CU-1    , ADDITEM-ROW-PURCHASE     , EA             ,``).
            # Without it, the leading space before each ``"`` in a
            # quoted description (``, "Additional Item, Right of Way,
            # Purchase",``) breaks Python's csv quote recognition and
            # silently 2-column-shifts every value to the right. The
            # symptom was ALB-6-AUR1's ``reduced_install_price`` being
            # read as ``0.176`` (the Removal Hours column) instead of
            # ``$45.95`` (the actual Install Subcontractor price).
            reader = csv.DictReader(f, skipinitialspace=True)
            stripped_to_raw = _strip_csv_fieldnames(reader.fieldnames)
            missing = _SUBCONTRACTOR_RATES_REQUIRED_HEADERS - set(stripped_to_raw.keys())
            if missing:
                logging.error(
                    f"Subcontractor rates CSV {filepath} missing "
                    f"required headers: {sorted(missing)}"
                )
                return rates

            def _cell(row: dict, stripped_name: str, default: "str | float | int | None" = '') -> "str | float | int | None":
                raw = stripped_to_raw.get(stripped_name)
                if raw is None:
                    return default
                value = row.get(raw, default)
                if isinstance(value, str):
                    return value.strip()
                if isinstance(value, (int, float)) or value is None:
                    return value
                return str(value)

            for row in reader:
                cu = str(_cell(row, 'CU', '') or '').upper()
                if not cu:
                    continue

                reduced_install = parse_price(
                    _cell(row, 'Install Price (Subcontractor Rates)', 0))
                reduced_remove = parse_price(
                    _cell(row, 'Removal Price (Subcontractor Rates)', 0))
                reduced_transfer = parse_price(
                    _cell(row, 'Transfer Price (Subcontractor Rates)', 0))
                new_install = parse_price(
                    _cell(row, 'Install Price (New Rates)', 0))
                new_remove = parse_price(
                    _cell(row, 'Removal Price (New Rates)', 0))
                new_transfer = parse_price(
                    _cell(row, 'Transfer Price (New Rates)', 0))

                # D-04: skip rows whose all six priced cells are zero
                # (placeholder CUs). They are NOT counted as "missing"
                # — they're legitimately blank in the operator file.
                if (
                    reduced_install == 0
                    and reduced_remove == 0
                    and reduced_transfer == 0
                    and new_install == 0
                    and new_remove == 0
                    and new_transfer == 0
                ):
                    continue

                # D-05: 9 literal fields per row. D-06: explicitly do
                # NOT include Old-Rates (cols 12-14) or Hours
                # (cols 6-8) — they stay reference-only on disk.
                rates[cu] = {
                    'cu_code': cu,
                    'cu_wbs': str(_cell(row, 'CU WBS #', '') or ''),
                    'compatible_unit_group': str(
                        _cell(row, 'Compatible Unit Group', '') or ''
                    ),
                    'reduced_install_price': reduced_install,
                    'reduced_remove_price': reduced_remove,
                    'reduced_transfer_price': reduced_transfer,
                    'new_install_price': new_install,
                    'new_remove_price': new_remove,
                    'new_transfer_price': new_transfer,
                }
        logging.info(
            f"Loaded {len(rates)} subcontractor CU rates from {filepath}"
        )
    except Exception as e:
        # Fail-safe contract: never raise into the caller. Surface the
        # filepath but not row content (no PII risk: only the integer
        # count would have been logged on success, and ``e`` here is
        # an open / csv / encoding error, not a row-level message).
        logging.error(
            f"Failed to load subcontractor rates from {filepath}: {e}"
        )
    return rates


def _compute_subcontractor_rates_fingerprint(
    rates_dict: dict[str, dict],
) -> str:
    """Return a deterministic 16-char SHA256 prefix over the six priced
    fields of every CU in ``rates_dict``.

    Per Phase 1 decision D-20: sorted keys + fixed precision guarantees
    byte-identical output for byte-identical input across runs and
    across machines. Dict-insertion-order does NOT influence the
    output. Editing any priced field on any CU MUST change the
    fingerprint.

    Returns ``''`` for an empty dict (matches the legacy
    ``_compute_rates_fingerprint`` convention used elsewhere when the
    rates table is empty).
    """
    if not rates_dict:
        return ''
    h = hashlib.sha256()
    for code in sorted(rates_dict.keys()):
        r = rates_dict[code]
        h.update(
            (
                f"{code}:"
                f"{r['reduced_install_price']:.2f},"
                f"{r['reduced_remove_price']:.2f},"
                f"{r['reduced_transfer_price']:.2f},"
                f"{r['new_install_price']:.2f},"
                f"{r['new_remove_price']:.2f},"
                f"{r['new_transfer_price']:.2f}\n"
            ).encode()
        )
    return h.hexdigest()[:16]


# Per D-20: load the subcontractor rate matrix once at module init so
# downstream plans (2-6) can read ``_SUBCONTRACTOR_RATES`` and
# ``_SUBCONTRACTOR_RATES_FINGERPRINT`` directly without re-parsing
# the CSV per WR group. When the kill switch is OFF, neither value is
# populated — every downstream consumer must short-circuit on the
# empty dict path so the pipeline behaves identically to pre-Phase-1.
_SUBCONTRACTOR_RATES: dict[str, dict] = (
    load_subcontractor_rates(SUBCONTRACTOR_RATES_CSV)
    if SUBCONTRACTOR_RATE_VARIANTS_ENABLED
    else {}
)


_SUBCONTRACTOR_RATES_FINGERPRINT: str = (
    _compute_subcontractor_rates_fingerprint(_SUBCONTRACTOR_RATES)
    if _SUBCONTRACTOR_RATES
    else ''
)


def _subcontractor_rescue_price(row_data: dict) -> float:
    """Phase 1.1 Bug A pre-acceptance rescue. Returns reduced-sub
    price * qty OR 0.0 (caller observes no rescue and the row drops
    at the existing has_price gate, same as legacy behaviour).

    Uses reduced_*_price as the safety floor regardless of AEP cutoff:
    the cutoff is variant-emission gating only; this helper is for
    pre-acceptance row admission, not for output pricing. The
    actual price written to Excel happens later in
    ``_resolve_row_price`` at the ``generate_excel`` call site,
    AFTER row acceptance.

    Reads ONLY canonical keys (``CU`` / ``Work Type`` / ``Quantity``)
    per Phase 1 Blocker 2 lock-in. Per [2026-05-16 23:45] ledger
    rule, the work-type matcher uses the SHORTEST UNAMBIGUOUS
    PREFIX as ``A`` in the ``A in B`` substring direction so that
    operator-entered abbreviations (``Inst`` / ``Rem`` / ``Trans``
    / ``Xfr``) AND full canonical forms (``Install`` / ``Removal``
    / ``Transfer``) both match.
    """
    # Phase 09 W2: read the runtime-rebindable subcontractor rates table
    # from the facade so BOTH mock.patch.object(gwp, '_SUBCONTRACTOR_RATES')
    # (rebind) and in-place mutation of the shared table are honoured.
    # pricing owns the table; the facade re-exports the same object.
    import generate_weekly_pdfs as _gwp  # noqa: PLC0415
    _SUBCONTRACTOR_RATES = _gwp._SUBCONTRACTOR_RATES
    cu = str(row_data.get('CU') or '').strip().upper()
    rate_row = _SUBCONTRACTOR_RATES.get(cu)
    if rate_row is None:
        return 0.0
    work_type_raw = (row_data.get('Work Type') or '').strip().lower()
    if 'inst' in work_type_raw:
        rate = rate_row.get('reduced_install_price', 0.0)
    elif 'rem' in work_type_raw:
        rate = rate_row.get('reduced_remove_price', 0.0)
    elif 'tran' in work_type_raw or 'xfr' in work_type_raw:
        rate = rate_row.get('reduced_transfer_price', 0.0)
    else:
        return 0.0
    qty_raw = row_data.get('Quantity', 0)
    try:
        qty = float(qty_raw) if qty_raw not in (None, '') else 0.0
    except (TypeError, ValueError):
        qty = 0.0
    if rate <= 0 or qty <= 0:
        return 0.0
    return rate * qty


def _resolve_row_price(row: dict, variant: str, missing_cus) -> float:
    """Return the per-row ``Units Total Price`` to write to Excel.

    Phase 01 Plan 03 Task 2 — variant-aware pricing helper used by
    ``generate_excel``'s row-write loop.

    For ``primary`` / ``helper`` / ``vac_crew`` rows (D-14 / D-15):
    return the existing SmartSheet ``Units Total Price`` value
    unchanged via ``parse_price``. Existing variant outputs MUST be
    byte-identical to pre-change behaviour, so this branch is the
    short-circuit path for the legacy variants.

    For ``aep_billable`` / ``reduced_sub`` / ``aep_billable_helper`` /
    ``reduced_sub_helper`` rows (D-08 / D-16):
      • Look up the canonical ``CU`` code in ``_SUBCONTRACTOR_RATES``.
      • Select the rate column from the canonical ``Work Type`` token
        (Install / Removal / Transfer, case-insensitive substring
        match per D-05).
      • For the AEP-Billable family use the ``new_*_price`` columns;
        for the Reduced-Sub family use the ``reduced_*_price`` columns.
      • Return ``rate × quantity`` from the canonical ``Quantity`` key.
      • If the CU is missing from the rates table, retain the row's
        SmartSheet ``Units Total Price`` (NEVER zero-out, NEVER raise)
        and record the missing code in the per-call ``missing_cus``
        ``collections.Counter[str]``. The fall-through pattern mirrors
        the recalc fall-through from Living Ledger 2026-04-21 22:35:
        silent zero-out is a correctness regression in the billing
        pipeline.
      • For unknown work types, degenerate quantities, or non-positive
        rates, the same SmartSheet fall-through applies as a safety
        floor.

    Canonical column-name discipline (Blocker 2 lock-in):
    The helper reads ONLY the canonical keys produced by
    ``_validate_single_sheet``'s synonyms layer at L2523-2547:

      * ``row['CU']`` — canonical CU code key (synonyms ``'CU'`` and
        ``'Billable Unit Code'`` BOTH map to ``row['CU']`` upstream;
        only the canonical key survives at this point in the pipeline).
      * ``row['Work Type']`` — canonical work-type key (no synonyms).
      * ``row['Quantity']`` — canonical quantity key (synonyms ``'Qty'``
        and ``'# Units'`` map to ``row['Quantity']`` upstream).
      * ``row['Units Total Price']`` — canonical price key (synonyms
        ``'Total Price'``, ``'Redlined Total Price'`` map upstream).

    Reading any other key here would be a silent regression — only
    the canonical keys exist by the time the row reaches
    ``generate_excel``. Future synonym additions go in
    ``_validate_single_sheet``, NOT here.

    Args:
        row: Group row dict (already passed through
            ``_validate_single_sheet`` synonyms layer).
        variant: One of ``{primary, helper, vac_crew, aep_billable,
            reduced_sub, aep_billable_helper, reduced_sub_helper}``.
        missing_cus: Per-call ``collections.Counter[str]`` accumulated
            across the row-write loop. Caller is responsible for
            instantiation and downstream forwarding.

    Returns:
        float: The price to write to the row's ``Units Total Price``
            cell. SmartSheet value for legacy variants / missing CUs;
            ``rate × qty`` for new variants with a known CU.
    """
    # Phase 09 W2: read the runtime-rebindable subcontractor rates table
    # from the facade so BOTH mock.patch.object(gwp, '_SUBCONTRACTOR_RATES')
    # (rebind) and in-place mutation of the shared table are honoured.
    # pricing owns the table; the facade re-exports the same object.
    import generate_weekly_pdfs as _gwp  # noqa: PLC0415
    _SUBCONTRACTOR_RATES = _gwp._SUBCONTRACTOR_RATES
    # Legacy variants short-circuit immediately — preserves the
    # D-14 / D-15 byte-identical guarantee for existing outputs.
    if variant not in (
        'aep_billable', 'reduced_sub',
        'aep_billable_helper', 'reduced_sub_helper',
    ):
        return parse_price(row.get('Units Total Price'))

    # Subcontractor variants: rate × qty from the rate matrix.
    # CU canonical key ONLY — see Blocker 2 docstring above.
    cu_raw = row.get('CU') or ''
    cu = str(cu_raw).strip().upper()
    rate_row = _SUBCONTRACTOR_RATES.get(cu)
    if rate_row is None:
        # Missing CU: record + fall through to SmartSheet (D-16).
        if cu:
            missing_cus[cu] += 1
        return parse_price(row.get('Units Total Price'))

    # Work-Type-keyed column selection (D-05). Canonical 'Work Type'.
    # Production hotfix 2026-05-16: Smartsheet operators commonly enter
    # the abbreviated forms 'Inst' / 'Rem' / 'Trans' / 'Xfr' rather
    # than the canonical 'Install' / 'Removal' / 'Transfer'. The
    # pre-fix matcher checked `'install' in work_type_raw` — a
    # substring test that succeeds on the full form but FAILS on the
    # abbreviation ('install' is 7 chars; 'inst' is 4 chars; the
    # 7-char string is NOT contained in the 4-char string). Fall-
    # through to the safety floor returned `Units Total Price` for
    # BOTH variants, producing byte-identical AEP and ReducedSub
    # workbooks (verified via SHA256 on 8 of 8 file pairs from GHA
    # run 25975684465). Aligned with the existing
    # ``recalculate_row_price`` pattern at L1655 — use the shortest
    # unambiguous prefix so both abbreviated AND full forms match.
    work_type_raw = (row.get('Work Type') or '').strip().lower()
    if 'inst' in work_type_raw:  # matches 'Inst', 'Install', 'Installation'
        wt = 'install'
    elif 'rem' in work_type_raw:  # matches 'Rem', 'Remov', 'Removal', 'Remove'
        wt = 'remove'
    elif 'tran' in work_type_raw or 'xfr' in work_type_raw:  # 'Tran'/'Trans'/'Transfer'/'Xfr'
        wt = 'transfer'
    else:
        # Unknown work type: keep SmartSheet pricing (safety floor).
        return parse_price(row.get('Units Total Price'))

    if variant in ('aep_billable', 'aep_billable_helper'):
        rate = rate_row.get(f'new_{wt}_price', 0.0)
    else:  # reduced_sub / reduced_sub_helper
        rate = rate_row.get(f'reduced_{wt}_price', 0.0)

    # Canonical 'Quantity' ONLY — never 'Units Completed' (checkbox).
    # Phase 01 gap closure (REVIEW-IN-02): explicit None / empty-string
    # handling. The previous ``or 0`` short-circuit collapsed
    # legitimate ``Quantity=0.0`` to int ``0`` (functionally correct
    # after the subsequent ``float()`` coercion but opaque to readers).
    # Numeric output is byte-identical for every pre-existing input case
    # (None, '', 0, 0.0, '1.5', invalid → 0.0 / 0.0 / 0.0 / 0.0 / 1.5
    # / 0.0 respectively).
    qty_raw = row.get('Quantity', 0)
    try:
        qty = float(qty_raw) if qty_raw not in (None, '') else 0.0
    except (TypeError, ValueError):
        qty = 0.0

    if rate <= 0 or qty <= 0:
        # Degenerate row: SmartSheet pricing as the safety floor,
        # NEVER silently zero out (mirrors the recalc fall-through
        # pattern in Living Ledger 2026-04-21 22:35).
        return parse_price(row.get('Units Total Price'))
    return rate * qty


def load_rate_versions():
    """Load new rate versions and build all necessary lookup structures.

    Returns:
        tuple: (cu_to_group, new_rates_primary, new_rates_arrowhead, rates_fingerprint)
            - cu_to_group: {DETAILED_CU: GROUP_CODE}
            - new_rates_primary: {GROUP_CODE: {install, removal, transfer}}
            - new_rates_arrowhead: {GROUP_CODE: {install, removal, transfer}} (rates * 0.90)
            - rates_fingerprint: short hash of rate table contents for cache invalidation
    """
    cu_to_group = build_cu_to_group_mapping(OLD_RATES_CSV)
    new_rates_primary = load_new_contract_rates(NEW_RATES_CSV)

    # Precompute Arrowhead (subcontractor) rates: primary rate * ARROWHEAD_DISCOUNT
    new_rates_arrowhead = {}
    for group_code, rates in new_rates_primary.items():
        new_rates_arrowhead[group_code] = {
            'install': round(rates['install'] * ARROWHEAD_DISCOUNT, 2),
            'removal': round(rates['removal'] * ARROWHEAD_DISCOUNT, 2),
            'transfer': round(rates['transfer'] * ARROWHEAD_DISCOUNT, 2),
        }

    # Only compute fingerprint if rates were successfully loaded
    rates_fingerprint = _compute_rates_fingerprint(new_rates_primary) if new_rates_primary else ''

    if not new_rates_primary:
        logging.warning("⚠️ New rate table is empty — rate recalculation will be skipped even though RATE_CUTOFF_DATE is set")
    else:
        logging.info(f"Rate versions loaded: {len(new_rates_primary)} primary groups, "
                     f"{len(new_rates_arrowhead)} Arrowhead groups (precomputed, not yet active), "
                     f"{len(cu_to_group)} CU-to-group mappings, "
                     f"fingerprint={rates_fingerprint}")
    return cu_to_group, new_rates_primary, new_rates_arrowhead, rates_fingerprint


def _resolve_cu_code(row_data):
    """Return the CU code for a row using the same priority chain as
    ``recalculate_row_price`` and ``revert_subcontractor_price``.

    Resolution order: ``CU Helper`` → ``CU`` → ``Billable Unit Code``,
    with the sentinel string ``'NAN'`` (produced by pandas when a float
    NaN is stringified) falling back to ``CU``. Returns an uppercased,
    stripped string (possibly empty if no column yields a value).
    """
    cu_code = str(
        row_data.get('CU Helper')
        or row_data.get('CU')
        or row_data.get('Billable Unit Code')
        or ''
    ).strip().upper()
    if cu_code == 'NAN':
        cu_code = str(row_data.get('CU') or '').strip().upper()
    return cu_code


def recalculate_row_price(row_data, cu_to_group, rates_dict, *, out_status=None):
    """Recalculate a row's price using new contract rates.

    Looks up the CU code, maps it to its Compatible Unit Group, then
    calculates price as rate × quantity using the provided rates dict.
    Modifies row_data['Units Total Price'] in-place if a matching rate is found.

    Args:
        row_data: Dict of row field values (modified in-place).
        cu_to_group: Dict mapping detailed CU codes to group codes.
        rates_dict: Dict mapping group codes to {install, removal, transfer} rates.
        out_status: Optional dict that, when provided, receives an
            ``'outcome'`` key describing why the function returned:
              * ``'recalculated'`` — a rate was successfully applied
                (the returned price may still equal the original
                SmartSheet price if the computed rate × qty matches it
                exactly; lookup succeeded either way).
              * ``'missing_rate'`` — neither the mapped group nor the
                CU code is present in ``rates_dict``; SmartSheet price
                retained. This is the only outcome the per-sheet
                "skipped" summary counts toward, because it is the
                actionable signal that ``NEW_RATES_CSV`` needs a new
                entry.
              * ``'invalid_quantity'`` — quantity is zero/missing/
                unparseable; SmartSheet price retained.
              * ``'zero_rate'`` — new rate for the resolved work type
                is zero; SmartSheet price retained.

    Returns:
        float: The (possibly recalculated) price value.
    """
    def _set_status(s):
        if out_status is not None:
            out_status['outcome'] = s

    price_val = parse_price(row_data.get('Units Total Price'))

    # Resolve CU code (same chain as revert_subcontractor_price)
    cu_code = _resolve_cu_code(row_data)

    # Map detailed CU code to group code
    group_code = cu_to_group.get(cu_code)
    if not group_code:
        # CU code not found in mapping — try direct group lookup (in case SmartSheet uses group codes)
        if cu_code in rates_dict:
            group_code = cu_code
        else:
            logging.debug(f"Rate recalculation: CU '{cu_code}' not found in CU-to-group mapping or rates, keeping SmartSheet price")
            _set_status('missing_rate')
            return price_val

    # If the mapped group isn't in the new rates table (e.g. old CSV maps
    # CU -> a verbose group name like "Vacuum Switch" that never appears
    # in the new rates' short-code keys), fall back to looking up the CU
    # code directly in the rates table. This recovers specialized work
    # items (common on VAC crew sheets) where the detailed CU code is
    # itself a key in the new contract rates. Only activates on exact
    # match, so no chance of mis-applying a rate.
    if group_code not in rates_dict:
        if cu_code in rates_dict:
            logging.debug(f"Rate recalculation: mapped group '{group_code}' not in new rates for CU '{cu_code}'; matched CU directly")
            group_code = cu_code
        else:
            logging.warning(f"Rate recalculation SKIPPED: CU '{cu_code}' maps to group '{group_code}' but neither is in new rates — keeping SmartSheet price (Qty={row_data.get('Quantity')}, Work Type={row_data.get('Work Type')})")
            _set_status('missing_rate')
            return price_val

    # Determine work type
    work_type_raw = str(row_data.get('Work Type') or '').strip().lower()
    wt_key = 'install'
    if 'rem' in work_type_raw:
        wt_key = 'removal'
    elif 'tran' in work_type_raw or 'xfr' in work_type_raw:
        wt_key = 'transfer'

    # Parse quantity — if missing or unparseable, keep SmartSheet price
    qty_str = str(row_data.get('Quantity', '') or '')
    try:
        qty = float(_RE_EXTRACT_NUMBERS.sub('', qty_str) or 0)
    except ValueError:
        qty = 0.0

    if qty <= 0:
        logging.debug(f"Rate recalculation: quantity '{qty_str}' is zero/missing for CU '{cu_code}', keeping SmartSheet price")
        _set_status('invalid_quantity')
        return price_val

    rate = rates_dict[group_code].get(wt_key, 0.0)
    if rate <= 0:
        logging.debug(f"Rate recalculation: rate is zero for group '{group_code}' work type '{wt_key}', keeping SmartSheet price")
        _set_status('zero_rate')
        return price_val

    new_price = round(rate * qty, 2)
    row_data['Units Total Price'] = new_price
    _set_status('recalculated')
    return new_price


def revert_subcontractor_price(row_data, original_rates):
    """Revert a subcontractor row's price to the 100% original contract rate.

    Looks up the CU code from row_data (preferring CU Helper, then CU,
    then Billable Unit Code), determines the work type, and recalculates
    the price as original_rate × quantity.

    Args:
        row_data: Dict of row field values (modified in-place if reverted).
        original_rates: Dict mapping CU codes to {install, removal, transfer} rates.

    Returns:
        The (possibly recalculated) price value as a float.
    """
    price_val = parse_price(row_data.get('Units Total Price'))

    cu_code = _resolve_cu_code(row_data)

    work_type_raw = str(row_data.get('Work Type') or '').strip().lower()

    wt_key = 'install'
    if 'rem' in work_type_raw:
        wt_key = 'removal'
    elif 'tran' in work_type_raw or 'xfr' in work_type_raw:
        wt_key = 'transfer'

    qty_str = str(row_data.get('Quantity', '') or '0')
    try:
        qty = float(_RE_EXTRACT_NUMBERS.sub('', qty_str) or 0)
    except ValueError:
        qty = 0.0

    if cu_code in original_rates:
        exact_original_rate = original_rates[cu_code].get(wt_key, 0.0)
        price_val = round(exact_original_rate * qty, 2)
        row_data['Units Total Price'] = price_val

    return price_val
