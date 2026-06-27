# Billing Pipeline Guardrails (Pointer)

> **This is a pointer, not a second copy.** Files in `.claude/rules/` auto-load
> into every context, so the billing invariants are NOT restated here — that would
> create a second always-loaded source that can silently drift from the canonical
> one. The authoritative text lives in `CLAUDE.md` and `memory-bank/living-ledger.md`.
> Read those before changing grouping, hashing, filename, attachment, or
> attribution code.

Quick index of the production guardrails (with where the full rule lives):

| Invariant | Canonical source |
|---|---|
| Change-detection key = `WR, week, variant, foreman, dept, job` — never shorten | `CLAUDE.md` → Data Pipeline Architecture; `living-ledger.md` |
| Helper rows need `helper_dept` + `helper_foreman`; dual-checkbox rows excluded from main file | `CLAUDE.md` → Helper rows |
| Excel: `safe_merge_cells()` only; never write `oddFooter.right.text` | `CLAUDE.md` → Critical Pitfalls |
| `PARALLEL_WORKERS ≤ 8` (Smartsheet 300 req/min) | `CLAUDE.md` → Smartsheet API |
| Never use the Smartsheet `@cell` formula in Python / API payloads | `CLAUDE.md` → Boundaries & Guardrails |
| Job # synonyms (`Job #`, `Job#`, `Job Number`, …) — do not collapse | `CLAUDE.md` → Critical Pitfalls |
| Keep the GitHub Actions `advanced_options` `key:value,key:value` parser | `CLAUDE.md` → Critical Pitfalls |
| WR sanitization & collision quarantine; rate recalc; attachment pre-fetch budgets | `memory-bank/living-ledger.md` (dated entries) |
| Time-budget family: `TIME_BUDGET_MINUTES` < runner `timeout-minutes` | `CLAUDE.md` → GitHub Actions Workflow |

`generate_weekly_pdfs.py` is production-critical: additive, surgical changes only;
validate with `pytest tests/ -v` before pushing.
