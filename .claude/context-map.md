# Context Map — Generate-Weekly-PDFs-DSR-Resiliency

One-screen index so a fresh session routes to the right files **without scanning
the whole repo**. Read this (Default-Startup step 2), then open only what the
task needs.

## The 3 coupled components (share a data contract)
| Component | Path | What it owns |
|---|---|---|
| **Python billing engine** (production) | `generate_weekly_pdfs.py` + `audit_billing_changes.py` | Smartsheet → row filter → WR grouping → Excel (openpyxl) → attachment upload. Cron every ~2h weekdays. **Production-critical — do not break.** |
| **Legacy Express backend** | `portal/` | Artifact-viewing API, session auth + CSRF, SSE run-polling. CommonJS, Node 20+. |
| **React frontend** | `portal-v2/` | Vite + TS + Tailwind + Supabase. Deploys to Vercel. |
| Docs runbook | `website/` | Docusaurus living runbook → Vercel. |

## Durable-context map (where knowledge lives)
| Need | File |
|---|---|
| **Rules / guardrails / architecture** | `CLAUDE.md` (lean) + `.claude/rules/` |
| **Current status ("where it stands")** | `.claude/project-state.md` |
| **Dated history + decisions + incident root-causes** | `memory-bank/living-ledger.md` ← canonical change/decision ledger |
| **Longer-form project context** | `memory-bank/` (`projectbrief`, `systemPatterns`, `techContext`, …) |
| **GSD planning front door** | `.planning/STATE.md` (+ `PROJECT.md`, `ROADMAP.md`, `phases/`) |
| **Recent session continuity / handoff** | `.remember/` |
| **Resume snapshot (periodic)** | `docs/AI_CONTEXT_RESUME.md` · setup handoff `docs/PROJECT_HANDOFF.md` |
| **Full env-var reference** | `.github/prompts/configuration-environment.md` |

> `memory-bank/living-ledger.md` is the authoritative substitute for
> `docs/CHANGELOG_CONTEXT.md` + `docs/DECISIONS.md` (those exist only as redirect stubs).

## MCP wiring (relevant to this repo)
- **Smartsheet MCP** + **Sentry MCP** — relevant to the Smartsheet→Excel→Smartsheet
  pipeline and error tracking; available via the global ClaudeOS stack.
- **Supabase MCP** — enabled locally (`settings.local.json`) but per CLAUDE.md
  Supabase is **`portal-v2`-only**, *not* part of the core billing engine.

## Skills & agents (repo-local)
- Skills: `.claude/skills/` — `run-billing-pipeline-locally`, `force-week-regeneration`, (P2) `investigate-price-anomaly`.
- Agents: `.claude/agents/` — `smartsheet-pipeline-debugger` (read-only), (P2) `billing-audit-analyst`, `excel-output-verifier`.

## Hard guardrails (see `CLAUDE.md` / `.claude/rules/billing-pipeline-guardrails.md`)
`safe_merge_cells()` only · never `oddFooter.right.text` · `PARALLEL_WORKERS ≤ 8`
· never the Smartsheet `@cell` formula in Python · keep the `advanced_options`
`key:value,key:value` parser · don't shorten the change-detection key.
