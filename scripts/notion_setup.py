#!/usr/bin/env python3
"""
Notion Workspace Setup — One-time bootstrap for the DSR Resiliency Run Log.

Creates the following databases inside a parent Notion page:
  1. 🏃 Pipeline Runs      — Every GitHub Actions workflow execution
  2. 📝 Changelog          — Commits with semantic categorization
  3. 📊 Codebase Metrics   — LOC, file counts, test coverage snapshots
  4. ⚠️ Incidents           — Failed / errored pipeline runs

Usage:
    python scripts/notion_setup.py

Requires env vars:
    NOTION_TOKEN       — Internal integration token (starts with ntn_)
    NOTION_PARENT_PAGE — ID of the Notion page to host the databases

After running, save the printed database IDs as GitHub repo secrets:
    NOTION_PIPELINE_DB, NOTION_CHANGELOG_DB, NOTION_METRICS_DB, NOTION_INCIDENTS_DB
"""

import os
import sys
import json
from notion_client import Client

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_PARENT_PAGE = os.getenv("NOTION_PARENT_PAGE")


def _require_env():
    missing = []
    if not NOTION_TOKEN:
        missing.append("NOTION_TOKEN")
    if not NOTION_PARENT_PAGE:
        missing.append("NOTION_PARENT_PAGE")
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        print("\nSetup instructions:")
        print("  1. Go to https://www.notion.so/my-integrations and create an integration")
        print("  2. Copy the Internal Integration Secret (starts with ntn_)")
        print("  3. Create a page in Notion for the dashboard")
        print("  4. Share that page with your integration (⋯ > Connections > Add)")
        print("  5. Copy the page ID from the URL (32-char hex after the page name)")
        print("  6. Set environment variables:")
        print(f'     $env:NOTION_TOKEN = "ntn_..."')
        print(f'     $env:NOTION_PARENT_PAGE = "your-page-id"')
        sys.exit(1)


# ── Color palette (professional Notion aesthetic) ──────────────────────────
# Using Notion's built-in color names for select/multi-select options.

def _select(name, color="default"):
    return {"name": name, "color": color}


# ── Database schemas ───────────────────────────────────────────────────────

PIPELINE_RUNS_SCHEMA = {
    "Run": {"title": {}},
    "Status": {
        "select": {
            "options": [
                _select("✅ Success", "green"),
                _select("❌ Failed", "red"),
                _select("⏳ In Progress", "yellow"),
                _select("⏭️ Skipped", "gray"),
                _select("⏰ Timed Out", "orange"),
            ]
        }
    },
    "Trigger": {
        "select": {
            "options": [
                _select("⏰ Scheduled", "blue"),
                _select("🖐️ Manual", "purple"),
                _select("🔄 Push", "green"),
                _select("📋 Weekly", "orange"),
                _select("🏖️ Weekend", "gray"),
            ]
        }
    },
    "Started": {"date": {}},
    "Duration (min)": {"number": {"format": "number"}},
    "Files Generated": {"number": {"format": "number"}},
    "Files Uploaded": {"number": {"format": "number"}},
    "Files Skipped": {"number": {"format": "number"}},
    "Groups Total": {"number": {"format": "number"}},
    "Groups Errored": {"number": {"format": "number"}},
    "Sheets Discovered": {"number": {"format": "number"}},
    "Rows Fetched": {"number": {"format": "number"}},
    "Variant Breakdown": {
        "rich_text": {}  # e.g. "Primary: 42 | Helper: 8 | VAC Crew: 3"
    },
    "Commit SHA": {"rich_text": {}},
    "Branch": {
        "select": {
            "options": [
                _select("master", "blue"),
                _select("develop", "green"),
                _select("feature", "purple"),
            ]
        }
    },
    "Run URL": {"url": {}},
    "Run Number": {"number": {"format": "number"}},
    "Execution Type": {
        "select": {
            "options": [
                _select("production_frequent", "blue"),
                _select("weekend_maintenance", "gray"),
                _select("weekly_comprehensive", "orange"),
                _select("manual", "purple"),
            ]
        }
    },
    "Hash Updates": {"number": {"format": "number"}},
    "API Calls": {"number": {"format": "number"}},
    "Audit Risk": {
        "select": {
            "options": [
                _select("LOW", "green"),
                _select("MEDIUM", "yellow"),
                _select("HIGH", "orange"),
                _select("CRITICAL", "red"),
                _select("UNKNOWN", "gray"),
            ]
        }
    },
    "Error Summary": {"rich_text": {}},
}

CHANGELOG_SCHEMA = {
    "Commit": {"title": {}},
    "Message": {"rich_text": {}},
    "Author": {"rich_text": {}},
    "Date": {"date": {}},
    "Type": {
        "select": {
            "options": [
                _select("✨ feat", "green"),
                _select("🐛 fix", "red"),
                _select("♻️ refactor", "blue"),
                _select("🔧 chore", "gray"),
                _select("📝 docs", "purple"),
                _select("⚡ perf", "orange"),
                _select("🔒 security", "yellow"),
                _select("🧪 test", "pink"),
            ]
        }
    },
    "Scope": {"rich_text": {}},
    "Files Changed": {"number": {"format": "number"}},
    "Insertions": {"number": {"format": "number"}},
    "Deletions": {"number": {"format": "number"}},
    "Breaking Change": {"checkbox": {}},
    "Commit URL": {"url": {}},
}

METRICS_SCHEMA = {
    "Snapshot": {"title": {}},
    "Date": {"date": {}},
    "Python LOC": {"number": {"format": "number"}},
    "Total Files": {"number": {"format": "number"}},
    "Test Files": {"number": {"format": "number"}},
    "Source Sheets": {"number": {"format": "number"}},
    "Dependencies": {"number": {"format": "number"}},
    "Workflow Steps": {"number": {"format": "number"}},
    "Open Issues": {"number": {"format": "number"}},
    "Cache Version": {"number": {"format": "number"}},
    "Avg Run Duration (min)": {"number": {"format": "number"}},
    "Success Rate (%)": {"number": {"format": "percent"}},
}

INCIDENTS_SCHEMA = {
    "Incident": {"title": {}},
    "Severity": {
        "select": {
            "options": [
                _select("🔴 Critical", "red"),
                _select("🟠 High", "orange"),
                _select("🟡 Medium", "yellow"),
                _select("🟢 Low", "green"),
            ]
        }
    },
    "Status": {
        "select": {
            "options": [
                _select("🔥 Active", "red"),
                _select("🔍 Investigating", "yellow"),
                _select("✅ Resolved", "green"),
                _select("🔇 Ignored", "gray"),
            ]
        }
    },
    "Detected": {"date": {}},
    "Resolved": {"date": {}},
    "Run Number": {"number": {"format": "number"}},
    "Error Type": {"rich_text": {}},
    "Error Message": {"rich_text": {}},
    "Root Cause": {"rich_text": {}},
    "Resolution": {"rich_text": {}},
    "Run URL": {"url": {}},
    "Commit SHA": {"rich_text": {}},
    "Impact": {"rich_text": {}},
}


def create_database(notion: Client, parent_id: str, title: str, icon: str, schema: dict, description: str = "") -> str:
    """Create a Notion database and return its ID."""
    db = notion.databases.create(
        parent={"type": "page_id", "page_id": parent_id},
        title=[{"type": "text", "text": {"content": title}}],
        icon={"type": "emoji", "emoji": icon},
        description=[{"type": "text", "text": {"content": description}}] if description else [],
        properties=schema,
    )
    return db["id"]


def create_dashboard_header(notion: Client, page_id: str):
    """Add a professional header block to the parent page."""
    notion.blocks.children.append(
        block_id=page_id,
        children=[
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": "DSR Resiliency — Pipeline Operations Center"},
                            "annotations": {"bold": True},
                        },
                        {
                            "type": "text",
                            "text": {"content": "\nAutomated run logs, changelog, metrics, and incident tracking for the Weekly PDF Generator pipeline. Data syncs automatically from GitHub Actions."},
                        },
                    ],
                    "icon": {"type": "emoji", "emoji": "🏗️"},
                    "color": "blue_background",
                },
            },
            {
                "object": "block",
                "type": "divider",
                "divider": {},
            },
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "📊 Quick Stats"}}],
                },
            },
            {
                "object": "block",
                "type": "column_list",
                "column_list": {
                    "children": [
                        {
                            "object": "block",
                            "type": "column",
                            "column": {
                                "children": [
                                    {
                                        "object": "block",
                                        "type": "callout",
                                        "callout": {
                                            "rich_text": [
                                                {"type": "text", "text": {"content": "Pipeline Runs"}, "annotations": {"bold": True}},
                                                {"type": "text", "text": {"content": "\nView all workflow executions with status, metrics, and artifacts."}},
                                            ],
                                            "icon": {"type": "emoji", "emoji": "🏃"},
                                            "color": "green_background",
                                        },
                                    }
                                ]
                            },
                        },
                        {
                            "object": "block",
                            "type": "column",
                            "column": {
                                "children": [
                                    {
                                        "object": "block",
                                        "type": "callout",
                                        "callout": {
                                            "rich_text": [
                                                {"type": "text", "text": {"content": "Changelog"}, "annotations": {"bold": True}},
                                                {"type": "text", "text": {"content": "\nAll commits categorized by type: features, fixes, refactors."}},
                                            ],
                                            "icon": {"type": "emoji", "emoji": "📝"},
                                            "color": "purple_background",
                                        },
                                    }
                                ]
                            },
                        },
                        {
                            "object": "block",
                            "type": "column",
                            "column": {
                                "children": [
                                    {
                                        "object": "block",
                                        "type": "callout",
                                        "callout": {
                                            "rich_text": [
                                                {"type": "text", "text": {"content": "Incidents"}, "annotations": {"bold": True}},
                                                {"type": "text", "text": {"content": "\nFailed runs and errors tracked with severity and resolution."}},
                                            ],
                                            "icon": {"type": "emoji", "emoji": "⚠️"},
                                            "color": "red_background",
                                        },
                                    }
                                ]
                            },
                        },
                    ]
                },
            },
            {
                "object": "block",
                "type": "divider",
                "divider": {},
            },
        ],
    )


def main():
    _require_env()
    notion = Client(auth=NOTION_TOKEN)
    parent = NOTION_PARENT_PAGE.replace("-", "")

    print("🏗️  Setting up DSR Resiliency Notion Dashboard...")
    print(f"   Parent page: {parent}")
    print()

    # Create dashboard header
    try:
        create_dashboard_header(notion, parent)
        print("✅ Dashboard header created")
    except Exception as e:
        print(f"⚠️  Header creation skipped (may already exist): {e}")

    # Create databases
    dbs = {}
    configs = [
        ("pipeline_runs", "🏃 Pipeline Runs", "🏃", PIPELINE_RUNS_SCHEMA,
         "Every GitHub Actions workflow execution with full metrics, variant breakdown, and audit status."),
        ("changelog", "📝 Changelog", "📝", CHANGELOG_SCHEMA,
         "Git commits categorized by conventional commit type. Auto-synced from repository."),
        ("metrics", "📊 Codebase Metrics", "📊", METRICS_SCHEMA,
         "Daily snapshots of codebase health: LOC, file counts, dependencies, success rates."),
        ("incidents", "⚠️ Incidents", "⚠️", INCIDENTS_SCHEMA,
         "Failed pipeline runs and errors with severity tracking and resolution notes."),
    ]

    for key, title, icon, schema, desc in configs:
        try:
            db_id = create_database(notion, parent, title, icon, schema, desc)
            dbs[key] = db_id
            print(f"✅ Created: {title} → {db_id}")
        except Exception as e:
            print(f"❌ Failed to create {title}: {e}")
            sys.exit(1)

    print()
    print("=" * 60)
    print("🎉 Notion Dashboard Setup Complete!")
    print("=" * 60)
    print()
    print("Add these as GitHub repository secrets:")
    print(f'  NOTION_TOKEN          = {NOTION_TOKEN[:12]}...')
    print(f'  NOTION_PIPELINE_DB    = {dbs["pipeline_runs"]}')
    print(f'  NOTION_CHANGELOG_DB   = {dbs["changelog"]}')
    print(f'  NOTION_METRICS_DB     = {dbs["metrics"]}')
    print(f'  NOTION_INCIDENTS_DB   = {dbs["incidents"]}')
    print()
    print("Or set them all at once via GitHub CLI:")
    print(f'  gh secret set NOTION_PIPELINE_DB --body "{dbs["pipeline_runs"]}"')
    print(f'  gh secret set NOTION_CHANGELOG_DB --body "{dbs["changelog"]}"')
    print(f'  gh secret set NOTION_METRICS_DB --body "{dbs["metrics"]}"')
    print(f'  gh secret set NOTION_INCIDENTS_DB --body "{dbs["incidents"]}"')
    print()

    # Save config locally for reference
    config_path = os.path.join(os.path.dirname(__file__), "notion_config.json")
    with open(config_path, "w") as f:
        json.dump({
            "parent_page": parent,
            "databases": dbs,
            "setup_date": __import__("datetime").datetime.now().isoformat(),
        }, f, indent=2)
    print(f"📋 Config saved to: {config_path}")


if __name__ == "__main__":
    main()
