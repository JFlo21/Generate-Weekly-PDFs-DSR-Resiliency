"""pipeline.upload -- Smartsheet target-sheet mapping + upload-task building (W5).

BILLING GUARD: the delete-old-then-upload attachment replacement order and the
Sentry-instrumented ``attach_file_to_row`` boundary live in the facade's upload
worker; this module owns the target-sheet WR# map builders (with collision
quarantine, D-22 / Living Ledger rounds 6/7/9) and the per-group upload-task
builder (dual-routing to TARGET_SHEET_ID + SUBCONTRACTOR_PPP_SHEET_ID, D-12 /
SUB-03). PARALLEL_WORKERS <= 8 (Smartsheet 300 req/min) is unchanged; the
ThreadPoolExecutor upload worker itself stays in the facade.

``create_target_sheet_map`` / ``_build_upload_tasks_for_group`` bind the
test-mutable / facade-resident sheet-id constants (TARGET_SHEET_ID,
SUBCONTRACTOR_PPP_SHEET_ID) from the generate_weekly_pdfs facade at entry so
test-time rebinds on generate_weekly_pdfs.NAME are honoured (production value is
identical -- the facade re-exports pipeline.config; SUBCONTRACTOR_PPP_SHEET_ID
is facade-resident). ``create_target_sheet_map_for`` reads no facade-resident
constants and is relocated fully byte-for-byte.

Symbols relocated byte-for-byte from ``generate_weekly_pdfs.py`` (W5):
  create_target_sheet_map_for, create_target_sheet_map,
  _build_upload_tasks_for_group
"""
from __future__ import annotations

import logging

import sentry_sdk

from pipeline.config import _RE_SANITIZE_HELPER_NAME
from pipeline.observability import _redact_exception_message

logger = logging.getLogger(__name__)


def create_target_sheet_map_for(client, sheet_id):
    """Build a sanitized ``{wr_num: target_row}`` map for any target
    sheet id.

    Phase 01 Plan 04 Task 1: extracted from the legacy
    ``create_target_sheet_map(client)`` so the dual-routing pipeline
    can build a SECOND target_map against ``SUBCONTRACTOR_PPP_SHEET_ID``
    for ``_ReducedSub`` / ``_ReducedSub_Helper_<name>`` uploads (D-12,
    SUB-03) while keeping the original TARGET_SHEET_ID map for every
    other variant.

    Critical invariants (D-22 / Living Ledger rounds 6, 7, 9):

    - Producer-side sanitization via ``_RE_SANITIZE_HELPER_NAME``
      applied at populate time — so consumer-side
      ``target_map[sanitized_wr]`` lookups in the main loop hit
      consistently across both target_maps (round-7 /
      2026-04-23 18:25).
    - Collision quarantine state (``_quarantined_keys`` /
      ``_seen_raw_for_key``) is FUNCTION-LOCAL: declared inside this
      helper's body, NOT at module scope (Plan 4 Warning 5). Each
      call owns its own quarantine sets so a duplicate WR# on one
      target sheet cannot poison the lookup table for another.
    - On collision, BOTH ambiguous raw values are removed from
      ``target_map`` and the sanitized key is quarantined (round-6
      P1). Loud not-found is strictly safer than silent wrong-row
      upload.

    Returns:
        Tuple of ``(target_map dict, target_sheet object)``. Mirrors
        the legacy return shape so the back-compat wrapper
        ``create_target_sheet_map(client)`` is a drop-in.
    """
    try:
        with sentry_sdk.start_span(op="smartsheet.api", name="Fetch target sheet for WR mapping") as span:
            target_sheet = client.Sheets.get_sheet(sheet_id)
            span.set_data("target_sheet_id", sheet_id)
            span.set_data("row_count", len(target_sheet.rows) if target_sheet.rows else 0)
        target_map: dict = {}

        # Find the Work Request # column
        wr_column_id = None
        for column in target_sheet.columns:
            if column.title == 'Work Request #':
                wr_column_id = column.id
                break

        if not wr_column_id:
            logging.error(
                f"Work Request # column not found in target sheet "
                f"{sheet_id}"
            )
            return {}, None

        # Map work request numbers to rows. Sanitize with the same
        # filesystem-safety regex used on source-row WR#s so downstream
        # ``target_map.get(sanitized_wr)`` lookups are consistent. For
        # realistic numeric WR#s this is a no-op; for any row with a
        # path-traversal-bearing WR the sanitized key matches the same
        # key the generation pipeline uses, so skip checks, upload
        # tasks, and attachment deletion all agree.
        #
        # Codex P2 guardrail: sanitize+truncate can (in principle)
        # collapse two distinct WR# cell values to the same key — e.g.
        # values that differ only in stripped characters, or IDs whose
        # first 50 chars happen to match. A silent overwrite would
        # retarget uploads / attachment deletes to the wrong row.
        # Track which raw value first produced a given sanitized key;
        # on collision, log a WARNING, quarantine the sanitized key,
        # and remove any existing mapping so both (or all) ambiguous
        # WRs are skipped deterministically until the target sheet is
        # deduplicated. A loud "not found in target sheet" warning
        # is strictly safer than a silent wrong-row upload.
        #
        # FUNCTION-LOCAL per Plan 04 Task 1 Warning 5: each invocation
        # owns its own quarantine sets so two target_map builds (one
        # for TARGET_SHEET_ID, one for SUBCONTRACTOR_PPP_SHEET_ID)
        # cannot poison each other. A module-level set would let a
        # duplicate WR# on one sheet remove the same WR# from the
        # other sheet's map — silently breaking dual-routing.
        _seen_raw_for_key: dict = {}
        _quarantined_keys: set = set()
        _collisions = 0
        for row in target_sheet.rows:
            for cell in row.cells:
                if cell.column_id == wr_column_id and cell.display_value:
                    raw_wr = str(cell.display_value).split('.')[0]
                    wr_num = _RE_SANITIZE_HELPER_NAME.sub('_', raw_wr)[:50]
                    if wr_num in _quarantined_keys:
                        # Already ambiguous — don't re-add under any
                        # raw value. Log once per collision instance
                        # so operators see every colliding row.
                        _collisions += 1
                        prior_raw = _seen_raw_for_key.get(
                            wr_num, '<quarantined>',
                        )
                        logging.warning(
                            f"⚠️ Target-sheet WR# collision (already quarantined): "
                            f"raw={raw_wr!r} also maps to sanitized key "
                            f"{wr_num!r} (prior seen: {prior_raw!r}) on sheet "
                            f"{sheet_id}. Uploads for this WR will be skipped "
                            f"until the target sheet is deduplicated."
                        )
                    elif wr_num in target_map:
                        prior_raw = _seen_raw_for_key.get(wr_num, '<unknown>')
                        if prior_raw != raw_wr:
                            # Collision: quarantine the key to prevent
                            # uploads from silently targeting the wrong
                            # row. The upload site's
                            # ``if wr_num in target_map`` check will
                            # then correctly return False for BOTH
                            # WRs, and the existing "not found in
                            # target sheet" warning fires so operators
                            # know to audit the target sheet. Removing
                            # both is strictly safer than keeping one
                            # — a silent wrong-row upload corrupts
                            # Smartsheet attachments; a loud
                            # not-found failure prompts cleanup.
                            _collisions += 1
                            del target_map[wr_num]
                            _quarantined_keys.add(wr_num)
                            logging.warning(
                                f"⚠️ Target-sheet WR# collision after sanitization "
                                f"on sheet {sheet_id}: raw={raw_wr!r} and prior "
                                f"raw={prior_raw!r} both map to sanitized key "
                                f"{wr_num!r}; QUARANTINING the key from "
                                f"target_map. Uploads for both WRs will be "
                                f"skipped until the target sheet is "
                                f"deduplicated — a 'not found in target "
                                f"sheet' warning will follow for each."
                            )
                    else:
                        target_map[wr_num] = row
                        _seen_raw_for_key[wr_num] = raw_wr
                    break

        if _collisions:
            logging.warning(
                f"⚠️ Target sheet {sheet_id} map had {_collisions} "
                f"sanitized-WR# collision event(s) across "
                f"{len(_quarantined_keys)} quarantined key(s) — "
                f"affected uploads will be skipped with 'not found in "
                f"target sheet' warnings."
            )
        logging.info(
            f"Created target sheet map for {sheet_id} with "
            f"{len(target_map)} work requests"
        )
        return target_map, target_sheet

    except Exception as e:
        logging.error(
            f"Failed to create target sheet map for {sheet_id}: "
            f"{_redact_exception_message(e)}"
        )
        return {}, None


def create_target_sheet_map(client):
    """Back-compat wrapper around ``create_target_sheet_map_for``.

    Preserved so existing call sites and tests continue to operate
    against the primary ``TARGET_SHEET_ID`` without churn. New code
    that needs a different sheet should call
    ``create_target_sheet_map_for(client, sheet_id)`` directly.

    Returns:
        Tuple of (target_map dict, target_sheet object) for reuse in cleanup.
    """
    # Phase 09 W5 (behaviour-preserving relocation): bind the
    # test-mutable / facade-resident sheet-id constant from the
    # generate_weekly_pdfs facade so test-time rebinds on
    # generate_weekly_pdfs.NAME are honoured (production value is
    # identical -- the facade re-exports pipeline.config).
    import generate_weekly_pdfs as _gwp  # noqa: PLC0415
    TARGET_SHEET_ID = _gwp.TARGET_SHEET_ID
    return create_target_sheet_map_for(client, TARGET_SHEET_ID)


def _build_upload_tasks_for_group(
    *,
    variant,
    wr_num,
    target_map,
    target_map_ppp,
    excel_path,
    filename,
    identifier,
    file_identifier,
    data_hash,
    week_raw,
    group_key,
):
    """Build the list of upload-task dicts for a single generated
    Excel file.

    Phase 01 Plan 04 Task 2: routes ``reduced_sub`` /
    ``reduced_sub_helper`` to BOTH ``TARGET_SHEET_ID`` and
    ``SUBCONTRACTOR_PPP_SHEET_ID`` (D-12 / SUB-03); every other
    variant routes to ``TARGET_SHEET_ID`` only. Each task carries
    its own ``target_sheet_id`` so the ``_upload_one`` worker
    resolves uploads to the correct sheet without consulting a
    global.

    Sanitization parity (Warning 9): the same ``wr_num`` value is
    reused for both ``target_map[wr_num]`` and
    ``target_map_ppp[wr_num]`` lookups. Because
    ``_RE_SANITIZE_HELPER_NAME`` is idempotent and both maps are
    populated using it at producer-side (see
    ``create_target_sheet_map_for``), this single sanitisation upstream
    is sufficient — no re-sanitisation is needed at the consumer.

    Independent quarantine (Warning 5 / round-6): the two target_maps
    own their own quarantine sets. If a WR# is quarantined on one
    sheet, the lookup returns False there but may still succeed on
    the other sheet — producing exactly the upload behaviour
    operators expect (uploads only to sheets whose WR# is
    unambiguous, with operator-visible WARNINGs on the quarantined
    side).

    Args:
        variant: One of ``primary`` / ``helper`` / ``vac_crew`` /
            ``aep_billable`` / ``aep_billable_helper`` /
            ``reduced_sub`` / ``reduced_sub_helper``.
        wr_num: Sanitised WR# (already passed through
            ``_RE_SANITIZE_HELPER_NAME`` at the main-loop derivation
            site).
        target_map: Primary ``TARGET_SHEET_ID`` mapping
            (``{sanitized_wr: row}``).
        target_map_ppp: Secondary ``SUBCONTRACTOR_PPP_SHEET_ID``
            mapping; empty / unreachable → reduced-sub routing
            degrades to single-target with a WARNING.
        excel_path / filename / identifier / file_identifier /
            data_hash / week_raw / group_key: Pass-through payload
            consumed by ``_upload_one``.

    Returns:
        A list of upload-task dicts. ``[]`` if ``wr_num`` is blank
        or neither map carries the WR.
    """
    # Phase 09 W5 (behaviour-preserving relocation): bind the
    # test-mutable / facade-resident sheet-id constants from the
    # generate_weekly_pdfs facade so test-time rebinds on
    # generate_weekly_pdfs.NAME are honoured (production value is
    # identical -- the facade re-exports pipeline.config;
    # SUBCONTRACTOR_PPP_SHEET_ID is facade-resident).
    import generate_weekly_pdfs as _gwp  # noqa: PLC0415
    SUBCONTRACTOR_PPP_SHEET_ID = _gwp.SUBCONTRACTOR_PPP_SHEET_ID
    TARGET_SHEET_ID = _gwp.TARGET_SHEET_ID
    if not wr_num:
        return []

    upload_tasks: list = []

    # Primary leg — every variant routes here, including
    # reduced_sub / reduced_sub_helper. The primary leg always runs
    # first so a missing-WR warning consistently mentions
    # TARGET_SHEET_ID first.
    primary_present = wr_num in target_map
    if primary_present:
        upload_tasks.append({
            'excel_path': excel_path,
            'filename': filename,
            'wr_num': wr_num,
            'target_row': target_map[wr_num],
            'target_sheet_id': TARGET_SHEET_ID,
            'variant': variant,
            'identifier': identifier,
            'file_identifier': file_identifier,
            'data_hash': data_hash,
            'week_raw': week_raw,
            'group_key': group_key,
        })
    else:
        # WR not on TARGET_SHEET_ID. Name the sheet id explicitly so
        # operators know which sheet to dedup / add the WR to (or to
        # check the source-side quarantine). Fires for both the
        # "map populated but WR absent" case and the "map empty —
        # PPP sheet unreachable / TEST_MODE" degraded case, since
        # both produce the same operator-actionable surface.
        logging.warning(
            f"⚠️ Work request {wr_num} not found in target sheet "
            f"{TARGET_SHEET_ID}"
        )

    # Second leg — only for reduced_sub variants per D-12 / SUB-03.
    if variant in ('reduced_sub', 'reduced_sub_helper'):
        if primary_present and wr_num in target_map_ppp:
            upload_tasks.append({
                'excel_path': excel_path,
                'filename': filename,
                'wr_num': wr_num,
                'target_row': target_map_ppp[wr_num],
                'target_sheet_id': SUBCONTRACTOR_PPP_SHEET_ID,
                'variant': variant,
                'identifier': identifier,
                'file_identifier': file_identifier,
                'data_hash': data_hash,
                'week_raw': week_raw,
                'group_key': group_key,
            })
        elif primary_present:
            # WR not on PPP sheet. Degrade gracefully — the primary
            # leg still runs (if it found the WR) and operators see
            # a sheet-specific WARNING with the PPP sheet id so they
            # can tell at a glance which sheet to update.
            logging.warning(
                f"⚠️ Work request {wr_num} not found in "
                f"subcontractor PPP target sheet "
                f"{SUBCONTRACTOR_PPP_SHEET_ID}"
            )

    return upload_tasks
