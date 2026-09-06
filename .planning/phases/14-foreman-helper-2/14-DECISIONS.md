# Phase 14 Decisions — Owner-Confirmed Live State

Companion to `14-CONTEXT.md` (D-14-xx locked decisions) and `14-PENDING-RESOLUTIONS.md`
(repository-answered gaps A1–A3). This file records only what a read-only look at live
Smartsheet showed. It is OWNER-OBSERVED LIVE STATE, never a dry-run pass and never a
production observation of Helper #2 behavior.

## LIVE-COLUMN-PROBE (plan 14-02, Task 3)

- Observation date: 2026-09-06
- Method: read-only column-metadata reads through the Smartsheet connector, delegated by
  the owner in-session ("Run the probe read only"). Zero writes. No column provisioning,
  no formula repair, no sheet reconnection, no row values read, no person's name recorded.
- Recorded: column titles, column ids, sheet counts, column counts, and one row-count
  filter result. Picklist option lists were returned by the API and deliberately NOT
  recorded.
- Drift versus the 2026-09-05 snapshot in `14-CONTEXT.md`: none observed.

### Q1 — Main ProMax `3239244454645636` carries all six Helper #2 titles

82 columns total. All six exact titles present:

| Title | Column id |
|---|---|
| `Foreman Helping? #2` | `7936189613248388` |
| `Foreman Helper #2 Active?` | `617840218771332` |
| `Helping Foreman #2 Completed Unit?` | `5121439846141828` |
| `Helper #2 Dept #` | `2869640032456580` |
| `Helper #2 Job [#]` | `7373239659827076` |
| `Foreman Helper #2 Email` | `289083157155716` |

Answer: YES, still 6/6.

### Q2 — Does any Intake or ProMax Database sheet carry a PARTIAL Helper #2 set?

Full sweep, every sheet in both folders plus the Resource Analyst sheet:

| Scope | Sheets | 6/6 (FULL) | 0/6 (NONE) | 1–5/6 (PARTIAL) |
|---|---|---|---|---|
| Intake folder `8815193070299012` | 11 | 10 | 1 (Intake ProMax 8) | 0 |
| ProMax Database folder `7644752003786628` (Main, `(NEW)` `277473162907524`, Backups 2–104) | 105 | 104 | 1 (Backup 2) | 0 |
| Resource Analyst `3733355007790980` | 1 | 0 | 1 (not a pipeline data source; see Q4) | 0 |
| Total | 117 | 114 | 3 | 0 |

Answer: NO partial set exists anywhere. The capability-unavailable case that plan 14-07's
fixtures must cover has no live analog today; the fixture stays synthetic (D-14-01 shape:
Helper #1 columns present, Helper #2 columns absent). Column counts observed: 72–79 on
backups, 78 on the intake sheets, 82 on Main.

### Q3 — Intake ProMax 8 `2244739192541060` and Backup 2 `2230129632694148`

| Sheet | Columns | Helper #2 titles present |
|---|---|---|
| Intake ProMax 8 `2244739192541060` | 78 | 0/6 |
| Resiliency Promax Database Backup 2 `2230129632694148` | 72 | 0/6 |

Answer: confirmed, still no Helper #2 columns. Recorded as ACCEPTED STATE under D-14-01.
Not a defect. Not work. Nothing to provision.

### Q4 — Resource Analyst `Foreman Helper #2` (column id `1589780186173316`)

- Sheet `3733355007790980`: 239 columns, 576 rows.
- Column `Foreman Helper #2` id `1589780186173316`, type PICKLIST, present.
- Row-count check: filter `Foreman Helper #2 IS_NOT_BLANK`, projected onto a single
  checkbox column so no name or value was returned. Result: `rowsInFilter = 0`.
- The sheet also carries four Helper-2-adjacent titles that are NOT the six pipeline
  titles (titles and ids only): `Assigned Helper 2?` `1303443306483588`,
  `Foreman Helping #2` `8426301807693700`, `Work Request Helper 2` `4314485728432004`,
  and `Foreman Helper #2` `1589780186173316` above. None of the six pipeline titles
  exist on this sheet, which is expected; it is not a billing data source.

Answer: BLANK ON EVERY ROW (0 of 576 non-blank).

### Markers

LIVE-COLUMN-PROBE: ANSWERED — observed 2026-09-06, read-only.

Pilot-mode consequence: FIXTURE-ONLY. Plan 14-10's pilot must state it ran over fixtures
and must not claim a dry-run over real Helper #2 rows, because no real Helper #2 row
exists on the Resource Analyst sheet as of 2026-09-06.

### Plan consequences carried forward

- 14-07: capability-unavailable fixture remains synthetic; no partial-set fixture is
  required by live evidence (add one only as a defensive shape, not as an observed one).
- 14-10: pilot is fixture-only; re-run this probe (read-only) before any claim of a
  dry-run over real Helper #2 data.
- 14-01 detection guard (`HELPER2_ENABLED` default `'0'`) is consistent with 114/117
  sheets already carrying the full column set: the flag, not column presence, gates
  behavior.
