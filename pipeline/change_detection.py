"""pipeline.change_detection -- SHA-256 change detection and group identity.

Relocated from ``generate_weekly_pdfs.py`` in Phase 09 Wave 2 (D-02/D-05,
byte-for-byte). ``build_group_identity`` (identity merged per D-02) and
``calculate_data_hash`` form the core change-detection path; the
change-detection key ``(WR, week_ending, variant, foreman, dept, job)`` is
preserved verbatim -- never shorten it (MOD-04).

Cross-wave seam: ``calculate_data_hash`` reads ``_RATES_FINGERPRINT`` from
``pipeline.fetch`` (built in W3) via a late in-function import with an
ImportError/AttributeError fallback to ``''`` (the empty-fingerprint state
during W2; W3 restores the real read). The other runtime-rebindable hash inputs
(``_SUBCONTRACTOR_RATES_FINGERPRINT``, ``RATE_CUTOFF_DATE``,
``EXTENDED_CHANGE_DETECTION``) and the authoritative-store guards
(``SUPABASE_HASH_STORE_AUTHORITATIVE``, ``BILLING_AUDIT_AVAILABLE``,
``TEST_MODE``) are read from the facade so test-time mutations on ``gwp`` and
the live config values are both honoured.

D-06 (T-09-02-02): ``_resolve_unchanged_for_skip`` takes the billing_audit
writer as an EXPLICIT kwarg injected by the caller -- never a ``globals()``
lookup, which after relocation would silently disable the authoritative
Supabase hash lookup.

Relocated symbols: calculate_data_hash, _compute_aggregated_content_hash,
extract_data_hash_from_filename, list_generated_excel_files,
build_group_identity, _resolve_unchanged_for_skip, load_hash_history,
save_hash_history, HASH_HISTORY_MAX_ENTRIES.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any

from pipeline.config import RESET_HASH_HISTORY
from pipeline.pricing import parse_price
from pipeline.utils import is_checked

logger = logging.getLogger(__name__)


def _extended_row_fields(row: dict, group_variant: str) -> list[str]:
    """The per-row fields hashed in EXTENDED change detection, in order.

    Extracted verbatim from the ``calculate_data_hash`` row loop (byte-
    identical output) so the same string can serve as the sort-key
    tiebreaker: rows that tie on the business sort key are ordered by
    their own hashed content, making the group hash independent of the
    parallel fetch's arrival order.
    """
    # CRITICAL: Use parse_price() for normalization to avoid format-based false changes
    normalized_price = f"{parse_price(row.get('Units Total Price', 0)):.2f}"

    row_fields = [
        str(row.get('Work Request #', '')),
        str(row.get('Snapshot Date', '') or ''),
        str(row.get('CU', '') or ''),
        str(row.get('Quantity', '') or ''),
        normalized_price,
        str(row.get('Pole #') or row.get('Point #') or row.get('Point Number') or ''),
        str(row.get('Work Type', '') or ''),
        str(row.get('Dept #', '') or ''),
        str(row.get('Scope #') or row.get('Scope ID', '') or ''),
        str(is_checked(row.get('Units Completed?'))),  # CRITICAL: Include completion status
        # Additional fields to catch changes previously missed
        str(row.get('Customer Name', '') or ''),
        str(row.get('Job #') or row.get('Job Number', '') or ''),
        str(row.get('Work Order #') or row.get('Work Order Number', '') or ''),
        str(row.get('CU Description', '') or ''),
        str(row.get('Unit of Measure', '') or ''),
        str(row.get('Area', '') or ''),
    ]
    # VAC crew groups use a single `_VACCREW` key with no foreman suffix,
    # so one group can hold multiple crew members. Including per-row VAC
    # crew fields here lets each row contribute its own name/dept/job to
    # the hash independently. This avoids two pitfalls of aggregating
    # values into `meta_parts` as a set:
    #   1. Set dedup — e.g. depts {500, 500, 600}: editing one row's dept
    #      from 500→600 leaves {500, 600} unchanged, silently skipping
    #      regeneration.
    #   2. Delimiter collision — ','.join on free-text names cannot
    #      distinguish ['A,B', 'C'] from ['A', 'B,C'].
    # Scoped to vac_crew so hash stability for primary/helper rows is
    # preserved (non-vac_crew row_str structure is unchanged).
    if group_variant == 'vac_crew':
        row_fields.extend([
            str(row.get('__vac_crew_name') or ''),
            str(row.get('__vac_crew_dept') or ''),
            str(row.get('__vac_crew_job') or ''),
        ])
    return row_fields


# Every column-title alias the REPORT DETAILS "Job #:" value accepts, in
# precedence order. The hash reads only 'Job #' / 'Job Number' (see
# _extended_row_fields); the others are header-only, so they belong in
# the canonical sort key: without them two rows tied on everything the
# hash reads could still surface a different Job # in the header between
# runs (Codex, PR #361). ``header_job_number`` is the ONE resolver --
# ``pipeline.excel.generate_excel`` displays it and the sort key orders
# by it -- so an alias added or reordered here changes both together
# and cannot silently reintroduce an order-dependent header (Copilot,
# PR #361).
_JOB_NUMBER_ALIASES = (
    'Job #', 'Job#', 'Job Number', 'JobNumber', 'Job_Number',
    'JOB #', 'JOB#', 'job #', 'job#',
)


def header_job_number(row: dict) -> Any:
    """The Job # value the workbook header shows for ``row`` ('' if none).

    Returns the raw cell value (the header writes it unchanged, so a
    numeric Job # keeps its cell type); callers that need text wrap it.

    Shared by ``pipeline.excel.generate_excel`` (display) and
    ``canonical_sorted_rows`` (order) -- keep it the only definition.
    """
    for key in _JOB_NUMBER_ALIASES:
        value = row.get(key)
        if value:
            return value
    return ''


def canonical_sorted_rows(
    group_rows: list[dict], extended: bool | None = None,
) -> list[dict]:
    """Return the group's rows in the order ``calculate_data_hash`` hashes
    them.

    This is the ONE definition of a group's canonical row order. The hash
    uses it, and ``pipeline.excel.generate_excel`` uses its first element
    for the workbook's header metadata (foreman / helper dept / helper job)
    so the row the hash considers "first" and the row Excel displays are
    the same row regardless of parallel-fetch arrival order (Codex, PR
    #359: a helper group can hold rows from two departments -- the group
    key is ``{week}_{wr}_HELPER_{name}`` -- so an arrival-order
    ``group_rows[0]`` could show a dept/job the stable hash never sees).

    ``extended`` defaults to the facade's ``EXTENDED_CHANGE_DETECTION``.
    Extended mode sorts on the business key, the VAC-crew fields, the
    row's own hashed-field string, its foreman, its helper metadata, the
    unjoined hashed fields (breaks ``|``-serialization collisions), the
    header's Job # under every alias, the header's raw Work Order # and
    the legacy identity ``User`` (a total order for any two rows that
    differ in anything the hash, the header or an orchestrate identity
    site reads). Everything after the hashed-field string is hash-neutral
    by construction: it can only reorder rows whose hashed strings are
    identical.
    Legacy mode keeps the original 5-key sort (rollback-stability
    guarantee -- see the note in ``calculate_data_hash``).
    """
    if not group_rows:
        return []
    if extended is None:
        import generate_weekly_pdfs as _gwp  # noqa: PLC0415
        extended = bool(_gwp.EXTENDED_CHANGE_DETECTION)
    _sort_base = lambda x: (
        str(x.get('Work Request #', '')),
        str(x.get('Snapshot Date', '')),
        str(x.get('CU', '')),
        str(
            x.get('Pole #') or x.get('Point #') or x.get('Point Number') or ''
        ),
        str(x.get('Quantity', '')),
    )
    if not extended:
        return sorted(group_rows, key=_sort_base)
    _sort_extended = lambda x: _sort_base(x) + (
        str(x.get('__vac_crew_name') or ''),
        str(x.get('__vac_crew_dept') or ''),
        str(x.get('__vac_crew_job') or ''),
    )
    _variant_for_key = group_rows[0].get('__variant', 'primary')
    return sorted(
        group_rows,
        key=lambda x: _sort_extended(x) + (
            "|".join(_extended_row_fields(x, _variant_for_key)),
            str(x.get('__current_foreman') or x.get('Foreman') or ''),
            str(x.get('__helper_foreman') or ''),
            str(x.get('__helper_dept') or ''),
            str(x.get('__helper_job') or ''),
            # The same hashed fields UNJOINED: the string above joins them
            # with an unescaped '|', so ('WO|East', 'Install') and ('WO',
            # 'East|Install') serialize identically -- same hash bytes,
            # but a different displayed Work Order (Copilot, PR #361).
            tuple(_extended_row_fields(x, _variant_for_key)),
            # Header-only input: the Job # aliases generate_excel accepts
            # beyond the two the hash reads (Codex, PR #361). Sits after
            # the hashed-field string, so it can only reorder rows whose
            # hashed strings are identical -- hash-neutral by construction.
            str(header_job_number(x)),
            # Header-only input: the hash collapses 'Work Order #' and
            # 'Work Order Number', but the header shows only the raw
            # 'Work Order #' -- prefer the row whose displayed column is
            # populated, then its value (Codex / Copilot, PR #361).
            (0 if x.get('Work Order #') else 1,
             str(x.get('Work Order #') or '')),
            # Identity-only input: with PRIMARY_CLAIM_ATTRIBUTION off the
            # orchestrate identity sites derive the primary identifier from
            # the canonical row's ``User`` (Copilot, PR #361). Last in the
            # key, after every hashed / meta field -- hash-neutral.
            str(x.get('User') or ''),
        ),
    )


def canonical_first_row(group_rows: list[dict]) -> dict:
    """The row every header / identity consumer reads for a group.

    Always the first row of the extended TOTAL order, whatever
    ``EXTENDED_CHANGE_DETECTION`` says. In extended mode that is exactly
    the row ``calculate_data_hash`` treats as first. In legacy mode the
    hash never reads a first row -- it hashes per-row fields in 5-key
    order and carries no meta -- so tied rows (same 5 keys, different
    helper dept / job) can pick a deterministic representative for the
    header and the identity sites without touching the legacy hash
    (Codex, PR #361 follow-up). For a group with no 5-key ties both
    orders start with the same row.
    """
    ordered = canonical_sorted_rows(group_rows, extended=True)
    return ordered[0] if ordered else {}


def _first_nonempty_foreman(sorted_rows: list[dict]) -> Any:
    """The first non-empty ``__current_foreman`` (else ``Foreman``) in
    ``sorted_rows`` -- the hash's ``FOREMAN=`` rule; '' if none."""
    for row in sorted_rows:
        foreman = row.get('__current_foreman') or row.get('Foreman') or ''
        if foreman:
            return foreman
    return ''


def canonical_foreman(group_rows: list[dict]) -> Any:
    """The group's canonical foreman: the first non-empty
    ``__current_foreman`` (else ``Foreman``) in the extended total order.

    In EXTENDED mode (production) this is exactly the value the hash
    records as its ``FOREMAN=`` meta token, so the primary workbook
    header and the hash cannot disagree (Codex, PR #361 follow-up). In
    LEGACY mode (``EXTENDED_CHANGE_DETECTION=0``) the hash carries no
    meta at all -- this value takes no part in it and is only the
    deterministic header selection. Raw value, '' if no row carries a
    foreman.
    """
    return _first_nonempty_foreman(
        canonical_sorted_rows(group_rows, extended=True))


def calculate_data_hash(group_rows: list[dict]) -> str:
    """Calculate a hash of the group data to detect changes.

    Args:
        group_rows: List of row dictionaries to hash
    
    Returns:
        str: 16-character SHA256 hash prefix

    Legacy (EXTENDED_CHANGE_DETECTION=0):
        Uses original minimal fields so hash stability is preserved for rollbacks.

    Extended (default):
        Incorporates additional business-critical fields so regenerated Excel
        files occur when any of these change:
          • Current foreman name (derived '__current_foreman')
          • Dept # values present across the group (set + order)
          • Scope ID / #
          • Aggregated total billed amount
          • Unique dept list and row count
          • All prior minimal fields
    """
    # Phase 09 W2: bind the runtime-rebindable hash inputs from their
    # canonical locations so test-time mutations on the facade are honoured.
    # EXTENDED_CHANGE_DETECTION / RATE_CUTOFF_DATE /
    # _SUBCONTRACTOR_RATES_FINGERPRINT live on the facade (config re-exports +
    # test rebinds land there). _RATES_FINGERPRINT moves to pipeline.fetch in
    # W3 -- late-import it with an ImportError/AttributeError fallback to ''
    # (the W2 empty-fingerprint state; W3 restores the real read).
    import generate_weekly_pdfs as _gwp  # noqa: PLC0415
    EXTENDED_CHANGE_DETECTION = _gwp.EXTENDED_CHANGE_DETECTION
    RATE_CUTOFF_DATE = _gwp.RATE_CUTOFF_DATE
    _SUBCONTRACTOR_RATES_FINGERPRINT = _gwp._SUBCONTRACTOR_RATES_FINGERPRINT
    try:
        import pipeline.fetch as _pipeline_fetch  # noqa: PLC0415
        _RATES_FINGERPRINT = _pipeline_fetch._RATES_FINGERPRINT
    except (ImportError, AttributeError):
        # Phase 09 W3: pipeline.fetch now exists and owns the real
        # _RATES_FINGERPRINT, so the normal path resolves. If this except
        # EVER fires the rates fingerprint silently degrades to '' — which
        # WEAKENS the change-detection hash (rate changes would stop
        # triggering regeneration). Make that operator-visible instead of
        # silent (carry-forward from the Wave-2 silent-failure review).
        logging.warning(
            "change_detection: pipeline.fetch._RATES_FINGERPRINT unavailable; "
            "falling back to '' — rate changes will NOT be reflected in the "
            "change-detection hash this run."
        )
        _RATES_FINGERPRINT = ''
    if not group_rows:
        return "0" * 16

    # Deterministic sorting across key business fields.
    #
    # In EXTENDED mode, VAC crew fields appear as tie-breakers so multi-member
    # VAC crew groups — where two rows can share (WR, Snapshot, CU, Pole, Qty)
    # while belonging to different crew members — hash stably across runs.
    # Without the tie-breaker, row insertion order (merged from parallel
    # `as_completed` futures in `get_all_source_rows`) bleeds into the hash
    # because VAC crew fields are included per-row in row_str.
    #
    # LEGACY mode (EXTENDED_CHANGE_DETECTION=0) intentionally keeps the
    # original 5-key sort: the docstring promises legacy uses only the
    # original minimal fields so hashes stay bit-stable for rollbacks.
    # Adding tie-breakers there would change row order for tied rows whose
    # legacy row_data still differs (Work Type / Units Completed? / price),
    # invalidating the rollback-stability guarantee. Legacy mode's row_data
    # also excludes VAC crew fields, so a vac_crew-specific tie-breaker
    # there would be purely cosmetic — skip it.
    # The order itself lives in canonical_sorted_rows() so Excel's header
    # row and the hash's first row can never disagree (see its docstring).
    if EXTENDED_CHANGE_DETECTION:
        # Total-order tiebreaker (2026-08-27, run #2801 / PR #359).
        #
        # The VAC-crew tiebreaker above only closed the tie for crew
        # fields. Two PRIMARY/helper rows that share the whole
        # (WR, Snapshot, CU, Pole, Qty) key but differ in a hashed field
        # (price, Work Type, Dept #, Scope, Job #, ...) still kept the
        # parallel-fetch `as_completed` arrival order under Python's
        # stable sort, so their group's hash flipped with thread timing:
        # `billing_audit.pipeline_run` showed WR 17451333 / week 080226
        # alternating between two hashes for 12 consecutive runs with a
        # constant assignment fingerprint -- regenerated and re-uploaded
        # every run, and a permanent shadow-parity divergence (Phase 11
        # D-07) because the row-hash-driven incremental path would never
        # regenerate it.
        #
        # The tiebreaker is the row's own hashed-field string plus every
        # other per-row input the hash reads from a *positional* row: the
        # foreman (FOREMAN= comes from the first row that has one) and the
        # helper metadata (HELPER= / HELPER_DEPT= / HELPER_JOB= come from
        # sorted_rows[0] for helper-style variants). Grouping keys on the
        # helper fields, so rows of one group normally agree on them -- but
        # the hash must not depend on that: with them in the key, two rows
        # that tie on everything else and differ only in helper dept/job
        # still order deterministically (Greptile, PR #359). It only
        # reorders rows that tie on the full key above, so any group
        # without such ties hashes byte-identically to before; a group
        # whose tied rows differ gets one deterministic hash from now on
        # (one final regeneration). Variant is group-level (every row in a
        # group shares `__variant`, see the note below the sort), so the
        # first row is authoritative.
        sorted_rows = canonical_sorted_rows(group_rows, extended=True)
    else:
        sorted_rows = canonical_sorted_rows(group_rows, extended=False)

    if not EXTENDED_CHANGE_DETECTION:
        # OPTIMIZATION: Use incremental hashing to avoid large string allocation
        hasher = hashlib.sha256()
        for row in sorted_rows:
            # CRITICAL: Use parse_price() for normalization to avoid format-based false changes
            normalized_price = f"{parse_price(row.get('Units Total Price', 0)):.2f}"
            row_data = (
                f"{row.get('Work Request #', '')}"
                f"{row.get('CU', '')}"
                f"{row.get('Quantity', '')}"
                f"{normalized_price}"
                f"{row.get('Snapshot Date', '')}"
                f"{row.get('Pole #', '')}"
                f"{row.get('Work Type', '')}"
                f"{is_checked(row.get('Units Completed?'))}"  # CRITICAL: Include completion status
            )
            hasher.update(row_data.encode('utf-8'))
        return hasher.hexdigest()[:16]

    # Extended mode: Use incremental hashing
    hasher = hashlib.sha256()

    # Variant is a group-level property (all rows in a group share the same
    # __variant). Compute it once before the row loop so per-row hash can
    # include variant-scoped fields deterministically.
    group_variant = sorted_rows[0].get('__variant', 'primary') if sorted_rows else 'primary'

    # FOREMAN= meta token: the first non-empty foreman in canonical order.
    # ONE rule -- the workbook header reads the same value through
    # canonical_foreman() (Codex, PR #361 follow-up). Byte-identical to
    # the former inline scan (golden digests in
    # tests/test_group_identity_and_header_foreman.py).
    group_foreman = _first_nonempty_foreman(sorted_rows) or None
    for row in sorted_rows:
        # Per-row hashed fields live in _extended_row_fields() so the sort
        # tiebreaker above and the hash below are guaranteed to see the
        # exact same string.
        row_str = "|".join(_extended_row_fields(row, group_variant))
        # Update hash incrementally with newline separator
        hasher.update(row_str.encode('utf-8'))
        hasher.update(b"\n")

    unique_depts = sorted({str(r.get('Dept #', '') or '') for r in sorted_rows if r.get('Dept #') is not None})
    total_price = sum(parse_price(r.get('Units Total Price')) for r in sorted_rows)

    # Append metadata
    meta_parts = []
    meta_parts.append(f"FOREMAN={group_foreman or ''}")
    
    # Variant-specific hash tokens (replaces activity log USER= token)
    variant = group_variant
    meta_parts.append(f"VARIANT={variant}")

    if variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper'):
        # Helper-style variants: include helper-specific metadata
        # (helper_job is OPTIONAL). The plain helper group key is
        # `_HELPER_{helper}` and the new Phase 01 subcontractor
        # shadow-helper variants will follow the same per-foreman
        # partitioning pattern in Plan 3 (`_AEPBILLABLE_HELPER_{name}` /
        # `_REDUCEDSUB_HELPER_{name}`), so reading sorted_rows[0]
        # here is safe — every row in such a group shares identical
        # helper info.
        _first = sorted_rows[0] if sorted_rows else {}
        helper_foreman = _first.get('__helper_foreman', '')
        helper_dept = _first.get('__helper_dept', '')
        helper_job = _first.get('__helper_job', '')
        # Validate required helper fields (helper_job is optional)
        if not helper_foreman or not helper_dept:
            logging.warning(f"⚠️ Helper variant missing required fields: foreman={helper_foreman}, dept={helper_dept}")
        if not helper_job:
            logging.info(f"ℹ️ Helper variant without Job #: foreman={helper_foreman}, dept={helper_dept} (proceeding anyway)")
        meta_parts.append(f"HELPER={helper_foreman}")
        meta_parts.append(f"HELPER_DEPT={helper_dept}")
        meta_parts.append(f"HELPER_JOB={helper_job}")  # Include even if empty for hash consistency
    # vac_crew variant intentionally has no meta_parts block: VAC crew
    # name/dept/job are already captured per-row in the row_str loop above,
    # which is strictly more sensitive than meta_parts aggregation and is not
    # vulnerable to set-dedup collisions or comma-in-name delimiter collisions.

    meta_parts.append(f"DEPTS={','.join(unique_depts)}")
    meta_parts.append(f"TOTAL={total_price:.2f}")
    meta_parts.append(f"ROWCOUNT={len(sorted_rows)}")
    if RATE_CUTOFF_DATE:
        meta_parts.append(f"RATE_CUTOFF={RATE_CUTOFF_DATE.isoformat()}")
        if _RATES_FINGERPRINT:
            meta_parts.append(f"RATES_FP={_RATES_FINGERPRINT}")

    # Per Phase 01 Plan 02 D-20: mix the subcontractor rates
    # fingerprint into the hash ONLY for the four new variants
    # that actually consume the subcontractor rates CSV. This
    # forces regeneration of _AEPBillable / _ReducedSub files (and
    # their shadow-helper twins) when the CSV changes, WITHOUT
    # touching the primary / helper / vac_crew hashes (preserves
    # the ROADMAP success criterion 5 byte-identical guarantee for
    # the legacy variant set). Mirrors the conditional shape of
    # the existing `if RATE_CUTOFF_DATE: ... RATES_FP=` block
    # above so a future engineer reading the two blocks side by
    # side sees them as parallel — one keys on the retired-but-
    # retained legacy recalc gate, the other keys on the variant
    # set that consumes the new rates table.
    if variant in (
        'aep_billable',
        'reduced_sub',
        'aep_billable_helper',
        'reduced_sub_helper',
    ):
        if _SUBCONTRACTOR_RATES_FINGERPRINT:
            meta_parts.append(
                f"SUB_RATES_FP={_SUBCONTRACTOR_RATES_FINGERPRINT}"
            )

    # Update hash with metadata
    if meta_parts:
        hasher.update("\n".join(meta_parts).encode('utf-8'))

    return hasher.hexdigest()[:16]


def _compute_aggregated_content_hash(rows: list[dict]) -> str:
    """Deterministic content hash for a cross-variant row bucket.

    Used by the billing_audit integration to produce a
    ``pipeline_run.content_hash`` that covers every variant's rows
    for a given (WR, week). ``calculate_data_hash()`` assumes the
    rows it's called with all come from a single production
    ``group_source_rows`` group; that assumption breaks for an
    aggregation bucket that unions multiple groups of the same
    variant. In particular, helper groups are split per-foreman
    (group key ``{week}_{wr}_HELPER_{sanitized_foreman}``) — so
    multiple helper groups can exist for the same (WR, week) and
    calling ``calculate_data_hash(variant='helper', rows=...)``
    with all of them at once would:

      1. Read helper_foreman/dept/job from ``sorted_rows[0]`` only
         (variant-specific meta block), so identity changes on
         non-first helpers never reach the hash.
      2. Depend on row sort order for which helper's identity
         gets recorded — flips spuriously between runs.

    Primary groups are keyed on ``{week}_{wr}`` alone (one group
    per WR/week, no user suffix) and vac_crew on
    ``{week}_{wr}_VACCREW`` (one group, multi-member handled
    internally by ``calculate_data_hash``'s per-row VAC fields)
    — so only the ``helper`` variant needs sub-bucketing here.

    The combined hash is SHA-256 over the sorted
    ``variant=hash`` tokens (sub-bucketed for helper).
    """
    by_variant: dict[str, list[dict]] = {}
    for r in rows:
        v = r.get('__variant', 'primary')
        by_variant.setdefault(v, []).append(r)

    parts: list[str] = []
    for v in sorted(by_variant.keys()):
        variant_rows = by_variant[v]
        if v == 'helper':
            # Sub-bucket by helper identity to match the per-
            # foreman group structure assumed by
            # calculate_data_hash's helper branch.
            sub: dict[tuple[str, str, str], list[dict]] = {}
            for r in variant_rows:
                sk = (
                    str(r.get('__helper_foreman', '')),
                    str(r.get('__helper_dept', '')),
                    str(r.get('__helper_job', '')),
                )
                sub.setdefault(sk, []).append(r)
            sub_parts = [
                f"{sk}={calculate_data_hash(sub[sk])}"
                for sk in sorted(sub.keys())
            ]
            variant_hash = hashlib.sha256(
                "|".join(sub_parts).encode('utf-8')
            ).hexdigest()[:16]
        else:
            variant_hash = calculate_data_hash(variant_rows)
        parts.append(f"{v}={variant_hash}")

    return hashlib.sha256(
        "|".join(parts).encode('utf-8')
    ).hexdigest()[:16]


def extract_data_hash_from_filename(filename: str) -> str | None:
    """Extract data hash from filename format: WR_{wr_num}_WeekEnding_{week_end}_{data_hash}.xlsx
    
    Args:
        filename: Excel filename to parse
    
    Returns:
        str | None: 16-character hash if found, else None
    """
    try:
        name_without_ext = filename.replace('.xlsx', '')
        parts = name_without_ext.split('_')
        if len(parts) >= 4 and len(parts[-1]) == 16:
            return parts[-1]
    except Exception:
        pass
    return None


def list_generated_excel_files(folder: str) -> list[str]:
    """List Excel files beginning with WR_ in the specified folder.
    
    Args:
        folder: Directory path to scan
    
    Returns:
        list[str]: List of matching Excel filenames
    """
    try:
        return [f for f in os.listdir(folder) if f.startswith('WR_') and f.lower().endswith('.xlsx')]
    except FileNotFoundError:
        return []


def build_group_identity(filename: str) -> tuple[str, str, str, str | None] | None:
    """
    Parse filename to extract identity tuple: (wr, week_ending, variant, helper_or_user).

    Args:
        filename: Excel filename to parse

    Returns:
        tuple with format:
        - Primary: (wr, week, 'primary', None)
        - Primary+User: (wr, week, 'primary', user_identifier)
        - Helper: (wr, week, 'helper', helper_name)
        - VAC Crew (legacy, no claimer): (wr, week, 'vac_crew', '')
        - VAC Crew (named, Subproject C): (wr, week, 'vac_crew', crew_name)
        - AEP Billable: (wr, week, 'aep_billable', '')
        - Reduced Sub: (wr, week, 'reduced_sub', '')
        - AEP Billable Helper: (wr, week, 'aep_billable_helper', helper_name)
        - Reduced Sub Helper: (wr, week, 'reduced_sub_helper', helper_name)

        Legacy format without variant: (wr, week, 'primary', None)

        Returns None if filename doesn't match expected format.

    Filename formats supported:
    - WR_{wr}_WeekEnding_{week}_{hash}.xlsx (legacy primary)
    - WR_{wr}_WeekEnding_{week}_{timestamp}_{hash}.xlsx (primary)
    - WR_{wr}_WeekEnding_{week}_{timestamp}_User_{user}_{hash}.xlsx (primary+user)
    - WR_{wr}_WeekEnding_{week}_{timestamp}_Helper_{helper}_{hash}.xlsx (helper)
    - WR_{wr}_WeekEnding_{week}_{timestamp}_VacCrew_{hash}.xlsx (VAC Crew, legacy)
    - WR_{wr}_WeekEnding_{week}_{timestamp}_VacCrew_{name}_{hash}.xlsx (VAC Crew named, Subproject C)
    - WR_{wr}_WeekEnding_{week}_{timestamp}_AEPBillable_{hash}.xlsx (AEP Billable)
    - WR_{wr}_WeekEnding_{week}_{timestamp}_ReducedSub_{hash}.xlsx (Reduced Sub)
    - WR_{wr}_WeekEnding_{week}_{timestamp}_AEPBillable_Helper_{helper}_{hash}.xlsx
    - WR_{wr}_WeekEnding_{week}_{timestamp}_ReducedSub_Helper_{helper}_{hash}.xlsx
    """
    if not filename.startswith('WR_'):
        return None
    base = filename[:-5] if filename.lower().endswith('.xlsx') else filename
    parts = base.split('_')

    # Minimum: WR_<wr>_WeekEnding_<week>
    if len(parts) < 4:
        return None
    if parts[0] != 'WR':
        return None
    # Find ``WeekEnding`` by search rather than fixed position so
    # filenames whose WR token itself contains ``_`` (possible when
    # ``_RE_SANITIZE_HELPER_NAME`` rewrote a sanitization-sensitive
    # source WR#) still parse correctly. For realistic numeric WR#s
    # the marker is at position 2 exactly — this preserves the
    # legacy layout while hardening against the edge case.
    #
    # Disambiguate via the filename format itself. The STRUCTURAL
    # ``WeekEnding`` in the modern format is followed by TWO
    # consecutive 6-digit tokens:
    #   ``WeekEnding_{MMDDYY week}_{HHMMSS timestamp}_...``
    # while the legacy format (still readable off disk but no longer
    # produced) is:
    #   ``WeekEnding_{MMDDYY week}_{hash}.xlsx``
    # where the hash is hex and is essentially never exactly 6
    # digits. Helper/user identifier segments that happen to contain
    # ``WeekEnding_<6digits>`` (pathological but possible, see
    # rounds 10/11) are followed by the HASH, not a second 6-digit
    # token. So we rank candidates:
    #   * STRONG match: ``WeekEnding`` + 6-digit week + 6-digit
    #     timestamp (new format's unambiguous marker).
    #   * WEAK match: ``WeekEnding`` + 6-digit week (accepts legacy
    #     format + any other filename where a second 6-digit token
    #     isn't present).
    # Pick the RIGHTMOST strong match if any — it's always the real
    # structural delimiter because no identifier segment is ever
    # followed by two 6-digit tokens in a row. Fall back to the
    # rightmost weak match only for legacy-format filenames whose
    # hash happens not to be 6 digits (vanishingly rare collision
    # window for the weak-match path).
    _strong_candidates: list[int] = []
    _weak_candidates: list[int] = []
    for _i, _p in enumerate(parts):
        if _p != 'WeekEnding' or _i < 2 or _i + 1 >= len(parts):
            continue
        _week = parts[_i + 1]
        if not (len(_week) == 6 and _week.isdigit()):
            continue
        _weak_candidates.append(_i)
        if _i + 2 < len(parts):
            _timestamp = parts[_i + 2]
            if len(_timestamp) == 6 and _timestamp.isdigit():
                _strong_candidates.append(_i)
    # Pick the LEFTMOST strong match if any — the structural
    # delimiter always comes before any identifier-internal
    # candidate in a filename generated by ``generate_excel``
    # (variant marker + identifier are appended AFTER the
    # timestamp). Using leftmost rather than rightmost resolves
    # the final known pathology: a pathological identifier that
    # sanitizes to ``WeekEnding_<6digits>_<6digits>`` (e.g. from
    # a foreman literally named "WeekEnding 041926 123456")
    # would produce a second strong candidate inside the tail,
    # and rightmost would incorrectly pick it. Fall back to the
    # leftmost weak match only for legacy-format filenames.
    #
    # The remaining residual — a WR token that itself sanitizes
    # to ``WeekEnding_<6digits>_<6digits>`` (which would then
    # provide its own strong match at a position earlier than
    # the structural one) — is the last unreachable edge. It
    # requires a raw WR# literally equal to that pattern, which
    # is not a realistic data-entry scenario for numeric WR#s;
    # the source-side collision quarantine (pre-scan on
    # sanitized WR alone) would also flag such a pathological
    # value long before the parser is exercised.
    if _strong_candidates:
        we_idx = _strong_candidates[0]
    elif _weak_candidates:
        we_idx = _weak_candidates[0]
    else:
        return None

    # WR may span one or more parts depending on whether the
    # sanitizer introduced underscores. Rejoin them so the returned
    # WR token round-trips with the generator's output.
    wr = '_'.join(parts[1:we_idx])
    week = parts[we_idx + 1]

    # Detect variant from filename structure. Scope the marker search
    # to the tail (everything after ``WeekEnding <week>``) so any
    # accidental ``Helper`` / ``User`` / ``VacCrew`` / ``AEPBillable``
    # / ``ReducedSub`` token inside a sanitized WR does not
    # false-positive the variant detection.
    variant = 'primary'
    identifier = None
    tail = parts[we_idx + 2:]

    # Sub-project E (2026-05-25): support BOTH legacy token-bearing names
    # (``..._{HHMMSS}_<marker>_<id>_<hash>``) and the new deterministic
    # clean names (``..._<marker>_<id>``, no timestamp/hash) that
    # ``generate_excel`` produces when SUPABASE_HASH_STORE_AUTHORITATIVE is
    # on. Both shapes coexist on Smartsheet during migration, so the parser
    # must read either. The discriminator is the LEADING 6-digit ``HHMMSS``
    # timestamp at ``tail[0]``: a legacy variant name ALWAYS carries it
    # (immediately after the week) AND a trailing ``data_hash`` token; a
    # clean name has NEITHER (``tail[0]`` is always a variant marker —
    # alphabetic — or ``tail`` is empty). So when (and only when) the
    # leading timestamp is present, strip it AND the trailing hash, leaving
    # ``tail`` == ``[<marker>, <id parts...>]`` for the dispatch below.
    # Clean names skip both strips, so their last identifier segment is
    # never eaten (the bug the old unconditional ``[:-1]`` slice caused for
    # token-less names). NOTE: the oldest legacy bare-primary format
    # ``WR_{wr}_WeekEnding_{week}_{hash}.xlsx`` has a hash but no timestamp
    # and no marker — its lone hash token stays in ``tail`` but, with no
    # reserved marker, yields the correct ``('primary', None)`` regardless.
    if tail and len(tail[0]) == 6 and tail[0].isdigit():
        tail = tail[1:]          # drop the legacy HHMMSS timestamp
        if tail:
            tail = tail[:-1]     # drop the legacy trailing data_hash

    # Reserved-token precedence (ledger [2026-05-21 13:20], generalized to
    # the bare ``_User_`` shape by Subproject D 2026-05-25): the variant is
    # determined by the EARLIEST reserved marker token in ``tail``, NOT by a
    # fixed check order. A claimer / helper / vac-crew name can itself contain
    # a reserved word (e.g. a foreman literally named "Pat Helper" →
    # ``_User_Pat_Helper_<hash>``); a fixed AEPBillable→ReducedSub→VacCrew→
    # Helper→User order would misclassify it (here, as ``helper`` with the
    # ``User`` token lost). Dispatching on the earliest-position marker fixes
    # this for ALL bare shapes while preserving the two-level
    # ``_AEPBillable_User_`` / ``_ReducedSub_Helper_`` handling (AEPBillable /
    # ReducedSub are always the earliest token in those filenames). The scan
    # operates on the post-``WeekEnding`` ``tail`` slice only, so a sanitized
    # WR# containing a reserved word in its body cannot false-positive the
    # variant — covered by the negative tests in
    # TestBuildGroupIdentityWithUnderscoresInWr.
    _reserved_positions = {
        _tok: tail.index(_tok)
        for _tok in ('AEPBillable', 'ReducedSub', 'VacCrew', 'Helper', 'User')
        if _tok in tail
    }
    _first_marker = (
        min(_reserved_positions, key=lambda _t: _reserved_positions[_t])
        if _reserved_positions else None
    )
    if _first_marker == 'AEPBillable':
        aep_idx_rel = tail.index('AEPBillable')
        post_aep = tail[aep_idx_rel + 1:]
        if post_aep and post_aep[0] == 'User':
            # Subproject B: _AEPBillable_User_<claimer>[_<hash>]. Reserved
            # 'User' token marks a primary-claimer identifier. Span-join so an
            # underscored claimer name survives; dangling 'User' -> '' (legacy).
            # ``tail`` already had any legacy timestamp/hash stripped (E), so
            # the identifier is everything after the marker.
            variant = 'aep_billable'
            identifier = '_'.join(post_aep[1:])
        elif 'Helper' in post_aep:
            variant = 'aep_billable_helper'
            helper_idx_rel = post_aep.index('Helper')
            if helper_idx_rel + 1 < len(post_aep):
                identifier = '_'.join(post_aep[helper_idx_rel + 1:])
        else:
            # Legacy unpartitioned _AEPBillable_<hash> (no User/Helper token).
            variant = 'aep_billable'
            identifier = ''
    elif _first_marker == 'ReducedSub':
        rs_idx_rel = tail.index('ReducedSub')
        post_rs = tail[rs_idx_rel + 1:]
        if post_rs and post_rs[0] == 'User':
            variant = 'reduced_sub'
            identifier = '_'.join(post_rs[1:])
        elif 'Helper' in post_rs:
            variant = 'reduced_sub_helper'
            helper_idx_rel = post_rs.index('Helper')
            if helper_idx_rel + 1 < len(post_rs):
                identifier = '_'.join(post_rs[helper_idx_rel + 1:])
        else:
            # Legacy unpartitioned _ReducedSub_<hash> (no User/Helper token).
            variant = 'reduced_sub'
            identifier = ''
    elif _first_marker == 'VacCrew':
        # Subproject C: _VacCrew_<name>_<hash>. Span-join so an underscored
        # name survives. Legacy _VacCrew (no name) -> ''.
        variant = 'vac_crew'
        vac_idx_rel = tail.index('VacCrew')
        identifier = ''  # legacy _VacCrew (no name) -> '' per identity contract
        if vac_idx_rel + 1 < len(tail):
            identifier = '_'.join(tail[vac_idx_rel + 1:])
    elif _first_marker == 'Helper':
        variant = 'helper'
        helper_idx_rel = tail.index('Helper')
        if helper_idx_rel + 1 < len(tail):
            identifier = '_'.join(tail[helper_idx_rel + 1:])
    elif _first_marker == 'User':
        variant = 'primary'
        user_idx_rel = tail.index('User')
        if user_idx_rel + 1 < len(tail):
            identifier = '_'.join(tail[user_idx_rel + 1:])

    return (wr, week, variant, identifier)


def _resolve_unchanged_for_skip(history_key, data_hash, hash_history,
                                wr_num, week_iso, variant, identifier,
                                billing_audit_writer: Any = None):
    """Decide whether a group's content hash is UNCHANGED vs the durable
    store, for the change-detection skip gate (Sub-project E, 2026-05-25).

    Decision model:
    - ``SUPABASE_HASH_STORE_AUTHORITATIVE`` ON (and billing_audit
      available, not TEST_MODE, and ``week_iso`` present): Supabase
      (``billing_audit.group_content_hash``) is authoritative.
        * ``success``  -> compare the stored hash to ``data_hash``.
        * ``no_row``   -> the group was never durably stored, so it is
          treated as CHANGED (return False -> regenerate). This is the
          safe default that makes the very first authoritative run
          regenerate everything once, populating the store.
        * ``fetch_failure`` / ``unavailable`` -> a Supabase outage (or
          the table/schema not yet exposed); fall through to the local
          ``hash_history`` json cache so a transient outage degrades to
          "use the cache / regenerate", never a silent wrong-skip.
          (``lookup_group_hash`` returns only these four statuses.)
    - A missing/empty ``week_iso`` (no ``__week_ending_date`` on the
      group) skips the Supabase read entirely and uses the json cache —
      ``week_ending`` is a DATE column, so passing ``''`` would be a
      PostgREST type error that could needlessly trip the per-op
      circuit breaker.
    - Authoritative OFF (default): the ``hash_history`` json cache alone
      decides — byte-identical to the pre-E behavior.

    The caller must already have confirmed ``_history_eligible_for_skip``
    (FORCE_GENERATION / REGEN_WEEKS / RESET_* gating) and still applies
    the ``ATTACHMENT_REQUIRED_FOR_SKIP`` guard downstream — a matching
    hash with a missing attachment must still regenerate.
    """
    # Phase 09 W2 (D-06 / T-09-02-02): the billing_audit writer is injected
    # EXPLICITLY by the caller via the billing_audit_writer kwarg. A module-level
    # writer lookup here would resolve in THIS module's namespace (writer absent)
    # and SILENTLY disable the authoritative Supabase hash lookup forever -- so
    # the writer is now a required kwarg. The boolean run-mode guards are read
    # from the facade so test mutations (gwp.SUPABASE_HASH_STORE_AUTHORITATIVE =
    # ...) and the live config values are both honoured.
    _writer = billing_audit_writer
    import generate_weekly_pdfs as _gwp  # noqa: PLC0415
    SUPABASE_HASH_STORE_AUTHORITATIVE = _gwp.SUPABASE_HASH_STORE_AUTHORITATIVE
    BILLING_AUDIT_AVAILABLE = _gwp.BILLING_AUDIT_AVAILABLE
    TEST_MODE = _gwp.TEST_MODE
    if (
        SUPABASE_HASH_STORE_AUTHORITATIVE
        and BILLING_AUDIT_AVAILABLE
        and _writer is not None
        and not TEST_MODE
        and week_iso
    ):
        _h, _status = _writer.lookup_group_hash(
            wr_num, week_iso, variant, identifier or '')
        if _status == 'success':
            return _h == data_hash
        if _status == 'no_row':
            return False  # never durably stored -> regenerate (safe)
        # fetch_failure / unavailable -> fall back to json cache.
    _prev = hash_history.get(history_key)
    return bool(_prev and _prev.get('hash') == data_hash)


def load_hash_history(path: str):
    if RESET_HASH_HISTORY:
        logging.info("♻️ Hash history reset requested; ignoring existing history file")
        return {}
    try:
        with open(path,'r') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logging.warning("⚠️ Hash history is not a dict; resetting")
            return {}
        # Validate entries: keep only those with a 'hash' key.
        # Phase 1.1 Pitfall 4: also preserve ``_``-prefixed sentinel
        # keys (e.g. ``_phase_prune_version``) so they survive the
        # load → save → load round-trip and the prune pass at session
        # startup stays idempotent. Without this, the int-valued
        # sentinel would be dropped at load time and the prune would
        # fire on every run (silent non-idempotent trap).
        valid = {
            k: v for k, v in data.items()
            if isinstance(k, str) and (
                k.startswith('_')
                or (isinstance(v, dict) and 'hash' in v)
            )
        }
        dropped = len(data) - len(valid)
        if dropped:
            logging.warning(f"⚠️ Dropped {dropped} malformed hash history entries")
        return valid
    except FileNotFoundError:
        return {}
    except Exception as e:
        logging.warning(f"⚠️ Failed to load hash history: {e}")
        return {}


HASH_HISTORY_MAX_ENTRIES = 1000


def save_hash_history(path: str, history: dict):
    try:
        # Retention: keep only the most recent entries by timestamp.
        # Phase 1.1 Pitfall 4: sentinel keys (``_phase_prune_version``,
        # any future ``_``-prefixed key) are int-valued — calling
        # ``history[k].get('timestamp', '')`` on an int raises
        # AttributeError and the whole save aborts. Filter sentinels
        # OUT of the sort candidates, then re-add them unconditionally
        # so they survive the save. Sentinels are NOT subject to the
        # entry cap because there is exactly one per migration version.
        if len(history) > HASH_HISTORY_MAX_ENTRIES:
            _sentinel_keys = {
                k: v for k, v in history.items()
                if isinstance(k, str) and k.startswith('_')
            }
            _real_entries = {
                k: v for k, v in history.items()
                if not (isinstance(k, str) and k.startswith('_'))
            }
            sorted_keys = sorted(
                _real_entries.keys(),
                key=lambda k: _real_entries[k].get('timestamp', ''),
                reverse=True
            )
            _kept = {
                k: _real_entries[k]
                for k in sorted_keys[:HASH_HISTORY_MAX_ENTRIES]
            }
            _kept.update(_sentinel_keys)
            history = _kept
            logging.info(
                f"🧹 Pruned hash history to {HASH_HISTORY_MAX_ENTRIES} "
                f"entries (+ {len(_sentinel_keys)} sentinel key(s) preserved)"
            )
        tmp_path = path + '.tmp'
        with open(tmp_path,'w') as f:
            json.dump(history, f, indent=2, default=str)
        os.replace(tmp_path, path)
        logging.info(f"📝 Hash history saved ({len(history)} entries)")
    except Exception as e:
        logging.warning(f"⚠️ Failed to save hash history: {e}")
