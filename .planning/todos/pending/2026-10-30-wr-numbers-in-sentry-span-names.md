---
created: 2026-10-30T21:45:00.000Z
title: Move WR numbers out of Sentry span names
area: observability
severity: minor
files:
  - pipeline/orchestrate.py
---

## Problem

Some existing Sentry span names embed a Work Request number, for example
`sentry_sdk.start_span(op="excel.generate", name=f"Generate Excel for WR
{wr_num}")` in the `main()` group loop. Span names bypass the log sanitizer
(`_PII_LOG_MARKERS`) and `_redact_exception_message`, so the WR travels in
performance and trace data.

The owner-approved WR exception (docs/DECISIONS.md, 2026-10-30) covers only
the structured `foreman_notes` context of Foreman Notes events, set on a
forked scope. These span names are outside that exception.

Found while closing the Foreman Notes Sentry gaps in quick task 261030-suf.
It is out of scope there and recorded here only.

## Solution

Give such spans a structural name (for example `Generate Excel`) and carry
the WR, if it is needed at all, as span data that can be scoped and scrubbed,
following the billing-audit span pattern in the same loop. Re-grep
`start_span(` / `start_transaction(` for every f-string name before changing
anything, and confirm no dashboard or alert filters on the old span names.
