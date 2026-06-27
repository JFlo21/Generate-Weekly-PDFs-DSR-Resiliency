"""pipeline.attribution -- per-WR/week hash-history pruning, claimer
remediation, and the billing-audit row cache (W5, D-02 / D-05 relocation-only).

This module owns the attribution lifecycle stage:
- the WR-scope builders (``_build_subcontractor_wr_scope`` /
  ``_build_vac_crew_wr_scope`` / ``_build_primary_wr_scope``) that gate on each
  group's authoritative ``__variant`` field (never a key-substring scan);
- the four idempotent one-time hash-history prune runners (Phase 1.1 /
  Subproject B / C / D) whose ``*_HASH_PRUNE_VERSION`` constant IS the kill
  switch (D-19);
- ``run_claimer_remediation`` (garbage-claimer attachment sweep) -- its
  ``REMEDIATE_CLAIMERS`` default-OFF / ``REMEDIATION_DRY_RUN`` default-ON
  behaviour is unchanged (the gate values are read by the facade caller);
- the billing-audit frozen-row cache I/O (``load_/save_billing_audit_row_cache``).

PII discipline (T-09-05-02): aggregate-only logging is preserved byte-for-byte;
no per-row WR / foreman / helper / vac-crew identifier is emitted at INFO or
WARNING, and the facade ``before_send_log`` sanitizer is the backstop.

The four ``*_HASH_PRUNE_VERSION`` constants relocate WITH their prune runners so
the bare-name reads resolve to this module's scope (the test suite never rebinds
them on the facade -- it only assert-regexes the assignment line, so the
source-grep guards are repointed to facade + this module).

Facade-read prelude (behaviour-preserving, Wave-3/4 pattern): the test suite
rebinds ``PRIMARY_CLAIM_ATTRIBUTION_ENABLED`` / ``VAC_CREW_CLAIM_ATTRIBUTION_ENABLED``
(and ``mock.patch``-es ``TARGET_SHEET_ID`` / ``SUBCONTRACTOR_PPP_SHEET_ID``) on
the ``generate_weekly_pdfs`` FACADE, so the three functions that read those
constants bind them from the facade at call time; production value is identical
because the facade re-exports pipeline.config. Stable regexes / functions /
stdlib are static module imports so the bodies stay byte-for-byte.

Symbols relocated byte-for-byte from ``generate_weekly_pdfs.py`` (W5):
  PHASE_1_1_HASH_PRUNE_VERSION, SUBPROJECT_B_HASH_PRUNE_VERSION,
  VAC_CREW_HASH_PRUNE_VERSION, SUBPROJECT_D_HASH_PRUNE_VERSION,
  BILLING_AUDIT_ROW_CACHE_PATH, BILLING_AUDIT_ROW_CACHE_MAX_ENTRIES,
  _SUBCONTRACTOR_SCOPE_VARIANTS, _build_subcontractor_wr_scope,
  _build_vac_crew_wr_scope, _build_primary_wr_scope, _run_phase_1_1_hash_prune,
  _run_subproject_b_hash_prune, _run_vac_crew_hash_prune,
  _run_subproject_d_hash_prune, run_claimer_remediation,
  load_billing_audit_row_cache, save_billing_audit_row_cache
"""
from __future__ import annotations

import datetime
import json
import logging
import os

from pipeline.change_detection import build_group_identity
from pipeline.config import (
    OUTPUT_FOLDER,
    _RE_SANITIZE_HELPER_NAME,
)
from pipeline.observability import (
    _ALWAYS_GARBAGE_PATTERNS,
    _GARBAGE_PATTERNS,
    _redact_exception_message,
)

logger = logging.getLogger(__name__)


# Phase 1.1 SUB-12 / D-17 / D-19: idempotent hash-history prune
# version. The constant IS the kill switch — advance to trigger a
# one-time prune of subcontractor primary orphan entries (the
# pre-Bug-B1 partitioning leftovers); leave at the current value to
# skip the prune. Mirrors the DISCOVERY_CACHE_VERSION pattern above.
# Persisted into ``hash_history.json`` under the
# ``_phase_prune_version`` sentinel key (the extended
# ``load_hash_history`` filter preserves underscore-prefixed sentinels
# and the hardened ``save_hash_history`` retention sort tolerates the
# int-valued sentinel — see the helpers below).
PHASE_1_1_HASH_PRUNE_VERSION = 2
# Subproject B (2026-05-20): one-time hash-history prune version for
# dropping LEGACY blank-identifier `reduced_sub` / `aep_billable`
# orphans left behind when B re-partitions those variants by frozen
# claimer. Separate sentinel (`_subproject_b_prune_version`) from the
# Phase 1.1 prune so the two migrations are independent + auditable.
# Advancing this constant is the kill switch (re-run trigger).
SUBPROJECT_B_HASH_PRUNE_VERSION = 1
# Subproject C (2026-05-21): one-time hash-history prune version for
# dropping LEGACY blank-identifier `vac_crew` orphans left behind when
# C re-partitions vac_crew variants by frozen claimer. Separate sentinel
# (`_vac_crew_prune_version`) from Phase 1.1 and Subproject B so all
# three migrations are independent + auditable.
# Advancing this constant is the kill switch (re-run trigger).
VAC_CREW_HASH_PRUNE_VERSION = 1
# Subproject D (2026-05-25): one-time hash-history prune version for
# dropping LEGACY blank-identifier `primary` orphans left behind when
# D re-partitions the production primary variant by frozen primary
# claimer. Separate sentinel (`_subproject_d_prune_version`) from
# Phase 1.1, Subproject B, and Subproject C so all four migrations are
# independent + auditable. Advancing this constant is the kill switch
# (re-run trigger).
SUBPROJECT_D_HASH_PRUNE_VERSION = 1


BILLING_AUDIT_ROW_CACHE_PATH = os.path.join(
    OUTPUT_FOLDER, "billing_audit_frozen_rows.json"
)
BILLING_AUDIT_ROW_CACHE_MAX_ENTRIES = 200000


_SUBCONTRACTOR_SCOPE_VARIANTS = frozenset({
    'reduced_sub', 'aep_billable',
    'reduced_sub_helper', 'aep_billable_helper',
})


def _build_subcontractor_wr_scope(groups: dict) -> set[str]:
    """Return the set of sanitized WR tokens active as subcontractor in this run.

    Gates on each group's authoritative ``__variant`` field (set at the
    ``group_source_rows`` emission site) — NOT a ``'_REDUCEDSUB'`` key
    substring scan. The variant gate is what distinguishes a subcontractor
    group, so a primary claimer, helper, or vac-crew name (or a pathological
    WR token) that itself contains an all-caps reserved word like
    ``REDUCEDSUB`` / ``AEPBILLABLE`` cannot false-positive into this
    destructive cleanup scope. This mirrors the ``_build_primary_wr_scope``
    consistency fix (Codex PR #223 P1) — variant detection MUST use the
    ``__variant`` field, never a key substring. The prior substring scan also
    silently missed ``_AEPBILLABLE``-only keys (the ``'_REDUCEDSUB'``
    substring is absent there); it happened to produce the correct WR set
    only because every sub WR always emits a ``reduced_sub`` group, so the
    variant gate is both more robust and strictly more complete.

    Shared by ``_run_phase_1_1_hash_prune`` (hash-prune scope) and the
    TARGET ``cleanup_untracked_sheet_attachments`` call site (SUB-09
    helper-dimension cleanup scope). A single implementation prevents the
    scope-build drift that the [2026-05-15 12:00] three-site invariant
    warns against.
    """
    _scope: set[str] = set()
    for _g_rows in groups.values():
        if not _g_rows:
            continue
        if _g_rows[0].get('__variant') in _SUBCONTRACTOR_SCOPE_VARIANTS:
            _g_wr_raw = _g_rows[0].get('Work Request #', '')
            _g_wr = str(_g_wr_raw).split('.')[0]
            _g_wr = _RE_SANITIZE_HELPER_NAME.sub('_', _g_wr)[:50]
            if _g_wr:
                _scope.add(_g_wr)
    return _scope


def _build_vac_crew_wr_scope(groups: dict) -> set[str]:
    """Return the set of sanitized WR tokens active as vac_crew in this run.

    Gates on each group's authoritative ``__variant`` field (``== 'vac_crew'``,
    set at the ``group_source_rows`` emission site) — NOT a ``'_VACCREW'`` key
    substring scan. The variant gate prevents a non-vac group whose
    claimer/helper name is the all-caps reserved token ``VACCREW`` (key
    ``..._HELPER_VACCREW``) from false-positiving into this destructive
    cleanup scope. Mirrors the ``_build_primary_wr_scope`` /
    ``_build_subcontractor_wr_scope`` consistency fix (Codex PR #223 P1):
    variant detection MUST use the ``__variant`` field, never a key substring.

    Shared by the TARGET ``cleanup_untracked_sheet_attachments`` call site
    (Task 6 vac-crew legacy cleanup scope).  A single implementation prevents
    scope-build drift — mirrors ``_build_subcontractor_wr_scope``.
    """
    _scope: set[str] = set()
    for _g_rows in groups.values():
        if not _g_rows:
            continue
        if _g_rows[0].get('__variant') == 'vac_crew':
            _g_wr_raw = _g_rows[0].get('Work Request #', '')
            _g_wr = str(_g_wr_raw).split('.')[0]
            _g_wr = _RE_SANITIZE_HELPER_NAME.sub('_', _g_wr)[:50]
            if _g_wr:
                _scope.add(_g_wr)
    return _scope


def _build_primary_wr_scope(groups: dict) -> set[str]:
    """Return the set of sanitized WR tokens that have a partitioned
    production-primary ``_USER_`` group in this run (Subproject D).

    A group qualifies iff its authoritative ``__variant`` field (set at
    emission) is ``'primary'`` AND its key carries the ``_USER_`` partition
    token. The ``__variant`` gate — NOT a key substring scan — is what
    excludes helper / vac_crew / subcontractor groups, so a claimer,
    helper, or vac-crew name (or a pathological WR token) that itself
    contains a reserved word cannot false-positive into D's scope (Codex
    PR #223 P1). For example a helper literally named "USER" produces a
    key ``..._HELPER_USER_...`` whose ``_USER_`` substring the prior
    implementation mis-bucketed as a primary group; the ``__variant ==
    'primary'`` gate now rejects it. Conversely a genuine primary claimer
    named "ReducedSub"/"AEPBillable" (key ``..._USER_ReducedSub``) is
    correctly INCLUDED, whereas the prior ``'_REDUCEDSUB' not in _key``
    substring exclusion wrongly dropped it. The ``'_USER_' in _key`` clause
    then distinguishes a PARTITIONED primary (Subproject D ``_USER_`` group)
    from a bare primary (OFF mode / legacy ``RES_GROUPING_MODE='primary'``).
    Both call sites gate on ``PRIMARY_CLAIM_ATTRIBUTION_ENABLED``, so in
    production ``'both'`` mode every primary group is the partitioned form.

    Shared by ``_run_subproject_d_hash_prune`` (hash-prune scope) and the
    TARGET ``cleanup_untracked_sheet_attachments`` call site (bare-primary
    migration scope). A single implementation prevents the scope-build
    drift that the [2026-05-15 12:00] three-site invariant warns against.
    """
    _scope: set[str] = set()
    for _key, _g_rows in groups.items():
        if not _g_rows:
            continue
        if _g_rows[0].get('__variant') == 'primary' and '_USER_' in _key:
            _g_wr_raw = _g_rows[0].get('Work Request #', '')
            _g_wr = str(_g_wr_raw).split('.')[0]
            _g_wr = _RE_SANITIZE_HELPER_NAME.sub('_', _g_wr)[:50]
            if _g_wr:
                _scope.add(_g_wr)
    return _scope


def _run_phase_1_1_hash_prune(hash_history: dict, groups: dict) -> bool:
    """Phase 1.1 SUB-12 / D-17..D-19: idempotent hash-history prune.

    Version 1 (Plan 01.1-05): After Bug B1 (Plan 01.1-02) stops emitting
    legacy primary group keys for subcontractor rows, drops subcontractor
    primary orphans (4-part keys: ``wr|week|primary|``).

    Version 2 (Plan 01.1-06 UAT gap closure): ALSO drops subcontractor
    legacy ``'helper'`` orphans (6-part keys: ``wr|week|helper|foreman|
    dept|job``) left behind after Task 1 stops emitting the legacy
    ``_HELPER_<name>`` key for subcontractor helper rows. Version 2 is a
    superset of version 1 — the primary-orphan drop is preserved.

    This helper:

      1. Reads the persisted ``_phase_prune_version`` sentinel (or 0
         if absent) from ``hash_history``.
      2. If the persisted version is already at or beyond
         ``PHASE_1_1_HASH_PRUNE_VERSION``, restores the sentinel and
         returns — no-op.
      3. Otherwise, delegates scope-building to
         ``_build_subcontractor_wr_scope(groups)`` (shared with the
         TARGET cleanup call site — single implementation, no drift).
      4. Walks ``hash_history.keys()`` and identifies orphan entries
         using a length-tolerant guard (``< 4``) and index access.
         Primary orphans: 4-part keys with ``variant == 'primary'``
         and blank identifier. Helper orphans: any-part-count keys
         with ``variant == 'helper'`` and ``wr in scope``.
      5. Drops those entries in place, persists the new sentinel
         value, and logs ONE INFO line naming the count + affected
         WR sample (per RESEARCH.md §HP Code Example §6).

    CRITICAL — helper-variant hash keys are SIX pipe-parts, NOT four:
    ``wr|week|helper|foreman|dept|job``. The former ``!= 4`` guard
    hard-skipped every helper key (false-clean "no orphans" log) AND
    the 4-element destructure would raise ``ValueError`` on a 6-element
    list. Both are replaced by the ``< 4`` guard + index access pattern.

    Mutates ``hash_history`` in place. The constant
    ``PHASE_1_1_HASH_PRUNE_VERSION`` IS the kill switch (D-19) —
    advance to trigger; leave to skip. Per [2026-04-25 12:00] rule 1:
    idempotent migrations; version advance is the trigger.
    """
    _persisted_prune_version = hash_history.pop('_phase_prune_version', 0)
    if (
        isinstance(_persisted_prune_version, int)
        and _persisted_prune_version >= PHASE_1_1_HASH_PRUNE_VERSION
    ):
        # Re-store the sentinel so ``save_hash_history`` persists it
        # (defensive — the ``.pop`` above removed it). No log because
        # the prune already ran on a prior session and the absence
        # of a log line is the "already migrated" signal.
        hash_history['_phase_prune_version'] = _persisted_prune_version
        # Codex P2: no mutation beyond the no-op sentinel restore — the
        # caller need not force a save on a no-update run.
        return False

    # Build the WR-token set from this run's groups via shared helper
    # (simplified D-18). Shared with TARGET cleanup call site so the
    # two scopes are guaranteed identical (T-01.1-06-05 mitigation).
    _sub_wr_scope: set[str] = _build_subcontractor_wr_scope(groups)

    # Walk hash_history, identify subcontractor primary AND helper orphans.
    _orphans_to_drop: list[str] = []
    for _hk in list(hash_history.keys()):
        if isinstance(_hk, str) and _hk.startswith('_'):
            continue  # sentinel keys — skip
        _parts = str(_hk).split('|')
        # Helper-variant keys are 6 parts (wr|week|helper|foreman|dept|job);
        # primary keys are 4 (wr|week|primary|''). Accept BOTH — the former
        # ``!= 4`` guard hard-skipped every helper key, producing a false-
        # clean "no orphans" log. Sentinel keys (startswith '_') already
        # skipped above.
        if len(_parts) < 4:
            continue
        # Index access (NOT a 4-element destructure) so a 6-part helper
        # key does not raise ValueError. Only positions 0 and 2 are needed
        # for the orphan classification.
        _hk_wr = _parts[0]
        _hk_variant = _parts[2]
        # Version 1: subcontractor primary orphans (variant=='primary',
        #   blank identifier — EXACTLY 4 parts). Version 2 (Phase 1.1 UAT
        #   gap closure): ALSO subcontractor legacy helper orphans
        #   (variant=='helper', 6 parts, any foreman/dept/job) left behind
        #   after Task 1 stops emitting the legacy `_HELPER_<name>` key for
        #   subcontractor rows. Both are pre-fix leftovers in
        #   hash_history.json on existing deployments.
        # IN-01 (review follow-up): the ``_hk_variant == 'helper'`` clause
        # intentionally matches a 'helper' key at ANY part count, not just
        # the documented 6-part production shape. Real production helper
        # keys ARE 6-part — ``history_key = f"{wr}|{week}|{variant}|
        # {identifier}"`` with ``identifier = f"{foreman}|{dept}|{job}"``
        # for the helper variant — but the broad match is a deliberately
        # safe superset for TWO reasons: (1) the version sentinel makes this
        # prune one-time, and (2) the prune only DROPS a hash-history entry,
        # forcing at most one benign regeneration on the next run — it never
        # deletes a file. So even the WR-01 cross-sheet-overlap case (a live
        # non-sub helper key for a WR that also has sub rows) is benign here:
        # the file regenerates once. This is unlike the every-run TARGET
        # ``cleanup_untracked_sheet_attachments`` gate, which DOES delete and
        # therefore carries the ``ident not in valid_wr_weeks`` exemption.
        if _hk_wr in _sub_wr_scope and (
            (len(_parts) == 4 and _hk_variant == 'primary' and _parts[3] == '')
            or _hk_variant == 'helper'
        ):
            _orphans_to_drop.append(_hk)

    for _hk in _orphans_to_drop:
        del hash_history[_hk]

    # Persist the new sentinel.
    hash_history['_phase_prune_version'] = PHASE_1_1_HASH_PRUNE_VERSION

    # ONE INFO log — PII marker "Phase 1.1 hash-history prune" already
    # registered in ``_PII_LOG_MARKERS``. Limit the affected-WR list
    # to the first 20 entries to keep the log line bounded; full count
    # still surfaces.
    if _orphans_to_drop:
        _wr_sample = sorted(_sub_wr_scope)[:20]
        _wr_suffix = (
            '' if len(_sub_wr_scope) <= 20
            else f' (+ {len(_sub_wr_scope) - 20} more)'
        )
        logging.info(
            f"🧹 Phase 1.1 hash-history prune "
            f"(version {_persisted_prune_version} → "
            f"{PHASE_1_1_HASH_PRUNE_VERSION}): "
            f"dropped {len(_orphans_to_drop)} subcontractor "
            f"primary/legacy-helper orphan(s) affecting "
            f"{len(_sub_wr_scope)} WR(s). "
            f"Affected WRs (first 20): {_wr_sample}{_wr_suffix}"
        )
    else:
        logging.info(
            f"🧹 Phase 1.1 hash-history prune "
            f"(version {_persisted_prune_version} → "
            f"{PHASE_1_1_HASH_PRUNE_VERSION}): "
            f"no primary/legacy-helper orphans to drop."
        )
    # Codex P2: the body path advanced the sentinel (and may have dropped
    # orphans) — report the mutation so the caller persists hash_history even
    # on a run with no group updates (where the history_updates-gated save is
    # skipped). Without this the migration re-runs every no-update execution.
    return True


def _run_subproject_b_hash_prune(hash_history: dict, groups: dict) -> bool:
    """Subproject B (2026-05-20): idempotent one-time hash-history prune.

    Drops LEGACY blank-identifier subcontractor primary orphans —
    4-part keys ``wr|week|reduced_sub|`` and ``wr|week|aep_billable|``
    with an EMPTY identifier — for WRs that are subcontractor in this
    run. B re-partitions those variants by frozen claimer (new keys
    carry a non-empty identifier), so the blank-identifier entries are
    obsolete. The normal stale-prune at the end of the run would clear
    them eventually; this makes the migration deterministic on the first
    run and survives interrupted / no-update runs.

    Scope-building delegates to ``_build_subcontractor_wr_scope`` (shared
    with the cleanup call site — no drift, per the [2026-05-15 12:00]
    three-site invariant). Sentinel key ``_subproject_b_prune_version``
    is distinct from the Phase 1.1 ``_phase_prune_version`` so the two
    migrations are independent. Mutates ``hash_history`` in place.
    Dropping a hash entry costs at most one benign regeneration — never
    data loss — so no live-identity exemption is needed on this drop
    path (unlike the every-run attachment cleanup).
    """
    _persisted = hash_history.pop('_subproject_b_prune_version', 0)
    if (
        isinstance(_persisted, int)
        and _persisted >= SUBPROJECT_B_HASH_PRUNE_VERSION
    ):
        hash_history['_subproject_b_prune_version'] = _persisted
        # Codex P2: no-op sentinel restore only — no save needed.
        return False

    _scope = _build_subcontractor_wr_scope(groups)
    _orphans: list[str] = []
    for _hk in list(hash_history.keys()):
        if isinstance(_hk, str) and _hk.startswith('_'):
            continue
        _parts = str(_hk).split('|')
        if len(_parts) != 4:
            continue
        _hk_wr, _hk_week, _hk_variant, _hk_ident = _parts
        if (
            _hk_wr in _scope
            and _hk_variant in ('reduced_sub', 'aep_billable')
            and _hk_ident == ''
        ):
            _orphans.append(_hk)
    for _ok in _orphans:
        del hash_history[_ok]
    hash_history['_subproject_b_prune_version'] = SUBPROJECT_B_HASH_PRUNE_VERSION
    if _orphans:
        _wr_sample = sorted({k.split('|')[0] for k in _orphans})[:20]
        logging.info(
            f"🧹 Subproject B hash-history prune: dropped {len(_orphans)} "
            f"legacy unpartitioned reduced_sub/aep_billable orphan(s) "
            f"(affected WRs first 20: {_wr_sample})"
        )
    else:
        logging.info(
            "🧹 Subproject B hash-history prune: no legacy unpartitioned "
            "reduced_sub/aep_billable orphans to drop"
        )
    # Codex P2: body path advanced the sentinel (and may have dropped
    # orphans) — report the mutation so the caller persists it even on a
    # no-update run.
    return True


def _run_vac_crew_hash_prune(hash_history: dict, groups: dict) -> bool:
    """Subproject C (2026-05-21): idempotent one-time hash-history prune.

    Drops LEGACY blank-identifier vac_crew orphans — 4-part keys
    ``wr|week|vac_crew|`` with an EMPTY identifier — for WRs that are
    vac_crew in this run. C re-partitions vac_crew variants by frozen
    claimer (new keys carry a non-empty identifier), so the
    blank-identifier entries are obsolete. The normal stale-prune at the
    end of the run would clear them eventually; this makes the migration
    deterministic on the first run and survives interrupted / no-update
    runs.

    Scope-building delegates to ``_build_vac_crew_wr_scope`` (shared
    with the cleanup call site — no drift, per the [2026-05-15 12:00]
    three-site invariant). Sentinel key ``_vac_crew_prune_version`` is
    DISTINCT from ``_phase_prune_version`` (Phase 1.1) and
    ``_subproject_b_prune_version`` (Subproject B) so the three
    migrations are independent. Mutates ``hash_history`` in place.
    Dropping a hash entry costs at most one benign regeneration — never
    data loss — so no live-identity exemption is needed on this drop
    path (unlike the every-run attachment cleanup).

    Codex P2 (PR #219): when ``VAC_CREW_CLAIM_ATTRIBUTION_ENABLED`` is OFF,
    the blank-identifier ``wr|week|vac_crew|`` key is the ACTIVE legacy
    format (the kill-switch-OFF path emits the bare ``_VACCREW`` key), so
    pruning it would delete valid current history and force regeneration
    churn — breaking the exact-legacy contract. Skip entirely when the flag
    is off, and do NOT advance the sentinel, so the one-time migration still
    runs if attribution is later enabled.
    """
    # Phase 09 W5 (behaviour-preserving relocation): bind the
    # test-mutable / facade-resident constant(s) from the
    # generate_weekly_pdfs facade so test-time rebinds on
    # generate_weekly_pdfs.NAME are honoured (production value is
    # identical -- the facade re-exports pipeline.config).
    import generate_weekly_pdfs as _gwp  # noqa: PLC0415
    VAC_CREW_CLAIM_ATTRIBUTION_ENABLED = _gwp.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED
    if not VAC_CREW_CLAIM_ATTRIBUTION_ENABLED:
        return False
    _persisted = hash_history.pop('_vac_crew_prune_version', 0)
    if (
        isinstance(_persisted, int)
        and _persisted >= VAC_CREW_HASH_PRUNE_VERSION
    ):
        hash_history['_vac_crew_prune_version'] = _persisted
        # Codex P2: no-op sentinel restore only — no save needed.
        return False

    _scope = _build_vac_crew_wr_scope(groups)
    _orphans: list[str] = []
    for _hk in list(hash_history.keys()):
        if isinstance(_hk, str) and _hk.startswith('_'):
            continue
        _parts = str(_hk).split('|')
        if len(_parts) != 4:
            continue
        _hk_wr, _hk_week, _hk_variant, _hk_ident = _parts
        if (
            _hk_wr in _scope
            and _hk_variant == 'vac_crew'
            and _hk_ident == ''
        ):
            _orphans.append(_hk)
    for _ok in _orphans:
        del hash_history[_ok]
    hash_history['_vac_crew_prune_version'] = VAC_CREW_HASH_PRUNE_VERSION
    if _orphans:
        _wr_sample = sorted({k.split('|')[0] for k in _orphans})[:20]
        logging.info(
            f"🧹 Vac crew hash-history prune: dropped {len(_orphans)} legacy "
            f"unpartitioned vac_crew orphan(s) "
            f"(WRs first 20: {_wr_sample})"
        )
    else:
        logging.info(
            "🧹 Vac crew hash-history prune: no legacy vac_crew orphans to drop"
        )
    # Body path advanced the sentinel (and may have dropped orphans) —
    # report the mutation so the caller persists it even on a no-update run.
    return True


def _run_subproject_d_hash_prune(hash_history: dict, groups: dict) -> bool:
    """Subproject D (2026-05-25): idempotent one-time hash-history prune.

    Drops LEGACY blank-identifier production-primary orphans — 4-part keys
    ``wr|week|primary|`` with an EMPTY identifier — for WRs that have a
    partitioned ``_USER_`` primary group in this run. D re-partitions the
    production primary variant by frozen claimer (new keys carry a
    non-empty identifier), so the blank-identifier entries are obsolete.
    The normal stale-prune at the end of the run would clear them
    eventually; this makes the migration deterministic on the first run
    and survives interrupted / no-update runs.

    Scope-building delegates to ``_build_primary_wr_scope`` (shared with
    the TARGET cleanup call site — no drift, per the [2026-05-15 12:00]
    three-site invariant). Sentinel key ``_subproject_d_prune_version`` is
    DISTINCT from the Phase 1.1 / Subproject B / Subproject C sentinels so
    all four migrations are independent. Mutates ``hash_history`` in place.
    Dropping a hash entry costs at most one benign regeneration — never
    data loss — so no live-identity exemption is needed on this drop path
    (unlike the every-run attachment cleanup).

    GATED on ``PRIMARY_CLAIM_ATTRIBUTION_ENABLED``: when OFF, the
    blank-identifier ``wr|week|primary|`` key is the ACTIVE legacy format
    (the kill-switch-OFF path emits the bare primary key), so pruning it
    would delete valid current history and force regeneration churn —
    breaking the exact-legacy contract. Skip entirely when the flag is
    off, and do NOT advance the sentinel, so the one-time migration still
    runs if attribution is later enabled. (Mirrors the Subproject C
    ``_run_vac_crew_hash_prune`` kill-switch guard.)
    """
    # Phase 09 W5 (behaviour-preserving relocation): bind the
    # test-mutable / facade-resident constant(s) from the
    # generate_weekly_pdfs facade so test-time rebinds on
    # generate_weekly_pdfs.NAME are honoured (production value is
    # identical -- the facade re-exports pipeline.config).
    import generate_weekly_pdfs as _gwp  # noqa: PLC0415
    PRIMARY_CLAIM_ATTRIBUTION_ENABLED = _gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED
    if not PRIMARY_CLAIM_ATTRIBUTION_ENABLED:
        return False
    _persisted = hash_history.pop('_subproject_d_prune_version', 0)
    if (
        isinstance(_persisted, int)
        and _persisted >= SUBPROJECT_D_HASH_PRUNE_VERSION
    ):
        hash_history['_subproject_d_prune_version'] = _persisted
        return False

    _scope = _build_primary_wr_scope(groups)
    _orphans: list[str] = []
    for _hk in list(hash_history.keys()):
        if isinstance(_hk, str) and _hk.startswith('_'):
            continue
        _parts = str(_hk).split('|')
        if len(_parts) != 4:
            continue
        _hk_wr, _hk_week, _hk_variant, _hk_ident = _parts
        if (
            _hk_wr in _scope
            and _hk_variant == 'primary'
            and _hk_ident == ''
        ):
            _orphans.append(_hk)
    for _ok in _orphans:
        del hash_history[_ok]
    hash_history['_subproject_d_prune_version'] = SUBPROJECT_D_HASH_PRUNE_VERSION
    if _orphans:
        _wr_sample = sorted({k.split('|')[0] for k in _orphans})[:20]
        logging.info(
            f"🧹 Subproject D hash-history prune: dropped {len(_orphans)} "
            f"legacy unpartitioned primary orphan(s) "
            f"(affected WRs first 20: {_wr_sample})"
        )
    else:
        logging.info(
            "🧹 Subproject D hash-history prune: no legacy unpartitioned "
            "primary orphans to drop"
        )
    # Body path advanced the sentinel (and may have dropped orphans) —
    # report the mutation so the caller persists it even on a no-update run.
    return True


def run_claimer_remediation(
    client,
    dry_run: bool,
    window_weeks: int,
    valid_wr_weeks: 'set | None' = None,
) -> None:
    """Sweep TARGET_SHEET_ID and SUBCONTRACTOR_PPP_SHEET_ID for garbage claimer
    attachments (``*_NO_MATCH*`` / ``*_Unknown_Foreman*``) and delete them.

    Phase 2 Plan 03 — D-06/D-07/D-08/D-12/D-14.

    Parameters
    ----------
    client:
        Initialized ``smartsheet.Smartsheet`` client.
    dry_run:
        When True, report counts only — no attachment is deleted.
        Matches ``REMEDIATION_DRY_RUN`` default (``'1'``).
    window_weeks:
        Sweep only attachments whose week-ending date is within the last N
        weeks of today (``0`` = unbounded).  Matches
        ``REMEDIATION_WINDOW_WEEKS`` default (``26``).
    valid_wr_weeks:
        A set of ``(wr, week_mmddyy, variant, identifier)`` 4-tuples
        representing the current run's live attachments.  When provided,
        a garbage-named file whose parsed 4-tuple IS in this set is
        EXEMPTED from deletion (live-identity exemption per
        [2026-05-19 23:45]).  Pass ``None`` for the isolated-mode path
        where no live-identity set is available — deletion is then gated
        solely on the name-pattern and window filter (WR-04: only the
        always-garbage ``_NO_MATCH`` token is swept; ``_Unknown_Foreman``
        is preserved because it is a legitimate current sentinel and there
        is no live-identity set to protect it in the isolated path).
    """
    # Phase 09 W5 (behaviour-preserving relocation): bind the
    # test-mutable / facade-resident constant(s) from the
    # generate_weekly_pdfs facade so test-time rebinds on
    # generate_weekly_pdfs.NAME are honoured (production value is
    # identical -- the facade re-exports pipeline.config).
    import generate_weekly_pdfs as _gwp  # noqa: PLC0415
    TARGET_SHEET_ID = _gwp.TARGET_SHEET_ID
    SUBCONTRACTOR_PPP_SHEET_ID = _gwp.SUBCONTRACTOR_PPP_SHEET_ID
    # IN-04: use the module-level datetime (not a shadowing local import).
    _today = datetime.date.today()
    _cutoff = (
        _today - datetime.timedelta(weeks=window_weeks)
        if window_weeks > 0
        else None
    )

    # WR-04: select the active garbage-pattern set based on whether the
    # live-identity exemption is available.  When valid_wr_weeks is None
    # (isolated path), restrict to _ALWAYS_GARBAGE_PATTERNS so a current
    # _Unknown_Foreman billing artifact is never deleted.
    _patterns = _GARBAGE_PATTERNS if valid_wr_weeks is not None else _ALWAYS_GARBAGE_PATTERNS

    # Determine which sheets to sweep.
    _sheet_ids: list[int] = [TARGET_SHEET_ID]
    if SUBCONTRACTOR_PPP_SHEET_ID:
        _sheet_ids.append(SUBCONTRACTOR_PPP_SHEET_ID)

    _total_scanned = 0
    _total_garbage = 0
    _total_deleted = 0
    _total_exempted = 0
    _total_out_of_window = 0

    for _sheet_id in _sheet_ids:
        try:
            _sheet = client.Sheets.get_sheet(_sheet_id)
        except Exception as _e:
            logging.warning(
                f"⚠️ run_claimer_remediation: failed to fetch sheet "
                f"{_sheet_id}: {_redact_exception_message(_e)}"
            )
            continue

        for _row in _sheet.rows:
            try:
                _row_resp = client.Attachments.list_row_attachments(
                    _sheet_id, _row.id
                )
            except Exception as _e:
                logging.warning(
                    f"⚠️ run_claimer_remediation: failed to list attachments "
                    f"for row {_row.id} on sheet {_sheet_id}: "
                    f"{_redact_exception_message(_e)}"
                )
                continue

            _attachments = getattr(_row_resp, 'attachments', None) or []
            for _att in _attachments:
                _name: str = getattr(_att, 'name', '') or ''
                _att_id = _att.id
                _total_scanned += 1

                # ── Step 1: parse filename with the battle-hardened parser ──
                # Files that build_group_identity cannot parse (non-WR filenames,
                # malformed names) are left alone — never deleted.
                _identity = build_group_identity(_name)
                if _identity is None:
                    continue  # unparseable → skip

                _wr, _week_mmddyy, _variant, _identifier = _identity

                # ── Step 2: garbage-pattern check (IN-02: runs BEFORE window) ──
                # Check the active pattern set (WR-04: _ALWAYS_GARBAGE_PATTERNS in
                # the isolated path, _GARBAGE_PATTERNS when the live-identity
                # exemption is available).  Clean real-claimer files never reach
                # the window filter, so out_of_window counts only GARBAGE files
                # that are too old — unambiguous blast-radius metric.
                _is_garbage = any(pat in _name for pat in _patterns)
                if not _is_garbage:
                    continue  # clean real-claimer name → skip

                # ── Step 3: window filter (runs only for garbage files) ──
                # Convert the MMDDYY week token to a date for comparison.
                if _cutoff is not None:
                    try:
                        _week_date = datetime.datetime.strptime(
                            _week_mmddyy, '%m%d%y'
                        ).date()
                        if _week_date < _cutoff:
                            _total_out_of_window += 1
                            continue  # too old — skip
                    except (ValueError, TypeError):
                        # Unparseable week token → conservatively skip
                        continue

                _total_garbage += 1

                # ── Step 4: live-identity exemption ──
                if valid_wr_weeks is not None and _identity in valid_wr_weeks:
                    _total_exempted += 1
                    logging.debug(
                        f"run_claimer_remediation: EXEMPT (live identity) "
                        f"att={_att_id} sheet={_sheet_id} "
                        f"wr={_wr} week={_week_mmddyy} variant={_variant}"
                    )
                    continue

                # ── Step 5: dry-run or execute ──
                if dry_run:
                    logging.info(
                        f"🔍 [DRY-RUN] would delete garbage attachment "
                        f"att={_att_id} sheet={_sheet_id} "
                        f"wr={_wr} week={_week_mmddyy} variant={_variant}"
                    )
                else:
                    try:
                        client.Attachments.delete_attachment(_sheet_id, _att_id)
                        _total_deleted += 1
                        logging.info(
                            f"🗑️ run_claimer_remediation: deleted garbage att "
                            f"att={_att_id} sheet={_sheet_id} "
                            f"wr={_wr} week={_week_mmddyy} variant={_variant}"
                        )
                    except Exception as _del_e:
                        logging.warning(
                            f"⚠️ run_claimer_remediation: failed to delete "
                            f"att={_att_id} sheet={_sheet_id}: "
                            f"{_redact_exception_message(_del_e)}"
                        )

    # ── PII-safe aggregate summary (ASVS V7: counts + sanitized IDs only) ──
    _mode = "DRY-RUN" if dry_run else "EXECUTE"
    logging.info(
        f"✅ run_claimer_remediation [{_mode}] complete: "
        f"scanned={_total_scanned} garbage={_total_garbage} "
        f"deleted={_total_deleted} exempted={_total_exempted} "
        f"out_of_window={_total_out_of_window}"
    )


def load_billing_audit_row_cache(path: str) -> set[str]:
    """Load cached freeze-attribution row keys.

    Keys are ``{wr_sanitized}|{week_mmddyy}|{row_id}``. This local cache
    is best-effort only — if missing/corrupt we simply fall back to
    normal freeze-row behavior.
    """
    try:
        with open(path, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {str(x) for x in data if x is not None}
        if isinstance(data, dict):
            # Backward-compatible shape if we later add metadata.
            rows = data.get("rows", [])
            if isinstance(rows, list):
                return {str(x) for x in rows if x is not None}
        logging.warning("⚠️ Billing-audit row cache malformed; resetting")
        return set()
    except FileNotFoundError:
        return set()
    except Exception as e:
        logging.warning(f"⚠️ Failed to load billing-audit row cache: {e}")
        return set()


def save_billing_audit_row_cache(path: str, rows: set[str]) -> None:
    """Persist cached freeze-attribution row keys."""
    # Phase 09 W5 (behaviour-preserving relocation): bind the
    # test-mutable / facade-resident constant(s) from the
    # generate_weekly_pdfs facade so test-time rebinds on
    # generate_weekly_pdfs.NAME are honoured (production value is
    # identical -- the facade re-exports pipeline.config).
    import generate_weekly_pdfs as _gwp  # noqa: PLC0415
    BILLING_AUDIT_ROW_CACHE_MAX_ENTRIES = _gwp.BILLING_AUDIT_ROW_CACHE_MAX_ENTRIES
    try:
        # Always sort set-backed cache entries so serialized output is
        # deterministic across runs; also produces smaller diffs.
        values = sorted(rows)
        if len(values) > BILLING_AUDIT_ROW_CACHE_MAX_ENTRIES:
            # Deterministic truncation. Cache is opportunistic; precision
            # is not required as fallback is to re-call freeze_row.
            values = values[-BILLING_AUDIT_ROW_CACHE_MAX_ENTRIES:]
            retained = len(values)
            logging.info(
                f"🧹 Pruned billing-audit row cache to {retained} entries"
            )
        tmp_path = path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(values, f, separators=(",", ":"))
        os.replace(tmp_path, path)
        logging.info(f"📝 Billing-audit row cache saved ({len(values)} entries)")
    except Exception as e:
        logging.warning(f"⚠️ Failed to save billing-audit row cache: {e}")
