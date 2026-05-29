"""Publish generated Excel artifacts to Supabase Storage + public.artifacts.

Additive post-billing CI step.  Designed to be loud-but-non-fatal:
all exceptions are caught, reported to Sentry and $GITHUB_STEP_SUMMARY,
and the script exits 0 so a Supabase outage **never** fails the billing run
(D-06 contract, on top of the workflow's continue-on-error: true).

Usage (invoked as an additive GitHub Actions step):
    python scripts/publish_artifacts_to_supabase.py generated_docs

Environment variables consumed:
    SUPABASE_URL                -- Supabase project URL (never logged)
    SUPABASE_SERVICE_ROLE_KEY   -- service_role JWT (never logged)
    GITHUB_RUN_ID               -- injected by GitHub Actions; default "local"
    GITHUB_STEP_SUMMARY         -- injected by GitHub Actions; written on any outcome
    TEST_MODE                   -- if "true"/"1"/"yes"/"on", skip publish
    SKIP_UPLOAD                 -- if "true"/"1"/"yes"/"on", skip publish (local dry-run)
    SENTRY_DSN                  -- optional; Sentry errors only if configured

Security posture (threat model T-03-*):
    - SUPABASE_SERVICE_ROLE_KEY is read inside billing_audit.client.get_client();
      it is never printed, logged, or passed to sentry_sdk payloads here.
    - Per-file failure messages contain only type(exc).__name__ + aggregate count,
      never the raw filename (Pitfall D / T-03-pii-sentry).
    - Unknown variant tokens are captured to Sentry (type+count, no PII) and
      still inserted -- no DB CHECK to hard-drop a future 8th variant.

Reuse targets (do NOT re-implement these):
    billing_audit.client.get_client        -- Supabase client (TEST_MODE-aware)
    billing_audit.client.with_retry        -- bounded retry + circuit breaker
    scripts.generate_artifact_manifest.calculate_file_hash  -- chunked SHA256
    scripts.generate_artifact_manifest.parse_excel_filename -- WR/week positions 1/3
"""

from __future__ import annotations

import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Repo-root path injection so ``python scripts/publish_artifacts_to_supabase.py``
# can import ``billing_audit.*`` and ``scripts.*`` regardless of CWD.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Reuse imports (battle-tested; do NOT re-implement)
# ---------------------------------------------------------------------------
from billing_audit.client import get_client, with_retry  # noqa: E402
from scripts.generate_artifact_manifest import (  # noqa: E402
    calculate_file_hash,
    parse_excel_filename,
)

# ---------------------------------------------------------------------------
# Lazy Sentry import -- no-op when SDK is not initialized or not installed
# ---------------------------------------------------------------------------
try:
    import sentry_sdk  # type: ignore
except Exception:
    sentry_sdk = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [publish_artifacts] %(message)s",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_BUCKET = "excel-artifacts"

# The 7 canonical variant values (no CHECK constraint on the DB; this set is
# used for the application-level unknown-token guard -- Pitfall E / Anti-Pattern E).
_CANONICAL_VARIANTS: frozenset[str] = frozenset({
    "primary",
    "helper",
    "vac_crew",
    "aep_billable",
    "reduced_sub",
    "aep_billable_helper",
    "reduced_sub_helper",
})


# ===========================================================================
# Environment guards
# ===========================================================================

def _is_test_mode() -> bool:
    """Match the pipeline's TEST_MODE semantics without importing it."""
    return os.getenv("TEST_MODE", "false").lower() in ("1", "true", "yes", "on")


def _skip_upload() -> bool:
    """Honor SKIP_UPLOAD=true for local dry-runs (mirrors generate_weekly_pdfs.py)."""
    return os.getenv("SKIP_UPLOAD", "false").lower() in ("1", "true", "yes", "on")


# ===========================================================================
# Variant normalizer (7-way precedence chain)
# ===========================================================================

def normalize_variant(filename: str) -> str:
    """Map filename suffix tokens to one of the 7 canonical snake_case variant values.

    Precedence mirrors generate_weekly_pdfs.py L2834:
        AEPBillable -> ReducedSub -> VacCrew -> Helper -> User
    Most-specific tokens checked first to prevent _AEPBillable_Helper_ matching
    _Helper_ alone (the two hybrid forms must outrank their component forms).

    Args:
        filename: Excel filename (basename only or full path string).

    Returns:
        One of the 7 canonical variant strings.
    """
    if "_AEPBillable_Helper_" in filename:
        return "aep_billable_helper"
    if "_ReducedSub_Helper_" in filename:
        return "reduced_sub_helper"
    if "_AEPBillable" in filename:
        return "aep_billable"
    if "_ReducedSub" in filename:
        return "reduced_sub"
    if "_VacCrew" in filename:
        return "vac_crew"
    if "_Helper_" in filename:
        return "helper"
    # Bare primary or _User_ named primary (Subproject D)
    return "primary"


# ===========================================================================
# Stable filename parsing (positions 1 & 3 only)
# ===========================================================================

def _parse_stable(filename: str) -> dict | None:
    """Return {'work_request': str, 'week_ending': str} from stable positions.

    Delegates to ``parse_excel_filename`` for the position-stable fields
    (WR at parts[1], MMDDYY at parts[3]).  Do NOT read 'timestamp' or
    'data_hash' from the returned dict -- those positions are fragile for
    non-bare-primary variant filenames (RESEARCH.md Item 2 / Pitfall A).

    Returns None if the filename does not match the WR_ pattern.
    """
    parsed = parse_excel_filename(filename)
    if parsed is None:
        return None
    return {
        "work_request": parsed["work_request"],
        "week_ending": parsed["week_ending"],
    }


# ===========================================================================
# MMDDYY -> ISO date conversion
# ===========================================================================

def _mmddyy_to_iso(mmddyy: str) -> str | None:
    """Convert MMDDYY string to ISO date string 'YYYY-MM-DD'.

    Returns None (rather than raising) on malformed input so callers can
    decide whether to skip the file or re-raise.  The test contract says
    malformed input must raise ValueError/TypeError OR return None -- never
    insert a null / garbage date.

    Args:
        mmddyy: Six-character date string, e.g. '051725'.

    Returns:
        ISO date string e.g. '2025-05-17', or None on parse failure.
    """
    try:
        return datetime.strptime(mmddyy, "%m%d%y").date().isoformat()
    except (ValueError, TypeError):
        return None


# ===========================================================================
# File collection
# ===========================================================================

def collect_xlsx_files(docs_folder: Path) -> list[Path]:
    """Scan docs_folder root + YYYY-MM-DD week subfolders for WR_*.xlsx files.

    Mirrors the scan logic in ``generate_artifact_manifest.py`` L100-120 so
    files written into week-dated subfolders are not missed (Open Question 3
    in RESEARCH.md).

    Args:
        docs_folder: Path to the generated_docs root folder.

    Returns:
        List of Path objects for each matching .xlsx file found.
    """
    files: list[Path] = []
    if not docs_folder.exists():
        return files

    # Root-level WR_*.xlsx files
    for entry in docs_folder.iterdir():
        if entry.is_file() and entry.name.startswith("WR_") and entry.suffix == ".xlsx":
            files.append(entry)

    # YYYY-MM-DD week subfolders
    for subfolder in docs_folder.iterdir():
        if subfolder.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", subfolder.name):
            for entry in subfolder.iterdir():
                if (
                    entry.is_file()
                    and entry.name.startswith("WR_")
                    and entry.suffix == ".xlsx"
                ):
                    files.append(entry)

    return files


# ===========================================================================
# Per-file publish
# ===========================================================================

def publish_file(client: Any, local_path: Path, docs_folder: Path) -> bool:
    """Upload one .xlsx to Storage and upsert its metadata row.

    Uses ``with_retry`` for both the Storage upload and the table upsert so
    the script inherits billing_audit's battle-tested bounded-retry, per-op
    circuit breaker, and SQLSTATE/PGRST error classification (RESEARCH.md
    Item 7 / PATTERNS.md Pattern 2).

    Args:
        client:      Supabase client from get_client().
        local_path:  Absolute path to the local .xlsx file.
        docs_folder: Root folder (used for context, not currently in the path).

    Returns:
        True on success; False on skipped/failed (caller continues the loop).
    """
    filename = local_path.name

    # -- Parse WR and week from stable positions 1 & 3 --
    parsed = _parse_stable(filename)
    if parsed is None:
        logging.warning(
            "WARNING: Skipping unparseable filename (type=ParseFailure, count=1)"
        )
        return False

    wr = parsed["work_request"]
    mmddyy = parsed["week_ending"]

    # -- Variant (normalizer, not positional parser) --
    variant = normalize_variant(filename)

    # Application-level guard for unknown future variants (Pitfall E).
    # Capture to Sentry (type+count, NO filename PII) and still attempt insert.
    if variant not in _CANONICAL_VARIANTS:
        logging.warning(
            "WARNING: Unknown variant token (type=UnknownVariant, count=1)"
        )
        if sentry_sdk is not None:
            sentry_sdk.capture_message(
                "publish_artifacts: UnknownVariant encountered (count=1)",
                level="warning",
            )
        # Fall through -- still insert the row (no DB CHECK blocks it)

    # -- SHA256 from file bytes (not the filename's embedded hash token) --
    sha256_hex = calculate_file_hash(str(local_path))
    if sha256_hex is None:
        logging.warning(
            "WARNING: Could not hash file (type=HashFailure, count=1)"
        )
        return False

    # -- MMDDYY -> ISO date --
    week_ending_iso = _mmddyy_to_iso(mmddyy)
    if week_ending_iso is None:
        logging.warning(
            "WARNING: Malformed week_ending date (type=DateParseFailure, count=1)"
        )
        return False

    storage_path = f"{week_ending_iso}/{filename}"
    size_bytes = local_path.stat().st_size
    run_id = os.environ.get("GITHUB_RUN_ID", "local")

    # -- Storage upload (wrapped in with_retry for bounded retry + circuit breaker) --
    def _upload() -> None:
        with open(local_path, "rb") as fh:
            client.storage.from_(_BUCKET).upload(
                path=storage_path,
                file=fh.read(),
                file_options={
                    "content-type": (
                        "application/vnd.openxmlformats-officedocument"
                        ".spreadsheetml.sheet"
                    ),
                    # supabase-py 2.9.1: string "true" is the documented
                    # file_options upsert keyword (verified against the installed
                    # storage3 version bundled with supabase==2.9.1).
                    "upsert": "true",
                },
            )

    with_retry(_upload, op="artifact_storage_upload")
    # with_retry returns None on exhausted/classified-permanent failure;
    # we do NOT abort here -- still attempt the metadata upsert (the row
    # being present without the file is preferable to losing both).

    # -- Metadata upsert (idempotent on sha256, D-08) --
    row: dict[str, Any] = {
        "work_request":    wr,
        "week_ending":     week_ending_iso,
        "week_ending_fmt": mmddyy,
        "variant":         variant,
        "filename":        filename,
        "storage_path":    storage_path,
        "size_bytes":      size_bytes,
        "sha256":          sha256_hex,
        "run_id":          run_id,
    }
    with_retry(
        lambda: client.table("artifacts").upsert(row, on_conflict="sha256").execute(),
        op="artifact_table_upsert",
    )

    return True


# ===========================================================================
# Summary helper (D-06 loud-on-failure contract)
# ===========================================================================

def _emit_summary(message: str) -> None:
    """Write a summary line to $GITHUB_STEP_SUMMARY (if set) and log WARNING.

    Both channels are written so a Supabase outage is visible in:
    - The GitHub Actions step summary UI (operator-facing)
    - The workflow run log (searchable via the Actions log viewer)
    """
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        try:
            with open(summary_file, "a", encoding="utf-8") as fh:
                fh.write(f"- {message}\n")
        except OSError:
            pass  # Cannot write summary -- log-only fallback below
    logging.warning(message)


# ===========================================================================
# Entry point
# ===========================================================================

def main(docs_folder_arg: str) -> None:
    """Scan docs_folder, upload each WR_*.xlsx to Supabase, upsert metadata row.

    Designed to be exception-safe: any uncaught exception at any point exits 0
    with a loud WARNING + $GITHUB_STEP_SUMMARY line.  This is the D-06
    defense-in-depth on top of the workflow's continue-on-error: true.

    Args:
        docs_folder_arg: Path to the generated_docs folder (CLI arg or default).
    """
    # -- Env guards (TEST_MODE / SKIP_UPLOAD for local dry-runs) --
    if _is_test_mode() or _skip_upload():
        logging.info(
            "INFO: publish_artifacts_to_supabase skipped (TEST_MODE or SKIP_UPLOAD)"
        )
        return

    # -- Supabase client (None on outage / missing creds / global-kill) --
    client = get_client()
    if client is None:
        _emit_summary(
            "WARNING: publish_artifacts_to_supabase: Supabase client unavailable"
            " -- artifact publish skipped (check SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY)"
        )
        return

    docs_folder = Path(docs_folder_arg)
    files = collect_xlsx_files(docs_folder)
    if not files:
        logging.info(
            "INFO: publish_artifacts_to_supabase: no WR_*.xlsx files found in %s"
            " -- nothing to publish",
            docs_folder,
        )
        return

    failed: list[str] = []
    published = 0

    for f in files:
        try:
            ok = publish_file(client, f, docs_folder)
            if ok:
                published += 1
        except Exception as exc:
            failed.append(f.name)
            # Capture to Sentry with NO PII in the message body (T-03-pii-sentry).
            # The exception object itself (which may contain PII from the filename)
            # is passed to capture_exception -- Sentry's before_send hook in the
            # pipeline applies _redact_exception_message to strip PII there.
            if sentry_sdk is not None:
                sentry_sdk.capture_exception(exc)
            # Log only the exception type name + aggregate count (Pitfall D).
            logging.warning(
                "WARNING: publish_artifacts_to_supabase failed for %d file(s): %s",
                len(failed),
                type(exc).__name__,
            )

    _emit_summary(
        f"publish_artifacts_to_supabase: published={published} failed={len(failed)}"
    )


if __name__ == "__main__":
    docs_folder_arg = sys.argv[1] if len(sys.argv) > 1 else "generated_docs"
    main(docs_folder_arg)
