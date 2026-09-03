# Context Map — Generate-Weekly-PDFs-DSR-Resiliency

One-screen index so a fresh session routes to the right files **without scanning the
whole repo**. Read this (Default-Startup step 2), then open only what the task needs.
_Rewritten 2026-09-02 (supersedes the 2026-06-27 map): `portal/` removed in 03153c3,
`.remember/` retired 2026-08-23 → claude-mem, Phase 9 `pipeline/` split, Phases 10–11
`pipeline_memory`, GSD `.planning/`, Lattice `.lattice/`, `docs/ai/` implementation truth._

## Components (share one data contract)
| Component | Path | What it owns |
|---|---|---|
| **Python billing engine** (production, cron ~2h weekdays) | `generate_weekly_pdfs.py` (thin facade) → `pipeline/` (`discovery`, `fetch`, `grouping`, `attribution`, `change_detection`, `excel`, `cleanup`, `snapshot_drift`, `orchestrate`, `config`, …) + `audit_billing_changes.py` + `billing_audit/` (attribution snapshot + hash store) + `pipeline_memory/` (Supabase run memory) | Smartsheet → row filter → WR grouping → Excel (openpyxl) → attachment upload. **Production-critical — additive, surgical changes only.** |
| **React frontend** | `portal-v2/` | Vite + TS + Tailwind + Supabase → Vercel |
| **Docs runbook** | `website/` | Docusaurus living runbook → Vercel |
| Scripts / tests | `scripts/` (`run_6_gates.sh`, backfills, Notion sync) · `tests/` (pytest) | Gates and regression suite |

Legacy Express `portal/` was removed (03153c3) — never `cd portal`.

## Read order for a fresh session
1. `CLAUDE.md` + `.claude/rules/*.md` (auto-loaded: billing guardrails, docs maintenance,
   Smartsheet/Python optimization, **Python module architecture**).
2. `.claude/project-state.md` — where the project stands (overwrite-in-place ledger).
3. `.planning/STATE.md` → `ROADMAP.md` → `phases/<current>/` — GSD position, plans, research.
4. `docs/ai/` — repo-local implementation truth (`architecture`, `implementation-truth`,
   `safe-commands`, `decisions` pointers, `known-bugs`); outranks second-brain notes.
5. `memory-bank/living-ledger.md` — canonical dated change + decision ledger. **Grep the
   header you need; never load the whole file** (8k+ lines).
6. `.lattice/config.yaml` — Lattice living-context config (GSD stays the pipeline; Lattice
   atoms are quality guardrails inside GSD phases).
7. Design specs under `docs/superpowers/specs/` (e.g. `2026-09-01-own-03-claim-time-backfill-design.md`).

## Where knowledge lives
| Need | File |
|---|---|
| Rules / guardrails / architecture | `CLAUDE.md` + `.claude/rules/` |
| Current status | `.claude/project-state.md` |
| Dated history, decisions, incident root causes | `memory-bank/living-ledger.md` (canonical; `docs/CHANGELOG_CONTEXT.md` mirrors operator-facing entries, `docs/DECISIONS.md` is a pointer stub) |
| Handoff snapshot | `docs/AI_CONTEXT_RESUME.md` |
| Implementation truth (verified from code) | `docs/ai/` |
| GSD planning | `.planning/` (`STATE.md`, `ROADMAP.md`, `REQUIREMENTS.md`, `PROJECT.md`, `phases/`, `config.json`) |
| Longer-form context | `memory-bank/` (`projectbrief`, `systemPatterns`, `techContext`, …) |
| Full env-var reference | `.github/prompts/configuration-environment.md` |
| Recent session continuity | claude-mem (auto-captured; `mem-search` skill). `.remember/` is a frozen archive. |
| Second brain | vault `wiki/projects/Generate-Weekly-PDFs-DSR-Resiliency.md` + `project-dashboard.md`. **Main session writes only**; subagents return packets to `.claude/writeback-pending/`. |

## Supabase surfaces (owner-deployed DDL/RPC — the repo never applies schema)
- `billing_audit` — `attribution_snapshot`, `pipeline_run`, `group_content_hash` (Sub-project E hash store), RPCs `freeze_attribution` / (Phase 12) `backfill_attribution` → `billing_audit/schema.sql`.
- `pipeline_memory` — `sheet_registry`, `row_state`, `row_event`, `group_state`, `run_ledger`, RPC `upsert_rows_bulk` → `pipeline_memory/schema.sql`.
- `public.artifacts` — generated-file registry read by `portal-v2`.

## MCP / tools
Smartsheet MCP · Sentry MCP · Supabase MCP (portal-v2 + run-memory reads) · Context7 for SDK docs · Serena for symbol navigation (`.serena/cache/` is local, gitignored). Codex assets (`.codex/`, `AGENTS.md`) are foreign to ClaudeOS — never routed (`~/.claude/rules/production-guardrails.md` § Harness boundary).

## Skills & agents (repo-local)
- Skills `.claude/skills/`: `run-billing-pipeline-locally`, `force-week-regeneration`, `investigate-price-anomaly` (mirrored in `.agents/skills/` for cross-runtime use).
- Agents `.claude/agents/`: read-only pipeline debugger, `billing-audit-analyst`, `excel-output-verifier`.
- Python edits: see `.claude/rules/python-module-architecture.md`.

## Hard guardrails (full text: `CLAUDE.md`, `.claude/rules/billing-pipeline-guardrails.md`)
`safe_merge_cells()` only · never `oddFooter.right.text` · `PARALLEL_WORKERS ≤ 8` · never the
Smartsheet `@cell` formula · keep the `advanced_options` `key:value` parser · never shorten the
change-detection key (`WR, week, variant, foreman, dept, job`) · a sentinel is never a claimer ·
Supabase DDL/RPC is owner-applied · live Smartsheet writes need Juan · never push to `master`.
