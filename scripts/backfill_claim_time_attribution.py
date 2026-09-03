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
    3  --apply: the billing_audit.attribution_snapshot_backup_<YYYYMMDD>
       table for the run's UTC date is absent (definitively missing,
       not a connectivity blip) -- run plan 12-03's
       billing_audit/own03_backfill_attribution.sql first
    4  --apply was given without --i-approved-this -- zero Supabase
       writes and zero RPC calls are made
    6  --apply: a raised RPC exception, or a non-zero server-reported
       per-row error count, occurred while calling
       billing_audit.backfill_attribution
    7  a source read raised a connectivity error, attribution
       discovery reported a definitive fetch failure, or the --apply
       backup-table probe failed for a reason other than the table
       being definitively absent
    8  --wr and --weeks were not both provided -- no source in this
       script can enumerate "every WR with a sentinel role" without a
       raw ``attribution_snapshot`` scan (prohibited by this plan), so
       explicit scoping is required (documented limitation, not a spec
       gap -- see 12-01-SUMMARY.md)
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
# flag is truthy AND the observed name is present and non-sentinel AND
# the event's / state's own ``week_ending`` column equals the target
# week (see _in_target_week -- D-12-A, never inferred across weeks).
_ROLE_COMPLETION_FIELDS: dict[str, tuple[str, str]] = {
    "primary": ("units_completed", "foreman_observed"),
    "helper": ("helper_completed", "helper_observed"),
    "vac_crew": ("vac_completed", "vac_crew_observed"),
}

# Cache key under which resolve_source_1 tallies the row_event /
# row_state rows it skipped because their own week_ending differed from
# (or lacked) the target week. Surfaced in the report summary and the
# run log so an all-unresolved run caused by a missing week column is
# visible, never mistaken for "no evidence".
_S1_OUT_OF_WEEK_KEY = "source_1_out_of_week_rows"

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


class _SourceReadConnectivityError(RuntimeError):
    """Raised when a source read's ``with_retry(...)`` call returns
    ``None`` (retries exhausted / circuit breaker open for that op).

    Post-merge review fix: every source fetcher used to treat a
    ``None`` result the same as a genuine zero-row response, so an
    outage silently produced "no evidence" (an incorrect
    ``unresolved`` report row) instead of a fatal read. Callers let
    this propagate to ``main()``'s existing connectivity try/except so
    the run exits 7 instead of shipping a report built on a partial,
    unconfirmed read.
    """


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
    parser.add_argument(
        "--include-blank-roles",
        dest="include_blank_roles",
        action="store_true",
        default=False,
        help=(
            "Opt-in: also target roles whose CURRENT frozen value is "
            "blank/None, not just a NAMED sentinel (e.g. 'Unknown "
            "Foreman'). OFF by default -- treating an ordinary row's "
            "never-populated helper/vac_crew as a sentinel target can "
            "propose the primary claimer's name into a role that never "
            "had a helper."
        ),
    )
    return parser.parse_args(argv)


# ── Shared helpers ────────────────────────────────────────────────────

_GENERATED_DOCS_DIR = _REPO_ROOT / "generated_docs"


def _is_named_sentinel(value: Any) -> bool:
    """True only when *value* is a non-blank string AND
    ``billing_audit.writer.is_sentinel_claimer`` classifies it as a
    sentinel -- excludes ``None`` / blank so an ordinary row whose
    helper/vac_crew role was never populated is NOT treated as a
    sentinel TARGET by default (post-merge review fix; see
    ``--include-blank-roles`` for the opt-in that restores the
    blank-is-a-target behavior)."""
    from billing_audit.writer import is_sentinel_claimer

    if value is None or not str(value).strip():
        return False
    return is_sentinel_claimer(value)


def _warn_if_report_dir_outside_generated_docs(report_dir: str) -> None:
    """Post-merge review fix (LOW): ``--report-dir`` is not restricted
    to ``generated_docs/`` -- warn (never refuse) when it resolves
    outside that directory, since only ``generated_docs/`` is
    git-ignored for claimer PII."""
    try:
        resolved = Path(report_dir).resolve()
        generated_docs = _GENERATED_DOCS_DIR.resolve()
    except OSError:
        return
    try:
        resolved.relative_to(generated_docs)
    except ValueError:
        logging.warning(
            f"⚠️ --report-dir {report_dir!r} resolves outside "
            f"{generated_docs} — its report files will NOT be covered "
            "by the generated_docs/ .gitignore rule. Confirm git "
            "status before committing anything from this run."
        )


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

    # Post-merge review fix (determinism, must_have): sort the INPUT
    # rows before grouping -- the server's row order for a given
    # filter is otherwise unspecified (especially across ties on the
    # read's own .order() column), so without this a shuffled server
    # response could flip which tied entry _pick_best_entry() picks,
    # or reorder the conflict evidence string, between two runs over
    # the identical row set.
    sorted_rows = sorted(
        rows,
        key=lambda r: (
            str(r.get("identifier") or ""),
            str(r.get("variant") or ""),
            str(r.get("updated_at") or ""),
        ),
    )

    candidates: dict[str, list[tuple[Any, str]]] = {}
    for row in sorted_rows:
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
            ev for name in names for _ts, ev in candidates[name]
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
                # Explicit order (determinism must_have) -- the
                # Python-side sort in _resolve_single_name is still
                # the authoritative guarantee; this is belt-and-
                # suspenders against a large result set.
                .order("identifier")
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
        if result is None:
            # Post-merge review fix: with_retry() exhausted / circuit
            # breaker open is a READ FAILURE, never "zero rows" --
            # raise so main()'s connectivity try/except exits 7
            # instead of silently reporting "no evidence".
            raise _SourceReadConnectivityError(
                "group_content_hash read failed (with_retry exhausted "
                f"/ circuit breaker open) for wr={wr!r} "
                f"week_ending={week_ending.isoformat()}"
            )
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
                # Explicit order (determinism must_have) -- see
                # _fetch_group_content_hash_rows.
                .order("identifier")
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
        if result is None:
            raise _SourceReadConnectivityError(
                "group_state read failed (with_retry exhausted / "
                f"circuit breaker open) for wr={wr!r} "
                f"week_ending={week_ending.isoformat()}"
            )
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
#
# Post-merge review fix (batched reads, HIGH): both tables are
# bulk-prefetched ONCE for every in-scope row_id via
# _prefetch_row_events_and_states's chunked .in_() reads -- never one
# query per row. _fetch_row_events / _fetch_row_states below are
# CACHE-ONLY reads of that prefetch; a cache miss (e.g. a caller that
# invokes resolve_source_1 directly without prefetching, as isolated
# unit tests do) reads as "no events for this row", matching the
# pre-batching no-client behavior.

_ROW_ID_CHUNK_SIZE = 500


def _prefetch_row_events_and_states(
    row_ids: "list[int]", cache: dict
) -> None:
    """Bulk-populate the per-row_id ``row_event`` / ``row_state`` cache
    entries source 1 reads, via chunked ``.in_("row_id", chunk)`` reads
    over *row_ids* (chunk size mirrors
    ``pipeline_memory.reader._MAPPING_CHUNK_SIZE``) -- NEVER one query
    per row.

    Idempotent: row_ids that already have BOTH cache entries populated
    are skipped on a repeat call. Every row_id passed in ends up with
    a cache entry (possibly an empty list) so a downstream cache read
    can never mistake "not yet fetched" for "confirmed zero rows".

    Raises ``_SourceReadConnectivityError`` on any chunk's
    ``with_retry`` failure -- the caller (``main``) already wraps the
    resolution loop in a try/except that treats this as a fatal read
    (exit 7), never as "no events for these rows".
    """
    pending = sorted(
        {
            rid for rid in row_ids
            if ("row_event_raw", rid) not in cache
            or ("row_state_raw", rid) not in cache
        }
    )
    if not pending:
        return

    from pipeline_memory.client import get_client as _get_pm_client
    from pipeline_memory.client import with_retry as _pm_with_retry

    events_by_row: dict[int, list[dict[str, Any]]] = {
        rid: [] for rid in pending
    }
    states_by_row: dict[int, list[dict[str, Any]]] = {
        rid: [] for rid in pending
    }

    client = _get_pm_client()
    if client is not None:
        chunks = [
            pending[i:i + _ROW_ID_CHUNK_SIZE]
            for i in range(0, len(pending), _ROW_ID_CHUNK_SIZE)
        ]
        for chunk in chunks:
            def _invoke_events(_ids=chunk):
                return (
                    client.schema("pipeline_memory")
                    .table("row_event")
                    .select("row_id,observed_at,week_ending,after_image")
                    .in_("row_id", list(_ids))
                    .order("observed_at")
                    .execute()
                )

            with sentry_sdk.start_span(
                op="own03.read_row_event_bulk",
                name=f"row_ids={len(chunk)}",
            ):
                try:
                    result = _pm_with_retry(
                        _invoke_events, op="own03_row_event_read"
                    )
                except Exception:
                    sentry_sdk.capture_exception()
                    raise
            if result is None:
                raise _SourceReadConnectivityError(
                    "row_event bulk read failed (with_retry exhausted "
                    f"/ circuit breaker open) for {len(chunk)} "
                    "row_id(s)"
                )
            data = getattr(result, "data", None) or []
            for row in data:
                if not isinstance(row, dict):
                    continue
                rid = row.get("row_id")
                if rid in events_by_row:
                    events_by_row[rid].append(row)

            def _invoke_states(_ids=chunk):
                return (
                    client.schema("pipeline_memory")
                    .table("row_state")
                    .select("*")
                    .in_("row_id", list(_ids))
                    .order("row_modified_at")
                    .execute()
                )

            with sentry_sdk.start_span(
                op="own03.read_row_state_bulk",
                name=f"row_ids={len(chunk)}",
            ):
                try:
                    result = _pm_with_retry(
                        _invoke_states, op="own03_row_state_read"
                    )
                except Exception:
                    sentry_sdk.capture_exception()
                    raise
            if result is None:
                raise _SourceReadConnectivityError(
                    "row_state bulk read failed (with_retry exhausted "
                    f"/ circuit breaker open) for {len(chunk)} "
                    "row_id(s)"
                )
            data = getattr(result, "data", None) or []
            for row in data:
                if not isinstance(row, dict):
                    continue
                rid = row.get("row_id")
                if rid in states_by_row:
                    states_by_row[rid].append(row)

    for rid in pending:
        # Defensive re-sort in Python (determinism must_have) -- two
        # runs must be byte-identical regardless of whether the server
        # actually honors .order() for a given row_id's bucket.
        events_by_row[rid].sort(
            key=lambda r: str(r.get("observed_at") or "")
        )
        states_by_row[rid].sort(
            key=lambda r: str(r.get("row_modified_at") or "")
        )
        cache[("row_event_raw", rid)] = events_by_row[rid]
        cache[("row_state_raw", rid)] = states_by_row[rid]


def _fetch_row_events(row_id: int, cache: dict) -> list[dict[str, Any]]:
    return cache.get(("row_event_raw", row_id), [])


def _fetch_row_states(row_id: int, cache: dict) -> list[dict[str, Any]]:
    return cache.get(("row_state_raw", row_id), [])


def _in_target_week(row: dict[str, Any], week_iso: str) -> bool:
    """True only when the row_event / row_state row's OWN ``week_ending``
    column equals the target week (ISO ``YYYY-MM-DD``).

    Both tables record the week the Smartsheet row belonged to at
    observation time, so a row re-dated after a data correction keeps
    its old-week events under the same ``row_id``. Without this guard
    the first qualifying event chronologically -- possibly an earlier
    week's owner -- would be written for the target week (Greptile
    review on PR #387). A ``NULL`` / missing week is NOT in-week
    evidence (D-12-A): such rows never resolve a target.
    """
    value = row.get("week_ending")
    return value is not None and str(value)[:10] == week_iso


def resolve_source_1(
    target: SentinelTarget, cache: dict
) -> "_Candidate | _Conflict | None":
    """Source 1 (tag ``live``): pipeline_memory.row_event / row_state
    per-row observation, restricted to rows whose own ``week_ending``
    equals ``target.week_ending``. See module docstring for precedence.
    """
    from billing_audit.writer import is_sentinel_claimer

    completed_field, observed_field = _ROLE_COMPLETION_FIELDS[target.role]
    week_iso = str(target.week_ending)[:10]

    for row in _fetch_row_events(target.row_id, cache):
        if not _in_target_week(row, week_iso):
            cache[_S1_OUT_OF_WEEK_KEY] = cache.get(_S1_OUT_OF_WEEK_KEY, 0) + 1
            continue
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
        if not _in_target_week(row, week_iso):
            cache[_S1_OUT_OF_WEEK_KEY] = cache.get(_S1_OUT_OF_WEEK_KEY, 0) + 1
            continue
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
                # Explicit order (determinism must_have) -- see
                # _fetch_group_content_hash_rows.
                .order("filename")
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
        if result is None:
            raise _SourceReadConnectivityError(
                "artifacts read failed (with_retry exhausted / "
                f"circuit breaker open) for wr={wr!r} "
                f"week_ending={week_ending.isoformat()}"
            )
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


# ── --apply write path (Task 3) ──────────────────────────────────────
# p_rows payload key list -- THIS EXACT SET, in THIS EXACT SPELLING, is
# the contract plan 12-03's SQL file's jsonb_to_recordset column list
# must match verbatim: wr, week_ending, smartsheet_row_id, role, value,
# backfill_source, backfill_run_id.
_APPLY_CHUNK_SIZE = 500
_APPLY_RESULT_KEYS: tuple[str, ...] = (
    "updated", "skipped_real_name", "skipped_no_row",
)


def _run_date() -> datetime.date:
    """The run's UTC date -- a separate, mockable function (not an
    inline ``datetime.datetime.now(...)`` call) so tests can pin the
    backup table name without depending on real wall-clock time."""
    return datetime.datetime.now(datetime.timezone.utc).date()


def _backup_table_name(run_date: datetime.date) -> str:
    return f"attribution_snapshot_backup_{run_date.strftime('%Y%m%d')}"


def _probe_backup_table_readable(run_date: datetime.date) -> "tuple[bool, str]":
    """Bounded read-only probe of
    ``billing_audit.attribution_snapshot_backup_<YYYYMMDD>``.

    Returns ``(readable, status)`` where ``status`` is one of ``'ok'``,
    ``'missing'`` or ``'connectivity_error'``. Mirrors the
    with_retry-then-bounded-single-reprobe pattern
    ``billing_audit.writer.prefetch_attribution`` uses to distinguish a
    DEFINITIVELY missing PGRST202 RPC from a transient outage -- here
    the target code is PGRST205 (table not found in the PostgREST
    schema cache). The reprobe is bounded to ONE extra direct call,
    only on the already-failed path, so it cannot reintroduce a retry
    storm.
    """
    table_name = _backup_table_name(run_date)

    from billing_audit.client import get_client as _get_ba_client
    from billing_audit.client import with_retry as _ba_with_retry
    from billing_audit import client as _ba_client_mod

    client = _get_ba_client()
    if client is None:
        return False, "connectivity_error"

    def _invoke():
        return (
            client.schema("billing_audit")
            .table(table_name)
            .select("wr")
            .limit(1)
            .execute()
        )

    with sentry_sdk.start_span(
        op="own03.probe_backup_table",
        name=f"table={table_name}",
    ):
        result = _ba_with_retry(_invoke, op="own03_backup_probe")
        if result is not None:
            return True, "ok"

        try:
            from postgrest import APIError as _APIError  # type: ignore
        except Exception:
            _APIError = ()
        try:
            _invoke()
            # Re-invoke succeeded where with_retry didn't -- the
            # original failure was transient, not a missing table.
            return True, "ok"
        except Exception as probe_exc:
            if isinstance(probe_exc, _APIError) and (
                _ba_client_mod._classify_postgrest_error(probe_exc)[2]
                == "PGRST205"
            ):
                return False, "missing"
            sentry_sdk.capture_exception()
            return False, "connectivity_error"


def _build_apply_payload(
    report_rows: list[dict[str, Any]], run_id: str,
    include_blank_roles: bool = False,
) -> list[dict[str, Any]]:
    """Include an entry only for rows whose ``status`` is ``proposed``
    AND whose ``current_value`` is a sentinel target -- a second,
    defensive, CLIENT-SIDE filter (T-12-01) even though the RPC
    enforces the same rule server-side. Never trusts the caller's own
    ``status`` classification alone.

    Post-merge review fix (targeting, HIGH): by default only a NAMED
    sentinel (a non-blank string classified by ``is_sentinel_claimer``,
    e.g. ``'Unknown Foreman'``) qualifies as a target -- a blank/None
    ``current_value`` is excluded unless *include_blank_roles* is set,
    matching ``_discover_sentinel_targets``'s targeting rule so the
    apply path never writes a proposal derived from a role that was
    never populated in the first place.
    """
    from billing_audit.writer import is_sentinel_claimer

    payload: list[dict[str, Any]] = []
    for row in report_rows:
        if row.get("status") != "proposed":
            continue
        current_value = row.get("current_value")
        if include_blank_roles:
            is_target = is_sentinel_claimer(current_value)
        else:
            is_target = _is_named_sentinel(current_value)
        if not is_target:
            continue
        payload.append(
            {
                "wr": row["wr"],
                "week_ending": row["week_ending"],
                "smartsheet_row_id": row["row_id"],
                "role": row["role"],
                "value": row["proposed_value"],
                "backfill_source": row["source"],
                "backfill_run_id": run_id,
            }
        )
    return payload


def _apply_backfill(
    report_rows: list[dict[str, Any]], run_id: str,
    include_blank_roles: bool = False,
) -> "tuple[dict[tuple, str], dict[str, int], int]":
    """Call ``billing_audit.backfill_attribution(p_rows)`` in chunks of
    at most 500 entries, mirroring ``freeze_row``'s call shape
    (``client.schema("billing_audit").rpc(name, params).execute()``).

    Returns ``(outcome_by_key, tallies, local_exceptions)``:
    - ``outcome_by_key``: ``(wr, week_ending, row_id, role) -> result``
      for every payload row a response covered, used to add the
      ``rpc_result`` column back onto the report.
    - ``tallies``: counts by ``updated`` / ``skipped_real_name`` /
      ``skipped_no_row`` / ``error`` (an ``error`` is any per-row
      result string outside that known vocabulary -- defensive, never
      silently ignored) plus ``skipped_client_side_real_name`` (rows
      the Python-side guard removed before the RPC ever saw them).
    - ``local_exceptions``: chunks where the RPC call itself did not
      return a usable response (an exception, or ``with_retry``
      exhausting retries), OR where the response's per-row result
      count did not match the chunk's payload size (post-merge review
      fix, MED -- an RPC that returns a partial/over-long response is
      never trusted implicitly) -- mirrors
      ``scripts/backfill_attribution_snapshot.py``'s local-exception
      counter that ORs into the final exit gate alongside the
      server-reported tally.
    """
    from billing_audit.client import get_client as _get_ba_client
    from billing_audit.client import with_retry as _ba_with_retry

    all_proposed = sum(1 for r in report_rows if r.get("status") == "proposed")
    payload = _build_apply_payload(
        report_rows, run_id, include_blank_roles=include_blank_roles
    )
    skipped_client_side_real_name = all_proposed - len(payload)

    tallies: dict[str, int] = {
        "updated": 0,
        "skipped_real_name": 0,
        "skipped_no_row": 0,
        "error": 0,
        "skipped_client_side_real_name": skipped_client_side_real_name,
    }
    outcome_by_key: dict[tuple, str] = {}
    local_exceptions = 0

    if not payload:
        return outcome_by_key, tallies, local_exceptions

    client = _get_ba_client()
    chunks = [
        payload[i:i + _APPLY_CHUNK_SIZE]
        for i in range(0, len(payload), _APPLY_CHUNK_SIZE)
    ]
    for chunk in chunks:
        def _invoke(_c=chunk):
            return (
                client.schema("billing_audit")
                .rpc("backfill_attribution", {"p_rows": _c})
                .execute()
            )

        with sentry_sdk.start_span(
            op="own03.apply_backfill",
            name=f"rows={len(chunk)}",
        ):
            try:
                result = _ba_with_retry(_invoke, op="own03_backfill_apply")
            except Exception:
                sentry_sdk.capture_exception()
                result = None

        if result is None:
            local_exceptions += 1
            continue

        data = getattr(result, "data", None) or []
        if isinstance(data, dict):
            data = [data]
        if len(data) != len(chunk):
            # Post-merge review fix (apply reconciliation, MED): never
            # trust a response whose per-row result count doesn't
            # match the chunk sent -- a partial/over-long response
            # means we cannot reliably map results back onto rows.
            local_exceptions += 1
            logging.error(
                "❌ backfill_attribution returned "
                f"{len(data)} result(s) for a chunk of {len(chunk)} "
                "row(s) -- refusing to trust a partial/over-long RPC "
                "response; treating this chunk as failed."
            )
            continue
        for row_result in data:
            if not isinstance(row_result, dict):
                tallies["error"] += 1
                continue
            key = (
                str(row_result.get("wr")),
                str(row_result.get("week_ending")),
                row_result.get("smartsheet_row_id"),
                row_result.get("role"),
            )
            outcome = row_result.get("result")
            if outcome in _APPLY_RESULT_KEYS:
                tallies[outcome] += 1
            else:
                tallies["error"] += 1
                logging.warning(
                    "⚠️ backfill_attribution returned an unrecognized "
                    f"per-row result: {row_result!r}"
                )
            if outcome == "skipped_real_name":
                logging.warning(
                    "⚠️ backfill_attribution skipped a row because its "
                    f"current value is a real name (server-side guard "
                    f"held): {row_result!r}"
                )
            outcome_by_key[key] = outcome or "error"

    return outcome_by_key, tallies, local_exceptions


# ── Sentinel discovery ────────────────────────────────────────────────

def _discover_sentinel_targets(
    wr_week_pairs: "set[tuple[str, datetime.date]]",
    roles: list[str],
    week_fmt_by_date: dict[datetime.date, str],
    cache: dict,
    include_blank_roles: bool = False,
) -> "tuple[list[SentinelTarget], str]":
    """Read the currently frozen per-row roles for every in-scope
    (wr, week_ending) pair through ``billing_audit.writer.prefetch_attribution``
    (a bulk RPC over the SAME lookup_attribution read surface
    ``_lookup_attribution_all`` uses for a single row) -- never a raw
    Supabase table-select on the attribution_snapshot table -- and
    select the (row_id, role) pairs whose CURRENT value is a sentinel
    target.

    Post-merge review fix (targeting, HIGH): by default a role only
    targets when its CURRENT value is a NAMED sentinel -- a non-blank
    string that ``billing_audit.writer.is_sentinel_claimer`` classifies
    as a sentinel (e.g. ``'Unknown Foreman'``). A blank/None value
    (a role that was never populated -- ``is_sentinel_claimer(None)``
    is also True) is EXCLUDED unless *include_blank_roles* is set,
    since treating an ordinary row's never-populated helper/vac_crew
    as a target risks proposing the primary claimer's name into a
    role that never had one. See ``--include-blank-roles``.

    Every row's full frozen dict is also cached under
    ``("attribution_row", wr, week_ending, row_id)`` -- for EVERY row
    seen, not just sentinel ones -- so source 2 can read another role's
    real name off the SAME already-fetched row without a second RPC.

    Returns ``(targets, status)`` where status mirrors
    ``prefetch_attribution``'s own status vocabulary. The caller
    (``main``) MUST treat any status outside ``{'success', 'no_row'}``
    as a connectivity failure (exit 7), never as "zero sentinel rows".
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
            if include_blank_roles:
                is_target = is_sentinel_claimer(current_value)
            else:
                is_target = _is_named_sentinel(current_value)
            if not is_target:
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
    report_dir: str, rows: list[dict[str, Any]], run_id: str,
    csv_columns: "tuple[str, ...]" = _REPORT_COLUMNS,
    extra_summary: dict[str, Any] | None = None,
    filename_stem: str = "own03_backfill_report",
) -> "tuple[Path, Path]":
    """*csv_columns* / *extra_summary* let the Task 3 apply-path REWRITE
    the same two files with an added ``rpc_result`` column + tallies
    without changing the default (dry-run) shape: the JSON row dicts
    already carry whatever keys are present (``rpc_result`` simply
    doesn't exist on a dry-run row, so it never appears in that JSON),
    and the CSV header only grows when a caller explicitly asks.

    *filename_stem* (default ``"own03_backfill_report"``, byte-for-byte
    preserving every pre-existing call site's output filename) lets a
    sibling script reuse this exact sort/serialize/summary logic under
    its OWN report name instead of duplicating it -- added for plan
    12-04's source 5 (``scripts/backfill_cell_history_attribution.py``),
    which must write ``own03_cell_history_report.{json,csv}`` rather
    than overwrite sources 1-4's own report file."""
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
    if extra_summary:
        summary.update(extra_summary)

    json_path = report_dir_path / f"{filename_stem}.json"
    csv_path = report_dir_path / f"{filename_stem}.csv"

    payload = {"summary": summary, "rows": sorted_rows}
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(csv_columns))
        writer.writeheader()
        for row in sorted_rows:
            writer.writerow({k: row.get(k, "") for k in csv_columns})

    return json_path, csv_path


# ── main ───────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    _warn_if_report_dir_outside_generated_docs(args.report_dir)

    # Cheapest, highest-risk gate first -- a pure argument-shape check
    # that needs no Supabase client, so a malformed --apply invocation
    # is refused before touching any credential or making any call.
    if args.apply and not args.i_approved_this:
        logging.error(
            "❌ --apply requires --i-approved-this — this confirms a "
            "human reviewed the dry-run report before any Supabase "
            "write. Zero writes and zero RPC calls were made."
        )
        return 4

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
            wr_week_pairs, args.roles, week_fmt_by_date, cache,
            include_blank_roles=args.include_blank_roles,
        )
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logging.error(
            f"❌ Source read raised a connectivity error during sentinel "
            f"discovery: {type(exc).__name__}"
        )
        return 7

    if discovery_status not in ("success", "no_row"):
        # Post-merge review fix (discovery status, MED): every status
        # outside {success, no_row} -- fetch_failure, unavailable,
        # rpc_missing -- is treated as fatal. unavailable/rpc_missing
        # used to fall through silently and yield zero targets (exit
        # 0), which is indistinguishable from a genuinely clean scope.
        logging.error(
            "❌ Attribution discovery did not return a definitive "
            f"result (prefetch_attribution status={discovery_status!r}). "
            "Not proceeding with a partial/incorrect scope."
        )
        return 7

    report_rows: list[dict[str, Any]] = []
    try:
        if 1 in args.sources:
            _prefetch_row_events_and_states(
                sorted({t.row_id for t in targets}), cache
            )
        for target in targets:
            report_rows.append(_resolve_target(target, args.sources, cache))
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logging.error(
            f"❌ Source read raised a connectivity error while resolving "
            f"claimers: {type(exc).__name__}"
        )
        return 7

    out_of_week = cache.get(_S1_OUT_OF_WEEK_KEY, 0)
    json_path, csv_path = _write_reports(
        args.report_dir, report_rows, run_id,
        extra_summary={
            "include_blank_roles": args.include_blank_roles,
            _S1_OUT_OF_WEEK_KEY: out_of_week,
        },
    )

    logging.info(f"✅ Dry-run report written: {json_path}")
    logging.info(f"                            {csv_path}")
    logging.info(f"   Sentinel rows considered: {len(report_rows)}")
    logging.info(f"   Source-1 rows skipped as out-of-week: {out_of_week}")

    if not args.apply:
        return 0

    # --apply --i-approved-this: probe the backup table BEFORE building
    # any payload (T-12-06 -- refuse to write with no rollback path).
    run_date = _run_date()
    readable, probe_status = _probe_backup_table_readable(run_date)
    if probe_status == "missing":
        table_name = _backup_table_name(run_date)
        logging.error(
            f"❌ billing_audit.{table_name} is not readable — the "
            "backup table for this run's UTC date does not exist. "
            "Run billing_audit/own03_backfill_attribution.sql (plan "
            "12-03) to create it before applying. Zero writes were made."
        )
        return 3
    if not readable:
        logging.error(
            "❌ Could not confirm the attribution_snapshot backup table "
            "is readable (retries exhausted). This is a CONNECTIVITY / "
            "AUTH issue, not a missing table — do not run the backfill "
            "SQL in response. Check SUPABASE_URL, "
            "SUPABASE_SERVICE_ROLE_KEY, and network reachability, then "
            "re-run. Zero writes were made."
        )
        return 7

    try:
        outcome_by_key, tallies, local_exceptions = _apply_backfill(
            report_rows, run_id,
            include_blank_roles=args.include_blank_roles,
        )
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logging.error(
            f"❌ billing_audit.backfill_attribution raised an unexpected "
            f"exception: {type(exc).__name__}"
        )
        return 6

    for row in report_rows:
        key = (row["wr"], row["week_ending"], row["row_id"], row["role"])
        row["rpc_result"] = outcome_by_key.get(key, "")

    json_path, csv_path = _write_reports(
        args.report_dir, report_rows, run_id,
        csv_columns=_REPORT_COLUMNS + ("rpc_result",),
        extra_summary={
            "include_blank_roles": args.include_blank_roles,
            _S1_OUT_OF_WEEK_KEY: out_of_week,
            "apply": tallies,
        },
    )
    logging.info(f"✅ Apply report rewritten: {json_path}")
    logging.info(f"                           {csv_path}")
    logging.info(f"   Apply tallies: {tallies}")
    logging.info(f"   Local RPC-call failures: {local_exceptions}")

    if local_exceptions or tallies.get("error", 0):
        logging.error(
            f"❌ Apply finished with {local_exceptions} chunk RPC-call "
            f"failure(s) + {tallies.get('error', 0)} unrecognized "
            "per-row result(s). Investigate before re-running — "
            "already-updated rows are idempotent no-ops on retry "
            "(the RPC only ever writes over a sentinel or NULL)."
        )
        return 6

    logging.info("✅ Apply complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
