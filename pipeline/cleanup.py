"""pipeline.cleanup -- stale-Excel / attachment cleanup + purge (W5).

Relocated byte-for-byte from ``generate_weekly_pdfs.py`` (D-05 relocation-only,
ZERO behaviour change).  These functions prune local stale Excel files and
prune/replace Smartsheet attachments.

Billing guards preserved verbatim:
- the (wr, week, variant, identifier) identity dimension that prevents
  primary/helper cross-deletion (``build_group_identity``);
- delete-old-then-upload ordering is owned by callers; these helpers only
  perform the variant-aware *delete* side;
- attachment pre-fetch / on-demand fallback: every consumer accepts a missing
  cache entry and falls back to a per-row ``list_row_attachments`` lookup;
- KEEP_HISTORICAL_WEEKS gating and the off-contract / legacy-migration gates
  are byte-for-byte.

PII discipline: attachment names embed WR + week; existing log levels are
unchanged (the facade ``before_send_log`` sanitizer is the backstop).

Test-mutable / facade-resident constants (KEEP_HISTORICAL_WEEKS,
SUPABASE_HASH_STORE_AUTHORITATIVE, OUTPUT_FOLDER) are bound from the
``generate_weekly_pdfs`` facade at function entry (behaviour-preserving
prelude) so test-time rebinds on ``generate_weekly_pdfs.NAME`` are honoured;
production value is identical because the facade re-exports pipeline.config.

Symbols relocated from ``generate_weekly_pdfs.py`` (W5):
  cleanup_stale_excels, cleanup_untracked_sheet_attachments,
  delete_old_excel_attachments, _has_existing_week_attachment,
  purge_existing_hashed_outputs
"""
from __future__ import annotations

import collections
import logging
import os

from pipeline.change_detection import (
    build_group_identity,
    extract_data_hash_from_filename,
    list_generated_excel_files,
)

logger = logging.getLogger(__name__)



def cleanup_stale_excels(output_folder: str, kept_filenames: set):
    """Remove Excel files not generated in current run (VARIANT-AWARE).

    Strategy:
      1. Keep all names in kept_filenames.
      2. For identities (wr, week, variant, identifier) present in kept_filenames, 
         remove any other files with same identity (older timestamp/hash).
      3. Remove any other WR_*.xlsx whose identity is not in current run 
         (per user requirement to only keep new system outputs).
      4. CRITICAL: Never cross-delete between variants (primary vs helper).
    
    Identity includes variant dimension to prevent primary/helper cross-deletion.
    Returns list of removed filenames.
    """
    removed = []
    existing = list_generated_excel_files(output_folder)
    identities_to_keep = set()
    for fname in kept_filenames:
        ident = build_group_identity(fname)
        if ident:
            identities_to_keep.add(ident)
    for fname in existing:
        if fname in kept_filenames:
            continue
        ident = build_group_identity(fname)
        if ident and ident in identities_to_keep:
            # Variant of identity we already produced this run
            try:
                os.remove(os.path.join(output_folder, fname))
                removed.append(fname)
            except Exception as e:
                logging.warning(f"⚠️ Failed to remove stale variant {fname}: {e}")
        elif ident:
            # Different identity (older run) – remove per requirement
            try:
                os.remove(os.path.join(output_folder, fname))
                removed.append(fname)
            except Exception as e:
                logging.warning(f"⚠️ Failed to remove legacy file {fname}: {e}")
        # Non-conforming files left untouched
    return removed

def cleanup_untracked_sheet_attachments(
    client,
    target_sheet_id: int,
    valid_wr_weeks: set,
    test_mode: bool,
    attachment_cache: dict | None = None,
    target_sheet=None,
    variant_whitelist: set[str] | None = None,
    sub_wr_scope: set[str] | None = None,
    sub_offcontract_variants: set[str] | None = None,
    sub_legacy_primary_variants: set[str] | None = None,
    vac_legacy_wr_scope: set[str] | None = None,
    primary_wr_scope: set[str] | None = None,
):
    """Prune only older variants for identities processed this run (VARIANT-AWARE).

    If KEEP_HISTORICAL_WEEKS=1 (default false here), weeks not in this run are preserved.
    valid_wr_weeks: set of 4-tuples (wr, week_mmddyy, variant, identifier) that were
                    generated or validated this session.
    attachment_cache: Pre-fetched dict of row_id -> attachment list (avoids per-row API calls).
    target_sheet: Pre-loaded target sheet object (avoids redundant API call).

    variant_whitelist: Per-sheet variant gate (Phase 1.1 Bug B2 /
        D-07 / SUB-10). When provided, any attachment whose
        ``build_group_identity``-parsed variant is NOT in the
        whitelist is treated as off-contract for THIS sheet and
        unconditionally deleted, regardless of ``valid_wr_weeks``
        membership and regardless of ``KEEP_HISTORICAL_WEEKS``.
        When None (default), preserves byte-identical legacy
        behaviour — every variant is accepted and the cleanup
        decision rests on identity grouping + valid_wr_weeks.
        PPP cleanup passes ``{'reduced_sub', 'reduced_sub_helper'}``;
        TARGET cleanup passes None.

    sub_wr_scope: Phase 1.1 UAT gap closure (SUB-09 helper dimension).
        When provided, any attachment whose parsed ``wr`` is in this set
        AND whose parsed ``variant`` is in ``sub_offcontract_variants``
        is treated as off-contract for THIS sheet and unconditionally
        deleted. Used to remove pre-existing legacy ``_Helper_<name>``
        and bare-primary attachments for subcontractor WRs from
        TARGET_SHEET_ID (Task 1 stops NEW ones; this removes OLD ones).
        When None (default), this gate is skipped entirely —
        byte-identical legacy TARGET behaviour for all callers that
        do not pass the parameter. WR-01 guard: an attachment whose
        identity is in ``valid_wr_weeks`` is exempt from this gate so a
        legitimate live non-subcontractor ``_Helper_`` file for a WR#
        that ALSO has subcontractor rows is never deleted (cross-sheet
        WR overlap — see the inline comment at the gate).

    sub_offcontract_variants: Set of variant strings that are off-contract
        for WRs in ``sub_wr_scope`` on THIS sheet. For TARGET cleanup,
        pass ``{'helper', 'primary'}`` (subcontractor non-helper rows
        now emit only variant keys per Bug B1; subcontractor helper rows
        now emit only shadow variants per Task 1 — so any bare 'primary'
        or legacy 'helper' attachment for a sub WR is a pre-fix orphan).
        When None and ``sub_wr_scope`` is provided, this gate is a no-op.
        Ignored when ``sub_wr_scope`` is None.

    sub_legacy_primary_variants: Subproject B (2026-05-20) one-time
        migration. When provided, any attachment whose parsed ``wr`` is
        in ``sub_wr_scope``, whose parsed ``variant`` is in this set, and
        whose parsed ``identifier`` is empty (legacy unpartitioned
        ``_ReducedSub`` / ``_AEPBillable``) is unconditionally deleted —
        UNLESS its identity is in ``valid_wr_weeks`` (live-identity
        exemption). New per-claimer files (non-empty identifier) are
        never matched. When None (default), this gate is skipped.
        Gated at the call sites by SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED.

    vac_legacy_wr_scope: Subproject C (2026-05-21) Task 6 one-time
        migration. When provided, any attachment whose parsed ``wr`` is
        in this set, whose parsed ``variant`` is ``'vac_crew'``, and
        whose parsed ``identifier`` is empty (legacy unpartitioned bare
        ``_VacCrew``) is unconditionally deleted — UNLESS its identity is
        in ``valid_wr_weeks`` (live-identity exemption). Per-claimer files
        (non-empty identifier like ``_VacCrew_John``) are never matched.
        When None (default), this gate is skipped — byte-identical legacy
        behaviour for callers that do not pass the parameter.
        Gated at the TARGET call site by VAC_CREW_LEGACY_CLEANUP_ENABLED.
        vac_crew files route to TARGET_SHEET_ID only (never PPP); the
        PPP call site must NOT receive this parameter.

    primary_wr_scope: Subproject D (2026-05-25) one-time migration. When
        provided, any attachment whose parsed ``wr`` is in this set, whose
        parsed ``variant`` is ``'primary'``, and whose parsed ``identifier``
        is empty (legacy unpartitioned bare ``primary``) is unconditionally
        deleted — UNLESS its identity is in ``valid_wr_weeks`` (live-identity
        exemption). Per-claimer files (non-empty identifier like
        ``_User_Alice``) are never matched. When None (default), this gate
        is skipped — byte-identical legacy behaviour for callers that do
        not pass the parameter. Gated at the TARGET call site by
        PRIMARY_CLAIM_ATTRIBUTION_ENABLED and
        LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED. Non-subcontractor primary
        files route to TARGET_SHEET_ID only — the PPP call site must NOT
        receive this parameter.

    CRITICAL: Identity includes variant dimension to prevent primary/helper cross-deletion.
              Each (wr, week, variant, identifier) is treated as independent.
    """
    # Phase 09 W5 (behaviour-preserving relocation): bind the
    # test-mutable / facade-resident constant from the
    # generate_weekly_pdfs facade so test-time rebinds on
    # generate_weekly_pdfs.NAME are honoured (production value is
    # identical -- the facade re-exports pipeline.config).
    import generate_weekly_pdfs as _gwp  # noqa: PLC0415
    KEEP_HISTORICAL_WEEKS = _gwp.KEEP_HISTORICAL_WEEKS
    if test_mode:
        logging.info("🧪 Test mode – skipping sheet attachment pruning")
        return
    try:
        sheet = target_sheet if target_sheet is not None else client.Sheets.get_sheet(target_sheet_id)
    except Exception as e:
        logging.warning(f"⚠️ Could not load target sheet for attachment cleanup: {e}")
        return
    removed_variants = 0
    removed_off_contract = 0  # Phase 1.1 Bug B2 (D-07 / SUB-10): off-contract counter
    for row in sheet.rows:
        try:
            # Use pre-fetched cache if available; otherwise fall back to per-row API call
            if attachment_cache is not None and row.id in attachment_cache:
                attachments = attachment_cache[row.id]
            else:
                attachments = client.Attachments.list_row_attachments(target_sheet_id, row.id).data
        except Exception:
            continue
        identity_groups = collections.defaultdict(list)
        off_contract_attachments = []  # Phase 1.1 Bug B2 / D-07: per-sheet whitelist
        for att in attachments:
            name = getattr(att,'name','') or ''
            if name.startswith('WR_') and name.endswith('.xlsx'):
                ident = build_group_identity(name)
                if ident:
                    wr, week, variant, _identifier = ident
                    # Phase 1.1 Bug B2 (D-07 / SUB-10): per-sheet
                    # variant whitelist gate. variant_whitelist=None
                    # (TARGET cleanup) preserves legacy "accept
                    # every variant" behaviour. When the caller
                    # supplies a whitelist (PPP cleanup passes
                    # {'reduced_sub','reduced_sub_helper'}), any
                    # other variant parsed from a filename on THIS
                    # sheet is off-contract and gets unconditionally
                    # pruned BEFORE the identity_groups +
                    # KEEP_HISTORICAL_WEEKS logic — variant-set
                    # membership is the authoritative gate for this
                    # sheet.
                    if (
                        variant_whitelist is not None
                        and variant not in variant_whitelist
                    ):
                        off_contract_attachments.append(att)
                        continue
                    # Phase 1.1 UAT gap closure (SUB-09 helper dimension):
                    # remove pre-existing legacy `_Helper_<name>` / bare-primary
                    # attachments for subcontractor WRs on TARGET. Task 1 stops
                    # NEW ones at the producer; this removes leftovers already
                    # uploaded by pre-fix merged runs.
                    #
                    # WR-01 cross-sheet-overlap guard (review follow-up): the
                    # ``sub_wr_scope`` set keys on WR# alone, but
                    # ``is_subcontractor_row`` is decided PER-ROW by source
                    # sheet. A single WR# can legitimately have helper rows on
                    # a subcontractor sheet (→ in scope) AND on a NON-sub sheet
                    # (→ a live ``_Helper_<name>.xlsx`` whose identity IS in
                    # ``valid_wr_weeks`` this run). Exempting identities present
                    # in ``valid_wr_weeks`` preserves the cleanup intent — a
                    # genuinely orphaned legacy sub-helper file is NEVER in
                    # ``valid_wr_weeks`` because Task 1 stopped emitting it — while
                    # protecting a legitimate live non-sub artifact from an
                    # every-run delete/regenerate/re-upload churn loop.
                    if (
                        sub_wr_scope is not None
                        and wr in sub_wr_scope
                        and sub_offcontract_variants is not None
                        and variant in sub_offcontract_variants
                        and ident not in valid_wr_weeks
                    ):
                        off_contract_attachments.append(att)
                        continue
                    # Subproject B (2026-05-20): one-time migration —
                    # delete LEGACY UNPARTITIONED `_ReducedSub` /
                    # `_AEPBillable` attachments (parsed identifier == '')
                    # for in-scope subcontractor WRs. B re-partitions
                    # these by frozen claimer, so the bare one-file-per-WR
                    # attachment is an obsolete duplicate. The
                    # ``not _identifier`` check is the precise legacy
                    # selector: new per-claimer files carry a non-empty
                    # identifier and are NOT deleted here. The
                    # ``ident not in valid_wr_weeks`` guard is
                    # belt-and-suspenders (B never emits an empty
                    # identifier, so a live file is never empty-id) per the
                    # [2026-05-19 23:45] WR-01 live-identity rule.
                    if (
                        sub_wr_scope is not None
                        and wr in sub_wr_scope
                        and sub_legacy_primary_variants is not None
                        and variant in sub_legacy_primary_variants
                        and not _identifier
                        and ident not in valid_wr_weeks
                    ):
                        off_contract_attachments.append(att)
                        continue
                    # Subproject C Task 6 (2026-05-21): one-time migration —
                    # delete LEGACY UNPARTITIONED bare ``_VacCrew`` attachments
                    # (parsed identifier == '') for in-scope vac_crew WRs.
                    # Subproject C re-partitions vac_crew files by frozen
                    # claimer (``_VacCrew_<name>``), so the old bare
                    # one-file-per-WR attachment is an obsolete duplicate.
                    # The ``not _identifier`` check is the precise legacy
                    # selector: new per-claimer files carry a non-empty
                    # identifier and are NOT deleted here.
                    # WR-01 live-identity exemption: an attachment whose
                    # identity IS in ``valid_wr_weeks`` is kept — this
                    # protects a live per-claimer file from being deleted
                    # if its identifier happened to be empty (belt-and-
                    # suspenders; per-claimer files always have non-empty
                    # identifiers so this branch is effectively unreachable
                    # for them, but the guard keeps the contract symmetric
                    # with the B sub_legacy_primary gate).
                    if (
                        vac_legacy_wr_scope is not None
                        and wr in vac_legacy_wr_scope
                        and variant == 'vac_crew'
                        and not _identifier
                        and ident not in valid_wr_weeks
                    ):
                        off_contract_attachments.append(att)
                        continue
                    # Subproject D (2026-05-25): one-time migration —
                    # delete LEGACY UNPARTITIONED bare ``primary``
                    # attachments (``build_group_identity`` parses a bare
                    # primary to ``identifier=None``; the ``not _identifier``
                    # gate below matches None and '') for in-scope
                    # NON-subcontractor WRs. D re-partitions production
                    # primary files by frozen claimer (``_User_<name>``),
                    # so the old bare one-file-per-WR attachment is an
                    # obsolete duplicate. The ``not _identifier`` check is
                    # the precise legacy selector: new per-claimer files
                    # carry a non-empty identifier and are NOT deleted here.
                    # WR-01 live-identity exemption: an attachment whose
                    # identity IS in ``valid_wr_weeks`` is kept — this
                    # protects a legitimate bare-primary file the current
                    # run produced (e.g. an overlapping WR still emitting
                    # bare primary because attribution was disabled for
                    # those rows) from an every-run delete/regenerate churn.
                    if (
                        primary_wr_scope is not None
                        and wr in primary_wr_scope
                        and variant == 'primary'
                        and not _identifier
                        and ident not in valid_wr_weeks
                    ):
                        off_contract_attachments.append(att)
                        continue
                    # Variant-migration orphan gate (2026-06-02):
                    # A dual-checkbox helper row that had blank helper_dept
                    # on Run 1 fell back to a primary group and produced a
                    # primary Excel attachment on Smartsheet. On Run 2, once
                    # helper_dept is corrected, the row migrates to the helper
                    # variant — the primary group disappears from ``groups``
                    # and its identity is NEVER added to ``valid_wr_weeks``.
                    # The identity_groups loop below keeps the single remaining
                    # attachment (no duplicate to prune), so it silently
                    # survives every subsequent run.
                    #
                    # Detection rule: this attachment is a 'primary' variant
                    # whose identity is NOT in ``valid_wr_weeks``, AND at
                    # least one helper-family variant for the SAME (wr, week)
                    # IS live in ``valid_wr_weeks`` this run. That combination
                    # is the unambiguous signal that the primary credit was
                    # superseded by a helper.
                    #
                    # Safety: the ``ident not in valid_wr_weeks`` guard ensures
                    # a legitimately live primary (one that IS still produced
                    # this run) is never touched. The helper-family presence
                    # check (any helper/aep_billable_helper/reduced_sub_helper
                    # for same wr+week) is the confirming signal that prevents
                    # over-eager deletion when a primary is simply not in scope
                    # today for other reasons (WR_FILTER, time-budget cutoff,
                    # KEEP_HISTORICAL_WEEKS). Without this confirming signal we
                    # would risk deleting a primary that is still valid but just
                    # not regenerated in this run.
                    _HELPER_VARIANTS_FOR_ORPHAN_GATE = frozenset({
                        'helper', 'aep_billable_helper', 'reduced_sub_helper'
                    })
                    if (
                        variant == 'primary'
                        and ident not in valid_wr_weeks
                        and any(
                            _vw[0] == wr
                            and _vw[1] == week
                            and _vw[2] in _HELPER_VARIANTS_FOR_ORPHAN_GATE
                            for _vw in valid_wr_weeks
                        )
                    ):
                        try:
                            import sentry_sdk as _sentry_sdk
                            with _sentry_sdk.new_scope() as _scope:
                                _scope.set_tag(
                                    'cleanup.reason',
                                    'variant_migration_orphan',
                                )
                                _scope.set_tag('wr', wr)
                                _scope.set_tag('week', week)
                        except Exception:
                            pass
                        off_contract_attachments.append(att)
                        logging.info(
                              f"🔄 Variant-migration orphan detected: "
                            f"primary attachment {att.name!r} superseded "
                            f"by live helper for WR {wr} week {week}. "
                            f"Queued for deletion."
                        )
                        continue
                    identity_groups[ident].append(att)
        # Phase 1.1 Bug B2 (D-07 / SUB-10): unconditionally delete
        # off-contract attachments. These are NEVER subject to
        # KEEP_HISTORICAL_WEEKS — variant-set-membership is the
        # authoritative gate for this sheet. PII marker
        # "Removed off-contract variant on sheet" registered in
        # _PII_LOG_MARKERS for the new log body below (the
        # attachment name embeds WR + week which the sanitizer
        # must catch under SENTRY_ENABLE_LOGS).
        for att in off_contract_attachments:
            try:
                client.Attachments.delete_attachment(target_sheet_id, att.id)
                removed_off_contract += 1
                logging.info(
                    f"🗑️ Removed off-contract variant on sheet "
                    f"{target_sheet_id}: {att.name}"
                )
            except Exception as e:
                logging.warning(
                    f"⚠️ Could not delete off-contract variant "
                    f"{att.name}: {e}"
                )
        for ident, atts in identity_groups.items():
            # Skip identities not processed if preserving historical weeks
            if ident not in valid_wr_weeks and KEEP_HISTORICAL_WEEKS:
                continue
            # Sort attachments newest first based on timestamp token
            def _ts(a):
                parts = a.name.split('_')
                # Find timestamp (should be after WeekEnding_{week})
                for i, p in enumerate(parts):
                    if p == 'WeekEnding' and i + 2 < len(parts):
                        ts_candidate = parts[i + 2]
                        if ts_candidate.isdigit() and len(ts_candidate) == 6:
                            return ts_candidate
                return '000000'
            atts_sorted = sorted(atts, key=_ts, reverse=True)
            # Keep newest; remove others
            for old in atts_sorted[1:]:
                try:
                    client.Attachments.delete_attachment(target_sheet_id, old.id)
                    removed_variants += 1
                    logging.info(f"🗑️ Removed older variant: {old.name}")
                except Exception as e:
                    logging.warning(f"⚠️ Could not delete variant {old.name}: {e}")
    logging.info(
        f"🧹 Variant pruning done: removed_variants={removed_variants}, "
        f"removed_off_contract={removed_off_contract}"
    )

def delete_old_excel_attachments(client, target_sheet_id, target_row, wr_num, week_raw, current_data_hash, variant='primary', identifier=None, force_generation=False, cached_attachments: list | None = None):
    """Delete prior Excel attachment(s) ONLY for the specific (WR, week, variant, identifier) identity.

    VARIANT-AWARE BEHAVIOR:
    • Looks for attachments matching (wr, week, variant, identifier) exactly
    • CRITICAL: Never deletes across variants (primary vs helper)
    • If an attachment for that identity already has the identical data hash
      (and not forcing) we skip regeneration & upload
    • Leaves attachments for other weeks and other variants untouched

    Args:
        variant: 'primary' or 'helper'
        identifier: For helper variant, the helper name; for primary+user, the user identifier
        cached_attachments: Pre-fetched attachment list (avoids redundant API call)

    Returns (deleted_count, skipped_due_to_same_data)
    """
    # Phase 09 W5 (behaviour-preserving relocation): bind the
    # test-mutable / facade-resident constant from the
    # generate_weekly_pdfs facade so test-time rebinds on
    # generate_weekly_pdfs.NAME are honoured (production value is
    # identical -- the facade re-exports pipeline.config).
    import generate_weekly_pdfs as _gwp  # noqa: PLC0415
    SUPABASE_HASH_STORE_AUTHORITATIVE = _gwp.SUPABASE_HASH_STORE_AUTHORITATIVE
    deleted_count = 0
    try:
        attachments = cached_attachments if cached_attachments is not None else client.Attachments.list_row_attachments(target_sheet_id, target_row.id).data
    except Exception as e:
        logging.warning(f"Could not list attachments for row {target_row.id}: {e}")
        return 0, False

    # Build variant-specific prefix patterns
    # Format: WR_{wr}_WeekEnding_{week}_<variant_marker>
    base_prefix = f"WR_{wr_num}_WeekEnding_{week_raw}"
    
    candidates = []
    for a in attachments:
        name = getattr(a, 'name', '') or ''
        if not name.endswith('.xlsx'):
            continue
        
        # Parse identity from filename
        ident = build_group_identity(name)
        if not ident:
            continue
        
        ident_wr, ident_week, ident_variant, ident_identifier = ident
        
        # Match only if all identity components match
        # Normalize None/'' to avoid mismatch between build_group_identity (returns None) and main loop (uses '')
        if (ident_wr == wr_num and 
            ident_week == week_raw and 
            ident_variant == variant and
            (ident_identifier or '') == (identifier or '')):
            candidates.append(a)

    if not candidates:
        return 0, False

    # Skip if any existing candidate already carries the same hash (unless
    # forced). Sub-project E (2026-05-25): this filename-embedded-hash
    # short-circuit is the LEGACY durable backstop. When
    # SUPABASE_HASH_STORE_AUTHORITATIVE is on, the durable skip decision is
    # made upstream by the Supabase-backed skip gate
    # (_resolve_unchanged_for_skip in main), AND clean filenames carry no
    # hash token (extract_data_hash_from_filename returns None for them), so
    # this short-circuit MUST NOT fire — the identity-based replacement loop
    # below still runs so a fresh clean file supersedes any prior (token-
    # named or clean) attachment for the same identity. Forcing always wins.
    if force_generation:
        logging.info(f"⚐ FORCE GENERATION for {variant} WR {wr_num} Week {week_raw}; ignoring existing hash match")
    elif not SUPABASE_HASH_STORE_AUTHORITATIVE:
        for att in candidates:
            existing_hash = extract_data_hash_from_filename(att.name)
            if existing_hash == current_data_hash:
                logging.info(f"⏩ Unchanged ({variant} WR {wr_num} Week {week_raw}) hash {current_data_hash}; skipping regeneration & upload")
                return 0, True

    logging.info(f"🗑️ Removing {len(candidates)} prior {variant} attachment(s) for WR {wr_num} Week {week_raw}")
    for att in candidates:
        try:
            client.Attachments.delete_attachment(target_sheet_id, att.id)
            deleted_count += 1
            logging.info(f"   ✅ Deleted: {att.name}")
        except Exception as e:
            msg = str(e).lower()
            if '404' in msg or 'not found' in msg:
                logging.info(f"   ℹ️ Already gone: {att.name}")
            else:
                logging.warning(f"   ⚠️ Delete failed {att.name}: {e}")
    return deleted_count, False

def _has_existing_week_attachment(client, target_sheet_id, target_row, wr_num: str, week_raw: str, variant: str = 'primary', identifier: str | None = None, cached_attachments: list | None = None) -> bool:
    """Return True if at least one attachment exists for this (WR, week, variant, identifier) identity."""
    try:
        attachments = cached_attachments if cached_attachments is not None else client.Attachments.list_row_attachments(target_sheet_id, target_row.id).data
    except Exception:
        return False
    
    # Check for attachments matching this exact identity
    for a in attachments:
        name = getattr(a, 'name', '') or ''
        if not name.endswith('.xlsx'):
            continue
        
        # Parse identity from filename
        ident = build_group_identity(name)
        if not ident:
            continue
        
        ident_wr, ident_week, ident_variant, ident_identifier = ident
        
        # Match only if all identity components match
        # Normalize None/'' to avoid mismatch between build_group_identity (returns None) and main loop (uses '')
        if (ident_wr == wr_num and 
            ident_week == week_raw and 
            ident_variant == variant and
            (ident_identifier or '') == (identifier or '')):
            return True
    
    return False

def purge_existing_hashed_outputs(client, target_sheet_id: int, wr_subset: set | None, test_mode: bool):
    """Delete existing hashed Excel attachments and local files so hashes recompute fresh.

    wr_subset: if provided, only purge attachments for these WR numbers; otherwise purge all WR_*.xlsx attachments.
    """
    # Phase 09 W5 (behaviour-preserving relocation): bind the
    # test-mutable / facade-resident constant from the
    # generate_weekly_pdfs facade so test-time rebinds on
    # generate_weekly_pdfs.NAME are honoured (production value is
    # identical -- the facade re-exports pipeline.config).
    import generate_weekly_pdfs as _gwp  # noqa: PLC0415
    OUTPUT_FOLDER = _gwp.OUTPUT_FOLDER
    # Local file purge
    try:
        local_files = list_generated_excel_files(OUTPUT_FOLDER)
        removed_local = 0
        for f in local_files:
            wr_ident = build_group_identity(f)
            if wr_subset and wr_ident and wr_ident[0] not in wr_subset:
                continue
            try:
                os.remove(os.path.join(OUTPUT_FOLDER, f))
                removed_local += 1
            except Exception:
                pass
        logging.info(f"🧨 Local hash reset: removed {removed_local} existing Excel file(s)")
    except Exception as e:
        logging.warning(f"⚠️ Local hash reset failed: {e}")

    if test_mode:
        logging.info("🧪 Test mode active – skipping remote attachment purge")
        return
    try:
        sheet = client.Sheets.get_sheet(target_sheet_id)
    except Exception as e:
        logging.warning(f"⚠️ Could not load target sheet for purge: {e}")
        return
    purged = 0
    scanned = 0
    for row in sheet.rows:
        try:
            attachments = client.Attachments.list_row_attachments(target_sheet_id, row.id).data
        except Exception:
            continue
        for att in attachments:
            name = getattr(att,'name','') or ''
            if not name.startswith('WR_') or not name.endswith('.xlsx'):
                continue
            ident = build_group_identity(name)
            if wr_subset and ident and ident[0] not in wr_subset:
                continue
            scanned += 1
            try:
                client.Attachments.delete_attachment(target_sheet_id, att.id)
                purged += 1
                logging.info(f"🗑️ Purged attachment: {name}")
            except Exception as e:
                logging.warning(f"⚠️ Failed to purge attachment {name}: {e}")
    logging.info(f"🔥 Remote hash reset complete: purged {purged} / scanned {scanned} matching attachment(s)")
