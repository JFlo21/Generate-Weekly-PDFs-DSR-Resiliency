---
created: 2026-10-30T18:45:00.000Z
title: Stop a failed GF lookup from re-uploading pilot workbooks without notes
area: pipeline
severity: major
blocks: turning FOREMAN_NOTES_UPLOAD on
files:
  - pipeline/foreman_notes.py:367
  - pipeline/change_detection.py
---

## Problem

When the General Foreman lookup fails, `initialize` builds
`FnState(scope=scope, allowlist=allowlist)` with an empty `pilot_wrs`
(`pipeline/foreman_notes.py:367-371`). Every group then reads as non-pilot, so
its notes token is `''` and its hash moves. Each pilot group regenerates and
re-uploads without notes, then regenerates again on the next good run.

`gf_loaded` records the failure, but nothing outside the module reads it.

Found by independent review of PR #437 on 2026-10-30; the failure branch was
confirmed in code and the hash move was probed. Production is unaffected: no
workflow sets `FOREMAN_NOTES_UPLOAD`.

## Solution

Owner decision between two options:

1. Hold pilot groups for that run, so nothing regenerates until the lookup works.
2. Reuse the last known pilot WR set.

**Decided 2026-10-30 (owner): option 1, hold pilot groups for that run, with a
Sentry warning.** Fix lands before `FOREMAN_NOTES_UPLOAD` goes on; #437 merges
without it.

Either needs a regression test that fails the lookup on a run after a good run
and asserts no pilot group regenerates.
