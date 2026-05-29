# Phase 3: Supabase Data Layer Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-29
**Phase:** 03-supabase-data-layer-foundation
**Areas discussed:** History/backfill, Supabase project placement, Publish-failure observability

---

## History / Backfill

| Option | Description | Selected |
|--------|-------------|----------|
| Go-forward only | Supabase starts empty; portal populates from the next CI run onward. Simplest, ships fastest. | ✓ |
| Backfill recent history | One-time script loads the last few weeks from local generated_docs/ or Smartsheet. | |
| Backfill ALL history | Load everything available; most work, largest storage, needs a durable source. | |

**User's choice:** Go-forward only
**Notes:** Backfill noted as an optional future follow-up in CONTEXT.md Deferred Ideas. Keeps Phase 03 focused on provisioning + the publish path rather than historical-source wrangling.

---

## Supabase Project Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse existing project | artifacts + Storage in the same Supabase project as billing_audit / Sub-project E hash store. One key set. | ✓ |
| Separate new project | Dedicated Supabase project for the portal; more isolation, duplicate keys, more to manage. | |

**User's choice:** Reuse existing project
**Notes:** Tables go in the `public` schema (not `billing_audit`) per research, to avoid the PGRST106 schema-cache footgun.

---

## Publish-Failure Observability

| Option | Description | Selected |
|--------|-------------|----------|
| Loud but non-fatal | continue-on-error (never breaks billing) + WARNING log + Sentry capture + GitHub job-summary line. | ✓ |
| Quiet non-fatal | continue-on-error with only a log line; risk of unnoticed silent publish outage. | |
| Fatal (block the run) | Would fail the billing run on a Supabase outage — violates the never-break-the-pipeline rule. | |

**User's choice:** Loud but non-fatal
**Notes:** Sentry captures must respect the project's PII redaction rules (no WR/foreman/customer/$ in events).

---

## Claude's Discretion

- Exact DDL-file location, Storage bucket name, and path convention.
- Publish-client choice (supabase-py vs storage3 vs REST) and reuse of the
  existing PostgREST retry/SQLSTATE error classifier.
- Sentry tagging specifics for publish-failure captures.

## Deferred Ideas

- Historical backfill of past artifacts (one-time script) — future follow-up.
- Separate Supabase project — considered and rejected.
- Auth/admin UI (Phase 04), table/search UI (Phase 05), Realtime + polish (Phase 06).
