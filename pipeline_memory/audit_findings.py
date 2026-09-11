"""Audit-memory write path for ``audit_billing_changes.py`` findings.

Fail-open contract: no function in this module ever raises. A failure
here means "this finding was not written to audit memory this run" --
it must NEVER be interpreted by a caller (or by a human reading
``pipeline_memory.audit_finding`` later) as evidence that a finding was
fixed. A write failure is silence, not a signal.

Logging discipline: mirrors ``pipeline_memory/writer.py`` -- this module
logs COUNTS and ERROR CODES ONLY. No WR, CU, price, or personnel name is
ever logged at any level; the summary breadcrumb on a successful RPC
call carries only integers.

Scope (Phase 13, plan 13-01, AUD-01 vertical slice): ``build_finding_payloads``
implements the ``rate_sanity_mismatch`` branch only. ``price_variance_anomaly``
and ``data_consistency_issue`` are declared in ``MEMORY_BACKED_CHECKS`` /
``IDENTITY_RECIPES`` (D-01) but have no payload-building branch yet -- a
finding of either type is skipped and counted, never raised on, never
given a placeholder key. Those branches are finished in plan 13-03.

Finding-key recipe (D-01, owner-confirmed 2026-09-11, verbatim answer
recorded in this plan's SUMMARY): the canonical hash input is a
``|``-joined string whose FIRST segment is ``FINDING_KEY_RECIPE_VERSION``
(``'v1'``), followed by ``check_id``, followed by that check's identity
values in the fixed ``IDENTITY_RECIPES`` order, each value normalized by
``str(...).strip()`` with ``None``/missing rendered as the empty string
and ``week_ending`` rendered as ISO ``YYYY-MM-DD`` or the empty string
when ``None``. ``finding_key = sha256(canonical).hexdigest()``. Python
computes ``finding_key``; no SQL statement in ``pipeline_memory/schema.sql``
recomputes or re-derives it (ASVS V6 -- one authoritative hashing side).
"""

from __future__ import annotations

import hashlib
import logging
import threading
from typing import Any, Iterable, Sequence

from pipeline.utils import excel_serial_to_date
from pipeline_memory.client import get_client, with_retry
from pipeline_memory.client import _audit_write_enabled

# ── Recipe constants (D-01) ──────────────────────────────────────────────

FINDING_KEY_RECIPE_VERSION = "v1"

# The three D-03 memory-backed check ids. A finding whose ``type`` is not
# in this set (notably ``recent_discussion``) is skipped silently, with
# no counter bumped -- it was never a candidate for audit memory.
MEMORY_BACKED_CHECKS: frozenset[str] = frozenset({
    "rate_sanity_mismatch",
    "price_variance_anomaly",
    "data_consistency_issue",
})

# Per-check identity field order, verbatim from D-01. Each tuple is the
# ordered list of logical identity fields hashed after ``check_id`` in the
# canonical string. ``data_consistency_issue``'s trailing field is a
# comma-joined sorted list of issue strings, handled specially in
# ``compute_finding_key`` (not a plain scalar).
IDENTITY_RECIPES: dict[str, tuple[str, ...]] = {
    "rate_sanity_mismatch": ("wr", "week_ending", "cu", "work_type"),
    "price_variance_anomaly": ("wr", "week_ending"),
    "data_consistency_issue": ("wr", "week_ending", "issues"),
}

# ── Module-level counters (mirrors pipeline_memory/writer.py) ────────────

_counters_lock = threading.Lock()
_counters: dict[str, int] = {
    "findings_emitted": 0,
    "findings_skipped_no_match": 0,
    "findings_skipped_multi_week": 0,
    "findings_skipped_unimplemented_check": 0,
    "upsert_written": 0,
    "upsert_errored": 0,
}


def _bump_counter(key: str) -> None:
    """Atomically increment ``_counters[key]`` by 1, creating it if new."""
    with _counters_lock:
        _counters[key] = _counters.get(key, 0) + 1


def counters() -> dict[str, int]:
    """Return a snapshot of module counters (for the run-summary log line)."""
    with _counters_lock:
        return dict(_counters)


def reset_counters() -> None:
    """Zero the module counters. Test-only helper."""
    with _counters_lock:
        for k in list(_counters):
            _counters[k] = 0


# ── Key derivation ────────────────────────────────────────────────────────

def _normalize_identity_value(value: Any) -> str:
    """Normalize a single identity value per the D-01 recipe.

    ``None``/missing renders as the empty string; everything else is
    ``str(...).strip()``. ``week_ending`` values are pre-formatted to ISO
    ``YYYY-MM-DD`` (or ``None``) by the caller before reaching this
    function, so this normalizer treats them like any other scalar.
    """
    if value is None:
        return ""
    return str(value).strip()


def compute_finding_key(
    check_id: str, identity_values: Sequence[Any],
) -> str:
    """Return the 64-char lowercase hex ``finding_key`` for one finding.

    Canonical hash input: ``FINDING_KEY_RECIPE_VERSION | check_id |
    <normalized identity values joined by '|'>``. Deterministic across
    processes for the same inputs (no randomness, no locale-dependent
    formatting).
    """
    segments = [FINDING_KEY_RECIPE_VERSION, check_id]
    segments.extend(_normalize_identity_value(v) for v in identity_values)
    canonical = "|".join(segments)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _week_ending_iso(value: Any) -> str | None:
    """Return ISO ``YYYY-MM-DD`` for a parsed date, or ``None``."""
    parsed = excel_serial_to_date(value)
    if parsed is None:
        return None
    return parsed.date().isoformat() if hasattr(parsed, "date") else None


# ── rate_sanity_mismatch payload building ────────────────────────────────

def _resolve_rate_sanity_week_ending(
    finding: dict, rows: Iterable[dict],
) -> str | None:
    """Resolve the single week_ending for a rate_sanity_mismatch finding.

    Matches rows in ``rows`` whose ``Work Request #`` / ``CU`` / ``Work
    Type`` equal the finding's identity fields, then resolves each
    matched row's week via ``pipeline.utils.excel_serial_to_date`` on
    ``Weekly Reference Logged Date``. If the matched rows resolve to
    exactly one distinct week, that week is returned; zero or more than
    one distinct week returns ``None`` and the caller bumps a named
    counter (the general D-CD-01 multi-week rule ships in plan 13-03).

    Never reads ``row['__mem_week_ending']`` -- that stash is only
    populated when ``RUN_MEMORY_WRITE_ENABLED`` is on, which is a
    different, independently-gated flag from this one.
    """
    wr = str(finding.get("work_request") or "").strip()
    cu = str(finding.get("cu") or "").strip()
    work_type = str(finding.get("work_type") or "").strip()

    weeks: set[str] = set()
    matched_any = False
    for row in rows:
        row_wr = str(row.get("Work Request #") or "").strip()
        row_cu = str(row.get("CU") or "").strip()
        row_work_type = str(row.get("Work Type") or "").strip()
        if row_wr != wr or row_cu != cu or row_work_type != work_type:
            continue
        matched_any = True
        iso_week = _week_ending_iso(row.get("Weekly Reference Logged Date"))
        if iso_week is not None:
            weeks.add(iso_week)

    if not matched_any:
        return "__NO_MATCH__"
    if len(weeks) == 1:
        return next(iter(weeks))
    return None


def _build_rate_sanity_payload(
    finding: dict, rows: Sequence[dict],
) -> dict | None:
    """Build one RPC payload dict for a ``rate_sanity_mismatch`` finding.

    Returns ``None`` (and bumps a named counter) when no source row
    matches the finding's ``(wr, cu, work_type)`` identity -- never
    raises.
    """
    wr = str(finding.get("work_request") or "").strip()
    cu = str(finding.get("cu") or "").strip()
    work_type = str(finding.get("work_type") or "").strip()

    week_ending = _resolve_rate_sanity_week_ending(finding, rows)
    if week_ending == "__NO_MATCH__":
        _bump_counter("findings_skipped_no_match")
        return None
    if week_ending is None:
        _bump_counter("findings_skipped_multi_week")

    identity_values = (wr, week_ending, cu, work_type)
    finding_key = compute_finding_key("rate_sanity_mismatch", identity_values)

    evidence = {
        "quantity": finding.get("quantity"),
        "expected_price": finding.get("expected_price"),
        "actual_price": finding.get("actual_price"),
        "delta": finding.get("delta"),
        "description": finding.get("description"),
    }

    return {
        "finding_key": finding_key,
        "recipe_version": FINDING_KEY_RECIPE_VERSION,
        "check_id": "rate_sanity_mismatch",
        "wr": wr,
        "week_ending": week_ending,
        "cu": cu,
        "work_type": work_type,
        "severity": finding.get("severity"),
        "evidence": evidence,
    }


# ── build_finding_payloads ────────────────────────────────────────────────

_AUDIT_RESULT_LIST_KEYS = (
    "anomalies_detected",
    "unauthorized_changes",
    "data_integrity_issues",
    "rate_sanity_mismatches",
)


def build_finding_payloads(
    audit_results: dict | None, rows: Sequence[dict] | None, run_id: str,
) -> list[dict]:
    """Build RPC payload rows for every memory-backed finding.

    Iterates the four finding lists ``audit_financial_data`` returns,
    reading each defensively with ``.get(key) or []`` so a missing or
    ``None`` key is never an error. Dispatches on each finding's
    ``type`` value (not on which list it came from). A ``type`` in
    ``MEMORY_BACKED_CHECKS`` with no branch implemented yet is skipped
    and counted; a ``type`` outside ``MEMORY_BACKED_CHECKS`` is skipped
    silently with no counter. Never raises.
    """
    if not audit_results:
        return []
    rows = rows or []

    payloads: list[dict] = []
    for list_key in _AUDIT_RESULT_LIST_KEYS:
        findings = audit_results.get(list_key) or []
        for finding in findings:
            finding_type = finding.get("type")
            if finding_type not in MEMORY_BACKED_CHECKS:
                continue
            if finding_type == "rate_sanity_mismatch":
                payload = _build_rate_sanity_payload(finding, rows)
                if payload is not None:
                    payloads.append(payload)
                    _bump_counter("findings_emitted")
            else:
                # price_variance_anomaly / data_consistency_issue: not
                # yet implemented (plan 13-03). Skip, never raise, never
                # emit a placeholder key.
                _bump_counter("findings_skipped_unimplemented_check")

    return payloads


# ── upsert_audit_findings ────────────────────────────────────────────────

def upsert_audit_findings(
    run_id: str, findings: Sequence[dict] | None,
    reaudited_pairs: Sequence[dict] | None,
) -> Any:
    """Upsert findings via the ``upsert_audit_findings`` RPC. NEVER raises.

    Follows ``run_ledger_start``'s shape: ``get_client()`` -> ``None``
    guard -> ``_audit_write_enabled()`` guard -> return early when both
    ``findings`` and ``reaudited_pairs`` are empty -> build the params
    dict -> ``with_retry``-wrapped RPC call on the dedicated
    ``audit_finding_upsert`` breaker op -> counter bump on failure/
    success -> return the RPC response data (or ``None``).
    """
    findings = list(findings or [])
    reaudited_pairs = list(reaudited_pairs or [])

    client = get_client()
    if client is None:
        return None
    if not _audit_write_enabled():
        return None
    if not findings and not reaudited_pairs:
        return None

    params = {
        "p_run_id": run_id,
        "p_findings": findings,
        "p_reaudited_pairs": reaudited_pairs,
    }

    def _invoke():
        return (
            client.schema("pipeline_memory")
            .rpc("upsert_audit_findings", params)
            .execute()
        )

    result = with_retry(_invoke, op="audit_finding_upsert")
    if result is None:
        _bump_counter("upsert_errored")
        return None

    _bump_counter("upsert_written")
    logging.info(
        "🧾 Audit-memory upsert: findings_sent=%d reaudited_pairs_sent=%d",
        len(findings), len(reaudited_pairs),
    )
    return getattr(result, "data", None)
