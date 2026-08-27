---
schema_version: 1
open_count: 1
waived_count: 0
fixed_count: 1
total_count: 2
last_updated: 2026-08-26T22:13:12.208Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | quick-260812-jqx | unrun-verify | pipeline/snapshot_drift.py |  | Task 3 human-check (live operator verification of A1/A4 assumptions against a known-drifted Smartsheet row) not run — no SMARTSHEET_API_TOKEN available in this sandbox. Must be run by Juan before setting SNAPSHOT_DRIFT_HOLD_ENABLED=true in the workflow. | fixed |  | 2026-08-12T21:28:42.447Z | 2026-08-12T21:43:06.317Z |
| 2 | 11 | deviation | pipeline/orchestrate.py |  | A (wr, week_ending) pair whose LAST remaining row is deleted by the deep run produces no group_state repair -- the group no longer exists for group_source_rows to build, so _repair_group_state_for_affected_pairs finds nothing to filter and the stale group_state row (last-known content_hash/row_count) is left as-is. Documented, out of scope for 11-06 -- needs a stored target_sheet_id reader to clean up safely. | open |  | 2026-08-26T22:13:12.208Z |  |

````json
[
  {
    "id": 1,
    "kind": "unrun-verify",
    "phase": "quick-260812-jqx",
    "file": "pipeline/snapshot_drift.py",
    "line": null,
    "description": "Task 3 human-check (live operator verification of A1/A4 assumptions against a known-drifted Smartsheet row) not run — no SMARTSHEET_API_TOKEN available in this sandbox. Must be run by Juan before setting SNAPSHOT_DRIFT_HOLD_ENABLED=true in the workflow.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-12T21:28:42.447Z",
    "resolved_at": "2026-08-12T21:43:06.317Z"
  },
  {
    "id": 2,
    "kind": "deviation",
    "phase": "11",
    "file": "pipeline/orchestrate.py",
    "line": null,
    "description": "A (wr, week_ending) pair whose LAST remaining row is deleted by the deep run produces no group_state repair -- the group no longer exists for group_source_rows to build, so _repair_group_state_for_affected_pairs finds nothing to filter and the stale group_state row (last-known content_hash/row_count) is left as-is. Documented, out of scope for 11-06 -- needs a stored target_sheet_id reader to clean up safely.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-26T22:13:12.208Z",
    "resolved_at": null
  }
]
````
