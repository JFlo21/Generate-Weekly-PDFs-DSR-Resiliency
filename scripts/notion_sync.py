#!/usr/bin/env python3
"""
Notion Sync — Pushes pipeline run data, commits, and metrics to Notion.

Called automatically by GitHub Actions after each workflow run.
Can also be run manually for backfill or debugging.

Usage:
    # Sync current run (called by CI):
    python scripts/notion_sync.py --mode run

    # Sync recent commits:
    python scripts/notion_sync.py --mode commits --since 7

    # Sync codebase metrics snapshot:
    python scripts/notion_sync.py --mode metrics

    # Full sync (all three):
    python scripts/notion_sync.py --mode all

Requires env vars:
    NOTION_TOKEN        — Integration token
    NOTION_PIPELINE_DB  — Pipeline Runs database ID
    NOTION_CHANGELOG_DB — Changelog database ID
    NOTION_METRICS_DB   — Codebase Metrics database ID
    NOTION_INCIDENTS_DB — Incidents database ID
"""

import argparse
import datetime
import json
import logging
import os
import re
import subprocess
import sys

from notion_client import Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Notion database IDs (set via env / GitHub secrets) ──────────────────────
NOTION_TOKEN        = os.getenv("NOTION_TOKEN", "")
NOTION_PIPELINE_DB  = os.getenv("NOTION_PIPELINE_DB", "")
NOTION_CHANGELOG_DB = os.getenv("NOTION_CHANGELOG_DB", "")
NOTION_METRICS_DB   = os.getenv("NOTION_METRICS_DB", "")
NOTION_INCIDENTS_DB = os.getenv("NOTION_INCIDENTS_DB", "")

# ── GitHub context (populated by Actions) ───────────────────────────────────
GITHUB_REPOSITORY  = os.getenv("GITHUB_REPOSITORY", "JFlo21/Generate-Weekly-PDFs-DSR-Resiliency")
GITHUB_SHA         = os.getenv("GITHUB_SHA", "")
GITHUB_REF_NAME    = os.getenv("GITHUB_REF_NAME", "master")
GITHUB_RUN_NUMBER  = os.getenv("GITHUB_RUN_NUMBER", "0")
GITHUB_RUN_ID      = os.getenv("GITHUB_RUN_ID", "0")
GITHUB_SERVER_URL  = os.getenv("GITHUB_SERVER_URL", "https://github.com")
GITHUB_EVENT_NAME  = os.getenv("GITHUB_EVENT_NAME", "")


def _text(content: str):
    """Helper: Notion rich_text property."""
    return {"rich_text": [{"text": {"content": str(content)[:2000]}}]}


def _title(content: str):
    """Helper: Notion title property."""
    return {"title": [{"text": {"content": str(content)[:200]}}]}


def _number(val):
    """Helper: Notion number property."""
    if val is None or val == "":
        return {"number": None}
    try:
        return {"number": float(val)}
    except (ValueError, TypeError):
        return {"number": None}


def _select(name: str):
    """Helper: Notion select property."""
    if not name:
        return {"select": None}
    return {"select": {"name": str(name)}}


def _date(iso_str: str):
    """Helper: Notion date property."""
    if not iso_str:
        return {"date": None}
    return {"date": {"start": iso_str}}


def _url(u: str):
    """Helper: Notion URL property."""
    if not u:
        return {"url": None}
    return {"url": u}


def _checkbox(val: bool):
    """Helper: Notion checkbox property."""
    return {"checkbox": bool(val)}


def _run_url():
    return f"{GITHUB_SERVER_URL}/{GITHUB_REPOSITORY}/actions/runs/{GITHUB_RUN_ID}"


def _commit_url(sha: str):
    return f"{GITHUB_SERVER_URL}/{GITHUB_REPOSITORY}/commit/{sha}"


# ── Duplicate detection ────────────────────────────────────────────────────

def _page_exists(notion: Client, db_id: str, title_prop: str, title_val: str) -> bool:
    """Check if a page with this title already exists in the database."""
    try:
        results = notion.databases.query(
            database_id=db_id,
            filter={"property": title_prop, "title": {"equals": title_val}},
            page_size=1,
        )
        return len(results.get("results", [])) > 0
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════
#  MODE: run — Sync current pipeline run
# ═══════════════════════════════════════════════════════════════════════════

def sync_run(notion: Client):
    """Push the current GitHub Actions run to the Pipeline Runs database."""
    if not NOTION_PIPELINE_DB:
        log.warning("NOTION_PIPELINE_DB not set — skipping run sync")
        return

    run_title = f"Run #{GITHUB_RUN_NUMBER}"

    # Skip if already synced (idempotent)
    if _page_exists(notion, NOTION_PIPELINE_DB, "Run", run_title):
        log.info(f"Run #{GITHUB_RUN_NUMBER} already exists in Notion — skipping")
        return

    # Read session summary from artifact manifest if available
    manifest_path = os.path.join("generated_docs", "artifact_manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)

    # Read run summary from environment (set by workflow steps)
    files_generated = os.getenv("FILES_GENERATED", manifest.get("summary", {}).get("total_files", 0))
    files_uploaded  = os.getenv("FILES_UPLOADED", "0")
    files_skipped   = os.getenv("FILES_SKIPPED", "0")
    groups_total    = os.getenv("GROUPS_TOTAL", "0")
    groups_errored  = os.getenv("GROUPS_ERRORED", "0")
    sheets_count    = os.getenv("SHEETS_DISCOVERED", "0")
    rows_fetched    = os.getenv("ROWS_FETCHED", "0")
    duration_min    = os.getenv("DURATION_MINUTES", "0")
    hash_updates    = os.getenv("HASH_UPDATES", "0")
    api_calls       = os.getenv("API_CALLS", "0")
    execution_type  = os.getenv("EXECUTION_TYPE", "manual")
    audit_risk      = os.getenv("AUDIT_RISK_LEVEL", "UNKNOWN")
    error_summary   = os.getenv("ERROR_SUMMARY", "")
    variant_breakdown = os.getenv("VARIANT_BREAKDOWN", "")
    job_status      = os.getenv("JOB_STATUS", "success")

    # Map job status to Notion select
    status_map = {
        "success": "✅ Success",
        "failure": "❌ Failed",
        "cancelled": "⏭️ Skipped",
        "timed_out": "⏰ Timed Out",
    }
    status = status_map.get(job_status, "⏳ In Progress")

    # Map trigger
    trigger_map = {
        "schedule": "⏰ Scheduled",
        "workflow_dispatch": "🖐️ Manual",
        "push": "🔄 Push",
    }
    trigger = trigger_map.get(GITHUB_EVENT_NAME, "⏰ Scheduled")
    if execution_type == "weekly_comprehensive":
        trigger = "📋 Weekly"
    elif execution_type == "weekend_maintenance":
        trigger = "🏖️ Weekend"

    properties = {
        "Run":                _title(run_title),
        "Status":             _select(status),
        "Trigger":            _select(trigger),
        "Started":            _date(datetime.datetime.now(datetime.timezone.utc).isoformat()),
        "Duration (min)":     _number(duration_min),
        "Files Generated":    _number(files_generated),
        "Files Uploaded":     _number(files_uploaded),
        "Files Skipped":      _number(files_skipped),
        "Groups Total":       _number(groups_total),
        "Groups Errored":     _number(groups_errored),
        "Sheets Discovered":  _number(sheets_count),
        "Rows Fetched":       _number(rows_fetched),
        "Variant Breakdown":  _text(variant_breakdown),
        "Commit SHA":         _text(GITHUB_SHA[:7] if GITHUB_SHA else ""),
        "Branch":             _select(GITHUB_REF_NAME if GITHUB_REF_NAME in ("master", "develop") else "feature"),
        "Run URL":            _url(_run_url()),
        "Run Number":         _number(GITHUB_RUN_NUMBER),
        "Execution Type":     _select(execution_type),
        "Hash Updates":       _number(hash_updates),
        "API Calls":          _number(api_calls),
        "Audit Risk":         _select(audit_risk if audit_risk != "UNKNOWN" else "UNKNOWN"),
        "Error Summary":      _text(error_summary),
    }

    notion.pages.create(parent={"database_id": NOTION_PIPELINE_DB}, properties=properties)
    log.info(f"✅ Synced Run #{GITHUB_RUN_NUMBER} to Notion Pipeline Runs")

    # Auto-create incident for failed runs
    if job_status == "failure" and NOTION_INCIDENTS_DB:
        _create_incident(notion, run_title, error_summary, audit_risk)


def _create_incident(notion: Client, run_title: str, error_summary: str, audit_risk: str):
    """Create an incident entry for a failed run."""
    incident_title = f"Pipeline Failure — {run_title}"
    if _page_exists(notion, NOTION_INCIDENTS_DB, "Incident", incident_title):
        return

    severity_map = {"CRITICAL": "🔴 Critical", "HIGH": "🟠 High", "MEDIUM": "🟡 Medium"}
    severity = severity_map.get(audit_risk, "🟡 Medium")

    notion.pages.create(
        parent={"database_id": NOTION_INCIDENTS_DB},
        properties={
            "Incident":      _title(incident_title),
            "Severity":      _select(severity),
            "Status":        _select("🔥 Active"),
            "Detected":      _date(datetime.datetime.now(datetime.timezone.utc).isoformat()),
            "Run Number":    _number(GITHUB_RUN_NUMBER),
            "Error Type":    _text("Pipeline Failure"),
            "Error Message": _text(error_summary[:2000]),
            "Run URL":       _url(_run_url()),
            "Commit SHA":    _text(GITHUB_SHA[:7] if GITHUB_SHA else ""),
            "Impact":        _text("Excel report generation may be incomplete"),
        },
    )
    log.info(f"⚠️ Created incident: {incident_title}")


# ═══════════════════════════════════════════════════════════════════════════
#  MODE: commits — Sync recent git commits
# ═══════════════════════════════════════════════════════════════════════════

def _classify_commit(message: str):
    """Parse conventional commit type from message."""
    msg_lower = message.lower().strip()
    type_map = {
        "feat":     "✨ feat",
        "fix":      "🐛 fix",
        "refactor": "♻️ refactor",
        "chore":    "🔧 chore",
        "docs":     "📝 docs",
        "perf":     "⚡ perf",
        "security": "🔒 security",
        "test":     "🧪 test",
        "ci":       "🔧 chore",
        "build":    "🔧 chore",
        "style":    "♻️ refactor",
    }
    # Match conventional commit format: type(scope): message
    m = re.match(r"^(\w+)(?:\(([^)]*)\))?[!]?:\s*", msg_lower)
    if m:
        ctype = m.group(1)
        scope = m.group(2) or ""
        is_breaking = "!" in message.split(":")[0] if ":" in message else False
        return type_map.get(ctype, "🔧 chore"), scope, is_breaking

    # Heuristic fallback
    if "fix" in msg_lower or "bug" in msg_lower:
        return "🐛 fix", "", False
    if "feat" in msg_lower or "add" in msg_lower:
        return "✨ feat", "", False
    if "refactor" in msg_lower:
        return "♻️ refactor", "", False
    if "security" in msg_lower or "vulnerab" in msg_lower:
        return "🔒 security", "", False
    return "🔧 chore", "", False


def sync_commits(notion: Client, since_days: int = 7):
    """Push recent git commits to the Changelog database."""
    if not NOTION_CHANGELOG_DB:
        log.warning("NOTION_CHANGELOG_DB not set — skipping commit sync")
        return

    since_date = (datetime.datetime.now() - datetime.timedelta(days=since_days)).strftime("%Y-%m-%d")

    try:
        # Get commits with stats
        result = subprocess.run(
            ["git", "log", f"--since={since_date}", "--format=%H|%s|%an|%aI", "--shortstat"],
            capture_output=True, text=True, check=True, timeout=30,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        log.warning(f"Failed to get git log: {e}")
        return

    lines = result.stdout.strip().split("\n")
    commits = []
    current = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "|" in line and len(line.split("|")) >= 4:
            # Commit line
            parts = line.split("|", 3)
            current = {
                "sha": parts[0],
                "message": parts[1],
                "author": parts[2],
                "date": parts[3],
                "files_changed": 0,
                "insertions": 0,
                "deletions": 0,
            }
            commits.append(current)
        elif current and ("file" in line or "insertion" in line or "deletion" in line):
            # Stat line: " 3 files changed, 45 insertions(+), 12 deletions(-)"
            m_files = re.search(r"(\d+) file", line)
            m_ins   = re.search(r"(\d+) insertion", line)
            m_del   = re.search(r"(\d+) deletion", line)
            if m_files:
                current["files_changed"] = int(m_files.group(1))
            if m_ins:
                current["insertions"] = int(m_ins.group(1))
            if m_del:
                current["deletions"] = int(m_del.group(1))

    synced = 0
    for c in commits:
        short_sha = c["sha"][:7]
        if _page_exists(notion, NOTION_CHANGELOG_DB, "Commit", short_sha):
            continue

        commit_type, scope, is_breaking = _classify_commit(c["message"])

        notion.pages.create(
            parent={"database_id": NOTION_CHANGELOG_DB},
            properties={
                "Commit":          _title(short_sha),
                "Message":         _text(c["message"]),
                "Author":          _text(c["author"]),
                "Date":            _date(c["date"]),
                "Type":            _select(commit_type),
                "Scope":           _text(scope),
                "Files Changed":   _number(c["files_changed"]),
                "Insertions":      _number(c["insertions"]),
                "Deletions":       _number(c["deletions"]),
                "Breaking Change": _checkbox(is_breaking),
                "Commit URL":      _url(_commit_url(c["sha"])),
            },
        )
        synced += 1

    log.info(f"📝 Synced {synced} commit(s) to Notion Changelog (checked {len(commits)} since {since_date})")


# ═══════════════════════════════════════════════════════════════════════════
#  MODE: metrics — Snapshot codebase health
# ═══════════════════════════════════════════════════════════════════════════

def sync_metrics(notion: Client):
    """Push a codebase metrics snapshot to the Metrics database."""
    if not NOTION_METRICS_DB:
        log.warning("NOTION_METRICS_DB not set — skipping metrics sync")
        return

    today = datetime.date.today().isoformat()
    snapshot_title = f"Snapshot {today}"
    if _page_exists(notion, NOTION_METRICS_DB, "Snapshot", snapshot_title):
        log.info(f"Metrics snapshot for {today} already exists — skipping")
        return

    # Count Python LOC
    python_loc = 0
    total_files = 0
    test_files = 0
    for root, dirs, files in os.walk("."):
        # Skip hidden dirs, __pycache__, node_modules, .git
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "node_modules", ".venv")]
        for f in files:
            total_files += 1
            if f.endswith(".py"):
                if "test" in f.lower():
                    test_files += 1
                try:
                    with open(os.path.join(root, f), "r", errors="ignore") as fh:
                        python_loc += sum(1 for line in fh if line.strip() and not line.strip().startswith("#"))
                except Exception:
                    pass

    # Count dependencies from requirements.txt
    dep_count = 0
    if os.path.exists("requirements.txt"):
        with open("requirements.txt", encoding="utf-8", errors="ignore") as f:
            dep_count = sum(1 for line in f if line.strip() and not line.startswith("#"))

    # Count source sheets (hardcoded IDs in generate_weekly_pdfs.py)
    source_sheets = 0
    if os.path.exists("generate_weekly_pdfs.py"):
        with open("generate_weekly_pdfs.py", "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            # Count lines matching the "# Added" pattern in base_sheet_ids
            source_sheets = len(re.findall(r"^\s+\d{10,},?\s*#", content, re.MULTILINE))
            # Add the first few that don't have comments
            source_sheets += len(re.findall(r"^\s+\d{10,},\s*$", content, re.MULTILINE))

    # Count workflow steps
    workflow_steps = 0
    wf_path = os.path.join(".github", "workflows", "weekly-excel-generation.yml")
    if os.path.exists(wf_path):
        with open(wf_path, encoding="utf-8", errors="ignore") as f:
            workflow_steps = sum(1 for line in f if line.strip().startswith("- name:"))

    # Cache version from generate_weekly_pdfs.py
    cache_version = 1
    if os.path.exists("generate_weekly_pdfs.py"):
        with open("generate_weekly_pdfs.py", encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = re.search(r"DISCOVERY_CACHE_VERSION\s*=\s*(\d+)", line)
                if m:
                    cache_version = int(m.group(1))
                    break

    notion.pages.create(
        parent={"database_id": NOTION_METRICS_DB},
        properties={
            "Snapshot":              _title(snapshot_title),
            "Date":                  _date(today),
            "Python LOC":            _number(python_loc),
            "Total Files":           _number(total_files),
            "Test Files":            _number(test_files),
            "Source Sheets":         _number(source_sheets),
            "Dependencies":          _number(dep_count),
            "Workflow Steps":        _number(workflow_steps),
            "Cache Version":         _number(cache_version),
        },
    )
    log.info(f"📊 Synced codebase metrics snapshot for {today}")


# ═══════════════════════════════════════════════════════════════════════════
#  Dashboard KPI Auto-Update
# ═══════════════════════════════════════════════════════════════════════════

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "notion_config.json")


def _load_kpi_config() -> dict:
    """Load KPI block IDs from notion_config.json."""
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("kpi_blocks", {})
    except Exception:
        return {}


def _update_callout(notion, block_id, emoji, rich_texts, color):
    """Update a callout block's content."""
    notion.blocks.update(
        block_id=block_id,
        callout={
            "rich_text": rich_texts,
            "icon": {"type": "emoji", "emoji": emoji},
            "color": color,
        },
    )


def _rt(text, bold=False, italic=False, color="default"):
    """Quick rich_text element builder."""
    return {
        "type": "text",
        "text": {"content": text},
        "annotations": {
            "bold": bold, "italic": italic, "strikethrough": False,
            "underline": False, "code": False, "color": color,
        },
    }


def update_dashboard_kpis(notion):
    """Query Pipeline Runs DB and update the 4 KPI callout blocks on the dashboard."""
    kpi_blocks = _load_kpi_config()
    if not kpi_blocks:
        log.info("📊 No KPI blocks configured — skipping dashboard update")
        return

    if not NOTION_PIPELINE_DB:
        return

    # Query all pipeline runs for statistics
    try:
        all_runs = []
        has_more = True
        start_cursor = None
        while has_more:
            params = {"database_id": NOTION_PIPELINE_DB, "page_size": 100}
            if start_cursor:
                params["start_cursor"] = start_cursor
            resp = notion.databases.query(**params)
            all_runs.extend(resp.get("results", []))
            has_more = resp.get("has_more", False)
            start_cursor = resp.get("next_cursor")

        total_runs = len(all_runs)
        if total_runs == 0:
            log.info("📊 No pipeline runs found — KPIs show defaults")
            return

        # Compute statistics
        success_count = 0
        total_duration = 0
        duration_count = 0
        last_run_status = "—"
        last_run_date = ""

        for run in all_runs:
            props = run.get("properties", {})

            # Status
            status_prop = props.get("Status", {}).get("select")
            if status_prop:
                name = status_prop.get("name", "")
                if "Success" in name:
                    success_count += 1

            # Duration
            dur = props.get("Duration (min)", {}).get("number")
            if dur is not None and dur > 0:
                total_duration += dur
                duration_count += 1

            # Last run (by Started date)
            started = props.get("Started", {}).get("date")
            if started and started.get("start"):
                run_date = started["start"]
                if run_date > last_run_date:
                    last_run_date = run_date
                    last_run_status = status_prop.get("name", "—") if status_prop else "—"

        success_rate = round(success_count / total_runs * 100) if total_runs > 0 else 0
        avg_duration = round(total_duration / duration_count, 1) if duration_count > 0 else 0

        # Determine KPI colors
        last_emoji = "🟢" if "Success" in last_run_status else "🔴" if "Failed" in last_run_status else "🟡"
        last_color = "green_background" if "Success" in last_run_status else "red_background" if "Failed" in last_run_status else "yellow_background"
        rate_color = "green_background" if success_rate >= 90 else "yellow_background" if success_rate >= 70 else "red_background"

        # Format last run date
        last_date_display = last_run_date[:10] if last_run_date else "—"

        # Update KPI blocks
        if "Last Run" in kpi_blocks:
            _update_callout(notion, kpi_blocks["Last Run"], last_emoji, [
                _rt(f"{last_run_status}\n", bold=True),
                _rt("Last Run\n"),
                _rt(last_date_display, italic=True, color="gray"),
            ], last_color)

        if "Success Rate" in kpi_blocks:
            _update_callout(notion, kpi_blocks["Success Rate"], "📈", [
                _rt(f"{success_rate}%\n", bold=True),
                _rt("Success Rate\n"),
                _rt(f"{success_count}/{total_runs} runs", italic=True, color="gray"),
            ], rate_color)

        if "Total Runs" in kpi_blocks:
            _update_callout(notion, kpi_blocks["Total Runs"], "📊", [
                _rt(f"{total_runs}\n", bold=True),
                _rt("Total Runs\n"),
                _rt("Since tracking began", italic=True, color="gray"),
            ], "purple_background")

        if "Avg Duration" in kpi_blocks:
            _update_callout(notion, kpi_blocks["Avg Duration"], "⏱️", [
                _rt(f"{avg_duration} min\n", bold=True),
                _rt("Avg Duration\n"),
                _rt(f"Across {duration_count} timed runs", italic=True, color="gray"),
            ], "orange_background")

        log.info(f"📊 Dashboard KPIs updated — {total_runs} runs, {success_rate}% success, {avg_duration} min avg")

    except Exception as e:
        log.warning(f"⚠️  KPI update failed (non-fatal): {e}")


# ═══════════════════════════════════════════════════════════════════════════
#  CLI entry point
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Sync DSR Resiliency data to Notion")
    parser.add_argument("--mode", choices=["run", "commits", "metrics", "all"], default="all",
                        help="What to sync (default: all)")
    parser.add_argument("--since", type=int, default=7,
                        help="For commits mode: sync commits from the last N days (default: 7)")
    parser.add_argument("--skip-kpi", action="store_true",
                        help="Skip dashboard KPI update")
    args = parser.parse_args()

    if not NOTION_TOKEN:
        log.error("❌ NOTION_TOKEN not set. Run `python scripts/notion_setup.py` first.")
        sys.exit(1)

    notion = Client(auth=NOTION_TOKEN)

    if args.mode in ("run", "all"):
        sync_run(notion)

    if args.mode in ("commits", "all"):
        sync_commits(notion, since_days=args.since)

    if args.mode in ("metrics", "all"):
        sync_metrics(notion)

    # Update dashboard KPIs after sync (if configured)
    if not args.skip_kpi:
        update_dashboard_kpis(notion)

    log.info("🎉 Notion sync complete")


if __name__ == "__main__":
    main()
