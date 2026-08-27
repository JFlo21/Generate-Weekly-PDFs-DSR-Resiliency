---
slug: pipeline-memory-client-init-fix
title: "Run-memory writes were silently lost after the flip — client init fixed for supabase-py sync options"
authors: [runbook-bot]
tags: [github, project, python, tests]
date: 2026-08-27T17:30:00+00:00
---

**Component:** Python billing pipeline (`generate_weekly_pdfs.py` →
`pipeline_memory/client.py`) on the GitHub Actions weekly workflow.
**Change type:** bug fix on the fail-open run-memory write path, plus a
diagnostic improvement. No workflow, schedule, schema, or billing change.
**PR:** #356, following #353 (the `RUN_MEMORY_WRITE_ENABLED` flip).

<!-- truncate -->

## What changed

The first production run carrying the flip (run 33090659647) completed
normally on the billing side but wrote **no run memory at all**. Its log
carried one warning right after Phase 1 —
`⚠️ Supabase client init failed; pipeline_memory writes disabled
(AttributeError)` — followed by `0 sheet(s) written, 113 errored,
confirmed=False`, a skipped shadow-parity check, and no `run_ledger` row.

The `pipeline_memory` client is now built with the SDK's
`SyncClientOptions` instead of the base `ClientOptions`. If the installed
SDK ever rejects the options object again, the client is retried without
it (writes survive; only the per-call PostgREST timeout bound is lost),
and both warning lines now print the exception **message**, not just its
class name.

## Why

The per-RPC timeout wiring (WR-02) passed the base
`supabase.lib.client_options.ClientOptions` to the sync `create_client`.
On the pinned `supabase==2.31.0`, that constructor reads
`options.storage`, which only the `SyncClientOptions` /
`AsyncClientOptions` subclasses define — so client construction raised
`'ClientOptions' object has no attribute 'storage'` before a single write
was attempted. The unit tests mocked `create_client` and inspected only
the captured options, so they could not see the real constructor fail;
the Phase 10 control runs predated the timeout wiring.

The fail-open contract worked as designed — Excel generation, attachment
uploads, and `billing_audit` (which builds its own client) were untouched
— but it also hid the defect behind a warning that read like a Supabase
outage. Until this fix lands, the five-run parity streak that authorises
the incremental read cannot start.

## What operators will see

- After the fix: `⚡ Run-memory row writes: N sheet(s) written, 0 errored
  … confirmed=True`, a shadow-parity line, and a new `run_ledger` row on
  every scheduled run — the behaviour the flip post described.
- If client construction fails again for any reason, the warning names
  the exception (`Type: message`). A second warning, `retrying without
  the 45s PostgREST timeout`, means the fallback client was used — the
  run's memory is still written, but the SDK/options drift should be
  fixed. The Operations page's symptom table has the row.
- A new regression test builds the client through the real SDK with fake
  credentials (no network at construction), so an SDK bump that breaks
  construction now fails `pytest` instead of production.

## Rollback

Revert #356. Behaviour returns to the previous state — memory writes
silently lost, billing unaffected — so there is no operational reason to
do so; the `RUN_MEMORY_WRITE_ENABLED` rollback in the flip post still
applies independently.

## Residual

`supabase==2.31.0` deprecates the `timeout` parameter the fix relies on.
The next SDK bump must move the bound to
`SyncClientOptions(httpx_client=httpx.Client(timeout=…))`; the new test
will catch the change.
