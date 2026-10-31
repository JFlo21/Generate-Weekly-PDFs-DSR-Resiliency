"""pipeline.foreman_notes -- pilot-scoped Foreman Notes + Smartsheet colour
carry-over.

Single responsibility: every Phase 15 decision that is *logic* (effective
scope,
General Foreman pilot gating, note normalisation, Smartsheet colour descriptor
parsing, notes digests) lives here as a pure or never-raising function.
Existing
modules only gain one-line pilot-gated seams that call into this module, so a
non-pilot group is byte-identical to today's output (FN-01).

Import rule: this module imports only the stdlib,
``openpyxl.cell.cell.ILLEGAL_CHARACTERS_RE``, ``pipeline.config`` and
``pipeline.retry``. It must NEVER import ``pipeline.change_detection``,
``pipeline.memory_candidate``, ``pipeline.excel``, ``pipeline.discovery`` or
``pipeline.orchestrate`` at module import -- those modules import it.
``pipeline.observability`` is imported lazily inside functions only (it
lazily imports this module, so a top-level import would be a cycle).

The module is READ-ONLY with respect to Smartsheet (``get_sheet`` only) and
never
logs or emits to Sentry any General Foreman name, WR number, note text or
colour
descriptor -- counts only (CLAUDE.md Sentry PII rule; public-repo identifier
rule). One owner-approved exception (quick 261030-suf, docs/DECISIONS.md
2026-10-30): held WR numbers may appear inside the structured
``foreman_notes`` context of a Foreman Notes Sentry event, set on a forked
scope. GF names and note text never leave.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, NamedTuple

from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

from pipeline import config
from pipeline.retry import smartsheet_call_with_retry

__all__ = [
    "FnState",
    "EFFECTIVE_SCOPE",
    "compute_effective_scope",
    "memory_writes_possible",
    "is_dry_run_pilot",
    "memory_write_blocked",
    "mapping_enabled",
    "mapping_schema_marker",
    "set_state",
    "get_state",
    "reset_state",
    "initialize",
    "load_gf_map",
    "norm_wr",
    "normalize_name",
    "parse_allowlist",
    "is_pilot_row",
    "is_pilot_group",
    "STYLE_KEY",
    "STYLE_COLUMNS",
    "PALETTE",
    "parse_descriptor",
    "resolve_cell_style",
    "build_sheet_column_maps",
    "attach_group_styles",
    "reset_style_cache",
    "NOTES_KEY",
    "norm_note",
    "row_notes_component",
    "group_notes_token",
    "globals_component",
    "GfLookup",
    "load_gf_lookup",
    "gf_lookup_failed",
    "should_hold_group",
    "report_run_end",
]

_VALID_SCOPES = ("off", "pilot", "all")
_GF_WR_TITLE = "Work Request #"
_GF_TITLE = "General Foreman"


# ---------------------------------------------------------------------------
# Effective scope (D-15-01 / D-15-03)
# ---------------------------------------------------------------------------

def compute_effective_scope(
    configured: str,
    *,
    test_mode: bool,
    upload_enabled: bool,
    memory_write_possible: bool,
) -> str:
    """Resolve the CONFIGURED scope to the EFFECTIVE scope. PURE (logs only).

    * invalid configured value -> ``'off'`` (fail-closed, one WARNING);
    * ``upload_enabled`` (a publishing run, FOREMAN_NOTES_UPLOAD=1) ->
      configured;
    * a dry run (``test_mode``) is pilot only when no pipeline_memory /
      hash-store write path could run; otherwise ``'off'`` with one WARNING,
      so a dry run can never persist pilot-flavoured fingerprints, markers
      or hashes;
    * everything else (the production cron) -> ``'off'``.

    SKIP_UPLOAD is deliberately NOT an input: on its own it keeps
    production-equivalent state handling, so it must not render pilot output.
    """
    if configured not in _VALID_SCOPES:
        logging.warning(
            "Foreman notes: invalid FOREMAN_NOTES_SCOPE; effective scope is "
            "off"
        )
        return "off"
    if configured == "off":
        return "off"
    if upload_enabled:
        return configured
    if test_mode and not memory_write_possible:
        return configured
    if test_mode:
        logging.warning(
            "Foreman notes: dry run requested but a pipeline_memory / "
            "hash-store write flag is on; effective scope is off. Set the "
            "write flags off (SUPABASE_HASH_STORE_WRITE_ENABLED=0, "
            "RUN_MEMORY_WRITE_ENABLED=0, AUDIT_MEMORY_ENABLED=0) for a "
            "pilot dry run."
        )
    return "off"


def memory_writes_possible() -> bool:
    """True when any pipeline_memory / hash-store write path could run.

    Authority: the plan 15-05 call-site inventory of
    ``pipeline/orchestrate.py``.
    ``AUDIT_MEMORY_ENABLED`` is included because the audit-findings upsert is
    gated on that flag alone (not on TEST_MODE).
    """
    return bool(
        config.SUPABASE_HASH_STORE_WRITE_ENABLED
        or (config.RUN_MEMORY_WRITE_ENABLED and not config.TEST_MODE)
        or getattr(config, "AUDIT_MEMORY_ENABLED", False)
    )


EFFECTIVE_SCOPE: str = compute_effective_scope(
    config.FOREMAN_NOTES_SCOPE,
    test_mode=config.TEST_MODE,
    upload_enabled=config.FOREMAN_NOTES_UPLOAD,
    memory_write_possible=memory_writes_possible(),
)

_BLOCKED_KINDS_LOGGED: set[str] = set()


def is_dry_run_pilot() -> bool:
    """A pilot-scoped run that must not persist anything (TEST_MODE, no
    upload)."""
    return bool(
        EFFECTIVE_SCOPE != "off"
        and config.TEST_MODE
        and not config.FOREMAN_NOTES_UPLOAD
    )


def memory_write_blocked(kind: str) -> bool:
    """True when a pipeline_memory write of ``kind`` must be skipped.

    Call this only INSIDE an existing write gate (i.e. when that gate would
    have
    let the write run): reaching it during a dry-run pilot means a write path
    was
    actually reached. Logs ERROR at most once per ``kind`` per run, naming only
    ``kind`` (never row data).
    """
    if not is_dry_run_pilot():
        return False
    if kind not in _BLOCKED_KINDS_LOGGED:
        _BLOCKED_KINDS_LOGGED.add(kind)
        _log_blocked_write(kind)
    return True


def _log_blocked_write(kind: str) -> None:
    """Log the blocked-write ERROR inside a forked, tagged Sentry scope (C2).

    ``LoggingIntegration`` turns this ERROR into the event, so the tags and
    fingerprint ride on that one event only. If the scope helper fails, the
    plain ``logging.error`` still runs.
    """
    msg = "Foreman notes: blocked pipeline_memory write during dry-run pilot "
    msg += "(kind=%s)"
    logged = False
    try:
        from pipeline import observability as _obs

        with _obs.foreman_notes_scope(
            tags={"foreman_notes": "1", "memory_kind": kind},
            fingerprint=["foreman-notes", "memory-write-blocked", kind],
        ):
            logging.error(msg, kind)
            logged = True
    except Exception:  # noqa: BLE001
        pass
    if not logged:
        logging.error(msg, kind)


def mapping_enabled() -> bool:
    """Whether the Foreman Notes column mapping synonym is active."""
    return EFFECTIVE_SCOPE != "off"


def mapping_schema_marker(base: str) -> str:
    """``base`` unchanged when off; ``base + '+fn1'`` when the mapping is
    active."""
    return base if not mapping_enabled() else base + "+fn1"


# ---------------------------------------------------------------------------
# Immutable run state
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FnState:
    scope: str = "off"
    allowlist: frozenset = frozenset()
    pilot_wrs: frozenset = frozenset()
    gf_loaded: bool = False
    # Quick 261030-suf: a failed GF lookup in an effective pilot scope.
    # Appended LAST with defaults so ``FnState()`` equality is unchanged.
    gf_failed: bool = False
    gf_fail_reason: str = ""
    gf_fail_exc: str = ""
    gf_fail_msg: str = ""


_STATE: FnState = FnState()


def set_state(state: FnState) -> None:
    """Replace the run state that every Foreman Notes check reads."""
    global _STATE
    _STATE = state


def get_state() -> FnState:
    """Return the current run state without changing it."""
    return _STATE


def reset_state() -> None:
    """Back to the default (scope off) state and clear per-run dedupe sets."""
    global _STATE
    _STATE = FnState()
    _BLOCKED_KINDS_LOGGED.clear()
    reset_style_cache()
    _reset_failures()


# Per-run failure counters (quick 261030-suf C3 / C4). Counts and exception
# class names only; reported once at run end by ``report_run_end``.
_RUN_FAILURES: dict = {}


def _reset_failures() -> None:
    """Zero every per-run style / digest failure counter."""
    _RUN_FAILURES.clear()
    _RUN_FAILURES.update(
        style_failed_chunks=0,
        style_rows_affected=0,
        style_attach_failures=0,
        style_exc=set(),
        digest={},
        digest_exc=set(),
    )


_reset_failures()


def _count_style(exc: BaseException, rows: int | None = None) -> None:
    """Count a style failure: a chunk (``rows`` given) or the whole attach.

    Never raises.
    """
    try:
        if rows is None:
            _RUN_FAILURES["style_attach_failures"] += 1
        else:
            _RUN_FAILURES["style_failed_chunks"] += 1
            _RUN_FAILURES["style_rows_affected"] += int(rows)
        _RUN_FAILURES["style_exc"].add(type(exc).__name__)
    except Exception:  # noqa: BLE001
        pass


def _count_digest(func: str, exc: BaseException) -> None:
    """Count a notes-digest failure in ``func``. Never raises."""
    try:
        digest = _RUN_FAILURES["digest"]
        digest[func] = digest.get(func, 0) + 1
        _RUN_FAILURES["digest_exc"].add(type(exc).__name__)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Name / WR normalisation and General Foreman lookup (D-15-04 / D-15-05)
# ---------------------------------------------------------------------------

def normalize_name(value: Any) -> str:
    """Case- and whitespace-insensitive name key; 'NA' / blank / None -> ''."""
    if value is None:
        return ""
    result = " ".join(str(value).split()).casefold()
    return "" if result == "na" else result


def parse_allowlist(raw: Any) -> frozenset:
    """Split a comma-separated allowlist and normalise; blanks are dropped.

    Names containing commas are unsupported (the comma is the separator).
    """
    if not raw:
        return frozenset()
    return frozenset(
        n for n in (normalize_name(p) for p in str(raw).split(",")) if n
    )


def norm_wr(raw: Any) -> str:
    """Reproduce ``pipeline.orchestrate.derive_row_wr`` byte-for-byte."""
    wr = str(raw).split(".")[0] if raw else ""
    return config._RE_SANITIZE_HELPER_NAME.sub("_", wr)[:50]


def _cell_text(cell: Any) -> Any:
    val = getattr(cell, "value", None)
    if val is None:
        val = getattr(cell, "display_value", None)
    return val


class GfLookup(NamedTuple):
    """Result of the General Foreman lookup.

    ``reason`` is ``''`` on success, else ``'columns_mismatch'``,
    ``'partial_read'`` or ``'exception'`` (``exc`` holds the exception).
    """

    gf_map: dict | None
    reason: str
    exc: BaseException | None


def load_gf_map(
    client: Any, sheet_id: Any, wr_col_id: Any, gf_col_id: Any
) -> dict | None:
    """ONE column-filtered read of the target sheet -> ``{norm_wr: norm_gf}``.

    Fail-closed (T-15-03): returns ``None`` on any exception or when either
    column title does not match; WRs whose rows disagree on the GF are omitted.
    """
    return load_gf_lookup(client, sheet_id, wr_col_id, gf_col_id).gf_map


def load_gf_lookup(
    client: Any, sheet_id: Any, wr_col_id: Any, gf_col_id: Any
) -> GfLookup:
    """``load_gf_map`` plus the failure reason. Never raises."""
    try:
        sheet = smartsheet_call_with_retry(
            client.Sheets.get_sheet,
            sheet_id,
            column_ids=f"{wr_col_id},{gf_col_id}",
            label="foreman_notes.gf_map",
        )
        titles = {
            getattr(c, "id", None): getattr(c, "title", None)
            for c in (getattr(sheet, "columns", None) or [])
        }
        if (
            titles.get(wr_col_id) != _GF_WR_TITLE
            or titles.get(gf_col_id) != _GF_TITLE
        ):
            logging.warning(
                "Foreman notes: GF lookup column titles do not match"
            )
            return GfLookup(None, "columns_mismatch", None)
        rows = getattr(sheet, "rows", None) or []
        total = getattr(sheet, "total_row_count", len(rows))
        if isinstance(total, int) and len(rows) < total:
            # PR #436: a partial read could hide a WR's second General
            # Foreman, so the lookup fails closed (no pilot groups).
            logging.warning(
                "Foreman notes: GF lookup read %d of %d rows; "
                "no pilot groups",
                len(rows), total,
            )
            return GfLookup(None, "partial_read", None)
        seen: dict[str, set] = {}
        for row in rows:
            wr = gf = None
            have_gf = False
            for cell in (getattr(row, "cells", None) or []):
                cid = getattr(cell, "column_id", None)
                if cid == wr_col_id:
                    wr = norm_wr(_cell_text(cell))
                elif cid == gf_col_id:
                    gf = normalize_name(_cell_text(cell))
                    have_gf = True
            if not wr:
                continue
            seen.setdefault(wr, set()).add(gf if have_gf else "")
        gf_map = {
            wr: next(iter(gfs)) for wr, gfs in seen.items() if len(gfs) == 1
        }
        return GfLookup(gf_map, "", None)
    except Exception as exc:  # noqa: BLE001 - never raises, fail-closed
        logging.warning(
            "Foreman notes: GF lookup failed (%s); no pilot groups",
            type(exc).__name__,
        )
        return GfLookup(None, "exception", exc)


def _breadcrumb(
    message: str = "initialized", level: str = "info", **data: Any
) -> None:
    """Sentry breadcrumb carrying counts / reason only (never names, WRs or
    notes). Successful initialize keeps ``"initialized"`` / ``info``."""
    try:
        import sentry_sdk  # noqa: WPS433 - optional dependency

        sentry_sdk.add_breadcrumb(
            category="foreman_notes",
            message=message,
            data=data,
            level=level,
        )
    except Exception:  # noqa: BLE001
        pass


def _gf_lookup_status(state: FnState) -> str:
    """``failed`` / ``ok`` / ``skipped`` for the run tag and report."""
    if state.gf_failed:
        return "failed"
    return "ok" if state.gf_loaded else "skipped"


def _report_initialized(state: FnState) -> None:
    """C1 failure event (when the lookup failed) and C5 run tags.

    Never raises.
    """
    try:
        if state.gf_failed:
            reason = state.gf_fail_reason
            _capture(
                "gf_lookup_failed", reason,
                ["foreman-notes", "gf-lookup-failed", reason],
                _lookup_context(state),
                level=_failure_level(),
            )
        from pipeline import observability as _obs

        _obs.set_foreman_notes_run_tags(
            EFFECTIVE_SCOPE, len(state.pilot_wrs), _gf_lookup_status(state)
        )
    except Exception:  # noqa: BLE001
        pass


def initialize(client: Any) -> FnState:
    """Resolve the run state once at start-up. Never raises."""
    try:
        _reset_failures()
        reset_style_cache()
        scope = EFFECTIVE_SCOPE
        if scope == "off":
            state = FnState()
        elif scope == "all":
            state = FnState(scope="all")
        else:
            allowlist = parse_allowlist(config.FOREMAN_NOTES_PILOT_GFS)
            if not allowlist:
                logging.warning(
                    "Foreman notes: pilot allowlist empty (count 0); no pilot "
                    "groups"
                )
                _breadcrumb(
                    "pilot allowlist empty", "warning",
                    allowlist_count=0, gf_rows=0, pilot_wrs=0,
                )
                state = FnState(scope=scope)
            else:
                lookup = load_gf_lookup(
                    client,
                    config.TARGET_SHEET_ID,
                    config.FOREMAN_NOTES_GF_WR_COLUMN_ID,
                    config.FOREMAN_NOTES_GF_COLUMN_ID,
                )
                gf_map = lookup.gf_map
                if gf_map is None:
                    _breadcrumb(
                        "gf lookup failed", "warning",
                        reason=lookup.reason or "exception",
                        allowlist_count=len(allowlist), gf_rows=0,
                        pilot_wrs=0,
                    )
                    state = FnState(
                        scope=scope,
                        allowlist=allowlist,
                        gf_failed=True,
                        gf_fail_reason=lookup.reason or "exception",
                        gf_fail_exc=_exc_class(lookup.exc),
                        gf_fail_msg=_redacted(lookup.exc),
                    )
                else:
                    pilot = frozenset(
                        w for w, g in gf_map.items() if g in allowlist
                    )
                    logging.info(
                        "Foreman notes: allowlist=%d gf_rows=%d pilot_wrs=%d",
                        len(allowlist), len(gf_map), len(pilot),
                    )
                    _breadcrumb(
                        allowlist_count=len(allowlist),
                        gf_rows=len(gf_map),
                        pilot_wrs=len(pilot),
                    )
                    state = FnState(
                        scope=scope,
                        allowlist=allowlist,
                        pilot_wrs=pilot,
                        gf_loaded=True,
                    )
        set_state(state)
        _report_initialized(state)
        return state
    except Exception as exc:  # noqa: BLE001
        logging.warning(
            "Foreman notes: initialize failed (%s)", type(exc).__name__
        )
        # Approved rule 4 (quick 261030-suf): only an effective pilot scope
        # with a non-empty allowlist can hold groups; anything else keeps
        # today's scope-off default exactly.
        try:
            failed = EFFECTIVE_SCOPE == "pilot" and bool(
                parse_allowlist(config.FOREMAN_NOTES_PILOT_GFS)
            )
        except Exception:  # noqa: BLE001
            failed = False
        if failed:
            state = FnState(
                gf_failed=True,
                gf_fail_reason="initialize_failed",
                gf_fail_exc=_exc_class(exc),
                gf_fail_msg=_redacted(exc),
            )
        else:
            state = FnState()
        set_state(state)
        _report_initialized(state)
        return state


def _exc_class(exc: BaseException | None) -> str:
    """Exception class name, or ``''`` when there is none."""
    return type(exc).__name__ if exc is not None else ""


def _redacted(exc: BaseException | None) -> str:
    """PII-redacted exception message (``''`` on any failure)."""
    if exc is None:
        return ""
    try:
        from pipeline.observability import _redact_exception_message

        return _redact_exception_message(exc)
    except Exception:  # noqa: BLE001
        return ""


# ---------------------------------------------------------------------------
# GF-lookup hold (quick 261030-suf, owner decision 2026-10-30, option 1)
# ---------------------------------------------------------------------------

_HELD_GROUPS_CAP = 200


def gf_lookup_failed() -> bool:
    """True when this run's GF lookup failed in an effective pilot scope
    and the run can publish.

    Always False in TEST_MODE (owner decision D2, 2026-10-30): a dry run
    never uploads, so it never holds. The failure itself is still recorded
    in the state and reported to Sentry. Never raises.
    """
    try:
        return bool(_STATE.gf_failed) and not config.TEST_MODE
    except Exception:  # noqa: BLE001
        return False


def should_hold_group(hash_matches_stored: bool) -> bool:
    """Hold a group (no regeneration, no upload) for this run.

    Nothing durable marks a group as pilot, so while the lookup has failed
    every group whose fresh hash differs from the stored hash is held: all
    pilot groups (they lost ``NOTES_FP``) plus changed or new groups.
    Never holds in TEST_MODE. Never raises.
    """
    try:
        return gf_lookup_failed() and not hash_matches_stored
    except Exception:  # noqa: BLE001
        return False


def _failure_level() -> str:
    """Level of the lookup-failed / hold events (owner decision D1).

    ``error`` on a publishing run; ``warning`` in TEST_MODE (a dry run).
    """
    try:
        return "warning" if config.TEST_MODE else "error"
    except Exception:  # noqa: BLE001
        return "error"


def _capture(
    kind: str, reason: str, fingerprint: list, context: dict,
    level: str = "warning",
) -> None:
    """Send one Foreman Notes event. Never raises."""
    try:
        from pipeline import observability as _obs

        _obs.sentry_capture_foreman_notes(
            kind=kind,
            level=level,  # type: ignore[arg-type]
            reason=reason,
            context=context,
            fingerprint=fingerprint,
        )
    except Exception:  # noqa: BLE001
        pass


def _lookup_context(state: FnState) -> dict:
    """Counts / IDs / reason context for a GF-lookup failure event."""
    from pipeline import observability as _obs

    try:
        allowlist_count = len(
            parse_allowlist(config.FOREMAN_NOTES_PILOT_GFS)
        )
    except Exception:  # noqa: BLE001
        allowlist_count = len(state.allowlist)
    ctx = {
        "reason": state.gf_fail_reason,
        "exception_class": state.gf_fail_exc,
        "exception_message": state.gf_fail_msg,
        "target_sheet_id": config.TARGET_SHEET_ID,
        "wr_column_id": config.FOREMAN_NOTES_GF_WR_COLUMN_ID,
        "gf_column_id": config.FOREMAN_NOTES_GF_COLUMN_ID,
        "expected_titles": [_GF_WR_TITLE, _GF_TITLE],
        "allowlist_count": allowlist_count,
        "remediation": list(_obs.FOREMAN_NOTES_REMEDIATION),
    }
    run_url = _obs._github_run_url()
    if run_url:
        ctx["run_url"] = run_url
    return ctx


def _report_style_and_digest(fails: dict, digest: dict) -> None:
    """One run-end warning event each for style and digest failures (C3 /
    C4). Counts and exception class names only. Never raises."""
    try:
        from pipeline import observability as _obs

        run_url = _obs._github_run_url()
        extra = {"run_url": run_url} if run_url else {}
        if fails["style_failed_chunks"] or fails["style_attach_failures"]:
            _capture(
                "style_fetch_failed", "style_fetch_failed",
                ["foreman-notes", "style-fetch-failed"],
                {
                    "reason": "style_fetch_failed",
                    "failed_chunks": fails["style_failed_chunks"],
                    "rows_affected": fails["style_rows_affected"],
                    "attach_failures": fails["style_attach_failures"],
                    "exception_classes": sorted(fails["style_exc"]),
                    **extra,
                },
            )
        if digest:
            _capture(
                "notes_digest_failed", "notes_digest_failed",
                ["foreman-notes", "notes-digest-failed"],
                {
                    "reason": "notes_digest_failed",
                    "failures": digest,
                    "total": sum(digest.values()),
                    "exception_classes": sorted(fails["digest_exc"]),
                    **extra,
                },
            )
    except Exception:  # noqa: BLE001
        pass


def report_run_end(
    held_groups: Any = None,
    force_flags: Any = None,
    reset_purge_skipped: bool = False,
) -> dict:
    """Run-end Foreman Notes report. Counts-only dict; ``{}`` when off.

    When groups were held, logs one counts-only WARNING and sends one
    ``foreman-notes / gf-hold`` event (level ``error`` on a publishing run,
    owner decision D1) whose ``foreman_notes`` context lists the held
    ``{wr, week_ending, variant}`` entries (capped at 200, with
    ``held_total``) and whether the RESET_* purge was skipped.
    ``variant`` is the group variant enum only. Style and notes-digest
    failures counted during the run each send one warning event (C3 /
    C4), and every count is in the returned dict. Never raises.
    """
    try:
        if EFFECTIVE_SCOPE == "off":
            return {}
        state = _STATE
        held = list(held_groups or [])
        forced = sorted(
            str(k) for k, v in dict(force_flags or {}).items() if v
        )
        fails = _RUN_FAILURES
        digest = dict(fails["digest"])
        report: dict = {
            "scope": EFFECTIVE_SCOPE,
            "gf_lookup": _gf_lookup_status(state),
            "held_total": len(held),
            "style_failed_chunks": fails["style_failed_chunks"],
            "style_rows_affected": fails["style_rows_affected"],
            "style_attach_failures": fails["style_attach_failures"],
            "digest_failures": sum(digest.values()),
            "digest_failures_by_function": digest,
            "reset_purge_skipped": bool(reset_purge_skipped),
        }
        _report_style_and_digest(fails, digest)
        if held:
            logging.warning(
                "Foreman notes: %d group(s) held because the GF lookup "
                "failed; carried as regeneration debt (force/regen flags "
                "active: %s; they do not override the hold)",
                len(held), "yes" if forced else "no",
            )
            ctx = _lookup_context(state)
            ctx["held_groups"] = [
                {"wr": str(g[0]), "week_ending": str(g[1]),
                 "variant": str(g[2])}
                for g in held[:_HELD_GROUPS_CAP]
            ]
            ctx["held_total"] = len(held)
            ctx["force_flags_active"] = forced
            ctx["reset_purge_skipped"] = bool(reset_purge_skipped)
            _capture(
                "gf_hold", state.gf_fail_reason,
                ["foreman-notes", "gf-hold"], ctx,
                level=_failure_level(),
            )
        return report
    except Exception:  # noqa: BLE001
        return {}


# ---------------------------------------------------------------------------
# Pilot predicates
# ---------------------------------------------------------------------------

def is_pilot_row(row: Any) -> bool:
    """Pilot membership of one source row (same WR string as derive_row_wr)."""
    try:
        state = _STATE
        if state.scope == "off" or not isinstance(row, dict):
            return False
        wr = norm_wr(row.get("Work Request #"))
        if not wr:
            return False
        if state.scope == "all":
            return True
        if state.scope == "pilot":
            return wr in state.pilot_wrs
        return False
    except Exception:  # noqa: BLE001
        return False


def is_pilot_group(rows: Any) -> bool:
    """Pilot membership of a group (first row, matching
    ``derive_group_wr``)."""
    try:
        return bool(rows) and is_pilot_row(rows[0])
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Smartsheet colour carry-over (D-15-09 / D-15-10 / D-15-12)
# ---------------------------------------------------------------------------

STYLE_KEY = "__fn_style"

# (excel_column_number, logical_column_name). Column 7 ("N/A") is never styled.
# Column 9 (Foreman Notes) is included: every CU-line column sourced from
# Smartsheet carries its colour (discretionary reading of D-15-10).
STYLE_COLUMNS: tuple = (
    (1, "Pole #"),
    (2, "CU"),
    (3, "Work Type"),
    (4, "CU Description"),
    (5, "Unit of Measure"),
    (6, "Quantity"),
    (8, "Units Total Price"),
    (9, "Foreman Notes"),
)

# Pinned copy of GET https://api.smartsheet.com/2.0/serverinfo formats.color
# (verified live 2026-10-29). Index 0 'none' and 3 'transparent' mean no
# colour.
PALETTE: tuple = (
    "none", "#000000", "#FFFFFF", "transparent", "#FFEBEE", "#FFF3DF",
    "#FFFEE6", "#E7F5E9", "#E2F2FE", "#F4E4F5", "#F2E8DE", "#FFCCD2",
    "#FFE1AF", "#FEFF85", "#C6E7C8", "#B9DDFC", "#EBC7EF", "#EEDCCA",
    "#E5E5E5", "#F87E7D", "#FFCD7A", "#FEFF00", "#7ED085", "#5FB3F9",
    "#D190DA", "#D0AF8F", "#BDBDBD", "#EA352E", "#FF8D00", "#FFED00",
    "#40B14B", "#1061C3", "#9210AD", "#974C00", "#757575", "#991310",
    "#EA5000", "#EBC700", "#237F2E", "#0B347D", "#61058B", "#592C00",
)

_DESC_MAX_PARTS = 17
_SLOT_TEXT = 8
_SLOT_BG = 9
_CHUNK = 100


def _slot_hex(part: str) -> str | None:
    part = part.strip()
    if not part:
        return None
    if not (part.isascii() and part.isdigit()):
        raise ValueError("non-numeric palette slot")
    idx = int(part)
    if idx >= len(PALETTE):
        raise ValueError("unknown palette index")
    entry = PALETTE[idx]
    if entry in ("none", "transparent"):
        return None
    return entry.lstrip("#").upper()


def parse_descriptor(desc: Any) -> tuple | None:
    """Parse a 17-slot Smartsheet format descriptor into ``(text_hex,
    bg_hex)``.

    ``None`` / ``''`` -> ``None`` (absent). A slot that is empty or palette
    index 0 / 3 yields ``None`` for that slot. Raises ``ValueError`` for more
    than 17 parts, a non-numeric slot or an unknown palette index.
    """
    if desc is None or desc == "":
        return None
    if not isinstance(desc, str):
        raise ValueError("descriptor is not a string")
    parts = desc.split(",")
    if len(parts) > _DESC_MAX_PARTS:
        raise ValueError("descriptor too long")
    for part in parts:
        part = part.strip()
        if part and not (part.isascii() and part.isdigit()):
            raise ValueError("non-numeric descriptor part")
    parts += [""] * (_DESC_MAX_PARTS - len(parts))
    return _slot_hex(parts[_SLOT_TEXT]), _slot_hex(parts[_SLOT_BG])


def resolve_cell_style(
    cell_cf: Any, row_cf: Any, cell_fmt: Any, row_fmt: Any
) -> tuple:
    """Effective ``(fill_hex, font_hex)`` for one cell.

    Per slot precedence: cell conditional > row conditional > cell static >
    row static. Any present-but-invalid descriptor in the chain fails the whole
    cell closed to ``(None, None)``.
    """
    try:
        parsed = [
            parse_descriptor(d) for d in (cell_cf, row_cf, cell_fmt, row_fmt)
        ]
    except ValueError:
        return None, None
    fill = font = None
    for p in parsed:
        if p is None:
            continue
        if font is None:
            font = p[0]
        if fill is None:
            fill = p[1]
    return fill, font


def build_sheet_column_maps(source_sheets: Any) -> dict:
    """``{int(sheet_id): {logical_name: column_id}}``; malformed entries
    skipped."""
    out: dict = {}
    for source in (source_sheets or []):
        try:
            out[int(source["id"])] = dict(source["column_mapping"])
        except Exception:  # noqa: BLE001
            continue
    return out


# (sheet_id, row_id) -> {logical_name: (fill_hex, font_hex)}; one fetch per row
# per run.
_STYLE_CACHE: dict = {}


def reset_style_cache() -> None:
    """Forget every cached row colour, including failed fetches."""
    _STYLE_CACHE.clear()


def _cache_key(row: dict) -> tuple | None:
    try:
        return int(row["__source_sheet_id"]), int(row["__row_id"])
    except Exception:  # noqa: BLE001
        return None


def _row_styles(resp_row: Any, col_to_name: dict) -> dict:
    row_cf = getattr(resp_row, "conditional_format", None)
    row_fmt = getattr(resp_row, "format_", None)
    cells = {}
    for cell in (getattr(resp_row, "cells", None) or []):
        name = col_to_name.get(getattr(cell, "column_id", None))
        if name is not None:
            cells[name] = cell
    styles = {}
    for _, name in STYLE_COLUMNS:
        cell = cells.get(name)
        styles[name] = resolve_cell_style(
            getattr(cell, "conditional_format", None),
            row_cf,
            getattr(cell, "format_", None),
            row_fmt,
        )
    return styles


def attach_group_styles(client: Any, group_rows: Any, sheet_maps: dict) -> int:
    """Lazily fetch Smartsheet colours for a PILOT group and attach them.

    Sets ``row[STYLE_KEY] = {logical_name: (fill_hex, font_hex)}`` on the group
    rows passed in (per-group copies; shared source rows are never touched).
    Non-pilot groups make zero client calls. Read-only; never raises. Returns
    the number of group rows that carry a style. Colours are never a hash input
    (FN-10).
    """
    try:
        if not is_pilot_group(group_rows):
            return 0
        todo: dict = {}
        for row in group_rows:
            key = _cache_key(row)
            if key is None or key in _STYLE_CACHE:
                continue
            ids = todo.setdefault(key[0], [])
            if key[1] not in ids:
                ids.append(key[1])
        for sheet_id, row_ids in todo.items():
            mapping = (sheet_maps or {}).get(sheet_id) or {}
            names = [n for _, n in STYLE_COLUMNS if n in mapping]
            if not names:
                continue
            col_to_name = {mapping[n]: n for n in names}
            column_ids = ",".join(str(mapping[n]) for n in names)
            for i in range(0, len(row_ids), _CHUNK):
                chunk = row_ids[i:i + _CHUNK]
                try:
                    sheet = smartsheet_call_with_retry(
                        client.Sheets.get_sheet,
                        sheet_id,
                        include="format",
                        column_ids=column_ids,
                        row_ids=",".join(str(r) for r in chunk),
                        label="foreman_notes.styles",
                    )
                    for resp_row in (getattr(sheet, "rows", None) or []):
                        rid = getattr(resp_row, "id", None)
                        if rid is None:
                            continue
                        _STYLE_CACHE[(sheet_id, int(rid))] = _row_styles(
                            resp_row, col_to_name
                        )
                except Exception as exc:  # noqa: BLE001
                    logging.warning(
                        "Foreman notes: style fetch failed (%s) for %d rows",
                        type(exc).__name__, len(chunk),
                    )
                    _count_style(exc, rows=len(chunk))
                # PR #436: a failed or omitted row is cached as plain, so
                # a row shared by several variant groups is fetched once.
                for rid in chunk:
                    _STYLE_CACHE.setdefault((sheet_id, int(rid)), None)
        attached = 0
        for row in group_rows:
            key = _cache_key(row)
            styles = _STYLE_CACHE.get(key) if key is not None else None
            if styles is not None:
                row[STYLE_KEY] = styles
                attached += 1
        return attached
    except Exception as exc:  # noqa: BLE001
        logging.warning(
            "Foreman notes: attach styles failed (%s)", type(exc).__name__
        )
        _count_style(exc)
        return 0


# ---------------------------------------------------------------------------
# Notes normaliser and digests (D-15-11, OQ-4)
# ---------------------------------------------------------------------------

NOTES_KEY = "Foreman Notes"
_NOTE_MAX = 32767


def norm_note(value: Any) -> str:
    """The ONLY note normaliser: used for hashing, fingerprints and Excel
    writes.

    Illegal XML characters removed, then trimmed, then capped at 32767 chars.
    """
    if value is None:
        return ""
    return ILLEGAL_CHARACTERS_RE.sub("", str(value)).strip()[:_NOTE_MAX]


def row_notes_component(row: Any) -> str | None:
    """Normalised note for a PILOT row; ``None`` when off or non-pilot."""
    try:
        if _STATE.scope == "off" or not is_pilot_row(row):
            return None
        return norm_note(row.get(NOTES_KEY))
    except Exception as exc:  # noqa: BLE001
        logging.warning(
            "Foreman notes: row component failed (%s)", type(exc).__name__
        )
        _count_digest("row_notes_component", exc)
        return None


def group_notes_token(sorted_rows: Any, row_identity: Any) -> str:
    """16-hex digest of (Smartsheet row, row identity, normalised note)
    entries for a pilot group.

    ``row_identity`` is a caller-supplied callable (change_detection passes its
    own identity so this module needs no change_detection import). Returns
    ``''`` for a non-pilot group. The row ids bind each note to its row, so a
    note that moves between rows that tie on identity changes the digest.
    Entries are sorted, so any row permutation yields the same digest.
    An all-blank pilot group yields a deterministic non-empty digest of its
    rows (OQ-4).
    """
    try:
        if not is_pilot_group(sorted_rows):
            return ""
        entries = sorted(
            [
                str(r.get("__source_sheet_id", "")),
                str(r.get("__row_id", "")),
                str(row_identity(r)),
                norm_note(r.get(NOTES_KEY)),
            ] for r in sorted_rows
        )
        payload = json.dumps(
            entries, ensure_ascii=False, separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    except Exception as exc:  # noqa: BLE001
        logging.warning(
            "Foreman notes: group token failed (%s)", type(exc).__name__
        )
        _count_digest("group_notes_token", exc)
        return ""


def globals_component() -> str:
    """16-hex digest of scope + allowlist + pilot WR set; ``''`` when off."""
    try:
        state = _STATE
        if state.scope == "off":
            return ""
        payload = json.dumps(
            [state.scope, sorted(state.allowlist), sorted(state.pilot_wrs)],
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    except Exception as exc:  # noqa: BLE001
        logging.warning(
            "Foreman notes: globals component failed (%s)", type(exc).__name__
        )
        _count_digest("globals_component", exc)
        return ""
