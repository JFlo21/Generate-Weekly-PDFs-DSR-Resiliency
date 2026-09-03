"""Claim-time attribution backfill CLI (OWN-03, Phase 12).

Derives the person who actually CLAIMED each sentinel-frozen row --
in the week it was claimed, never inferred across weeks -- from
observed history, and (with the operator's explicit approval) writes
it back into ``billing_audit.attribution_snapshot`` with provenance so
the next scheduled run regenerates the file under the real name.

This script is the opposite of ``scripts/backfill_attribution_snapshot.py``:
that script freezes whatever the CURRENT Smartsheet value is for a
target week ("policy C" -- current always wins). This script NEVER
reads current Smartsheet row state. It resolves a row's claimer from
four historical sources, in a total and deterministic precedence
order (spec: docs/superpowers/specs/2026-09-01-own-03-claim-time-backfill-design.md):

    1. pipeline_memory.row_event / row_state (tag ``live``)
    2. non-sentinel attribution_snapshot on the SAME row, another role
       (tag ``live``)
    3. public.artifacts filenames for the (wr, week_ending) (tag
       ``backfill_artifacts``)
    4. billing_audit.group_content_hash + pipeline_memory.group_state
       identifier tokens for the (wr, week_ending) -- per D-12-B this
       reads the Supabase hash store, NOT a JSON file (tag
       ``backfill_hash_history``)

Source 5 (Smartsheet cell history) is deliberately NOT implemented
here -- it runs only via the separate, isolated
``scripts/backfill_cell_history_attribution.py`` job (never inside a
production run, never inside this script).

D-12-A: there is no cross-week ("last known before the week") rung.
A row with no in-week evidence stays a sentinel; this ladder never
looks at an adjacent week for any source.

Usage (dry-run, default -- writes generated_docs/own03_backfill_report.{json,csv}):
    python scripts/backfill_claim_time_attribution.py \
        --wr 19073866 --weeks 082425,083125,091425,092125

Requires ``SUPABASE_URL`` + ``SUPABASE_SERVICE_ROLE_KEY`` in the
environment (the same client contract every ``billing_audit`` /
``pipeline_memory`` script already uses).

Exit codes:
    0  success (including a run whose every row is unresolved)
    2  no Supabase client available
    7  a source read raised a connectivity error, or attribution
       discovery reported a definitive fetch failure
    8  --wr and --weeks were not both provided -- no source in this
       script can enumerate "every WR with a sentinel role" without a
       raw ``attribution_snapshot`` scan (prohibited by this plan), so
       explicit scoping is required (documented limitation, not a spec
       gap -- see 12-01-SUMMARY.md)

(Task 3 adds: 3 backup table absent, 4 apply without approval flag,
6 RPC row errors -- see the module docstring update in that commit.)
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, NamedTuple

import sentry_sdk

# Allow running the script from anywhere in the repo.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ── Role / variant vocabulary ────────────────────────────────────────
# The pipeline emits seven filename variants; this script reasons about
# THREE roles. Defined once, module-level, per the plan's instruction
# (avoid re-deriving this mapping at each call site).
_VARIANT_TO_ROLE: dict[str, str] = {
    "primary": "primary",
    "reduced_sub": "primary",
    "aep_billable": "primary",
    "helper": "helper",
    "reduced_sub_helper": "helper",
    "aep_billable_helper": "helper",
    "vac_crew": "vac_crew",
}

_ALL_ROLES: tuple[str, ...] = ("primary", "helper", "vac_crew")

# Inverse mapping: role -> every variant that maps to it. Used by the
# group-level resolvers (sources 3 and 4) to scope their reads to the
# variants relevant for a given role.
_ROLE_VARIANTS: dict[str, tuple[str, ...]] = {
    role: tuple(v for v, r in _VARIANT_TO_ROLE.items() if r == role)
    for role in _ALL_ROLES
}

# role -> the column name billing_audit.lookup_attribution_bulk /
# lookup_attribution return for that role's frozen value.
_ROLE_TO_SNAPSHOT_COLUMN: dict[str, str] = {
    "primary": "primary_foreman",
    "helper": "helper",
    "vac_crew": "vac_crew",
}

# role -> (completed-flag field, observed-name field) on a
# pipeline_memory.row_event.after_image payload / pipeline_memory.row_state
# row. Source 1 reads these; a row only "qualifies" when the completed
# flag is truthy AND the observed name is present and non-sentinel.
_ROLE_COMPLETION_FIELDS: dict[str, tuple[str, str]] = {
    "primary": ("units_completed", "foreman_observed"),
    "helper": ("helper_completed", "helper_observed"),
    "vac_crew": ("vac_completed", "vac_crew_observed"),
}

# variant -> the filename token that immediately precedes the sanitized
# claimer name segment, per pipeline/excel.py's variant-suffix
# construction. Rule 2 deviation: the plan's own source-3 enumeration
# named only the bare _Helper_/_User_ tokens; the subcontractor helper
# variants (reduced_sub_helper, aep_billable_helper) are included here
# too, or filenames for those variants would silently never resolve via
# source 3 -- exactly the coverage gap OWN-03 exists to close. Because
# every artifacts row already carries its own `variant` column (public
# .artifacts schema), resolution always looks up the ONE token for
# THIS row's own variant -- there is no ambiguity between e.g. _User_
# and _ReducedSub_User_ despite one being a substring of the other.
_VARIANT_FILENAME_TOKENS: dict[str, str] = {
    "primary": "_User_",
    "reduced_sub": "_ReducedSub_User_",
    "aep_billable": "_AEPBillable_User_",
    "helper": "_Helper_",
    "reduced_sub_helper": "_ReducedSub_Helper_",
    "aep_billable_helper": "_AEPBillable_Helper_",
    "vac_crew": "_VacCrew_",
}

# Matches the pipeline's trailing 6-hex-char content hash + extension
# (see tests/test_sentinel_superseded_cleanup.py's fixture filenames).
_FILENAME_HASH_SUFFIX_RE = re.compile(r"_[0-9a-fA-F]{6}\.xlsx$")

# The pre-defect cutoff (living-ledger [2026-08-24 14:35]): source 4
# prefers a candidate observed BEFORE this instant, since the defect
# that froze sentinels in the first place started around this date.
_PRE_DEFECT_CUTOFF = datetime.datetime(2026, 8, 24, tzinfo=datetime.timezone.utc)

_REPORT_COLUMNS: tuple[str, ...] = (
    "wr",
    "week_ending",
    "week_ending_fmt",
    "row_id",
    "role",
    "current_value",
    "proposed_value",
    "source",
    "name_fidelity",
    "status",
    "evidence",
)

# Provenance tag emitted for each numbered source, per spec §3/§8.
_SOURCE_TAGS: dict[int, str] = {
    1: "live",
    2: "live",
    3: "backfill_artifacts",
    4: "backfill_hash_history",
}

_SOURCE_PRECEDENCE: tuple[int, ...] = (1, 2, 3, 4)


class SentinelTarget(NamedTuple):
    """One (wr, week_ending, row_id, role) whose CURRENT frozen value is
    a sentinel and therefore a backfill candidate."""

    wr: str
    week_ending: datetime.date
    week_ending_fmt: str
    row_id: int
    role: str
    current_value: str | None


class _Candidate(NamedTuple):
    """A resolver's proposed real name for a (wr, week_ending, role)."""

    name: str
    fidelity: str  # "exact" | "desanitized"
    evidence: str


class _Conflict(NamedTuple):
    """A resolver found >= 2 distinct real names for the same key --
    the single-name rule fails and the row is left unresolved with a
    conflict status, never guessed at."""

    names: tuple[str, ...]
    evidence: str


# ── CLI argument parsing ─────────────────────────────────────────────

def _parse_wr_csv(token: str) -> list[str]:
    if not token or not token.strip():
        raise argparse.ArgumentTypeError("--wr must be a non-empty comma list")
    result: list[str] = []
    for raw in token.split(","):
        raw = raw.strip()
        if not raw:
            raise argparse.ArgumentTypeError("--wr contains an empty token")
        result.append(raw)
    return result


def _parse_week_ending_fmt_token(token: str) -> tuple[str, datetime.date]:
    """Parse ONE MMDDYY token into ``(token, date)``.

    Mirrors ``scripts/backfill_attribution_snapshot.py::_parse_week_mmddyy``'s
    ``argparse.ArgumentTypeError`` discipline so malformed input produces
    a clean usage message instead of an unhandled traceback.
    """
    if len(token) != 6 or not token.isdigit():
        raise argparse.ArgumentTypeError(
            f"--weeks tokens must be MMDDYY (e.g. 082425); got {token!r}"
        )
    month = int(token[0:2])
    day = int(token[2:4])
    year = 2000 + int(token[4:6])
    try:
        return token, datetime.date(year, month, day)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--weeks token {token!r} is not a valid calendar date "
            f"({month:02d}/{day:02d}/{year}): {exc}"
        )


def _parse_weeks_csv(token: str) -> list[tuple[str, datetime.date]]:
    if not token or not token.strip():
        raise argparse.ArgumentTypeError("--weeks must be a non-empty comma list")
    return [_parse_week_ending_fmt_token(raw.strip()) for raw in token.split(",")]


def _parse_roles_csv(token: str) -> list[str]:
    if not token or not token.strip():
        raise argparse.ArgumentTypeError("--roles must be a non-empty comma list")
    result: list[str] = []
    for raw in token.split(","):
        raw = raw.strip()
        if raw not in _ALL_ROLES:
            raise argparse.ArgumentTypeError(
                f"--roles must be from {_ALL_ROLES}; got {raw!r}"
            )
        result.append(raw)
    return result


def _parse_sources_csv(token: str) -> list[int]:
    if not token or not token.strip():
        raise argparse.ArgumentTypeError("--sources must be a non-empty comma list")
    result: list[int] = []
    for raw in token.split(","):
        raw = raw.strip()
        if not raw.lstrip("-").isdigit():
            raise argparse.ArgumentTypeError(
                f"--sources tokens must be integers; got {raw!r}"
            )
        value = int(raw)
        if value == 5:
            raise argparse.ArgumentTypeError(
                "--sources 5 is not accepted by this script -- Source 5 "
                "(Smartsheet cell history) runs ONLY via the separate "
                "scripts/backfill_cell_history_attribution.py job, never "
                "inside this dry-run/apply script."
            )
        if value not in (1, 2, 3, 4):
            raise argparse.ArgumentTypeError(
                f"--sources must be from {{1,2,3,4}}; got {value}"
            )
        result.append(value)
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Claim-time attribution backfill (OWN-03). Resolves the "
            "historically-correct claimer for sentinel-frozen rows from "
            "sources 1-4 (never current Smartsheet state) and writes a "
            "dry-run report by default. See the module docstring for the "
            "full source precedence and exit-code table."
        )
    )
    parser.add_argument(
        "--wr",
        type=_parse_wr_csv,
        default=None,
        help=(
            "Comma list of WR numbers to scope the backfill to. "
            "No source in this script can enumerate 'every WR with a "
            "sentinel role' without a raw attribution_snapshot scan "
            "(prohibited) -- --wr is effectively required."
        ),
    )
    parser.add_argument(
        "--weeks",
        type=_parse_weeks_csv,
        default=None,
        help=(
            "Comma list of week_ending_fmt MMDDYY tokens to scope the "
            "backfill to (e.g. 082425,083125). Effectively required -- "
            "see --wr."
        ),
    )
    parser.add_argument(
        "--roles",
        type=_parse_roles_csv,
        default=list(_ALL_ROLES),
        help="Comma list from primary,helper,vac_crew (default: all three).",
    )
    parser.add_argument(
        "--sources",
        type=_parse_sources_csv,
        default=[1, 2, 3, 4],
        help=(
            "Comma list of integers from 1,2,3,4 (default: 1,2,3,4). "
            "5 is rejected -- see scripts/backfill_cell_history_attribution.py."
        ),
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=True,
        help="Dry-run only (default). Writes the report, no Supabase writes.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help=(
            "Apply resolved proposals as real writes. Requires "
            "--i-approved-this and a readable backup table. Write path "
            "implemented in a later task of this plan."
        ),
    )
    parser.add_argument(
        "--i-approved-this",
        dest="i_approved_this",
        action="store_true",
        default=False,
        help="Required alongside --apply -- confirms a human reviewed the dry-run report.",
    )
    parser.add_argument(
        "--report-dir",
        default="generated_docs",
        help="Directory for the dry-run report (default: generated_docs).",
    )
    return parser.parse_args(argv)


# ── Shared helpers ────────────────────────────────────────────────────

def _desanitize(identifier: str) -> str:
    """Reverse the pipeline's filename sanitizer well enough to recover a
    display name: underscores become single spaces, whitespace collapses.

    Mirrors the de-sanitization idiom used for source 3/4 group-level
    identifiers throughout this script -- NOT a second name sanitizer
    (this only ever runs on ALREADY-sanitized filename/identifier
    tokens to recover a readable name; it never writes a sanitized
    value anywhere).
    """
    return " ".join(identifier.replace("_", " ").split())


def _parse_supabase_timestamp(value: Any) -> datetime.datetime | None:
    """Best-effort parse of a Supabase-returned timestamp into an aware
    ``datetime``. Returns ``None`` for anything unparsable -- callers
    treat that as "no preference", never as an error."""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=datetime.timezone.utc)
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        normalized = text.replace("Z", "+00:00")
        parsed = datetime.datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def _compute_run_id() -> str:
    """Normalize to ``""`` -- never ``None``. When ``GITHUB_RUN_ID`` is
    present, append ``GITHUB_RUN_ATTEMPT`` so a rerun is distinguishable
    -- same rerun-awareness shape as
    ``scripts/backfill_attribution_snapshot.py``."""
    ga_run_id = os.getenv("GITHUB_RUN_ID", "") or ""
    ga_run_attempt = os.getenv("GITHUB_RUN_ATTEMPT", "") or ""
    if ga_run_id:
        return f"{ga_run_id}.{ga_run_attempt}" if ga_run_attempt else ga_run_id
    return ""


def _resolve_single_name(
    rows: list[dict[str, Any]], name_fidelity: str
) -> "_Candidate | _Conflict | None":
    """Apply the shared single-name rule used by sources 3 and 4: propose
    a value only when exactly ONE distinct de-sanitized, non-sentinel
    name results; two or more distinct names is a conflict; zero is
    silence (``None``, so the ladder falls through to the next source).
    """
    from billing_audit.writer import is_sentinel_claimer

    candidates: dict[str, list[tuple[Any, str]]] = {}
    for row in rows:
        identifier = row.get("identifier")
        if not identifier:
            continue
        if is_sentinel_claimer(identifier):
            continue
        normalized = _desanitize(identifier)
        if not normalized:
            continue
        updated_at = row.get("updated_at")
        evidence = f"{row.get('variant')}|{identifier}|{updated_at}"
        candidates.setdefault(normalized, []).append((updated_at, evidence))

    if not candidates:
        return None

    if len(candidates) > 1:
        names = tuple(sorted(candidates.keys()))
        all_evidence = "; ".join(
            ev for entries in candidates.values() for _ts, ev in entries
        )
        return _Conflict(names=names, evidence=all_evidence)

    name, entries = next(iter(candidates.items()))
    best_evidence = _pick_best_entry(entries)
    return _Candidate(name=name, fidelity=name_fidelity, evidence=best_evidence)


def _pick_best_entry(entries: list[tuple[Any, str]]) -> str:
    """Among entries for the SAME winning name, prefer one whose
    ``updated_at`` predates the pre-defect cutoff; break remaining ties
    by earliest ``updated_at``. Unparsable timestamps sort last."""

    def _sort_key(item: tuple[Any, str]) -> datetime.datetime:
        ts, _ev = item
        parsed = _parse_supabase_timestamp(ts)
        return parsed if parsed is not None else datetime.datetime.max.replace(
            tzinfo=datetime.timezone.utc
        )

    pre_defect = [
        item for item in entries
        if _parse_supabase_timestamp(item[0]) is not None
        and _parse_supabase_timestamp(item[0]) < _PRE_DEFECT_CUTOFF
    ]
    pool = pre_defect if pre_defect else entries
    return min(pool, key=_sort_key)[1]


# ── Source 4 (backfill_hash_history, D-12-B) ─────────────────────────
# Reads billing_audit.group_content_hash + pipeline_memory.group_state.
# _WEEK_SCOPED: both reads filter strictly on this row's OWN
# week_ending -- neither ever looks at an adjacent week (rule (c)).

def _fetch_group_content_hash_rows(
    wr: str, week_ending: datetime.date, cache: dict
) -> list[dict[str, Any]]:
    cache_key = ("gch_raw", wr, week_ending)
    if cache_key in cache:
        return cache[cache_key]

    from billing_audit.client import get_client as _get_ba_client
    from billing_audit.client import with_retry as _ba_with_retry
    from billing_audit.writer import _WR_SANITIZE

    rows: list[dict[str, Any]] = []
    client = _get_ba_client()
    if client is not None:
        wr_sanitized = _WR_SANITIZE.sub("_", str(wr).split(".")[0])[:50]

        def _invoke():
            return (
                client.schema("billing_audit")
                .table("group_content_hash")
                .select("variant,identifier,updated_at")
                .eq("wr", wr_sanitized)
                # _WEEK_SCOPED: filters on week_ending -- this row's own
                # week only, never an adjacent one.
                .eq("week_ending", week_ending.isoformat())
                .execute()
            )

        with sentry_sdk.start_span(
            op="own03.read_group_content_hash",
            name=f"wr={wr_sanitized} week={week_ending.isoformat()}",
        ):
            try:
                result = _ba_with_retry(
                    _invoke, op="own03_group_content_hash_read"
                )
            except Exception:
                sentry_sdk.capture_exception()
                raise
        if result is not None:
            data = getattr(result, "data", None) or []
            rows = [r for r in data if isinstance(r, dict)]

    cache[cache_key] = rows
    return rows


def _fetch_group_state_rows(
    wr: str, week_ending: datetime.date, cache: dict
) -> list[dict[str, Any]]:
    cache_key = ("gs_raw", wr, week_ending)
    if cache_key in cache:
        return cache[cache_key]

    from pipeline_memory.client import get_client as _get_pm_client
    from pipeline_memory.client import with_retry as _pm_with_retry
    from billing_audit.writer import _WR_SANITIZE

    rows: list[dict[str, Any]] = []
    client = _get_pm_client()
    if client is not None:
        wr_sanitized = _WR_SANITIZE.sub("_", str(wr).split(".")[0])[:50]

        def _invoke():
            return (
                client.schema("pipeline_memory")
                .table("group_state")
                .select("variant,identifier,updated_at")
                .eq("wr", wr_sanitized)
                # _WEEK_SCOPED: filters on week_ending -- this row's own
                # week only, never an adjacent one.
                .eq("week_ending", week_ending.isoformat())
                .execute()
            )

        with sentry_sdk.start_span(
            op="own03.read_group_state",
            name=f"wr={wr_sanitized} week={week_ending.isoformat()}",
        ):
            try:
                result = _pm_with_retry(_invoke, op="own03_group_state_read")
            except Exception:
                sentry_sdk.capture_exception()
                raise
        if result is not None:
            data = getattr(result, "data", None) or []
            rows = [r for r in data if isinstance(r, dict)]

    cache[cache_key] = rows
    return rows


def resolve_source_4(
    target: SentinelTarget, cache: dict
) -> "_Candidate | _Conflict | None":
    """Source 4 (tag ``backfill_hash_history``, D-12-B): the Supabase
    hash store, never a JSON file. See module docstring for precedence."""
    cache_key = ("source4_result", target.wr, target.week_ending, target.role)
    if cache_key in cache:
        return cache[cache_key]

    variants = _ROLE_VARIANTS.get(target.role, ())
    gch_rows = [
        r for r in _fetch_group_content_hash_rows(target.wr, target.week_ending, cache)
        if r.get("variant") in variants
    ]
    gs_rows = [
        r for r in _fetch_group_state_rows(target.wr, target.week_ending, cache)
        if r.get("variant") in variants
    ]
    result = _resolve_single_name(gch_rows + gs_rows, name_fidelity="desanitized")
    cache[cache_key] = result
    return result


# ── Source 1 (live, pipeline_memory.row_event / row_state) ──────────
# Row-level (not group-level): a completed observation is either
# present or it isn't, so this never returns a _Conflict -- only a
# _Candidate or None. "Earliest qualifying" = the first observation,
# in time, whose completed flag is truthy AND whose observed name is
# present and non-sentinel; that is the moment the row was actually
# claimed. row_event is preferred (full history); row_state (the
# latest snapshot only) is the fallback when no event qualifies.

def _fetch_row_events(row_id: int, cache: dict) -> list[dict[str, Any]]:
    cache_key = ("row_event_raw", row_id)
    if cache_key in cache:
        return cache[cache_key]

    from pipeline_memory.client import get_client as _get_pm_client
    from pipeline_memory.client import with_retry as _pm_with_retry

    rows: list[dict[str, Any]] = []
    client = _get_pm_client()
    if client is not None:

        def _invoke():
            return (
                client.schema("pipeline_memory")
                .table("row_event")
                .select("row_id,observed_at,after_image")
                .eq("row_id", row_id)
                .order("observed_at")
                .execute()
            )

        with sentry_sdk.start_span(
            op="own03.read_row_event",
            name=f"row_id={row_id}",
        ):
            try:
                result = _pm_with_retry(_invoke, op="own03_row_event_read")
            except Exception:
                sentry_sdk.capture_exception()
                raise
        if result is not None:
            data = getattr(result, "data", None) or []
            rows = [r for r in data if isinstance(r, dict)]

    cache[cache_key] = rows
    return rows


def _fetch_row_states(row_id: int, cache: dict) -> list[dict[str, Any]]:
    cache_key = ("row_state_raw", row_id)
    if cache_key in cache:
        return cache[cache_key]

    from pipeline_memory.client import get_client as _get_pm_client
    from pipeline_memory.client import with_retry as _pm_with_retry

    rows: list[dict[str, Any]] = []
    client = _get_pm_client()
    if client is not None:

        def _invoke():
            return (
                client.schema("pipeline_memory")
                .table("row_state")
                .select("*")
                .eq("row_id", row_id)
                .execute()
            )

        with sentry_sdk.start_span(
            op="own03.read_row_state",
            name=f"row_id={row_id}",
        ):
            try:
                result = _pm_with_retry(_invoke, op="own03_row_state_read")
            except Exception:
                sentry_sdk.capture_exception()
                raise
        if result is not None:
            data = getattr(result, "data", None) or []
            rows = [r for r in data if isinstance(r, dict)]

    cache[cache_key] = rows
    return rows


def resolve_source_1(
    target: SentinelTarget, cache: dict
) -> "_Candidate | _Conflict | None":
    """Source 1 (tag ``live``): pipeline_memory.row_event / row_state
    per-row observation. See module docstring for precedence."""
    from billing_audit.writer import is_sentinel_claimer

    completed_field, observed_field = _ROLE_COMPLETION_FIELDS[target.role]

    for row in _fetch_row_events(target.row_id, cache):
        after = row.get("after_image") or {}
        if not after.get(completed_field):
            continue
        observed = after.get(observed_field)
        if not observed or is_sentinel_claimer(observed):
            continue
        return _Candidate(
            name=str(observed).strip(),
            fidelity="exact",
            evidence=f"row_event|observed_at={row.get('observed_at')}",
        )

    for row in _fetch_row_states(target.row_id, cache):
        if not row.get(completed_field):
            continue
        observed = row.get(observed_field)
        if not observed or is_sentinel_claimer(observed):
            continue
        return _Candidate(
            name=str(observed).strip(),
            fidelity="exact",
            evidence=f"row_state|row_modified_at={row.get('row_modified_at')}",
        )

    return None


# ── Source 2 (live, same row, another role) ──────────────────────────
# Confined to the SAME row_id -- never another row, even one for the
# same (wr, week_ending). Reuses the attribution row _discover_sentinel_
# targets already fetched via prefetch_attribution (cached, not a
# second RPC call) rather than re-reading attribution_snapshot.

def resolve_source_2(
    target: SentinelTarget, cache: dict
) -> "_Candidate | _Conflict | None":
    """Source 2 (tag ``live``): non-sentinel attribution_snapshot on the
    SAME row, a different role. See module docstring for precedence."""
    from billing_audit.writer import is_sentinel_claimer

    cache_key = ("attribution_row", target.wr, target.week_ending, target.row_id)
    row = cache.get(cache_key)
    if row is None:
        return None

    for other_role in _ALL_ROLES:
        if other_role == target.role:
            continue
        column = _ROLE_TO_SNAPSHOT_COLUMN[other_role]
        value = row.get(column)
        if not value or is_sentinel_claimer(value):
            continue
        return _Candidate(
            name=str(value).strip(),
            fidelity="exact",
            evidence=f"same_row_other_role={other_role}|{column}={value}",
        )

    return None


# ── Source 3 (backfill_artifacts, public.artifacts filenames) ────────
# Group-level (like source 4): applies the shared single-name rule via
# _resolve_single_name, so >= 2 distinct names for the (wr, week_ending,
# role) is a conflict, never a guess. public.artifacts already carries
# its own `variant` column, so no filename sniffing is needed to
# classify a row -- only to recover the sanitized name segment.

def _extract_claimer_from_filename(filename: str, token: str) -> str | None:
    """Recover the sanitized name segment between *token* and the
    trailing ``_<hash>.xlsx`` suffix. Returns ``None`` when *token* is
    absent or the segment is empty (e.g. a bare ``_VacCrew`` filename
    with no name, per pipeline/excel.py's disabled-mode suffix)."""
    idx = filename.find(token)
    if idx == -1:
        return None
    remainder = filename[idx + len(token):]
    match = _FILENAME_HASH_SUFFIX_RE.search(remainder)
    name_part = remainder[: match.start()] if match else remainder
    name_part = name_part.strip("_")
    return name_part or None


def _fetch_artifacts_rows(
    wr: str, week_ending: datetime.date, cache: dict
) -> list[dict[str, Any]]:
    cache_key = ("artifacts_raw", wr, week_ending)
    if cache_key in cache:
        return cache[cache_key]

    from billing_audit.client import get_client as _get_ba_client
    from billing_audit.client import with_retry as _ba_with_retry

    rows: list[dict[str, Any]] = []
    client = _get_ba_client()
    if client is not None:

        def _invoke():
            # public.artifacts is the DEFAULT schema -- client.table(...)
            # directly, never client.schema("billing_audit").table(...).
            return (
                client.table("artifacts")
                .select("variant,filename,created_at")
                .eq("work_request", wr)
                # _WEEK_SCOPED: this row's own week only.
                .eq("week_ending", week_ending.isoformat())
                .execute()
            )

        with sentry_sdk.start_span(
            op="own03.read_artifacts",
            name=f"wr={wr} week={week_ending.isoformat()}",
        ):
            try:
                result = _ba_with_retry(_invoke, op="own03_artifacts_read")
            except Exception:
                sentry_sdk.capture_exception()
                raise
        if result is not None:
            data = getattr(result, "data", None) or []
            rows = [r for r in data if isinstance(r, dict)]

    cache[cache_key] = rows
    return rows


def resolve_source_3(
    target: SentinelTarget, cache: dict
) -> "_Candidate | _Conflict | None":
    """Source 3 (tag ``backfill_artifacts``): public.artifacts filenames.
    See module docstring for precedence."""
    variants = _ROLE_VARIANTS.get(target.role, ())
    rows = [
        r for r in _fetch_artifacts_rows(target.wr, target.week_ending, cache)
        if r.get("variant") in variants
    ]

    entries: list[dict[str, Any]] = []
    for row in rows:
        variant = row.get("variant")
        token = _VARIANT_FILENAME_TOKENS.get(variant)
        if not token:
            continue
        name_part = _extract_claimer_from_filename(row.get("filename") or "", token)
        if not name_part:
            continue
        entries.append(
            {
                "identifier": name_part,
                "variant": variant,
                "updated_at": row.get("created_at"),
            }
        )

    return _resolve_single_name(entries, name_fidelity="desanitized")


_SOURCE_RESOLVERS: dict[int, Any] = {
    1: resolve_source_1,
    2: resolve_source_2,
    3: resolve_source_3,
    4: resolve_source_4,
}


def _resolve_target(
    target: SentinelTarget, sources: list[int], cache: dict
) -> dict[str, Any]:
    """Walk the fixed 1->2->3->4 precedence, restricted to *sources*
    (``--sources`` only enables/disables; it never reorders). The first
    source returning a DEFINITIVE outcome (a proposal OR a conflict)
    wins; later sources are not consulted for this key. A source that
    is silent (returns ``None``) falls through to the next."""
    for source_id in _SOURCE_PRECEDENCE:
        if source_id not in sources:
            continue
        resolver = _SOURCE_RESOLVERS[source_id]
        result = resolver(target, cache)
        if result is None:
            continue
        if isinstance(result, _Conflict):
            return _make_report_row(
                target,
                status="conflict",
                proposed_value="",
                source=_SOURCE_TAGS[source_id],
                name_fidelity="",
                evidence=(
                    f"conflict among: {', '.join(result.names)} "
                    f"({result.evidence})"
                ),
            )
        return _make_report_row(
            target,
            status="proposed",
            proposed_value=result.name,
            source=_SOURCE_TAGS[source_id],
            name_fidelity=result.fidelity,
            evidence=result.evidence,
        )
    return _make_report_row(
        target,
        status="unresolved",
        proposed_value="",
        source="",
        name_fidelity="",
        evidence=(
            "no source (1-4, as enabled by --sources) produced a "
            "candidate for this row/role"
        ),
    )


def _make_report_row(
    target: SentinelTarget,
    status: str,
    proposed_value: str,
    source: str,
    name_fidelity: str,
    evidence: str,
) -> dict[str, Any]:
    return {
        "wr": target.wr,
        "week_ending": target.week_ending.isoformat(),
        "week_ending_fmt": target.week_ending_fmt,
        "row_id": target.row_id,
        "role": target.role,
        "current_value": target.current_value or "",
        "proposed_value": proposed_value,
        "source": source,
        "name_fidelity": name_fidelity,
        "status": status,
        "evidence": evidence,
    }


# ── Sentinel discovery ────────────────────────────────────────────────

def _discover_sentinel_targets(
    wr_week_pairs: "set[tuple[str, datetime.date]]",
    roles: list[str],
    week_fmt_by_date: dict[datetime.date, str],
    cache: dict,
) -> "tuple[list[SentinelTarget], str]":
    """Read the currently frozen per-row roles for every in-scope
    (wr, week_ending) pair through ``billing_audit.writer.prefetch_attribution``
    (a bulk RPC over the SAME lookup_attribution read surface
    ``_lookup_attribution_all`` uses for a single row) -- never a raw
    Supabase table-select on the attribution_snapshot table -- and
    select the (row_id, role) pairs whose CURRENT value satisfies
    ``billing_audit.writer.is_sentinel_claimer``.

    Every row's full frozen dict is also cached under
    ``("attribution_row", wr, week_ending, row_id)`` -- for EVERY row
    seen, not just sentinel ones -- so source 2 can read another role's
    real name off the SAME already-fetched row without a second RPC.

    Returns ``(targets, status)`` where status mirrors
    ``prefetch_attribution``'s own status vocabulary. A caller MUST
    treat ``'fetch_failure'`` as a connectivity failure (exit 7), never
    as "zero sentinel rows".
    """
    from billing_audit.writer import is_sentinel_claimer, prefetch_attribution

    with sentry_sdk.start_span(
        op="own03.discover_sentinel_targets",
        name=f"pairs={len(wr_week_pairs)}",
    ):
        try:
            attribution_map, status = prefetch_attribution(wr_week_pairs)
        except Exception:
            sentry_sdk.capture_exception()
            raise

    targets: list[SentinelTarget] = []
    for (wr, week_ending, row_id), row in attribution_map.items():
        wr_str = str(wr)
        row_id_int = int(row_id)
        cache[("attribution_row", wr_str, week_ending, row_id_int)] = row
        week_fmt = week_fmt_by_date.get(week_ending, week_ending.strftime("%m%d%y"))
        for role in roles:
            column = _ROLE_TO_SNAPSHOT_COLUMN[role]
            current_value = row.get(column)
            if not is_sentinel_claimer(current_value):
                continue
            targets.append(
                SentinelTarget(
                    wr=wr_str,
                    week_ending=week_ending,
                    week_ending_fmt=week_fmt,
                    row_id=row_id_int,
                    role=role,
                    current_value=current_value,
                )
            )
    return targets, status


# ── Report writer ─────────────────────────────────────────────────────

def _write_reports(
    report_dir: str, rows: list[dict[str, Any]], run_id: str
) -> "tuple[Path, Path]":
    from collections import Counter

    report_dir_path = Path(report_dir)
    report_dir_path.mkdir(parents=True, exist_ok=True)

    # Sorted so two runs over identical input produce byte-identical
    # reports (must_have truth).
    sorted_rows = sorted(
        rows, key=lambda r: (r["wr"], r["week_ending"], r["row_id"], r["role"])
    )

    by_source = Counter(r["source"] for r in sorted_rows if r["source"])
    by_status = Counter(r["status"] for r in sorted_rows)
    summary = {
        "run_id": run_id,
        "total_rows": len(sorted_rows),
        "rows_by_source": dict(sorted(by_source.items())),
        "rows_by_status": dict(sorted(by_status.items())),
    }

    json_path = report_dir_path / "own03_backfill_report.json"
    csv_path = report_dir_path / "own03_backfill_report.csv"

    payload = {"summary": summary, "rows": sorted_rows}
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(_REPORT_COLUMNS))
        writer.writeheader()
        for row in sorted_rows:
            writer.writerow({k: row.get(k, "") for k in _REPORT_COLUMNS})

    return json_path, csv_path


# ── main ───────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # Load .env BEFORE constructing the Supabase client -- same
    # ImportError-vs-other-exception split as
    # scripts/backfill_attribution_snapshot.py (grep-tested there).
    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError:
        pass
    else:
        try:
            load_dotenv()
        except Exception as exc:
            logging.warning(
                "⚠️ load_dotenv() failed "
                f"({type(exc).__name__}); falling back to "
                "pre-exported env vars. Check .env syntax / "
                "permissions if credentials appear missing below."
            )

    from billing_audit.client import get_client as _get_ba_client

    client = _get_ba_client()
    if client is None:
        logging.error(
            "❌ Supabase client unavailable — set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY (and unset TEST_MODE) before "
            "running the backfill."
        )
        return 2

    if not args.wr or not args.weeks:
        logging.error(
            "❌ --wr and --weeks are both required. No source available "
            "to this script can enumerate 'every WR with a sentinel "
            "role' without a raw attribution_snapshot scan, which this "
            "plan prohibits — scope the backfill explicitly with both "
            "flags (see 12-01-SUMMARY.md for the documented limitation)."
        )
        return 8

    week_fmt_by_date: dict[datetime.date, str] = {
        week_date: fmt for fmt, week_date in args.weeks
    }
    wr_week_pairs = {
        (wr, week_date) for wr in args.wr for _fmt, week_date in args.weeks
    }

    run_id = _compute_run_id()

    # Created before discovery so _discover_sentinel_targets can populate
    # the per-row attribution cache that source 2 reads (same row, other
    # role) without a second RPC call.
    cache: dict = {}
    try:
        targets, discovery_status = _discover_sentinel_targets(
            wr_week_pairs, args.roles, week_fmt_by_date, cache
        )
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logging.error(
            f"❌ Source read raised a connectivity error during sentinel "
            f"discovery: {type(exc).__name__}"
        )
        return 7

    if discovery_status == "fetch_failure":
        logging.error(
            "❌ Attribution discovery reported a definitive connectivity "
            "failure (prefetch_attribution: fetch_failure). Not "
            "proceeding with a partial/incorrect scope."
        )
        return 7

    report_rows: list[dict[str, Any]] = []
    try:
        for target in targets:
            report_rows.append(_resolve_target(target, args.sources, cache))
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logging.error(
            f"❌ Source read raised a connectivity error while resolving "
            f"claimers: {type(exc).__name__}"
        )
        return 7

    json_path, csv_path = _write_reports(args.report_dir, report_rows, run_id)

    logging.info(f"✅ Dry-run report written: {json_path}")
    logging.info(f"                            {csv_path}")
    logging.info(f"   Sentinel rows considered: {len(report_rows)}")

    # --apply / --i-approved-this handling and the live write path are
    # implemented in this plan's Task 3. This task is dry-run-only by
    # design (must_have: zero Supabase writes).
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
