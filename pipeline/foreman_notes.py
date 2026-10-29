"""pipeline.foreman_notes -- pilot-scoped Foreman Notes + Smartsheet colour carry-over.

Single responsibility: every Phase 15 decision that is *logic* (effective scope,
General Foreman pilot gating, note normalisation, Smartsheet colour descriptor
parsing, notes digests) lives here as a pure or never-raising function. Existing
modules only gain one-line pilot-gated seams that call into this module, so a
non-pilot group is byte-identical to today's output (FN-01).

Import rule: this module imports only the stdlib,
``openpyxl.cell.cell.ILLEGAL_CHARACTERS_RE``, ``pipeline.config`` and
``pipeline.retry``. It must NEVER import ``pipeline.change_detection``,
``pipeline.memory_candidate``, ``pipeline.excel``, ``pipeline.discovery`` or
``pipeline.orchestrate`` at module import -- those modules import it.

The module is READ-ONLY with respect to Smartsheet (``get_sheet`` only) and never
logs or emits to Sentry any General Foreman name, WR number, note text or colour
descriptor -- counts only (CLAUDE.md Sentry PII rule; public-repo identifier rule).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

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
    * ``upload_enabled`` (a publishing run, FOREMAN_NOTES_UPLOAD=1) -> configured;
    * a dry run (``test_mode``) is pilot only when no pipeline_memory / hash-store
      write path could run; otherwise ``'off'`` with one WARNING so a dry run can
      never persist pilot-flavoured fingerprints, markers or hashes;
    * everything else (the production cron) -> ``'off'``.

    SKIP_UPLOAD is deliberately NOT an input: on its own it keeps
    production-equivalent state handling, so it must not render pilot output.
    """
    if configured not in _VALID_SCOPES:
        logging.warning(
            "Foreman notes: invalid FOREMAN_NOTES_SCOPE; effective scope is off"
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
            "Foreman notes: dry run requested but a pipeline_memory / hash-store "
            "write flag is on; effective scope is off. Set the write flags off "
            "(SUPABASE_HASH_STORE_WRITE_ENABLED=0, RUN_MEMORY_WRITE_ENABLED=0) "
            "for a pilot dry run."
        )
    return "off"


def memory_writes_possible() -> bool:
    """True when any pipeline_memory / hash-store write path could run.

    NOTE: plan 15-05 Task 2's call-site inventory is the authority for this
    expression; it must be extended there if another write flag is found.
    """
    return bool(
        config.SUPABASE_HASH_STORE_WRITE_ENABLED
        or (config.RUN_MEMORY_WRITE_ENABLED and not config.TEST_MODE)
    )


EFFECTIVE_SCOPE: str = compute_effective_scope(
    config.FOREMAN_NOTES_SCOPE,
    test_mode=config.TEST_MODE,
    upload_enabled=config.FOREMAN_NOTES_UPLOAD,
    memory_write_possible=memory_writes_possible(),
)

_BLOCKED_KINDS_LOGGED: set[str] = set()


def is_dry_run_pilot() -> bool:
    """A pilot-scoped run that must not persist anything (TEST_MODE, no upload)."""
    return bool(
        EFFECTIVE_SCOPE != "off"
        and config.TEST_MODE
        and not config.FOREMAN_NOTES_UPLOAD
    )


def memory_write_blocked(kind: str) -> bool:
    """True when a pipeline_memory write of ``kind`` must be skipped.

    Call this only INSIDE an existing write gate (i.e. when that gate would have
    let the write run): reaching it during a dry-run pilot means a write path was
    actually reached. Logs ERROR at most once per ``kind`` per run, naming only
    ``kind`` (never row data).
    """
    if not is_dry_run_pilot():
        return False
    if kind not in _BLOCKED_KINDS_LOGGED:
        _BLOCKED_KINDS_LOGGED.add(kind)
        logging.error(
            "Foreman notes: blocked pipeline_memory write during dry-run pilot "
            "(kind=%s)", kind,
        )
    return True


def mapping_enabled() -> bool:
    """Whether the Foreman Notes column mapping synonym is active."""
    return EFFECTIVE_SCOPE != "off"


def mapping_schema_marker(base: str) -> str:
    """``base`` unchanged when off; ``base + '+fn1'`` when the mapping is active."""
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


_STATE: FnState = FnState()


def set_state(state: FnState) -> None:
    global _STATE
    _STATE = state


def get_state() -> FnState:
    return _STATE


def reset_state() -> None:
    """Back to the default (scope off) state and clear per-run dedupe sets."""
    global _STATE
    _STATE = FnState()
    _BLOCKED_KINDS_LOGGED.clear()
    try:  # style cache lives in the same module once Task 2 lands
        reset_style_cache()  # type: ignore[name-defined]
    except NameError:
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
    return frozenset(n for n in (normalize_name(p) for p in str(raw).split(",")) if n)


def norm_wr(raw: Any) -> str:
    """Reproduce ``pipeline.orchestrate.derive_row_wr`` byte-for-byte."""
    wr = str(raw).split(".")[0] if raw else ""
    return config._RE_SANITIZE_HELPER_NAME.sub("_", wr)[:50]


def _cell_text(cell: Any) -> Any:
    val = getattr(cell, "value", None)
    if val is None:
        val = getattr(cell, "display_value", None)
    return val


def load_gf_map(
    client: Any, sheet_id: Any, wr_col_id: Any, gf_col_id: Any
) -> dict | None:
    """ONE column-filtered read of the target sheet -> ``{norm_wr: norm_gf}``.

    Fail-closed (T-15-03): returns ``None`` on any exception or when either
    column title does not match; WRs whose rows disagree on the GF are omitted.
    """
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
        if titles.get(wr_col_id) != _GF_WR_TITLE or titles.get(gf_col_id) != _GF_TITLE:
            logging.warning("Foreman notes: GF lookup column titles do not match")
            return None
        rows = getattr(sheet, "rows", None) or []
        total = getattr(sheet, "total_row_count", len(rows))
        if isinstance(total, int) and len(rows) < total:
            logging.warning(
                "Foreman notes: GF lookup read %d of %d rows (unknown WRs are non-pilot)",
                len(rows), total,
            )
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
        return {wr: next(iter(gfs)) for wr, gfs in seen.items() if len(gfs) == 1}
    except Exception as exc:  # noqa: BLE001 - never raises, fail-closed
        logging.warning(
            "Foreman notes: GF lookup failed (%s); no pilot groups", type(exc).__name__
        )
        return None


def _breadcrumb(**counts: int) -> None:
    """Sentry breadcrumb carrying counts only (never names / WRs / notes)."""
    try:
        import sentry_sdk  # noqa: WPS433 - optional dependency

        sentry_sdk.add_breadcrumb(
            category="foreman_notes", message="initialized", data=counts, level="info"
        )
    except Exception:  # noqa: BLE001
        pass


def initialize(client: Any) -> FnState:
    """Resolve the run state once at start-up. Never raises."""
    try:
        scope = EFFECTIVE_SCOPE
        if scope == "off":
            state = FnState()
        elif scope == "all":
            state = FnState(scope="all")
        else:
            allowlist = parse_allowlist(config.FOREMAN_NOTES_PILOT_GFS)
            if not allowlist:
                logging.warning(
                    "Foreman notes: pilot allowlist empty (count 0); no pilot groups"
                )
                _breadcrumb(allowlist=0, gf_rows=0, pilot_wrs=0)
                state = FnState(scope=scope)
            else:
                gf_map = load_gf_map(
                    client,
                    config.TARGET_SHEET_ID,
                    config.FOREMAN_NOTES_GF_WR_COLUMN_ID,
                    config.FOREMAN_NOTES_GF_COLUMN_ID,
                )
                if gf_map is None:
                    _breadcrumb(allowlist=len(allowlist), gf_rows=0, pilot_wrs=0)
                    state = FnState(scope=scope, allowlist=allowlist)
                else:
                    pilot = frozenset(w for w, g in gf_map.items() if g in allowlist)
                    logging.info(
                        "Foreman notes: allowlist=%d gf_rows=%d pilot_wrs=%d",
                        len(allowlist), len(gf_map), len(pilot),
                    )
                    _breadcrumb(
                        allowlist=len(allowlist), gf_rows=len(gf_map), pilot_wrs=len(pilot)
                    )
                    state = FnState(
                        scope=scope, allowlist=allowlist, pilot_wrs=pilot, gf_loaded=True
                    )
        set_state(state)
        return state
    except Exception as exc:  # noqa: BLE001
        logging.warning("Foreman notes: initialize failed (%s)", type(exc).__name__)
        state = FnState()
        set_state(state)
        return state


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
    """Pilot membership of a group (first row, matching ``derive_group_wr``)."""
    try:
        return bool(rows) and is_pilot_row(rows[0])
    except Exception:  # noqa: BLE001
        return False
