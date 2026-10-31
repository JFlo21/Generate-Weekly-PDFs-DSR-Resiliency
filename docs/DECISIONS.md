# Decisions

> **Canonical decisions log: [`memory-bank/living-ledger.md`](../memory-bank/living-ledger.md).**
> Durable architectural/operational decisions are recorded as dated
> `[YYYY-MM-DD HH:MM]` entries in the Living Ledger (alongside their context and
> incident root-causes), not in a separate ADR file.
>
> This stub exists so the global context-continuity write-back order (which names
> `docs/DECISIONS.md`) resolves to a real path. For locked, phase-level decisions
> see also `.planning/PROJECT.md` and `.planning/phases/*/*-CONTEXT.md`.

## 2026-10-30 - Foreman Notes Sentry WR exception (owner-approved)

- WR numbers may appear in Sentry only inside the structured `foreman_notes`
  context of Foreman Notes events (`pipeline/observability.py`
  `sentry_capture_foreman_notes`). That context is set on a forked scope
  (`sentry_sdk.new_scope()`), never on the shared scope, so it never rides on
  another event.
- The general `_redact_exception_message` WR redaction is unchanged for all
  other events, and event message text never carries a WR.
- General Foreman names are never sent (counts only), and note text is never
  sent.
- Why: when the General Foreman lookup fails and pilot groups are held, the
  operator needs exactly which Work Requests were held, and why, to audit and
  fix it.

Context and the related hold decision: Living Ledger entry
`[2026-10-30 21:40] Foreman Notes: hold changed groups when the GF lookup
fails; Sentry gap closure.` in
[`memory-bank/living-ledger.md`](../memory-bank/living-ledger.md) (quick task
261030-suf).

## 2026-10-30 - Foreman Notes GF-lookup failure severity and dry runs (owner)

- D1: the `gf-lookup-failed` and `gf-hold` Sentry events are level `error` on
  every failed publishing run, and a run that held any group checks in to the
  Sentry cron monitor as ERROR. Billing output is unchanged. Changed or new
  non-pilot groups stay held every run until the GF read works.
- D2: a `TEST_MODE` dry run never holds (it never uploads). The lookup
  failure is still reported, as a warning event.

Context: Living Ledger entry `[2026-10-30 23:30] Foreman Notes GF-lookup
hold: review fix round` in
[`memory-bank/living-ledger.md`](../memory-bank/living-ledger.md).
