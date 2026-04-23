"""One-shot backfill CLI for the attribution snapshot table.

Populates ``billing_audit.attribution_snapshot`` from current
completed rows in Smartsheet for a specified week. Idempotent
because of the first-write-wins RPC, so it can safely be rerun.

Usage:
    python scripts/backfill_attribution_snapshot.py --week=112624
    python scripts/backfill_attribution_snapshot.py --week=112624 --wr=91467680

Requires ``SUPABASE_URL`` + ``SUPABASE_SERVICE_ROLE_KEY`` and
``SMARTSHEET_API_TOKEN`` in the environment. Exits non-zero if the
Supabase client cannot initialize (backfill cannot run without it).
"""

from __future__ import annotations

import argparse
import datetime
import logging
import os
import sys
from pathlib import Path

# Allow running the script from anywhere in the repo.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _parse_week_mmddyy(token: str) -> datetime.date:
    """Parse a MMDDYY token into a date (two-digit year → 2000+YY)."""
    if len(token) != 6 or not token.isdigit():
        raise argparse.ArgumentTypeError(
            f"--week must be MMDDYY (e.g. 112624); got {token!r}"
        )
    month = int(token[0:2])
    day = int(token[2:4])
    year = 2000 + int(token[4:6])
    return datetime.date(year, month, day)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill billing_audit.attribution_snapshot for a given "
            "week's completed rows."
        )
    )
    parser.add_argument(
        "--week",
        required=True,
        type=_parse_week_mmddyy,
        help="Target week ending date in MMDDYY format (e.g. 112624).",
    )
    parser.add_argument(
        "--wr",
        action="append",
        default=[],
        help=(
            "Restrict to one or more WR numbers. Repeat flag for "
            "multiple (e.g. --wr 91467680 --wr 91467681)."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    from billing_audit import writer as ba_writer
    from billing_audit.client import get_client, get_flag

    client = get_client()
    if client is None:
        logging.error(
            "❌ Supabase client unavailable — set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY (and unset TEST_MODE) before "
            "running the backfill."
        )
        return 2

    # Fail fast if the feature flag is off. ``freeze_row`` is a
    # silent no-op when ``write_attribution_snapshot`` is disabled,
    # and a one-shot backfill that reports success while writing
    # zero rows is the worst of both worlds — it gives operators
    # false confidence that the snapshot table is populated.
    if not get_flag("write_attribution_snapshot", default=False):
        logging.error(
            "❌ billing_audit.feature_flag.write_attribution_snapshot "
            "is DISABLED. freeze_row() would no-op for every row. "
            "Enable the flag in Supabase before running the backfill "
            "(UPDATE billing_audit.feature_flag SET enabled=TRUE "
            "WHERE flag_key='write_attribution_snapshot';)."
        )
        return 5

    # Import the main pipeline's discovery/fetch helpers. Must match
    # the function names exported by ``generate_weekly_pdfs``.
    try:
        from generate_weekly_pdfs import (  # type: ignore
            discover_source_sheets,
            get_all_source_rows,
            excel_serial_to_date,
            is_checked,
        )
        import smartsheet  # type: ignore
    except Exception as exc:
        logging.error(
            f"❌ Could not import pipeline helpers: "
            f"{type(exc).__name__}: {exc}"
        )
        return 3

    token = os.getenv("SMARTSHEET_API_TOKEN")
    if not token:
        logging.error("❌ SMARTSHEET_API_TOKEN is not set.")
        return 4

    ss_client = smartsheet.Smartsheet(token)
    ss_client.errors_as_exceptions(True)

    logging.info("🔎 Discovering source sheets …")
    sheets = discover_source_sheets(ss_client)
    logging.info(f"📄 Discovered {len(sheets)} source sheet(s).")

    logging.info("📥 Fetching rows from all source sheets …")
    all_rows = get_all_source_rows(ss_client, sheets)
    logging.info(f"📦 Fetched {len(all_rows)} total row(s).")

    target_week = args.week
    wr_filter: set[str] = {str(w) for w in args.wr}

    release = os.getenv("SENTRY_RELEASE")
    run_id = os.getenv(
        "GITHUB_RUN_ID",
        f"backfill-{datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
    )

    considered = 0
    frozen_attempts = 0
    for row in all_rows:
        logged_raw = row.get("Weekly Reference Logged Date")
        logged_date = excel_serial_to_date(logged_raw)
        if not logged_date:
            continue
        if hasattr(logged_date, "date"):
            logged_date = logged_date.date()
        if logged_date != target_week:
            continue
        considered += 1
        if wr_filter:
            raw_wr = row.get("Work Request #")
            wr_str = str(raw_wr).split(".")[0] if raw_wr is not None else ""
            if wr_str not in wr_filter:
                continue
        if not is_checked(row.get("Units Completed?")):
            continue
        # Inject __week_ending_date so freeze_row doesn't have to
        # re-parse. Matches the main loop's contract.
        row["__week_ending_date"] = datetime.datetime.combine(
            target_week, datetime.time.min
        )
        frozen_attempts += 1
        try:
            ba_writer.freeze_row(row, release=release, run_id=run_id)
        except Exception as exc:
            logging.warning(
                f"⚠️ freeze_row failed: {type(exc).__name__} "
                "(continuing backfill)"
            )

    counters = ba_writer.get_counters()
    logging.info("✅ Backfill complete.")
    logging.info(
        f"   Rows matched week {target_week.strftime('%m/%d/%y')}: "
        f"{considered}"
    )
    logging.info(f"   Freeze attempts: {frozen_attempts}")
    logging.info(f"   Counters: {counters}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
