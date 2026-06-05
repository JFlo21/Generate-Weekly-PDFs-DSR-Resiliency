"""Tests for the Sentry Crons monitor_config contract.

Guards the schedule/timezone contract between the Sentry cron monitor
(``_build_cron_monitor_config`` in ``generate_weekly_pdfs``) and the
GitHub Actions workflow that actually triggers the job.

Regression: ``GENERATE-WEEKLY-EXCEL-6V`` ("Cron failure: missed check-in").
The monitor schedule string is the weekday GitHub Actions cron, which Actions
evaluates in **UTC**. Labeling the monitor ``timezone`` as ``America/Chicago``
made Sentry expect every check-in 5-6h late and fire a perpetual
missed-check-in outage. The timezone MUST be ``UTC`` and the schedule VALUE
MUST stay identical to the workflow's weekday cron.
"""

import os
import re
from pathlib import Path
from unittest.mock import patch

# Import under a patched environment so a developer's real SENTRY_DSN cannot
# trigger import-time Sentry initialization during pytest collection.
with patch.dict(os.environ, {"SENTRY_DSN": ""}, clear=False):
    import generate_weekly_pdfs as gwp

_WORKFLOW = (
    Path(__file__).resolve().parent.parent
    / ".github" / "workflows" / "weekly-excel-generation.yml"
)


class TestBuildCronMonitorConfig:
    """The monitor_config dict shape and the timezone fix."""

    def test_timezone_is_utc(self):
        # The core regression guard: GitHub Actions crons are UTC, so the
        # Sentry monitor timezone must be UTC — never America/Chicago.
        cfg = gwp._build_cron_monitor_config()
        assert cfg["timezone"] == "UTC"

    def test_timezone_is_not_a_local_zone(self):
        cfg = gwp._build_cron_monitor_config()
        assert cfg["timezone"] not in ("America/Chicago", "America/Phoenix")

    def test_schedule_shape(self):
        cfg = gwp._build_cron_monitor_config()
        assert cfg["schedule"]["type"] == "crontab"
        assert cfg["schedule"]["value"] == gwp._CRON_MONITOR_SCHEDULE

    def test_runtime_and_threshold_fields(self):
        cfg = gwp._build_cron_monitor_config()
        assert cfg["max_runtime"] == 180
        assert cfg["checkin_margin"] == 5
        assert cfg["failure_issue_threshold"] == 1
        assert cfg["recovery_threshold"] == 1


class TestScheduleMatchesWorkflow:
    """The monitor schedule must track the real workflow trigger cron."""

    def test_monitor_schedule_matches_workflow_weekday_cron(self):
        text = _WORKFLOW.read_text(encoding="utf-8")
        crons = re.findall(r"- cron:\s*'([^']+)'", text)
        # The weekday cron (Mon-Fri, '* * 1-5') is the one the monitor tracks.
        weekday = [c for c in crons if c.strip().endswith("1-5")]
        assert weekday, f"no weekday cron found in {_WORKFLOW.name}: {crons}"
        assert gwp._CRON_MONITOR_SCHEDULE in weekday, (
            "Sentry monitor schedule drifted from the workflow weekday cron: "
            f"{gwp._CRON_MONITOR_SCHEDULE!r} not in {weekday!r}"
        )
