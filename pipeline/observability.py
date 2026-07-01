"""pipeline.observability -- Sentry telemetry and logging helpers.

``init_sentry()`` wraps the module-scope Sentry init block that previously ran
at L1392 of ``generate_weekly_pdfs.py``. The facade body calls it immediately
after importing this module, preserving the EXACT import-time Sentry trigger
the engine had at module scope (D-04). Leaf pipeline modules MUST NOT call it.

Idempotent via ``_SENTRY_INITIALIZED``. The ``before_send_log`` PII sanitizer
(``sentry_before_send_log``) and the redaction helpers move verbatim from the
facade -- they are a defense-in-depth backstop and must not be weakened.

D-04 import-cycle rule: this module imports ONLY stdlib / third-party at module
level. ``pipeline.config`` is imported lazily INSIDE ``init_sentry()`` and
``_set_sentry_session_tags()`` (config is fully loaded before either runs).

Symbols relocated from ``generate_weekly_pdfs.py`` (Phase 09 Wave 1).
"""
from __future__ import annotations

import logging
import os
import sys
import re
from typing import Any, Literal, cast, TYPE_CHECKING

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.threading import ThreadingIntegration
from sentry_sdk.crons import capture_checkin
from sentry_sdk.crons.consts import MonitorStatus

if TYPE_CHECKING:
    from sentry_sdk._types import MonitorConfig

# Idempotency flag + module logger. ``logger`` is bound by ``init_sentry()``
# (None until then); every OTHER pipeline module uses logging.getLogger(__name__).
_SENTRY_INITIALIZED: bool = False
logger: logging.Logger | None = None


SENTRY_DSN = os.getenv("SENTRY_DSN")

# Compiled patterns used to scrub billing-row PII out of exception
# messages before they land in Sentry event context_data. The
# ``before_send_log`` hook further down only sanitizes logging records
# — it does NOT walk ``event['contexts']`` — so any raw ``str(e)``
# passed into ``sentry_capture_with_context(...)``'s context_data
# payload would bypass that defense. Keep these patterns conservative:
# they only strip recognised PII tokens, leaving the rest of the
# exception message intact so operators can still diagnose the root
# cause from the Sentry dashboard.
# Match any ``WR``-prefixed identifier, not just digit-only tokens.
# Earlier ``\d+`` missed alphanumeric WR values (``WR=ABCD-123``) and
# only partially matched path-traversal suffixes (``WR=1234/../evil``
# would redact only ``1234``, leaking ``/../evil`` through the
# Sentry context). The negative lookahead ``(?![a-zA-Z])`` keeps the
# pattern from over-matching English words that happen to start with
# ``WR`` (e.g. ``WRITE``). The identifier char class accepts word
# characters plus ``/ \ . -`` so path-traversal tokens and decorated
# IDs are captured in full, and the ``+`` stops at the first
# whitespace / delimiter so only the identifier itself is redacted.
_RE_REDACT_WR = re.compile(r'(?i)\bWR(?![a-zA-Z])\s*[#:=]?\s*[\w/\\\-.]+')
_RE_REDACT_MONEY = re.compile(r'\$\s*\d[\d,]*(?:\.\d+)?')
_RE_REDACT_EMAIL = re.compile(r'[\w.+-]+@[\w.-]+\.\w+')
_RE_REDACT_CUSTOMER = re.compile(r'(?i)\b(customer|foreman|dept|snapshot|cu|job)\s*[#:=]?\s*["\']?[^,;"\')\]}\n]{1,80}')


def _redact_exception_message(exc: BaseException | None, *, max_len: int = 240) -> str:
    """Return a PII-scrubbed single-line form of ``str(exc)``.

    Used exclusively for the ``error_message`` field of
    ``sentry_capture_with_context(...)``'s context_data payload — that
    dict bypasses the INFO-log ``before_send_log`` sanitizer because
    Sentry attaches it directly as event context. The redactor strips
    WR identifiers, dollar amounts, emails, and ``customer=``/
    ``foreman=``/``dept=``/``snapshot=``/``cu=``/``job=`` key-value
    pairs, collapses whitespace, prefixes the exception class name for
    event-grouping stability, and truncates the result.
    """
    if exc is None:
        return ''
    try:
        raw = str(exc)
    except Exception:
        return f"{type(exc).__name__}: <unrepresentable>"
    if not raw:
        return type(exc).__name__
    redacted = _RE_REDACT_CUSTOMER.sub(r'\1=<redacted>', raw)
    redacted = _RE_REDACT_WR.sub('WR=<redacted>', redacted)
    redacted = _RE_REDACT_MONEY.sub('$<redacted>', redacted)
    redacted = _RE_REDACT_EMAIL.sub('<email>', redacted)
    redacted = re.sub(r'\s+', ' ', redacted).strip()
    # Codex: truncate AFTER adding the class prefix so ``max_len``
    # caps the full returned payload (what actually lands in the
    # Sentry event), not just the body portion.
    result = f"{type(exc).__name__}: {redacted}"
    if len(result) > max_len:
        result = result[:max_len - 3] + '...'
    return result


# Sentry helper functions for enhanced error context
def sentry_add_breadcrumb(category: str, message: str, level: str = "info", data: dict | None = None):
    """Add a breadcrumb for execution flow tracking in Sentry dashboard."""
    if SENTRY_DSN:
        sentry_sdk.add_breadcrumb(
            category=category,
            message=message,
            level=level,
            data=data or {}
        )

def sentry_capture_with_context(exception: Exception, context_name: str | None = None, 
                                  context_data: dict | None = None, tags: dict | None = None,
                                  fingerprint: list | None = None):
    """Capture exception with rich context, tags, and custom fingerprinting.
    
    Args:
        exception: The exception to capture
        context_name: Name for the context block in Sentry dashboard
        context_data: Dictionary of contextual data for debugging
        tags: Additional tags for filtering in Sentry
        fingerprint: Custom fingerprint for error grouping
    """
    if not SENTRY_DSN:
        return
    
    scope = sentry_sdk.get_current_scope()
    
    # Add rich context data
    if context_name and context_data:
        sentry_sdk.set_context(context_name, context_data)
    
    # Add custom tags for filtering
    if tags:
        for key, value in tags.items():
            scope.set_tag(key, str(value))
    
    # Set custom fingerprint for error grouping
    if fingerprint:
        scope.fingerprint = fingerprint
    
    # Capture with full context
    sentry_sdk.capture_exception(exception)


# Frame fields that can carry runtime data or embedded source literals. We
# strip all of them from the sheet-drop event: ``vars`` holds sampled row
# locals, and the source-context fields can echo a data literal from the source
# line. Structural fields (function / filename / lineno / module) are kept so
# grouping and "where did it fail" debugging still work.
_PII_FRAME_FIELDS = ("vars", "pre_context", "context_line", "post_context")


def _strip_frame_vars(event: Any, hint: Any = None) -> Any:
    """Drop data-bearing fields (``vars`` + source context) from every
    stacktrace frame in ``event``.

    The engine runs Sentry with ``include_local_variables=True``, so frame
    locals are serialized into events; on the billing paths those locals hold
    row data (foreman / customer / WR / prices). We strip ``vars`` AND the
    source-context fields (``pre_context`` / ``context_line`` / ``post_context``)
    so neither a runtime local value nor an embedded source literal leaks, while
    keeping the frame's structural metadata (function / filename / lineno) for
    grouping and debugging.

    IMPORTANT — for message events this MUST run at ``before_send`` time, not as
    a scope event-processor. With ``attach_stacktrace=True`` the SDK appends the
    current thread's ``threads[*].stacktrace.frames[*]`` AFTER scope
    event-processors run, so a scope processor never sees (and cannot remove)
    them (empirically verified — Codex P1, PR #281). The authoritative call
    site is ``_scrub_sheet_drop_frame_vars`` inside ``before_send_filter``.
    """
    for _container in ("exception", "threads"):
        for _val in (event.get(_container) or {}).get("values") or []:
            for _frame in (_val.get("stacktrace") or {}).get("frames") or []:
                for _field in _PII_FRAME_FIELDS:
                    _frame.pop(_field, None)
    return event


def _scrub_sheet_drop_frame_vars(event: Any) -> Any:
    """``before_send`` hook: strip frame-local ``vars`` from the discovery
    sheet-drop event ONLY.

    Gated on the ``error_location`` tag so ``include_local_variables`` stays
    intact for every other event (debugging non-PII errors still gets locals).
    This is the load-bearing PII scrub for ``sentry_capture_sheet_drop`` — the
    thread-stacktrace ``vars`` that ``attach_stacktrace=True`` adds only exist
    at ``before_send`` time, after scope processors have run.
    """
    if (event.get("tags") or {}).get("error_location") == "discovery_sheet_drop":
        _strip_frame_vars(event)
    return event


def sentry_capture_sheet_drop(sheet_id: object, exc: BaseException) -> None:
    """Loud-but-PII-safe Sentry signal for a dropped Smartsheet source sheet.

    A dropped source sheet means missing billing rows, so it must escalate to
    a Sentry issue rather than hide behind a log WARNING. But the SDK runs with
    ``include_local_variables=True`` + ``attach_stacktrace=True``, so the emitted
    message would otherwise carry this frame's locals (sampled billing rows on
    the discovery path). We tag the event ``error_location=discovery_sheet_drop``;
    ``before_send_filter`` -> ``_scrub_sheet_drop_frame_vars`` then strips every
    frame's ``vars`` from THIS event before it is sent — keeping the loud,
    grouped alert (sheet id + exception class) without exfiltrating row PII. A
    scope event-processor cannot do this: the thread-stacktrace ``vars`` are
    attached only after scope processors run (Codex P1, PR #281).
    """
    if not SENTRY_DSN:
        return
    with sentry_sdk.isolation_scope() as scope:
        scope.set_tag("error_location", "discovery_sheet_drop")
        scope.set_tag("sheet_id", str(sheet_id))
        # Group all discovery drops of the same exception type into ONE issue
        # (loud, not a per-sheet flood); the sheet id is a filterable tag.
        scope.fingerprint = ["discovery-sheet-drop", type(exc).__name__]
        sentry_sdk.capture_message(
            f"Discovery dropped source sheet {sheet_id} after retries "
            f"({type(exc).__name__})",
            level="error",
        )


# Log level type for Sentry SDK 2.x
SentryLogLevel = Literal["fatal", "critical", "error", "warning", "info", "debug"]

def sentry_capture_message_with_context(message: str, level: SentryLogLevel = "error",
                                         context_name: str | None = None, context_data: dict | None = None,
                                         tags: dict | None = None):
    """Capture a message with rich context for Sentry dashboard visibility."""
    if not SENTRY_DSN:
        return
    
    scope = sentry_sdk.get_current_scope()
    
    if context_name and context_data:
        sentry_sdk.set_context(context_name, context_data)
    
    if tags:
        for key, value in tags.items():
            scope.set_tag(key, str(value))
    
    sentry_sdk.capture_message(message, level=level)


def _build_run_kpis(
    *,
    files_generated: int,
    groups_total: int,
    groups_skipped: int,
    groups_generated: int,
    groups_uploaded: int,
    groups_errored: int,
    duration_seconds: float,
    sheets_discovered: int,
    rows_fetched: int,
    api_calls: int,
) -> dict[str, int | float]:
    """Return a flat dict of numeric run-level KPIs for the root Sentry transaction.

    ALL values are int or float — no strings — so there is zero risk of PII
    leakage via set_data().  A derived throughput metric is included.

    This helper is intentionally pure (no side effects) so it is fully
    unit-testable and the no-PII guarantee is test-enforced.
    """
    if duration_seconds and duration_seconds > 0:
        groups_per_minute = round(groups_generated / (duration_seconds / 60.0), 2)
    else:
        groups_per_minute = 0.0
    return {
        "files_generated": files_generated,
        "groups_total": groups_total,
        "groups_skipped": groups_skipped,
        "groups_generated": groups_generated,
        "groups_uploaded": groups_uploaded,
        "groups_errored": groups_errored,
        "duration_seconds": duration_seconds,
        "sheets_discovered": sheets_discovered,
        "rows_fetched": rows_fetched,
        "api_calls": api_calls,
        "groups_per_minute": groups_per_minute,
    }


def _build_run_context_snapshot(
    *,
    success: bool,
    duration_seconds: float,
    groups_attempted: int,
    groups_generated: int,
    groups_uploaded: int,
    groups_errored: int,
    error_type: str | None = None,
) -> dict:
    """Return a PII-safe counts/booleans snapshot for failure-path Sentry attachments.

    This dict is serialised to JSON and attached via scope.add_attachment, which
    BYPASSES before_send_log.  Every value must be a count, boolean, None, or the
    already-safe exception class name only — never a WR number, foreman/dept/job
    name, dollar amount, or any row-level data.

    This helper is intentionally pure (no side effects) so PII-safety is
    test-enforced rather than relying on review alone.
    """
    return {
        "success": success,
        "duration_seconds": duration_seconds,
        "groups_attempted": groups_attempted,
        "groups_generated": groups_generated,
        "groups_uploaded": groups_uploaded,
        "groups_errored": groups_errored,
        "error_type": error_type,  # exception class name only — never the message
    }


def _sentry_log_event(level: str, message: str, **attributes: int | float | bool | str | None) -> None:
    """Guarded structured-log emitter using sentry_sdk.logger (SDK >= 2.54.0).

    ONLY pass non-PII scalars (counts, booleans, fixed enums) as attributes.
    This path BYPASSES before_send_log — never pass row data, WR numbers,
    foreman/dept/job names, dollar amounts, or any per-row values.

    Safety contract:
    - No-ops immediately if SENTRY_DSN is falsy.
    - No-ops immediately if sentry_sdk has no 'logger' attribute (older SDK).
    - Swallows all internal errors (try/except) — never raises, never masks
      the caller's exception.
    - Only emits to Sentry when SENTRY_ENABLE_LOGS is True (the SDK gate).
    """
    if not SENTRY_DSN:
        return
    if not hasattr(sentry_sdk, "logger"):
        return
    try:
        # ``sentry_sdk.logger`` is a lazily-bound attribute (real in
        # sentry-sdk >= 2.54.0; presence already asserted by the hasattr guard
        # above). Resolve it via getattr so static analysis does not flag it as
        # an unknown module attribute. Runtime behavior is unchanged.
        _logger = getattr(sentry_sdk, "logger")
        log_fn = getattr(_logger, level, _logger.info)
        log_fn(message, **attributes)
    except Exception as _log_exc:
        logging.debug(f"_sentry_log_event swallowed error: {_log_exc}")


# Substring markers that identify billing-engine log messages known
# to embed row-level PII (WR, dept, job, foreman, helper / vac-crew
# names, cell values, prices). If any of these appear in a log body,
# the record is dropped before it ships to the Sentry Logs product.
# Applied in addition to the ``SENTRY_ENABLE_LOGS`` env gate —
# defense in depth. Defined at module scope (not inside the
# ``if SENTRY_DSN:`` block) so it is importable and unit-testable
# without a live DSN.
_PII_LOG_MARKERS: tuple[str, ...] = (
    # Per-row / per-cell debug dumps
    "Row data sample",
    "Cell ",
    "ESSENTIAL FIELDS",
    # Helper detection + grouping
    "HELPER ROW DETECTED",
    "HELPER GROUP CREATED",
    "HELPER GROUP SUMMARY",
    "Helper group '",
    "Helper groups: ",
    "Helper detection criteria",
    "Helper variant",
    "Helper row for WR",
    "MAPPED HELPER COLUMN",
    "Sample Helper",
    "Foreman Helping?",
    # VAC Crew detection + grouping
    "VAC Crew detection",
    "VAC CREW ROW DETECTED",
    "VAC CREW GROUP CREATED",
    "VAC CREW GROUP SUMMARY",
    "VAC Crew group '",
    "Adding row to existing VAC Crew group",
    "MAPPED VAC CREW COLUMN",
    "VAC Crew Helping?",
    # Rate / pricing recalc (CU + group codes + quantities + rates)
    "Rate recalculation",
    "Rate recalc",
    # Foreman / assignment / exclusion diagnostics
    "Foreman Assignment",
    "foremen(top5)",
    "Excluding row",
    "EXCLUDING from main Excel",
    "EXCLUDING from foreman/helper",
    # WR-keyed log lines
    "for WR#",
    "WR# ",
    "for WR ",
    "Work request ",
    "Job # not found",
    "Sample group keys",
    # Runtime WR lists (operator-supplied filter / exclusion / reset
    # lists that print every WR identifier they contain).
    "WR_FILTER applied",
    "EXCLUDE_WRS ",
    "EXCLUDE_WRS:",
    "Hash reset requested for specific WRs",
    # Group keys / totals validation. group_key shapes are
    # ``{week}_{wr}`` (primary), ``{week}_{wr}_HELPER_{foreman}``
    # (helper), ``{week}_{wr}_VACCREW`` (vac crew). Any log body
    # carrying ``_HELPER_`` or ``_VACCREW`` is therefore emitting a
    # group key (which embeds WR + week + foreman). Plus the
    # always-on totals validation block at the end of a run, which
    # logs ``{group_key}: rows=N total=$X.YY`` per group.
    "_HELPER_",
    "_VACCREW",
    "Totals Validation",
    "total=$",
    "Failed to process group ",
    "Synthetic group failure ",
    # Attachment / regeneration lifecycle (WR + week embedded)
    "Removing ",
    "Unchanged (",
    "Skip (unchanged",
    "Regenerating ",
    "FORCE GENERATION for ",
    # Output filenames interpolate
    # ``WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}[_Helper_<foreman>|
    # _User_<foreman>|_VacCrew]_{hash}.xlsx``, so any log body that
    # contains ``_WeekEnding_`` is carrying an artifact name that
    # embeds WR + week + foreman. Broad catch-all + explicit prefixes
    # for the upload / delete / generate lifecycle.
    "_WeekEnding_",
    "Generating Excel file",
    "Generated Excel",
    "Uploaded: ",
    "Skipping upload ",
    "Rate limited on upload",
    "Upload retry ",
    "Upload failed for ",
    "Deleted: ",
    "Already gone: ",
    "Delete failed ",
    # Legacy / manual attachment cleanup. `purge_existing_hashed_outputs`
    # logs any ``WR_*.xlsx`` name — including short legacy forms like
    # ``WR_42.xlsx`` that don't contain ``_WeekEnding_`` — so the broad
    # filename catch-all is not sufficient for these paths.
    "Purged attachment:",
    "Failed to purge attachment",
    # Phase 01 Plan 02 D-22: subcontractor variant group keys and
    # group-creation INFO logs (Plan 3 will emit
    # ``AEP BILLABLE GROUP CREATED`` / ``REDUCED SUB GROUP CREATED``
    # plus a missing-CU WARNING that embeds the literal CU code).
    # The group-key tokens (``_AEPBILLABLE`` / ``_REDUCEDSUB`` /
    # the ``_HELPER_`` suffixed variants) cover any log body that
    # embeds the variant's group key — equivalent to the existing
    # ``_HELPER_`` / ``_VACCREW`` markers for the legacy variant set.
    # Locking these in Plan 02 (before Plan 3 emits them) keeps the
    # sanitizer ahead of the call sites, per Living Ledger
    # 2026-04-20 12:00 defense-in-depth rule.
    "_AEPBILLABLE",
    "_REDUCEDSUB",
    "_AEPBILLABLE_HELPER_",
    "_REDUCEDSUB_HELPER_",
    "AEP BILLABLE GROUP CREATED",
    "REDUCED SUB GROUP CREATED",
    # Subproject D (Task 4 review fix / [2026-05-25]): the new
    # PRIMARY GROUP CREATED INFO log embeds WR= and Week= row PII
    # (see the ``🧑 PRIMARY GROUP CREATED`` log in
    # ``group_source_rows``). Explicit marker per the
    # [2026-04-20 12:00] / [2026-05-15 12:00] ledger rules —
    # mirrors the five sibling GROUP CREATED markers above.
    "PRIMARY GROUP CREATED",
    # Phase 01 gap closure (REVIEW-WR-04 / Living Ledger 2026-04-20
    # 12:00): the new helper-shadow GROUP CREATED logs already match
    # against the substring "HELPER GROUP CREATED" by accident — the
    # tokens "REDUCED SUB HELPER GROUP CREATED" and "AEP BILLABLE
    # HELPER GROUP CREATED" happen to CONTAIN that substring. That
    # makes scrubbing fragile to future wording changes (e.g., a
    # rename to "REDUCED SUB HELPER GROUP REGISTERED" or "REDUCED
    # SUB HELPER GRP CREATED" would silently leak the helper
    # foreman name to Sentry Logs). Explicit markers are the
    # defense-in-depth contract per the 2026-04-20 12:00 ledger
    # rule. Sibling markers for the non-shadow variants
    # ("AEP BILLABLE GROUP CREATED" and "REDUCED SUB GROUP
    # CREATED") were landed in Phase 01 Plan 02; these two finish
    # the set.
    "REDUCED SUB HELPER GROUP CREATED",
    "AEP BILLABLE HELPER GROUP CREATED",
    "Subcontractor rates CSV missing",
    # Phase 1.1 Bug A (SUB-08): pre-acceptance rescue diagnostic log
    # embeds WR + CU + rescued price. Explicit marker per the
    # [2026-05-15 12:00] rule 3 (explicit markers for new INFO-level
    # log bodies — no accidental substring matching against
    # pre-existing markers).
    "Subcontractor pre-acceptance rescue",
    # Phase 1.1 Bug B2 (SUB-10): per-sheet variant whitelist
    # off-contract delete INFO log embeds attachment name
    # (``WR_*_WeekEnding_*.xlsx``), which carries WR + week + (for
    # helper-shadow variants) helper foreman name. Explicit marker
    # per the [2026-05-15 12:00] rule 3 — no accidental substring
    # containment with pre-existing markers (the body
    # ``Removed off-contract variant on sheet`` does not overlap
    # any existing marker on its own).
    "Removed off-contract variant on sheet",
    # Phase 1.1 Bug C (SUB-11): per-WR fall-back WARNING for
    # claim-history attribution lookups embeds the sanitized helper
    # foreman name. Explicit marker per the [2026-05-15 12:00]
    # rule 3 — the body ``Subcontractor helper claim attribution
    # fallback`` is an explicit literal that does not overlap any
    # pre-existing marker on its own (no accidental substring
    # containment).
    "Subcontractor helper claim attribution fallback",
    # Phase 1.1 SUB-12 / D-17 / D-19: idempotent hash-history one-time
    # prune INFO log embeds the affected-WR list (capped to the first
    # 20 entries). WR numbers are sanitized at the producer site but
    # are still PII at the project's row-level threshold. Explicit
    # marker per the [2026-05-15 12:00] rule 3 — no accidental
    # substring containment with pre-existing markers.
    "Phase 1.1 hash-history prune",
    # Subproject B Task 8: one-time hash-history prune INFO log embeds
    # the affected-WR list (capped to first 20 entries). Explicit marker
    # per the [2026-05-15 12:00] rule 3 — no accidental substring
    # containment with pre-existing markers (this body does not overlap
    # "Phase 1.1 hash-history prune").
    "Subproject B hash-history prune",
    # Subproject C Task 7: one-time hash-history prune INFO log embeds
    # the affected-WR list (capped to first 20 entries). Explicit marker
    # per the [2026-05-15 12:00] rule 3 — no accidental substring
    # containment with pre-existing markers.
    "Vac crew hash-history prune",
    # Subproject D Task 9: one-time hash-history prune INFO log embeds
    # the affected-WR list (capped to first 20 entries). Explicit marker
    # per the [2026-05-15 12:00] rule 3 — no accidental substring
    # containment with pre-existing markers (body does not overlap
    # "Subproject B hash-history prune" or "Vac crew hash-history prune").
    "Subproject D hash-history prune",
)


def sentry_before_send_log(record, hint):
    """Drop Sentry Logs records that embed billing-row PII.

    Runs only when ``SENTRY_ENABLE_LOGS`` is truthy (otherwise the
    SDK never invokes this hook). Matches against the rendered log
    body; returns ``None`` to drop, or the record unchanged to forward.
    Defined at module scope so it is importable and unit-testable.

    Missing or empty bodies are normalized to ``""`` and forwarded
    unless a configured marker is present. The hook fails **closed**
    for unexpected inspectable payloads: non-string body values, or
    any exception raised while inspecting the record, cause the
    record to be dropped so uninspectable payloads cannot bypass the
    marker checks.
    """
    try:
        # Resolve the body without ``or ""`` coercion — falsy non-string
        # values (0, False, [], {}) must reach the isinstance check so
        # they hit the fail-closed branch instead of being silently
        # converted to "" and forwarded.
        if isinstance(record, dict):
            body = record["body"] if "body" in record else ""
        else:
            body = (
                getattr(record, "body")
                if hasattr(record, "body")
                else ""
            )
        if not isinstance(body, str):
            # Fail closed for unexpected body types so uninspectable
            # records cannot bypass PII marker checks.
            return None
        for marker in _PII_LOG_MARKERS:
            if marker in body:
                return None
    except Exception:
        # Never let the sanitizer crash the SDK — drop on error so
        # unclassified records don't slip through to Sentry Logs.
        return None
    return record


def sentry_before_breadcrumb(crumb, hint):
    """Drop breadcrumbs whose log message embeds billing-row PII.

    ``LoggingIntegration(level=logging.INFO)`` converts every INFO/WARNING
    log record into a Sentry breadcrumb UNCONDITIONALLY — independent of the
    ``SENTRY_ENABLE_LOGS`` gate that guards the Sentry Logs product (and thus
    ``sentry_before_send_log``). Breadcrumbs attach to any subsequently
    captured event, so a PII-bearing log body — e.g. the subcontractor
    helper-claim attribution fallback WARNING, which names ``WR=`` + helper
    foreman, or the always-on ``PRIMARY GROUP CREATED`` / totals-validation
    INFO lines — would ride onto an unrelated error event and exfiltrate row
    data. ``before_send_log`` never sees these (wrong plane), and the
    sheet-drop scrub only strips frame vars (wrong field). This hook is the
    breadcrumb-plane counterpart, reusing the SINGLE ``_PII_LOG_MARKERS``
    registry so there is no marker drift.

    Returns ``None`` to drop, or the crumb unchanged to keep. Only the string
    log-message vector is inspected: non-log breadcrumbs (navigation, http,
    manual ``add_breadcrumb`` calls) legitimately carry ``message=None`` and
    are kept so the debug trail is not gutted. Fails closed on an inspection
    error (drops) so an uninspectable payload cannot bypass the marker checks.
    """
    try:
        if isinstance(crumb, dict):
            message = crumb.get("message")
        else:
            message = getattr(crumb, "message", None)
        if isinstance(message, str):
            for marker in _PII_LOG_MARKERS:
                if marker in message:
                    return None
    except Exception:
        # Never let the scrubber crash the SDK — drop on error so an
        # uninspectable crumb cannot slip PII past the marker checks.
        return None
    return crumb


def _parse_sentry_enable_logs(raw: str | None) -> bool:
    """Parse the SENTRY_ENABLE_LOGS env value into a bool.

    Truthy: ``1``, ``true``, ``yes``, ``on`` (case-insensitive,
    whitespace-tolerant). Anything else — including unset / empty —
    is falsy. Extracted so tests can cover both branches without
    needing a live DSN.
    """
    if raw is None:
        return False
    return raw.strip().lower() in ("1", "true", "yes", "on")


# ──────────────────────────────────────────────────────────────────────
# Garbage patterns / Sentry-cron helpers (relocated; byte-for-byte).
# ──────────────────────────────────────────────────────────────────────


# ── Garbage patterns for the claimer-remediation sweep (Phase 2 Plan 03) ──
# These are the EXACT tokens that ``resolve_claimer`` emits when attribution
# has no frozen history (``#NO_MATCH``) or a blank role (``Unknown_Foreman``).
# They are not realistic human foreman names, so a simple substring match is
# safe (WARNING 6 accepted tradeoff, per the plan's threat-model).
_GARBAGE_PATTERNS: tuple[str, ...] = ('_NO_MATCH', '_Unknown_Foreman')
# WR-04: in the isolated EXECUTE path (valid_wr_weeks=None), only tokens that
# are NEVER a legitimate filename component are swept.  _NO_MATCH is a pure
# Smartsheet ``#NO MATCH`` error token that should never appear in a real file.
# _Unknown_Foreman IS a legitimate current sentinel (emitted when
# ``effective_user`` is blank) and is preserved in the isolated path because
# there is no live-identity set to protect it — an EXECUTE sweep with
# valid_wr_weeks=None would otherwise delete a valid billing artifact.
_ALWAYS_GARBAGE_PATTERNS: tuple[str, ...] = ('_NO_MATCH',)


# Sentry Crons monitor schedule. This cron VALUE must stay byte-for-byte
# identical to the weekday ``schedule.cron`` in
# .github/workflows/weekly-excel-generation.yml. GitHub Actions evaluates every
# ``schedule:`` cron in UTC, so the monitor ``timezone`` below MUST be "UTC".
# (Mislabeling it "America/Chicago" made Sentry expect each check-in 5-6h late
# and fire a perpetual "missed check-in" outage — GENERATE-WEEKLY-EXCEL-6V.)
_CRON_MONITOR_SCHEDULE = "0 13,15,17,19,21,23,1 * * 1-5"


def _build_cron_monitor_config() -> "MonitorConfig":
    """Return the Sentry Crons ``monitor_config`` for the weekly billing job.

    Pure (no I/O); extracted so the schedule/timezone contract can be unit
    tested. ``timezone`` MUST equal the timezone GitHub Actions evaluates the
    workflow ``schedule:`` cron in (UTC); see ``_CRON_MONITOR_SCHEDULE``.
    """
    return {
        "schedule": {"type": "crontab", "value": _CRON_MONITOR_SCHEDULE},
        "timezone": "UTC",
        "checkin_margin": 5,
        "max_runtime": 180,
        "failure_issue_threshold": 1,
        "recovery_threshold": 1,
    }


def _sentry_cron_checkin_start(monitor_slug):
    """Send a Sentry cron 'in_progress' check-in. Returns the check-in id or None.

    Extracted from ``main()`` to reduce its cyclomatic complexity; behavior
    (including swallow-and-log on failure) is preserved verbatim.
    """
    if not SENTRY_DSN:
        return None
    try:
        return capture_checkin(
            monitor_slug=monitor_slug,
            status=MonitorStatus.IN_PROGRESS,
            monitor_config=_build_cron_monitor_config(),
        )
    except Exception as exc:
        logging.warning(f"⚠️ Sentry cron check-in (in_progress) failed: {exc}")
        return None




def _set_sentry_session_tags(session_start):
    """Apply session-level Sentry tags. No-op when Sentry is not configured."""
    if not SENTRY_DSN:
        return
    from pipeline import config as _cfg
    scope = sentry_sdk.get_isolation_scope()
    scope.set_tag("session_start", session_start.isoformat())
    scope.set_tag("test_mode", str(_cfg.TEST_MODE))
    scope.set_tag("github_actions", str(_cfg.GITHUB_ACTIONS_MODE))


def init_sentry() -> None:
    """Initialize Sentry at import time -- called from the facade body ONLY (D-04).

    Wraps the module-scope ``if SENTRY_DSN:`` block that previously ran at L1392
    of ``generate_weekly_pdfs.py``. Idempotent via ``_SENTRY_INITIALIZED`` -- a
    second call is a no-op. Leaf pipeline modules MUST NOT call this. The
    operator-visible logger name is pinned to 'generate_weekly_pdfs' (Pitfall 4),
    and ``before_send_log`` keeps the PII sanitizer wired unchanged.
    """
    global _SENTRY_INITIALIZED, logger
    if _SENTRY_INITIALIZED:
        return
    from pipeline import config as _cfg

    if SENTRY_DSN:
        sentry_logging = LoggingIntegration(
            level=logging.INFO,
            event_level=logging.ERROR
        )

        def before_send_filter(event, hint):
            """Filter out normal Smartsheet 404 errors during cleanup operations.

            Sentry 2.x compatible: Enriches events with additional context.
            """
            # Filter Smartsheet internal logger noise
            if event.get('logger') == 'smartsheet.smartsheet':
                return None

            # Filter out 404 attachment deletion errors (normal operations)
            if 'exception' in event and event['exception'].get('values'):
                for exc_value in event['exception']['values']:
                    if exc_value.get('value'):
                        error_msg = exc_value['value'].lower()
                        if ("404" in error_msg or "not found" in error_msg) and "attachment" in error_msg:
                            logging.info("⚠️ Filtered 404 attachment error from Sentry (normal operation)")
                            return None

            # Enrich all events with runtime context
            event.setdefault('contexts', {})
            event['contexts']['runtime_info'] = {
                'test_mode': _cfg.TEST_MODE,
                'github_actions': bool(os.getenv('GITHUB_ACTIONS')),
                'max_groups': _cfg.MAX_GROUPS,
                'extended_change_detection': _cfg.EXTENDED_CHANGE_DETECTION,
                'python_version': sys.version,
            }

            # PII guard (Codex P1, PR #281): strip frame-local vars from the
            # discovery sheet-drop event. MUST happen here — attach_stacktrace
            # appends thread-frame vars after scope processors run, so this is
            # the only stage that sees them. Gated by tag; other events keep
            # include_local_variables for debugging.
            event = _scrub_sheet_drop_frame_vars(event)

            return event

        def traces_sampler(sampling_context):
            """Dynamic sampling for performance tracing based on operation type."""
            # Always trace errors
            if sampling_context.get('parent_sampled'):
                return 1.0

            # Sample main operations at 100% for full visibility
            transaction_name = sampling_context.get('transaction_context', {}).get('name', '')
            if 'excel_generation' in transaction_name or 'main' in transaction_name:
                return 1.0

            # Sample other operations at 50%
            return 0.5

        try:
            sentry_sdk.init(
                dsn=SENTRY_DSN,
                integrations=[
                    sentry_logging,
                    ThreadingIntegration(propagate_hub=True),
                ],
                # Performance monitoring
                traces_sample_rate=1.0,
                traces_sampler=traces_sampler,
                profiles_sample_rate=0.5,  # SDK 2.x: No longer experimental

                # Environment configuration — SENTRY_* vars take priority over legacy fallbacks
                environment=os.getenv("SENTRY_ENVIRONMENT") or os.getenv("ENVIRONMENT", "production"),
                release=os.getenv("SENTRY_RELEASE") or os.getenv("RELEASE", "weekly-excel-generator@1.0.0"),
                server_name=os.getenv("HOSTNAME", "local"),

                # Error enrichment
                before_send=before_send_filter,
                # Breadcrumb PII scrub (Codex P2, PR #281): LoggingIntegration
                # records INFO/WARNING logs as breadcrumbs unconditionally
                # (the SENTRY_ENABLE_LOGS gate only guards before_send_log's
                # Logs product), and breadcrumbs attach to any later event.
                # Reuse the _PII_LOG_MARKERS registry to drop row-PII crumbs.
                # Cast to Any: the SDK's typed signature is
                # (Breadcrumb, Hint) -> Breadcrumb | None but our hook is
                # intentionally generic over dict/object crumbs.
                before_breadcrumb=cast(Any, sentry_before_breadcrumb),
                attach_stacktrace=True,
                include_local_variables=True,  # SDK 2.x: Replaces with_locals
                max_breadcrumbs=100,

                # Request handling (SDK 2.x syntax)
                max_request_body_size="medium",  # SDK 2.x: Replaces request_bodies

                # Enable source context for better stack traces
                include_source_context=True,

                # Shutdown timeout for graceful error flushing
                shutdown_timeout=5,

                # Sentry Logs (SDK >= 2.35.0): forward records captured by
                # LoggingIntegration into the Sentry Logs product in addition
                # to breadcrumbs/events. Gated opt-in via SENTRY_ENABLE_LOGS
                # because INFO-level call sites in this engine can include
                # row/cell debug content (foreman, dept, job, WR, prices)
                # that must not be exfiltrated to Sentry by default. Set
                # SENTRY_ENABLE_LOGS=true only after auditing log call sites
                # and keeping PER_CELL_DEBUG_ENABLED / row sampling off.
                enable_logs=_parse_sentry_enable_logs(
                    os.getenv("SENTRY_ENABLE_LOGS")
                ),

                # Defense-in-depth PII sanitizer for the Logs product. Even
                # when the env gate is on, drop records that embed known
                # row-level markers (see _PII_LOG_MARKERS above).
                # Cast to Any: the SDK's typed signature is (Log, Hint) -> Log | None,
                # but our hook is intentionally generic over dict/object records.
                before_send_log=cast(Any, sentry_before_send_log),
            )

            # Set user context (SDK 2.x: top-level API)
            sentry_sdk.set_user({
                "id": "excel_generator",
                "username": "weekly_pdf_generator",
                "segment": "billing_automation"
            })

            # Set global tags for all events (SDK 2.x: top-level API)
            sentry_sdk.set_tag("component", "excel_generation")
            sentry_sdk.set_tag("process", "weekly_reports")
            sentry_sdk.set_tag("test_mode", str(_cfg.TEST_MODE))
            sentry_sdk.set_tag("github_actions", str(bool(os.getenv('GITHUB_ACTIONS'))))
            # PII-safe run-mode tags for issue filtering (no raw WR list - WR numbers are row-PII;
            # set_tag bypasses before_send_log so only booleans/enums/counts are permitted here)
            sentry_sdk.set_tag("res_grouping_mode", _cfg.RES_GROUPING_MODE)
            sentry_sdk.set_tag("wr_filter_active", str(bool(_cfg.WR_FILTER)))   # BOOL, never the WR list
            sentry_sdk.set_tag("force_generation", str(_cfg.FORCE_GENERATION))

            # Set initial context (SDK 2.x: top-level API)
            sentry_sdk.set_context("configuration", {
                "max_groups": _cfg.MAX_GROUPS,
                "extended_change_detection": _cfg.EXTENDED_CHANGE_DETECTION,
                "use_discovery_cache": _cfg.USE_DISCOVERY_CACHE,
                "force_generation": _cfg.FORCE_GENERATION,
                # was: "wr_filter": _cfg.WR_FILTER  (raw WR list - row-PII; set_context bypasses
                # before_send_log so the list would reach Sentry servers on every init)
                "wr_filter_active": bool(_cfg.WR_FILTER),
                "wr_filter_count": len(_cfg.WR_FILTER),
            })

            logger = logging.getLogger('generate_weekly_pdfs')
            logging.info("🛡️ Sentry.io error monitoring initialized (SDK 2.x)")
        except Exception as e:
            logging.warning(f"⚠️ Sentry initialization failed: {e}")
            logger = logging.getLogger('generate_weekly_pdfs')
    else:
        logger = logging.getLogger('generate_weekly_pdfs')
        logging.warning("⚠️ SENTRY_DSN not configured - error monitoring disabled")
    _SENTRY_INITIALIZED = True
