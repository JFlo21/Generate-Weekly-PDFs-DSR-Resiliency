#!/usr/bin/env python3
"""System health check entry point for ``system-health-check.yml``.

Runs a read-only daily diagnostic of the billing infrastructure and
writes ``generated_docs/system_health.json`` with an
``overall_status`` of ``OK`` / ``WARN`` / ``CRITICAL``.

Contract with the workflow (do not change casually):

* The workflow step ``Run system health check`` invokes
  ``python validate_system_health.py``.
* This script ALWAYS writes the JSON report and ALWAYS exits 0 when
  the report was written -- the workflow's ``Evaluate health status``
  step reads ``overall_status`` and is the single owner of pass/fail
  (it exits 1 on CRITICAL). This script exits 1 only when the report
  itself could not be written.
* Checks are strictly read-only: two Smartsheet API calls at most
  (current user + target-sheet metadata at ``page_size=1``), no row
  writes, no attachment operations.
* Output must never contain secret values or personal data -- only
  presence booleans, counts, and durations.
"""

import datetime
import importlib
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("system_health")

# Mirrors pipeline/config.py (default-fallback is the correct
# behavior; TARGET_SHEET_ID has no "disabled" state). Read directly
# from the environment so a broken pipeline import cannot prevent
# the API checks from running -- facade import health is its own
# check below.
DEFAULT_TARGET_SHEET_ID = 5723337641643908

REPORT_PATH = os.path.join("generated_docs", "system_health.json")

# Import failures here mean the production pipeline cannot run.
CORE_IMPORTS = ("smartsheet", "openpyxl", "dateutil", "dotenv")

# Import failures here degrade monitoring/optional surfaces only.
OPTIONAL_IMPORTS = ("sentry_sdk", "pandas", "supabase", "psutil")

FACADE_IMPORT_TIMEOUT_SEC = 180

# Authoritative source for check_production_workflow_config below.
# Built from __file__, never the process cwd, mirroring how
# check_facade_import derives its subprocess `cwd` -- a cwd-relative
# path would silently re-create the same vacuous-pass class of bug
# this check exists to close.
WORKFLOW_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".github",
    "workflows",
    "weekly-excel-generation.yml",
)
MAX_PARALLEL_WORKERS = 8
WORKFLOW_WORKER_KEYS = ("PARALLEL_WORKERS", "PARALLEL_WORKERS_DISCOVERY")

# Detail-hygiene: any raw workflow value embedded in a problem
# string or a note is redacted (if it looks like a secrets-context
# expression) and truncated before it can reach the JSON report.
_DETAIL_ECHO_LIMIT = 80
_REDACTED_MARKER = "<redacted>"
_SECRETS_CONTEXT_MARKER = "secrets."

_EXPRESSION_FALLBACK_RE = re.compile(r"\|\|\s*'([^']*)'")

STATUS_OK = "ok"
STATUS_WARN = "warn"
STATUS_CRITICAL = "critical"
STATUS_SKIPPED = "skipped"


@dataclass
class CheckResult:
    """Outcome of a single health check."""

    name: str
    status: str
    detail: str
    duration_ms: int = 0


@dataclass
class HealthContext:
    """Mutable state shared across checks (client reuse)."""

    token_present: bool = False
    client: Any = None
    notes: List[str] = field(default_factory=list)


def _timed(
    name: str, fn: Callable[[], "tuple[str, str]"]
) -> CheckResult:
    """Run ``fn`` and wrap its (status, detail) into a CheckResult.

    Any unexpected exception is captured as CRITICAL for that check
    rather than crashing the whole health run.
    """
    start = time.monotonic()
    try:
        status, detail = fn()
    except Exception as exc:  # noqa: BLE001 - report, never crash
        status = STATUS_CRITICAL
        detail = f"unexpected {type(exc).__name__}: {exc}"
    duration_ms = int((time.monotonic() - start) * 1000)
    return CheckResult(name, status, detail, duration_ms)


def check_python_version() -> "tuple[str, str]":
    """WARN when below the documented 3.10+ floor."""
    version = ".".join(str(part) for part in sys.version_info[:3])
    if sys.version_info < (3, 10):
        return STATUS_WARN, f"python {version} < required 3.10"
    return STATUS_OK, f"python {version}"


def check_core_dependencies() -> "tuple[str, str]":
    """CRITICAL when a pipeline-required package cannot import."""
    missing = []
    for module_name in CORE_IMPORTS:
        try:
            importlib.import_module(module_name)
        except Exception:  # noqa: BLE001 - any failure counts
            missing.append(module_name)
    if missing:
        return STATUS_CRITICAL, "missing core: " + ", ".join(missing)
    return STATUS_OK, f"all {len(CORE_IMPORTS)} core imports OK"


def check_optional_dependencies() -> "tuple[str, str]":
    """WARN when a monitoring/optional package cannot import."""
    missing = []
    for module_name in OPTIONAL_IMPORTS:
        try:
            importlib.import_module(module_name)
        except Exception:  # noqa: BLE001 - any failure counts
            missing.append(module_name)
    if missing:
        return STATUS_WARN, "missing optional: " + ", ".join(missing)
    return STATUS_OK, f"all {len(OPTIONAL_IMPORTS)} optional imports OK"


def check_facade_import() -> "tuple[str, str]":
    """CRITICAL when ``import generate_weekly_pdfs`` fails.

    Runs in a subprocess so an import-time crash (or hang) in the
    production facade is captured as a finding instead of killing
    this health run. Covers syntax errors, broken pipeline modules,
    and import-time regressions in one real-world probe.
    """
    # PYTHONUTF8=1: the facade prints emoji at import time; without
    # this, a Windows child process defaults to cp1252 stdout and
    # dies in UnicodeEncodeError before the import is proven -- a
    # false CRITICAL that cannot happen on the UTF-8 CI runner.
    child_env = {**os.environ, "PYTHONUTF8": "1"}
    # encoding/errors: decode the child's UTF-8 output explicitly --
    # bare text=True decodes with the locale codec (cp1252 on
    # Windows), which raises in the reader threads on emoji output.
    proc = subprocess.run(
        [sys.executable, "-c", "import generate_weekly_pdfs"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=FACADE_IMPORT_TIMEOUT_SEC,
        cwd=os.path.dirname(os.path.abspath(__file__)),
        env=child_env,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()
        # Last line only: enough to identify the exception without
        # dumping a full traceback (which could embed local paths).
        last_line = tail.splitlines()[-1] if tail else "no output"
        return STATUS_CRITICAL, f"facade import failed: {last_line}"
    return STATUS_OK, "generate_weekly_pdfs imports cleanly"


def check_smartsheet_token(ctx: HealthContext) -> "tuple[str, str]":
    """CRITICAL when SMARTSHEET_API_TOKEN is absent or empty."""
    ctx.token_present = bool(os.getenv("SMARTSHEET_API_TOKEN"))
    if not ctx.token_present:
        return STATUS_CRITICAL, "SMARTSHEET_API_TOKEN not set"
    return STATUS_OK, "SMARTSHEET_API_TOKEN present (value not logged)"


def _build_client(token: str) -> Any:
    """Construct a Smartsheet client with exceptions enabled."""
    import smartsheet

    client = smartsheet.Smartsheet(token)
    client.errors_as_exceptions(True)
    return client


def check_smartsheet_api(ctx: HealthContext) -> "tuple[str, str]":
    """CRITICAL when the API rejects auth or is unreachable.

    One read-only request: ``Users.get_current_user``. The identity
    payload is intentionally NOT logged (no emails in CI logs).
    """
    if not ctx.token_present:
        return STATUS_SKIPPED, "skipped: no API token"
    token = os.environ["SMARTSHEET_API_TOKEN"]
    ctx.client = _build_client(token)
    ctx.client.Users.get_current_user()
    return STATUS_OK, "authenticated; API reachable"


def check_target_sheet(ctx: HealthContext) -> "tuple[str, str]":
    """CRITICAL when the upload destination sheet is inaccessible.

    One read-only request at ``page_size=1`` -- metadata only, the
    row payload is never inspected.
    """
    if ctx.client is None:
        return STATUS_SKIPPED, "skipped: no authenticated client"
    raw = os.getenv("TARGET_SHEET_ID")
    try:
        sheet_id = int(raw) if raw else DEFAULT_TARGET_SHEET_ID
    except ValueError:
        sheet_id = DEFAULT_TARGET_SHEET_ID
    sheet = ctx.client.Sheets.get_sheet(sheet_id, page_size=1)
    total_rows = getattr(sheet, "total_row_count", None)
    return STATUS_OK, (
        f"target sheet reachable (total rows: {total_rows})"
    )


def check_generated_docs_writable() -> "tuple[str, str]":
    """CRITICAL when the report/output directory is not writable."""
    directory = os.path.dirname(REPORT_PATH) or "."
    os.makedirs(directory, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=directory, delete=True):
        pass
    return STATUS_OK, f"{directory}/ writable"


def check_config_sanity(ctx: HealthContext) -> "tuple[str, str]":
    """WARN on guardrail values present in THIS process's own env.

    Scope: this job's own process environment only.
    ``system-health-check.yml`` never exports ``PARALLEL_WORKERS`` or
    ``TIME_BUDGET_MINUTES`` -- only the weekly production workflow
    does -- so this check can only ever catch drift if the health
    job itself is one day given those variables. The authoritative
    production values (parsed straight from
    ``weekly-excel-generation.yml``) are graded by
    ``check_production_workflow_config`` instead.
    """
    problems = []
    raw_workers = os.getenv("PARALLEL_WORKERS")
    if raw_workers:
        try:
            if int(raw_workers) > 8:
                problems.append(
                    "process env: PARALLEL_WORKERS="
                    f"{raw_workers} exceeds cap 8"
                )
        except ValueError:
            problems.append(
                "process env: PARALLEL_WORKERS="
                f"{raw_workers!r} not an integer"
            )
    raw_budget = os.getenv("TIME_BUDGET_MINUTES")
    if raw_budget:
        try:
            float(raw_budget)
        except ValueError:
            problems.append(
                "process env: TIME_BUDGET_MINUTES="
                f"{raw_budget!r} not numeric"
            )
    if os.getenv("SENTRY_DSN"):
        ctx.notes.append("SENTRY_DSN present")
    else:
        ctx.notes.append("SENTRY_DSN not set (non-fatal)")
    if problems:
        return STATUS_WARN, "; ".join(problems)
    return (
        STATUS_OK,
        "process environment config within documented guardrails",
    )


def _strip_comment(line: str) -> str:
    """Return ``line`` with any comment portion removed.

    A line whose first non-space character is ``#`` is entirely a
    comment and becomes an empty string. Otherwise the line is
    truncated at the first ``" #"`` (space then hash) so a trailing
    inline comment is discarded while leaving live content intact.
    """
    if line.lstrip().startswith("#"):
        return ""
    idx = line.find(" #")
    if idx != -1:
        return line[:idx]
    return line


def _resolve_value(raw: str) -> Optional[str]:
    """Resolve a mapping right-hand side to a plain literal.

    A GitHub Actions expression (``${{ ... }}``) resolves to its
    ``|| 'fallback'`` literal -- that is the value a scheduled,
    non-dispatch run actually receives. A quoted literal has its
    matching quotes stripped. Anything else (including an
    expression with no ``||`` fallback) returns ``None``.
    """
    text = raw.strip()
    if "${{" in text:
        match = _EXPRESSION_FALLBACK_RE.search(text)
        return match.group(1) if match else None
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1]
    return text or None


def _find_key_value(lines: List[str], key: str) -> Optional[str]:
    """Return the raw right-hand side of the first line for ``key``.

    ``lines`` must already be comment-stripped -- a value that only
    ever appears on a commented line can never be found here.
    """
    pattern = re.compile(r"^\s*" + re.escape(key) + r"\s*:\s*(.*)$")
    for line in lines:
        match = pattern.match(line)
        if match:
            return match.group(1)
    return None


def _find_timeout_minutes(lines: List[str]) -> List[int]:
    """Return every live ``timeout-minutes: N`` value found, as int.

    ``lines`` must already be comment-stripped, so a commented
    ``timeout-minutes`` mention can never inflate this list.
    """
    pattern = re.compile(r"^\s*timeout-minutes\s*:\s*(\d+)")
    values = []
    for line in lines:
        match = pattern.match(line)
        if match:
            values.append(int(match.group(1)))
    return values


def _sanitize_detail_value(value: str) -> str:
    """Redact secrets-context expressions and cap echo length.

    Applied to any raw workflow value before it can reach a problem
    string or a note, so a workflow value never lands in the JSON
    report verbatim.
    """
    if _SECRETS_CONTEXT_MARKER in value:
        return _REDACTED_MARKER
    if len(value) > _DETAIL_ECHO_LIMIT:
        return value[:_DETAIL_ECHO_LIMIT] + "..."
    return value


def check_production_workflow_config(
    ctx: HealthContext, path: Optional[str] = None
) -> "tuple[str, str]":
    """WARN on production workflow config drift the env check misses.

    Reads ``.github/workflows/weekly-excel-generation.yml`` directly
    -- the authoritative source for ``PARALLEL_WORKERS``,
    ``PARALLEL_WORKERS_DISCOVERY``, and ``TIME_BUDGET_MINUTES`` --
    because the health job's own process environment never exports
    them. ``path`` defaults to the module-level ``WORKFLOW_PATH``
    resolved at call time (the pattern ``write_report`` already
    uses), so tests can point it at a temp fixture while production
    callers get the real repo file.
    """
    if path is None:
        path = WORKFLOW_PATH
    if not os.path.isfile(path):
        return (
            STATUS_CRITICAL,
            "production workflow file not found -- the billing "
            "schedule itself is missing",
        )
    with open(path, encoding="utf-8", errors="replace") as handle:
        raw_lines = handle.readlines()
    lines = [_strip_comment(line) for line in raw_lines]

    problems: List[str] = []

    for key in WORKFLOW_WORKER_KEYS:
        raw_value = _find_key_value(lines, key)
        if raw_value is None:
            ctx.notes.append(
                f"production workflow: {key} not set "
                "(engine default applies)"
            )
            continue
        resolved = _resolve_value(raw_value)
        if resolved is None:
            problems.append(
                f"{key}="
                f"{_sanitize_detail_value(raw_value)!r} could not "
                "be resolved"
            )
            continue
        try:
            worker_count = int(resolved)
        except ValueError:
            problems.append(
                f"{key}="
                f"{_sanitize_detail_value(resolved)!r} is not an "
                "integer"
            )
            continue
        if worker_count > MAX_PARALLEL_WORKERS:
            problems.append(
                f"{key}={worker_count} exceeds cap "
                f"{MAX_PARALLEL_WORKERS}"
            )
        elif worker_count < 1:
            problems.append(
                f"{key}={worker_count} is not a positive "
                "worker count"
            )

    # Asymmetry with the worker keys above is deliberate: an absent
    # worker key falls back to the engine default of 8, which sits AT
    # the documented cap (safe). An absent TIME_BUDGET_MINUTES falls
    # back to the engine default of 0 = graceful-stop budget DISABLED,
    # so the 180-minute runner ceiling would hard-kill the job and
    # lose cache/attachment-upload progress -- that is drift worth a
    # WARN, not a note.
    raw_budget = _find_key_value(lines, "TIME_BUDGET_MINUTES")
    if raw_budget is None:
        problems.append(
            "TIME_BUDGET_MINUTES not set in production workflow "
            "(engine default 0 disables the graceful-stop budget)"
        )
    else:
        resolved_budget = _resolve_value(raw_budget)
        budget: Optional[float] = None
        if resolved_budget is not None:
            try:
                budget = float(resolved_budget)
            except ValueError:
                budget = None
        if budget is None:
            problems.append(
                "TIME_BUDGET_MINUTES="
                f"{_sanitize_detail_value(raw_budget)!r} not "
                "numeric"
            )
        else:
            timeout_values = _find_timeout_minutes(lines)
            if timeout_values:
                ceiling = max(timeout_values)
                if not budget < ceiling:
                    problems.append(
                        f"TIME_BUDGET_MINUTES={budget:g} is not "
                        "strictly below timeout-minutes ceiling "
                        f"{ceiling}"
                    )
            else:
                ctx.notes.append(
                    "production workflow: no live timeout-minutes "
                    "found to compare TIME_BUDGET_MINUTES against"
                )

    if problems:
        return STATUS_WARN, "; ".join(problems)
    return (
        STATUS_OK,
        "production workflow config within documented guardrails",
    )


def overall_status(checks: List[CheckResult]) -> str:
    """Reduce check statuses to the workflow-facing overall value.

    ``skipped`` never escalates on its own -- a skip always follows
    a CRITICAL upstream cause that is already counted.
    """
    statuses = {check.status for check in checks}
    if STATUS_CRITICAL in statuses:
        return "CRITICAL"
    if STATUS_WARN in statuses:
        return "WARN"
    return "OK"


def run_checks(ctx: Optional[HealthContext] = None) -> List[CheckResult]:
    """Execute every health check in dependency order."""
    ctx = ctx or HealthContext()
    return [
        _timed("python_version", check_python_version),
        _timed("core_dependencies", check_core_dependencies),
        _timed("optional_dependencies", check_optional_dependencies),
        _timed("facade_import", check_facade_import),
        _timed(
            "smartsheet_token", lambda: check_smartsheet_token(ctx)
        ),
        _timed("smartsheet_api", lambda: check_smartsheet_api(ctx)),
        _timed("target_sheet_access", lambda: check_target_sheet(ctx)),
        _timed(
            "generated_docs_writable", check_generated_docs_writable
        ),
        _timed("config_sanity", lambda: check_config_sanity(ctx)),
        _timed(
            "production_workflow_config",
            lambda: check_production_workflow_config(ctx),
        ),
    ]


def build_report(
    checks: List[CheckResult], notes: List[str]
) -> Dict[str, Any]:
    """Assemble the JSON-serializable health report."""
    now = datetime.datetime.now(datetime.timezone.utc)
    counts: Dict[str, int] = {}
    for check in checks:
        counts[check.status] = counts.get(check.status, 0) + 1
    return {
        "overall_status": overall_status(checks),
        "generated_at_utc": now.isoformat(),
        "runtime": {
            "python": ".".join(
                str(part) for part in sys.version_info[:3]
            ),
            "platform": sys.platform,
            "github_sha": os.getenv("GITHUB_SHA", ""),
            "github_run_id": os.getenv("GITHUB_RUN_ID", ""),
        },
        "summary": counts,
        "notes": notes,
        "checks": [asdict(check) for check in checks],
    }


def write_report(
    report: Dict[str, Any], path: Optional[str] = None
) -> None:
    """Write the report JSON (UTF-8, pretty-printed).

    ``path`` defaults to the module-level ``REPORT_PATH`` resolved at
    call time (not def time) so tests can patch the module global.
    """
    if path is None:
        path = REPORT_PATH
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")


def _init_sentry_if_available() -> None:
    """Best-effort Sentry init; absence is never an error."""
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv(
                "SENTRY_ENVIRONMENT", "system-health"
            ),
            release=os.getenv("SENTRY_RELEASE") or None,
            traces_sample_rate=0.0,
        )
    except Exception:  # noqa: BLE001 - monitoring must not break us
        logger.info("⚠️ Sentry init failed (continuing without it)")


_STATUS_ICONS = {
    STATUS_OK: "✅",
    STATUS_WARN: "⚠️",
    STATUS_CRITICAL: "❌",
    STATUS_SKIPPED: "⏭️",
}


def main() -> int:
    """Run all checks, write the report, log a summary.

    Returns 0 whenever the report was written (the workflow's
    evaluate step owns pass/fail); 1 only when writing failed.
    """
    _init_sentry_if_available()
    ctx = HealthContext()
    checks = run_checks(ctx)
    report = build_report(checks, ctx.notes)

    for check in checks:
        icon = _STATUS_ICONS.get(check.status, "•")
        logger.info(
            "%s %s: %s (%d ms)",
            icon, check.name, check.detail, check.duration_ms,
        )
    logger.info("🩺 Overall status: %s", report["overall_status"])

    try:
        write_report(report)
    except Exception as exc:  # noqa: BLE001 - the one fatal path
        logger.error(
            "❌ Could not write %s: %s: %s",
            REPORT_PATH, type(exc).__name__, exc,
        )
        try:
            import sentry_sdk

            sentry_sdk.capture_exception(exc)
        except Exception:  # noqa: BLE001
            pass
        return 1
    logger.info("📄 Report written to %s", REPORT_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
