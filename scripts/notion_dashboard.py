#!/usr/bin/env python3
"""
Notion Dashboard Builder — Creates a professional Operations Dashboard page
with live KPI blocks, database cross-references, view setup guides, and
rich formatting.

Creates a child page under the parent Notion page with:
  • Live KPI callout cards (auto-updated by notion_sync.py)
  • @database mentions linking to each of the 4 databases
  • Recommended view instructions for each database
  • Quick-links section to GitHub, Actions, API docs
  • Full view setup guide

Run once after notion_setup.py has created the databases:
    python scripts/notion_dashboard.py

Requires env vars:
    NOTION_TOKEN       — Internal integration token
    NOTION_PARENT_PAGE — ID of the parent Notion page
    NOTION_PIPELINE_DB, NOTION_CHANGELOG_DB, NOTION_METRICS_DB, NOTION_INCIDENTS_DB
"""

import json
import os
import sys
from datetime import datetime, timezone

from notion_client import Client

# ── Environment ─────────────────────────────────────────────────────────────
NOTION_TOKEN       = os.getenv("NOTION_TOKEN", "")
NOTION_PARENT_PAGE = os.getenv("NOTION_PARENT_PAGE", "")
NOTION_PIPELINE_DB = os.getenv("NOTION_PIPELINE_DB", "")
NOTION_CHANGELOG_DB = os.getenv("NOTION_CHANGELOG_DB", "")
NOTION_METRICS_DB  = os.getenv("NOTION_METRICS_DB", "")
NOTION_INCIDENTS_DB = os.getenv("NOTION_INCIDENTS_DB", "")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "notion_config.json")
GITHUB_REPO = "JFlo21/Generate-Weekly-PDFs-DSR-Resiliency"


def _load_config():
    """Load database IDs and parent page from config file if env vars not set."""
    global NOTION_PARENT_PAGE, NOTION_PIPELINE_DB, NOTION_CHANGELOG_DB, NOTION_METRICS_DB, NOTION_INCIDENTS_DB
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        NOTION_PARENT_PAGE  = NOTION_PARENT_PAGE  or cfg.get("parent_page", "")
        dbs = cfg.get("databases", {})
        NOTION_PIPELINE_DB  = NOTION_PIPELINE_DB  or dbs.get("pipeline_runs", "")
        NOTION_CHANGELOG_DB = NOTION_CHANGELOG_DB or dbs.get("changelog", "")
        NOTION_METRICS_DB   = NOTION_METRICS_DB   or dbs.get("metrics", "")
        NOTION_INCIDENTS_DB = NOTION_INCIDENTS_DB  or dbs.get("incidents", "")


def _require_env():
    missing = []
    if not NOTION_TOKEN:       missing.append("NOTION_TOKEN")
    if not NOTION_PARENT_PAGE: missing.append("NOTION_PARENT_PAGE")
    if not NOTION_PIPELINE_DB: missing.append("NOTION_PIPELINE_DB")
    if missing:
        print(f"❌ Missing: {', '.join(missing)}")
        print("Run notion_setup.py first, or set env vars / check notion_config.json")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════
#  Block Builder Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _rich(text, bold=False, italic=False, code=False, color="default", link=None):
    """Build a single rich_text element."""
    rt = {
        "type": "text",
        "text": {"content": text},
        "annotations": {
            "bold": bold, "italic": italic, "strikethrough": False,
            "underline": False, "code": code, "color": color,
        },
    }
    if link:
        rt["text"]["link"] = {"url": link}
    return rt


def _db_mention(db_id):
    """Build a rich_text mention referencing a database."""
    return {
        "type": "mention",
        "mention": {"type": "database", "database": {"id": db_id}},
    }


def heading(level, text, color="default", toggleable=False):
    key = f"heading_{level}"
    return {
        "object": "block", "type": key,
        key: {
            "rich_text": [_rich(text)],
            "color": color,
            "is_toggleable": toggleable,
        },
    }


def paragraph(rich_texts, color="default"):
    if isinstance(rich_texts, str):
        rich_texts = [_rich(rich_texts)]
    return {
        "object": "block", "type": "paragraph",
        "paragraph": {"rich_text": rich_texts, "color": color},
    }


def callout(rich_texts, emoji, color="default"):
    if isinstance(rich_texts, str):
        rich_texts = [_rich(rich_texts)]
    return {
        "object": "block", "type": "callout",
        "callout": {
            "rich_text": rich_texts,
            "icon": {"type": "emoji", "emoji": emoji},
            "color": color,
        },
    }


def divider():
    return {"object": "block", "type": "divider", "divider": {}}


def table_of_contents(color="default"):
    return {"object": "block", "type": "table_of_contents", "table_of_contents": {"color": color}}


def bookmark(url, caption=""):
    bm = {"object": "block", "type": "bookmark", "bookmark": {"url": url, "caption": []}}
    if caption:
        bm["bookmark"]["caption"] = [_rich(caption)]
    return bm


def toggle(rich_texts, children, color="default"):
    if isinstance(rich_texts, str):
        rich_texts = [_rich(rich_texts)]
    return {
        "object": "block", "type": "toggle",
        "toggle": {"rich_text": rich_texts, "color": color, "children": children},
    }


def bullet(text, children=None):
    b = {
        "object": "block", "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": [_rich(text)], "color": "default"},
    }
    if children:
        b["bulleted_list_item"]["children"] = children
    return b


def numbered(text, children=None):
    n = {
        "object": "block", "type": "numbered_list_item",
        "numbered_list_item": {"rich_text": [_rich(text)], "color": "default"},
    }
    if children:
        n["numbered_list_item"]["children"] = children
    return n


def quote(text, color="default"):
    return {
        "object": "block", "type": "quote",
        "quote": {"rich_text": [_rich(text)], "color": color},
    }


def column_list(columns):
    """Build a column_list with column children. Each column is a list of blocks."""
    col_blocks = []
    for col_children in columns:
        col_blocks.append({
            "object": "block", "type": "column",
            "column": {"children": col_children},
        })
    return {
        "object": "block", "type": "column_list",
        "column_list": {"children": col_blocks},
    }


def todo(text, checked=False):
    return {
        "object": "block", "type": "to_do",
        "to_do": {"rich_text": [_rich(text)], "checked": checked, "color": "default"},
    }


def code_block(text, language="plain text"):
    return {
        "object": "block", "type": "code",
        "code": {
            "rich_text": [_rich(text)],
            "language": language,
            "caption": [],
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
#  KPI Card Builders (callout blocks that get updated by sync)
# ═══════════════════════════════════════════════════════════════════════════

def kpi_card(emoji, label, value, subtitle, color):
    """Build a KPI callout card."""
    return callout(
        [
            _rich(f"{value}\n", bold=True),
            _rich(f"{label}\n", bold=False),
            _rich(subtitle, italic=True, color="gray"),
        ],
        emoji=emoji,
        color=color,
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Database Section Builders
# ═══════════════════════════════════════════════════════════════════════════

def db_section(title, emoji, db_id, description, view_instructions):
    """Build a full database section: heading + description + @mention + views toggle."""
    blocks = [
        heading(2, f"{emoji} {title}"),
        callout(
            [
                _rich(description + "\n\n"),
                _rich("Open database → ", bold=True),
                _db_mention(db_id),
            ],
            emoji=emoji,
            color="gray_background",
        ),
        toggle(
            [_rich("💡 Recommended Views  ", bold=True), _rich("(click to expand)", italic=True, color="gray")],
            children=view_instructions,
        ),
        divider(),
    ]
    return blocks


# ═══════════════════════════════════════════════════════════════════════════
#  View Instructions for Each Database
# ═══════════════════════════════════════════════════════════════════════════

def pipeline_views():
    return [
        callout(
            [_rich("To create views: Open the database → Click ", bold=False),
             _rich("+ Add a view", bold=True, code=True),
             _rich(" at the top left")],
            emoji="💡", color="yellow_background",
        ),
        heading(3, "📋 Table View — All Runs"),
        bullet("This is the default view — already created"),
        bullet("Sort: \"Started\" → Descending (newest first)"),
        bullet("Visible columns: Status, Trigger, Started, Duration, Files Generated, Files Uploaded, Audit Risk"),
        bullet("Hide: Commit SHA, Run URL, API Calls, Error Summary (show on expand)"),
        paragraph(""),
        heading(3, "🗂️ Board View — By Status"),
        numbered("Click + Add a view → select Board"),
        numbered("Group by: Status"),
        numbered("Card preview: show Duration (min), Files Generated, Trigger"),
        numbered("This gives you a Kanban-style view: ✅ Success | ❌ Failed | ⏳ In Progress"),
        paragraph(""),
        heading(3, "📅 Calendar View — Run Timeline"),
        numbered("Click + Add a view → select Calendar"),
        numbered("Date property: Started"),
        numbered("Shows run dots on each calendar day — great for spotting gaps"),
        paragraph(""),
        heading(3, "🔍 Filtered View — Failed Runs Only"),
        numbered("Click + Add a view → select Table"),
        numbered("Rename it to \"Failed Runs\""),
        numbered("Add filter: Status = ❌ Failed"),
        numbered("Sort: Started → Descending"),
        numbered("This isolates all failures for root-cause analysis"),
        paragraph(""),
        heading(3, "📊 Gallery View — Run Cards"),
        numbered("Click + Add a view → select Gallery"),
        numbered("Card preview: Status, Duration (min), Files Generated, Trigger"),
        numbered("Gives a visual card-based overview of recent runs"),
    ]


def changelog_views():
    return [
        callout(
            [_rich("To create views: Open the database → Click ", bold=False),
             _rich("+ Add a view", bold=True, code=True),
             _rich(" at the top left")],
            emoji="💡", color="yellow_background",
        ),
        heading(3, "📋 Table View — Recent Commits"),
        bullet("Default view — already created"),
        bullet("Sort: \"Date\" → Descending"),
        bullet("Columns: Message, Type, Author, Date, Files Changed, Insertions, Deletions"),
        paragraph(""),
        heading(3, "🗂️ Board View — By Commit Type"),
        numbered("Click + Add a view → select Board"),
        numbered("Group by: Type"),
        numbered("Shows commits grouped: ✨ feat | 🐛 fix | ♻️ refactor | 🔧 chore | etc."),
        numbered("Great for seeing what kind of work is happening"),
        paragraph(""),
        heading(3, "📅 Calendar View — Commit Timeline"),
        numbered("Click + Add a view → select Calendar"),
        numbered("Date property: Date"),
        numbered("Visualizes commit cadence — find active vs. quiet periods"),
        paragraph(""),
        heading(3, "🔍 Filtered View — Features Only"),
        numbered("Create a Table view filtered to: Type = ✨ feat"),
        numbered("Quick way to see all new features added"),
        paragraph(""),
        heading(3, "🔍 Filtered View — Bug Fixes"),
        numbered("Create a Table view filtered to: Type = 🐛 fix"),
        numbered("Track all bug fixes in one place"),
    ]


def metrics_views():
    return [
        callout(
            [_rich("To create views: Open the database → Click ", bold=False),
             _rich("+ Add a view", bold=True, code=True),
             _rich(" at the top left")],
            emoji="💡", color="yellow_background",
        ),
        heading(3, "📋 Table View — Snapshot History"),
        bullet("Default view — already created"),
        bullet("Sort: \"Date\" → Descending"),
        bullet("Key columns: Python LOC, Total Files, Test Files, Dependencies, Success Rate (%)"),
        paragraph(""),
        heading(3, "📈 Trend Analysis"),
        bullet("Notion doesn't have built-in charts, but you can:"),
        numbered("Export to CSV from the ••• menu → Export"),
        numbered("Import into Google Sheets or Excel"),
        numbered("Create line charts for LOC growth, file count trends, success rates"),
        paragraph(""),
        heading(3, "🔍 Filtered View — Low Success Rate"),
        numbered("Create a Table view filtered to: Success Rate (%) < 0.9"),
        numbered("Highlights periods where the pipeline was struggling"),
    ]


def incidents_views():
    return [
        callout(
            [_rich("To create views: Open the database → Click ", bold=False),
             _rich("+ Add a view", bold=True, code=True),
             _rich(" at the top left")],
            emoji="💡", color="yellow_background",
        ),
        heading(3, "📋 Table View — All Incidents"),
        bullet("Default view — already created"),
        bullet("Sort: \"Detected\" → Descending"),
        bullet("Columns: Severity, Status, Error Type, Detected, Resolved"),
        paragraph(""),
        heading(3, "🗂️ Board View — By Status"),
        numbered("Click + Add a view → select Board"),
        numbered("Group by: Status"),
        numbered("Lanes: 🔥 Active → 🔍 Investigating → ✅ Resolved → 🔇 Ignored"),
        numbered("Drag incidents between lanes as they're triaged"),
        paragraph(""),
        heading(3, "🗂️ Board View — By Severity"),
        numbered("Click + Add a view → select Board"),
        numbered("Group by: Severity"),
        numbered("Lanes: 🔴 Critical → 🟠 High → 🟡 Medium → 🟢 Low"),
        numbered("Prioritize response by severity"),
        paragraph(""),
        heading(3, "🔍 Filtered View — Active Incidents"),
        numbered("Create a Table filtered to: Status = 🔥 Active OR Status = 🔍 Investigating"),
        numbered("Your real-time incident response view"),
    ]


# ═══════════════════════════════════════════════════════════════════════════
#  Full View Setup Guide (detailed toggle section)
# ═══════════════════════════════════════════════════════════════════════════

def view_setup_guide():
    """Build the comprehensive view setup guide section."""
    return [
        heading(2, "📖 How to Create Database Views", toggleable=True),
        callout(
            [_rich("The Notion API cannot create views programmatically. ", bold=True),
             _rich("Follow these steps to set up the recommended views in the Notion UI. "
                   "Each database can have multiple views — Table, Board, Calendar, Gallery, Timeline, and List.")],
            emoji="ℹ️", color="blue_background",
        ),
        paragraph(""),
        heading(3, "Step 1: Open a Database"),
        numbered("Click on a database name (e.g., 🏃 Pipeline Runs) or use the @mention link"),
        numbered("The database opens in full-page mode"),
        paragraph(""),
        heading(3, "Step 2: Add a New View"),
        numbered("Click the + button next to the existing view tabs at the top"),
        numbered("Or click the ••• menu → Add a view"),
        numbered("Choose the view type: Table, Board, Calendar, Gallery, Timeline, or List"),
        numbered("Give it a descriptive name (e.g., \"Failed Runs\", \"By Status\")"),
        paragraph(""),
        heading(3, "Step 3: Configure Filters"),
        numbered("Click the Filter button (funnel icon) at the top of the view"),
        numbered("Click + Add a filter"),
        numbered("Select the property, condition, and value"),
        numbered("Multiple filters can be combined with AND/OR logic"),
        paragraph(""),
        heading(3, "Step 4: Configure Sorts"),
        numbered("Click the Sort button (↕ icon) at the top of the view"),
        numbered("Click + Add a sort"),
        numbered("Select the property and direction (Ascending/Descending)"),
        paragraph(""),
        heading(3, "Step 5: Customize Visible Properties"),
        numbered("Click the ••• menu → Properties"),
        numbered("Toggle properties on/off for the current view"),
        numbered("Drag to reorder columns"),
        numbered("Each view remembers its own property visibility"),
        paragraph(""),
        heading(3, "Step 6: Board View Grouping"),
        numbered("In Board view, click the ••• menu → Group by"),
        numbered("Select a Select or Status property (e.g., Status, Severity, Type)"),
        numbered("Each unique value becomes a lane/column"),
        numbered("Drag items between lanes to change their status"),
        paragraph(""),
        quote("💡 Tip: Each view is independent — changing filters in one view doesn't affect others. "
              "Create as many views as you need for different perspectives!"),
    ]


# ═══════════════════════════════════════════════════════════════════════════
#  Main Dashboard Builder
# ═══════════════════════════════════════════════════════════════════════════

def build_dashboard(notion: Client):
    """Create the Operations Dashboard as a child page."""
    parent_id = NOTION_PARENT_PAGE.replace("-", "")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    print("📊 Building Operations Dashboard...")

    # ── Create child page ───────────────────────────────────────────────
    page = notion.pages.create(
        parent={"type": "page_id", "page_id": parent_id},
        icon={"type": "emoji", "emoji": "📊"},
        properties={
            "title": {"title": [{"text": {"content": "Operations Dashboard"}}]},
        },
    )
    dashboard_id = page["id"]
    print(f"   Created page: {dashboard_id}")

    # ── Section 1: Hero Banner + TOC ────────────────────────────────────
    hero_blocks = [
        table_of_contents(color="gray_background"),
        paragraph(""),
        callout(
            [
                _rich("DSR Resiliency — Pipeline Operations Center\n", bold=True),
                _rich("Automated pipeline monitoring for the Weekly PDF Generator.\n"),
                _rich("Data syncs from GitHub Actions on every push, run, and schedule.\n\n"),
                _rich(f"Dashboard created: {now}", italic=True, color="gray"),
            ],
            emoji="🏗️",
            color="blue_background",
        ),
        divider(),
    ]

    # ── Section 2: Live KPI Cards ───────────────────────────────────────
    kpi_blocks = [heading(1, "⚡ Live Pipeline Status")]
    kpi_last_run   = kpi_card("🟢", "Last Run", "—", "No data yet", "green_background")
    kpi_success    = kpi_card("📈", "Success Rate", "—%", "All time", "blue_background")
    kpi_total_runs = kpi_card("📊", "Total Runs", "0", "Since tracking began", "purple_background")
    kpi_avg_time   = kpi_card("⏱️", "Avg Duration", "— min", "Per run", "orange_background")

    kpi_columns = column_list([
        [kpi_last_run],
        [kpi_success],
        [kpi_total_runs],
        [kpi_avg_time],
    ])
    kpi_blocks.append(kpi_columns)
    kpi_blocks.append(
        paragraph([_rich("KPIs update automatically after each pipeline run.", italic=True, color="gray")])
    )
    kpi_blocks.append(divider())

    # ── Section 3: Database Sections ────────────────────────────────────
    pipeline_section = db_section(
        "Pipeline Runs", "🏃", NOTION_PIPELINE_DB,
        "Every GitHub Actions workflow execution with status, timing, file counts, "
        "variant breakdown, and audit risk level.",
        pipeline_views(),
    )

    changelog_section = db_section(
        "Changelog", "📝", NOTION_CHANGELOG_DB,
        "Git commits automatically categorized by conventional commit type — "
        "features, bug fixes, refactors, chores, docs, and more.",
        changelog_views(),
    )

    metrics_section = db_section(
        "Codebase Metrics", "📊", NOTION_METRICS_DB,
        "Daily snapshots of codebase health: Python LOC, file counts, "
        "test coverage, dependencies, and pipeline success rates.",
        metrics_views(),
    )

    incidents_section = db_section(
        "Incidents", "⚠️", NOTION_INCIDENTS_DB,
        "Failed and errored pipeline runs tracked with severity, status, "
        "root cause analysis, and resolution notes.",
        incidents_views(),
    )

    # ── Section 4: Quick Links ──────────────────────────────────────────
    links_blocks = [
        heading(2, "🔗 Quick Links"),
        column_list([
            [callout(
                [_rich("GitHub Repository\n", bold=True),
                 _rich("Source code, issues, PRs", color="gray")],
                emoji="🐙", color="gray_background",
            )],
            [callout(
                [_rich("GitHub Actions\n", bold=True),
                 _rich("Workflow runs & logs", color="gray")],
                emoji="⚡", color="gray_background",
            )],
            [callout(
                [_rich("Notion API Docs\n", bold=True),
                 _rich("Reference & guides", color="gray")],
                emoji="📚", color="gray_background",
            )],
        ]),
        bookmark(f"https://github.com/{GITHUB_REPO}", "GitHub Repository"),
        bookmark(f"https://github.com/{GITHUB_REPO}/actions", "GitHub Actions"),
        bookmark("https://developers.notion.com/reference", "Notion API Reference"),
        divider(),
    ]

    # ── Section 5: View Setup Guide ─────────────────────────────────────
    guide_blocks = view_setup_guide()

    # ── Section 6: Footer ───────────────────────────────────────────────
    footer_blocks = [
        divider(),
        callout(
            [
                _rich("Powered by ", italic=True),
                _rich("notion_sync.py", bold=True, code=True),
                _rich(" + GitHub Actions\n", italic=True),
                _rich("Integration: Workflow generate weekly integration\n", color="gray"),
                _rich(f"Config: scripts/notion_config.json", color="gray"),
            ],
            emoji="⚙️",
            color="gray_background",
        ),
    ]

    # ── Assemble and Append ─────────────────────────────────────────────
    all_blocks = (
        hero_blocks
        + kpi_blocks
        + pipeline_section
        + changelog_section
        + metrics_section
        + incidents_section
        + links_blocks
        + guide_blocks
        + footer_blocks
    )

    # Notion API allows max 100 blocks per append call
    BATCH_SIZE = 100
    for i in range(0, len(all_blocks), BATCH_SIZE):
        batch = all_blocks[i:i + BATCH_SIZE]
        notion.blocks.children.append(block_id=dashboard_id, children=batch)
        print(f"   Appended blocks {i + 1}–{i + len(batch)} of {len(all_blocks)}")

    # ── Extract KPI block IDs ───────────────────────────────────────────
    # The KPI callout blocks are inside the column_list. We need to walk
    # the page blocks to find them.
    kpi_block_ids = _extract_kpi_block_ids(notion, dashboard_id)

    return dashboard_id, kpi_block_ids


def _extract_kpi_block_ids(notion: Client, page_id: str) -> dict:
    """Walk the dashboard page to find the 4 KPI callout blocks inside columns."""
    kpi_ids = {}
    labels = ["Last Run", "Success Rate", "Total Runs", "Avg Duration"]

    # List top-level children
    children = notion.blocks.children.list(block_id=page_id)["results"]
    for block in children:
        if block["type"] == "column_list":
            # Get columns
            cols = notion.blocks.children.list(block_id=block["id"])["results"]
            for col in cols:
                # Get callouts inside each column
                col_children = notion.blocks.children.list(block_id=col["id"])["results"]
                for child in col_children:
                    if child["type"] == "callout":
                        text = "".join(
                            rt.get("plain_text", "")
                            for rt in child["callout"]["rich_text"]
                        )
                        for label in labels:
                            if label in text and label not in kpi_ids:
                                kpi_ids[label] = child["id"]
    return kpi_ids


# ═══════════════════════════════════════════════════════════════════════════
#  Database Enhancements (covers, descriptions, relations)
# ═══════════════════════════════════════════════════════════════════════════

def enhance_databases(notion: Client):
    """Add formula properties and cross-references to databases."""
    print("🔧 Enhancing databases...")

    # Add Duration Category formula to Pipeline Runs
    try:
        notion.databases.update(
            database_id=NOTION_PIPELINE_DB,
            properties={
                "Duration Category": {
                    "formula": {
                        "expression": 'if(prop("Duration (min)") <= 2, "⚡ Fast", if(prop("Duration (min)") <= 5, "🟢 Normal", if(prop("Duration (min)") <= 10, "🟡 Slow", "🔴 Very Slow")))',
                    }
                },
                "Files per Minute": {
                    "formula": {
                        "expression": 'if(prop("Duration (min)") > 0, round(prop("Files Generated") / prop("Duration (min)") * 100) / 100, 0)',
                    }
                },
            },
        )
        print("   ✅ Pipeline Runs: Added Duration Category + Files per Minute formulas")
    except Exception as e:
        print(f"   ⚠️  Pipeline Runs formulas: {e}")

    # Add Impact Score formula to Changelog
    try:
        notion.databases.update(
            database_id=NOTION_CHANGELOG_DB,
            properties={
                "Impact": {
                    "formula": {
                        "expression": 'prop("Insertions") + prop("Deletions")',
                    }
                },
            },
        )
        print("   ✅ Changelog: Added Impact (Insertions + Deletions) formula")
    except Exception as e:
        print(f"   ⚠️  Changelog formula: {e}")

    # Add Health Score formula to Metrics
    try:
        notion.databases.update(
            database_id=NOTION_METRICS_DB,
            properties={
                "Test Ratio": {
                    "formula": {
                        "expression": 'if(prop("Total Files") > 0, round(prop("Test Files") / prop("Total Files") * 10000) / 100, 0)',
                    }
                },
            },
        )
        print("   ✅ Codebase Metrics: Added Test Ratio formula")
    except Exception as e:
        print(f"   ⚠️  Metrics formula: {e}")

    # Add Time to Resolve formula to Incidents
    try:
        notion.databases.update(
            database_id=NOTION_INCIDENTS_DB,
            properties={
                "Days Open": {
                    "formula": {
                        "expression": 'if(empty(prop("Resolved")), dateBetween(now(), prop("Detected"), "days"), dateBetween(prop("Resolved"), prop("Detected"), "days"))',
                    }
                },
            },
        )
        print("   ✅ Incidents: Added Days Open formula")
    except Exception as e:
        print(f"   ⚠️  Incidents formula: {e}")


# ═══════════════════════════════════════════════════════════════════════════
#  Save Configuration
# ═══════════════════════════════════════════════════════════════════════════

def save_config(dashboard_id, kpi_block_ids):
    """Merge dashboard config into existing notion_config.json."""
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)

    cfg["dashboard_page"] = dashboard_id
    cfg["kpi_blocks"] = kpi_block_ids
    cfg["dashboard_created"] = datetime.now(timezone.utc).isoformat()

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print(f"   📋 Config saved to {CONFIG_PATH}")


# ═══════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    _load_config()
    _require_env()

    notion = Client(auth=NOTION_TOKEN)

    # Step 1: Enhance databases with formulas
    enhance_databases(notion)

    # Step 2: Build dashboard page
    dashboard_id, kpi_block_ids = build_dashboard(notion)

    # Step 3: Save config
    save_config(dashboard_id, kpi_block_ids)

    print()
    print("=" * 60)
    print("🎉 Operations Dashboard Created!")
    print("=" * 60)
    print()
    print(f"Dashboard page: {dashboard_id}")
    print(f"KPI blocks: {json.dumps(kpi_block_ids, indent=2)}")
    print()
    print("Next steps:")
    print("  1. Open the dashboard in Notion")
    print("  2. Set up the recommended views for each database")
    print("  3. KPIs will update automatically on each pipeline run")
    print()
    if kpi_block_ids:
        print(f"Found {len(kpi_block_ids)} KPI blocks for auto-update ✅")
    else:
        print("⚠️  Could not find KPI blocks — auto-update won't work")


if __name__ == "__main__":
    main()
