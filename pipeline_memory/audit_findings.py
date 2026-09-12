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

Scope (Phase 13, plan 13-01 + 13-03, AUD-01): ``build_finding_payloads``
implements all three ``MEMORY_BACKED_CHECKS`` branches -- ``rate_sanity_mismatch``
(13-01), ``price_variance_anomaly`` and ``data_consistency_issue`` (13-03).
A finding whose ``type`` is in ``MEMORY_BACKED_CHECKS`` but absent from
``IDENTITY_RECIPES`` (a future check added to one collection but not the
other) is skipped and counted, never raised on, never given a placeholder
key -- see the recipe-coverage check in ``build_finding_payloads`` (D-02).

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
import os
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

# ── Python <-> SQL contract constants (plan 13-04, Task 3) ───────────────
# Declared here (not just as literals inside a test) so there is ONE
# Python-side name to grep, per tests/test_audit_findings_sql_contract.py's
# lockstep assertions against pipeline_memory/schema.sql's
# upsert_audit_findings RPC. Renaming a value here or in schema.sql without
# updating the other fails that test.

# The upsert_audit_findings RPC's positional parameter names, verbatim,
# in the order this module's params dict builds them.
RPC_PARAM_KEYS: tuple[str, ...] = ("p_run_id", "p_findings", "p_reaudited_pairs")

# pipeline_memory.audit_finding.status CHECK value set (schema.sql).
FINDING_STATUS_VALUES: frozenset[str] = frozenset({
    "open", "fixed", "acknowledged", "suppressed", "resurfaced",
})

# pipeline_memory.audit_finding_event.transition CHECK value set
# (schema.sql).
FINDING_EVENT_TRANSITIONS: frozenset[str] = frozenset({
    "opened", "seen", "fixed", "reopened", "resurfaced", "acknowledged",
    "suppressed",
})

# ── Module-level counters (mirrors pipeline_memory/writer.py) ────────────

_counters_lock = threading.Lock()
_counters: dict[str, int] = {
    "findings_emitted": 0,
    "findings_skipped_no_match": 0,
    "findings_skipped_multi_week": 0,
    "findings_skipped_unimplemented_check": 0,
    # D-CD-01: a price_variance_anomaly whose WR-wide row pool resolves
    # to MORE THAN ONE distinct week_ending. Zero distinct weeks also
    # persists week_ending=None but is not "ambiguous" (nothing to
    # disambiguate), so it does not bump this counter.
    "findings_week_ambiguous": 0,
    # A data_consistency_issue whose row_index does not resolve against
    # the rows list passed to build_finding_payloads.
    "findings_skipped_unresolved_row": 0,
    # A finding whose type is in MEMORY_BACKED_CHECKS but absent from
    # IDENTITY_RECIPES (D-02 recipe-coverage gap; see the module test
    # asserting set(IDENTITY_RECIPES) == MEMORY_BACKED_CHECKS).
    "findings_skipped_no_recipe": 0,
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


# ── price_variance_anomaly payload building ──────────────────────────────

def _resolve_price_variance_week_ending(
    finding: dict, rows: Iterable[dict],
) -> str | None:
    """Resolve week_ending for a price_variance_anomaly finding (D-CD-01).

    ``_detect_price_anomalies`` pools ``Units Total Price`` per Work
    Request with NO week filter at all, so this collects the distinct
    weeks of every row in ``rows`` whose Work Request matches the
    finding's ``work_request``. Exactly one distinct non-``None`` week
    means use it. Zero distinct weeks (no matching rows, or matching
    rows with no parseable date) legitimately persists ``None`` without
    bumping any counter -- there is nothing ambiguous about "no data".
    More than one distinct week ALSO persists ``None``, but bumps the
    ``findings_week_ambiguous`` counter so the real production frequency
    of a multi-week pool is observable in shadow (RESEARCH.md Assumption
    A2). A ``None`` week is a legitimate persisted value here, never a
    reason to drop the finding (unlike rate_sanity_mismatch's no-match
    case).
    """
    wr = str(finding.get("work_request") or "").strip()

    weeks: set[str] = set()
    for row in rows:
        row_wr = str(row.get("Work Request #") or "").strip()
        if row_wr != wr:
            continue
        iso_week = _week_ending_iso(row.get("Weekly Reference Logged Date"))
        if iso_week is not None:
            weeks.add(iso_week)

    if len(weeks) == 1:
        return next(iter(weeks))
    if len(weeks) > 1:
        _bump_counter("findings_week_ambiguous")
    return None


def _build_price_variance_payload(
    finding: dict, rows: Sequence[dict],
) -> dict:
    """Build one RPC payload dict for a ``price_variance_anomaly`` finding.

    Never returns ``None`` -- a price_variance_anomaly is never dropped,
    even when ``week_ending`` cannot be resolved (D-CD-01).
    """
    wr = str(finding.get("work_request") or "").strip()
    week_ending = _resolve_price_variance_week_ending(finding, rows)

    identity_values = (wr, week_ending)
    finding_key = compute_finding_key("price_variance_anomaly", identity_values)

    evidence = {
        "price_range": finding.get("price_range"),
        "average_price": finding.get("average_price"),
        "variance_percentage": finding.get("variance_percentage"),
        "description": finding.get("description"),
    }

    return {
        "finding_key": finding_key,
        "recipe_version": FINDING_KEY_RECIPE_VERSION,
        "check_id": "price_variance_anomaly",
        "wr": wr,
        "week_ending": week_ending,
        # _detect_price_anomalies always emits severity="medium" today
        # (audit_billing_changes.py). Stored exactly as emitted, never
        # re-derived here (D-04) -- this module has no risk-ladder logic.
        "severity": finding.get("severity"),
        "evidence": evidence,
    }


# ── data_consistency_issue payload building ──────────────────────────────

# This constant exists ONLY to make a reword of _validate_data_consistency's
# message text a CI failure rather than a silent orphaning of every open
# data_consistency_issue finding (RESEARCH.md Pitfall 2). It mirrors --
# verbatim, character for character -- every string audit_billing_changes.py's
# _validate_data_consistency() can put into a finding's ``issues`` list,
# including the four "Missing {field}" strings its per-field loop builds
# from ['Work Request #', 'Units Total Price', 'Quantity', 'CU']. These
# strings are part of the durable ``data_consistency_issue`` identity
# (D-01 / D-CD-02, sorted-and-joined into the hash input) -- a wording
# change on either side is caught by
# tests/test_audit_findings.py's contract test, which asserts set equality
# in both directions. A DELIBERATE change to any of these strings is a key
# migration requiring a FINDING_KEY_RECIPE_VERSION bump, never a plain edit.
DATA_CONSISTENCY_ISSUE_LITERALS: frozenset[str] = frozenset({
    "Missing Work Request #",
    "Missing Units Total Price",
    "Missing Quantity",
    "Missing CU",
    "Negative price detected",
    "Invalid price format",
    "Zero or negative quantity",
    "Invalid quantity format",
})


def _build_data_consistency_payload(
    finding: dict, rows: Sequence[dict],
) -> dict | None:
    """Build one RPC payload dict for a ``data_consistency_issue`` finding.

    Resolves the source row by the finding's ``row_index`` against the
    same ``rows`` list passed to ``audit_financial_data``. An index
    outside that list is a skip with ``findings_skipped_unresolved_row``
    bumped -- never an exception. ``row_index`` is used ONLY to resolve
    the row for the ``week_ending`` join and to carry provenance in
    ``evidence``; it never enters the hash input (D-01 -- see
    ``compute_finding_key`` call below).

    The identity segment for the issue set is ``_validate_data_consistency``'s
    ``issues`` list, ``sorted()`` and joined by ``,``. Those exact string
    literals are durable identity for this check -- pinned by the
    ``DATA_CONSISTENCY_ISSUE_LITERALS`` contract test (plan 13-03 Task 3).
    Changing any of them in ``audit_billing_changes.py`` is a deliberate
    key migration requiring a ``FINDING_KEY_RECIPE_VERSION`` bump, not a
    cosmetic wording edit (RESEARCH.md Pitfall 2).
    """
    row_index = finding.get("row_index")
    if not isinstance(row_index, int) or isinstance(row_index, bool) or not (
        0 <= row_index < len(rows)
    ):
        _bump_counter("findings_skipped_unresolved_row")
        return None
    row = rows[row_index]

    wr = str(finding.get("work_request") or "").strip()
    week_ending = _week_ending_iso(row.get("Weekly Reference Logged Date"))

    issues = finding.get("issues") or []
    issue_codes = sorted(str(issue) for issue in issues)

    identity_values = (wr, week_ending, ",".join(issue_codes))
    finding_key = compute_finding_key("data_consistency_issue", identity_values)

    evidence = {
        "row_index": row_index,
        "description": finding.get("description"),
    }

    return {
        "finding_key": finding_key,
        "recipe_version": FINDING_KEY_RECIPE_VERSION,
        "check_id": "data_consistency_issue",
        "wr": wr,
        "week_ending": week_ending,
        "issue_codes": issue_codes,
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
    ``type`` value (not on which list it came from):

    - A ``type`` outside ``MEMORY_BACKED_CHECKS`` (notably
      ``recent_discussion``) is skipped silently, no counter -- it was
      never a candidate for audit memory (Pitfall 4). The filter is
      membership in ``MEMORY_BACKED_CHECKS``, never an explicit
      exclusion list, so a future sheet-level check is ignored by
      default too.
    - A ``type`` in ``MEMORY_BACKED_CHECKS`` but absent from
      ``IDENTITY_RECIPES`` is a recipe-coverage gap (D-02): skipped in
      production with ``findings_skipped_no_recipe`` bumped and a
      WARNING naming only the check id (never raised) -- while a
      dedicated test asserts ``set(IDENTITY_RECIPES) ==
      MEMORY_BACKED_CHECKS`` so the gap fails CI before it ever reaches
      a production run.
    - Every other memory-backed type has both a recipe and a
      payload-building branch below.

    Collapse observability (Pitfall 3): findings sharing an identical
    ``finding_key`` (e.g. two ``rate_sanity_mismatch`` rows with the
    same ``(wr, cu, work_type, week_ending)``, which the D-01 recipe
    deliberately cannot disambiguate) collapse to one payload,
    last-write-wins for ``evidence``. The INFO summary line below always
    reports both the number of findings examined and the number of
    distinct keys emitted, so a growing gap is visible rather than
    silently hidden. Never raises.
    """
    if not audit_results:
        return []
    rows = rows or []

    examined = 0
    keyed_payloads: dict[str, dict] = {}
    key_order: list[str] = []
    for list_key in _AUDIT_RESULT_LIST_KEYS:
        findings = audit_results.get(list_key) or []
        for finding in findings:
            finding_type = finding.get("type")
            if finding_type not in MEMORY_BACKED_CHECKS:
                continue
            if finding_type not in IDENTITY_RECIPES:
                logging.warning(
                    "Audit-memory: no identity recipe for check_id=%s",
                    finding_type,
                )
                _bump_counter("findings_skipped_no_recipe")
                continue
            if finding_type == "rate_sanity_mismatch":
                payload = _build_rate_sanity_payload(finding, rows)
            elif finding_type == "price_variance_anomaly":
                payload = _build_price_variance_payload(finding, rows)
            elif finding_type == "data_consistency_issue":
                payload = _build_data_consistency_payload(finding, rows)
            else:
                # Defensive fail-safe only: a check_id was added to both
                # MEMORY_BACKED_CHECKS and IDENTITY_RECIPES but no
                # payload-building branch was wired here. Never reached
                # today -- the recipe-coverage test above keeps the two
                # collections equal, and every entry in IDENTITY_RECIPES
                # has a branch -- but skipped and counted rather than
                # raising, matching every other unresolvable-finding path
                # in this module.
                _bump_counter("findings_skipped_unimplemented_check")
                continue
            if payload is None:
                continue
            examined += 1
            _bump_counter("findings_emitted")
            key = payload["finding_key"]
            if key not in keyed_payloads:
                key_order.append(key)
            keyed_payloads[key] = payload  # last-write-wins on collapse

    payloads = [keyed_payloads[key] for key in key_order]
    if examined:
        logging.info(
            "🔎 Audit-memory findings: examined=%d distinct=%d",
            examined, len(payloads),
        )
    return payloads


# ── executed_checks / build_reaudited_pairs (AUD-02, D-10) ───────────────

def executed_checks() -> frozenset[str]:
    """Return the subset of ``MEMORY_BACKED_CHECKS`` that actually ran
    this run.

    ``price_variance_anomaly`` and ``data_consistency_issue`` always run
    inside ``audit_financial_data`` -- no kill switch gates either one.
    ``rate_sanity_mismatch`` is gated by ``RATE_SANITY_AUDIT_ENABLED``: this
    is a DELIBERATE, read-only mirror of ``_detect_rate_sanity_mismatches``'s
    own gate in ``audit_billing_changes.py`` (same env var, same default
    ``"true"``, same case-insensitive ``!= "true"`` comparison) so the two
    can never silently disagree about whether the check ran. D-02 forbids
    editing ``audit_billing_changes.py`` to expose this as a shared
    constant -- the two literal gates must be changed together BY HAND if
    the check's own gate ever changes (pinned character-for-character by
    ``tests/test_audit_findings.py``).

    Per Pitfall 5 (13-RESEARCH.md): a check that did not run this run must
    never be treated as having "re-audited" any group, or a temporarily
    disabled check's findings would be closed as a side effect of the
    OTHER two checks' groups being re-audited.
    """
    checks = set(MEMORY_BACKED_CHECKS)
    if os.getenv("RATE_SANITY_AUDIT_ENABLED", "true").lower() != "true":
        checks.discard("rate_sanity_mismatch")
    return frozenset(checks)


def build_reaudited_pairs(
    rows: Sequence[dict] | None, executed_checks_: Iterable[str],
) -> list[dict[str, Any]]:
    """Return one ``{check_id, wr, week_ending}`` triple per distinct
    ``(wr, week)`` pair in *rows*, for every check id in
    *executed_checks_* (D-10: "re-audited group" = the set of (wr,
    week_ending) pairs whose rows were in this run's audited row set).

    Never drops a row for an unparseable week -- it still contributes a
    triple with ``week_ending=None`` (serialized as JSON ``null``), so a
    finding persisted with ``week_ending IS NULL`` (D-CD-01's
    price_variance_anomaly pooled-week rule) remains eligible to close.
    ``week_ending`` is serialized as an ISO ``YYYY-MM-DD`` string or
    ``None``.

    Returns ``[]`` for empty *rows* OR an empty *executed_checks_* --
    per AUD-02/Pitfall 5, an unexecuted check can never close a finding,
    so there is nothing to compute for it.

    Deterministic output: sorted by ``check_id``, then ``wr``, then
    ``week_ending`` (``None`` last) -- the RPC's own transition result
    must not depend on this order (it is expressed as a set-based SQL
    join), but a stable payload is cheap to produce and aids debugging.
    """
    rows = rows or []
    executed = list(executed_checks_ or [])
    if not rows or not executed:
        return []

    distinct_pairs: set[tuple[str, str | None]] = set()
    for row in rows:
        wr = str(row.get("Work Request #") or "").strip()
        week_ending = _week_ending_iso(row.get("Weekly Reference Logged Date"))
        distinct_pairs.add((wr, week_ending))

    pairs = [
        {"check_id": check_id, "wr": wr, "week_ending": week_ending}
        for check_id in executed
        for (wr, week_ending) in distinct_pairs
    ]
    pairs.sort(
        key=lambda p: (
            p["check_id"], p["wr"],
            p["week_ending"] is None, p["week_ending"] or "",
        )
    )
    return pairs


# ── summarize_upsert_result ───────────────────────────────────────────────

_SUMMARY_COUNT_KEYS: tuple[str, ...] = (
    "opened", "seen", "fixed", "resurfaced", "reopened",
)


def summarize_upsert_result(rpc_data: Any) -> dict[str, int]:
    """Extract the opened/seen/fixed/resurfaced/reopened summary counts
    from an ``upsert_audit_findings`` RPC response's ``.data`` payload.

    Defensive -- returns all-zero counts for any unexpected shape
    (missing rows, a test double's minimal fake response, etc.). Never
    raises. Counts only, no identifiers -- safe for the INFO log line and
    the Sentry breadcrumb.
    """
    if isinstance(rpc_data, list) and rpc_data and isinstance(rpc_data[0], dict):
        row = rpc_data[0]
        return {k: int(row.get(k) or 0) for k in _SUMMARY_COUNT_KEYS}
    return {k: 0 for k in _SUMMARY_COUNT_KEYS}


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

    # Built from RPC_PARAM_KEYS (never re-typed as literals) so the
    # caller's params dict can never drift from the module constant
    # tests/test_audit_findings_sql_contract.py pins against the DDL.
    params = dict(zip(RPC_PARAM_KEYS, (run_id, findings, reaudited_pairs)))

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
    data = getattr(result, "data", None)
    summary = summarize_upsert_result(data)
    logging.info(
        "🧾 Audit-memory upsert: findings_sent=%d reaudited_pairs_sent=%d "
        "opened=%d seen=%d fixed=%d resurfaced=%d reopened=%d",
        len(findings), len(reaudited_pairs),
        summary["opened"], summary["seen"], summary["fixed"],
        summary["resurfaced"], summary["reopened"],
    )
    return data
