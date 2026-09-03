---
name: align-instruction-files
description: Use when the repo's instruction and context files drift apart — CLAUDE.md over its size cap, AGENTS.md / .github/copilot-instructions.md older than CLAUDE.md, .planning/PROJECT.md out of step with STATE/ROADMAP, docs ledgers or memory-bank pages stale, .claude/project-state.md grown into a log, or a pointer to a moved/removed path. Runs a read-only drift check against the ownership map, then a fixed repair order (gsd health → gsd docs-update → CLAUDE.md trim + mirror regen → project-state cut → pointer validation → write-back). Docs-only; never touches code.
---

# Align instruction files (ownership map + drift check + repair order)

> Extracted 2026-09-02 from the post-Phase-12 bootstrap audit (ledger `[2026-09-02 20:20]`).
> Status: **v1.1** — the four owner decisions (AGENTS.md frozen, memory-bank stubs, cadence,
> caps 150/120) were taken by Juan on 2026-09-02; see "Decisions" at the end. Run 1 (2026-09-02)
> found that the harness-boundary hook denies every ClaudeOS write to `AGENTS.md`, so its freeze
> is an owner hand step (step 3.4).

## Purpose

Keep every file that instructs an AI session (Claude Code, Copilot, the Codex mirror) and every
file that records project truth (GSD `.planning/`, docs ledgers, `docs/ai/`, `.claude/`) saying the
same thing, each within its size cap, with no dangling pointers — so a fresh session reads a small,
current, non-contradictory set instead of four drifting copies.

## When to use

- After a GSD phase or milestone closes (PROJECT.md / STATE.md just changed).
- `/global-project-bootstrap` or the drift check reports a cap or staleness breach.
- CLAUDE.md > 150 lines · `.claude/project-state.md` > 120 lines · a mirror is older than
  CLAUDE.md · a `memory-bank/*.md` page is > 90 days old · CLAUDE.md or the context map points at
  a path that no longer exists (e.g. `portal/`, `.remember/`).
- Juan says "align the project files" / "clean up CLAUDE.md".

## When not to use

- Mid-phase execution or during a live incident (docs churn hides the real diff).
- For user-facing or code-derived docs (README, runbook, architecture prose): use
  `/gsd-core:docs-update`; this skill only calls it.
- To regenerate CLAUDE.md from scratch with `/init` — never; it clobbers curated guardrails.

## Required inputs

Repo root · clean working tree on a docs branch · the ownership map below · Juan available for
the OPEN QUESTION decisions the first time.

## Source-of-truth order

1. Repo code, tests, migrations, workflows (the territory).
2. `.planning/PROJECT.md` + `ROADMAP.md` + `STATE.md` (GSD planning truth).
3. `CLAUDE.md` + `.claude/rules/*.md` (rules; auto-loaded, must stay small).
4. `docs/ai/*` (verified implementation truth; outranks vault notes).
5. `memory-bank/living-ledger.md` (canonical dated history + decisions; grep only).
6. `.claude/project-state.md`, `docs/AI_CONTEXT_RESUME.md` (status snapshots).
7. `memory-bank/{projectbrief,systemPatterns,techContext,activeContext,progress,productContext}.md`
   (pointer stubs only after the first run; they hold no truth of their own).
8. Mirrors: `AGENTS.md`, `.github/copilot-instructions.md` — **derived, never edited by hand**.

## Ownership map

| File | Canonical for | Cap / freshness | Must NOT contain | Refreshed by |
|---|---|---|---|---|
| `CLAUDE.md` | Rules, guardrails, pointers, validation commands | ≤ 150 lines | Status, history, env-var catalogs, cron tables, architecture prose (→ `docs/ai/`, `.github/prompts/`) | This skill (step 3) |
| `.claude/rules/*.md` | Always-loaded invariants (pointer style) | each ≤ 60 lines | Second copies of CLAUDE.md text | Bootstrap / this skill |
| `.claude/context-map.md` | Read order + where knowledge lives | ≤ 80 lines | Status | This skill (step 6) |
| `.claude/project-state.md` | Current status block only (overwrite in place) | ≤ 120 lines | History (→ ledger) | Every session close; cut in step 4 |
| `.planning/PROJECT.md` / `STATE.md` / `ROADMAP.md` | GSD planning truth, decisions table | GSD-managed | Hand edits outside GSD verbs | `/gsd-core:health`, phase/milestone verbs |
| `docs/ai/*.md` | Verified implementation truth | each ≤ 130 lines; `NEEDS_VERIFICATION` allowed | Secrets, env values | `/gsd-core:docs-update`, bootstrap |
| `memory-bank/living-ledger.md` | Dated change + decision ledger | append-only | Secrets, raw PII | Every meaningful change |
| `docs/CHANGELOG_CONTEXT.md` | Operator-facing mirror of ledger entries | append | Duplicated ledger prose | Session close |
| `docs/DECISIONS.md` | Pointer stub → ledger | stub | Decisions themselves | — |
| `docs/AI_CONTEXT_RESUME.md` | Latest snapshot blockquote + history | newest snapshot ≤ 25 lines | Rules | Session close |
| `docs/PROJECT_BRIEF.md` | Why the repo exists, stakeholders | refreshed per milestone | Status | `global-docs-handoff-writer` |
| `.github/copilot-instructions.md` | Copilot summary of CLAUDE.md | date ≥ CLAUDE.md date | Hand edits | Regenerated in step 3 |
| `AGENTS.md` | Codex-owned mirror — **ClaudeOS cannot edit it** (the harness-boundary hook denies Write and Bash on `AGENTS.md`); Juan freezes it by hand with the `FROZEN MIRROR` header from step 3.4 | ≤ 15 lines once frozen | Rules text; ClaudeOS edits; routing through it | Juan, by hand, once; the drift check only reports its line count / marker |
| `memory-bank/*` (non-ledger) | **Pointer stubs** (≤ 8 lines each) → `docs/ai/` + ledger | stub only | Duplicated architecture/status prose | Collapsed in step 2 (once) |

## Procedure

**Step 0 — drift check (read-only).** From repo root, run the embedded check below. It prints
line counts + last-commit dates for every owned file, the two caps, mirror staleness, dangling
pointers in CLAUDE.md + context map, and memory-bank age. Paste the output into the PR body.

```bash
# instruction-file drift check — read-only; run from repo root (Git Bash / bash)
files=(CLAUDE.md AGENTS.md .github/copilot-instructions.md .planning/PROJECT.md .planning/STATE.md .planning/ROADMAP.md docs/PROJECT_BRIEF.md docs/AI_CONTEXT_RESUME.md docs/CHANGELOG_CONTEXT.md docs/DECISIONS.md .claude/context-map.md .claude/project-state.md docs/ai/architecture.md docs/ai/implementation-truth.md docs/ai/safe-commands.md docs/ai/decisions.md docs/ai/known-bugs.md memory-bank/activeContext.md memory-bank/systemPatterns.md memory-bank/techContext.md memory-bank/projectbrief.md memory-bank/progress.md memory-bank/productContext.md)
printf "%-40s %6s  %s\n" FILE LINES LAST_COMMIT
for f in "${files[@]}"; do if [ -f "$f" ]; then printf "%-40s %6s  %s\n" "$f" "$(wc -l <"$f")" "$(git log -1 --format=%cs -- "$f")"; else printf "%-40s ABSENT\n" "$f"; fi; done
echo; c=$(wc -l <CLAUDE.md); if [ "$c" -le 150 ]; then echo "CLAUDE.md $c lines OK"; else echo "CLAUDE.md $c lines > 150 -> step 3"; fi
p=$(wc -l <.claude/project-state.md); if [ "$p" -le 120 ]; then echo "project-state $p lines OK"; else echo "project-state $p lines > 120 -> step 4"; fi
echo; cd_=$(git log -1 --format=%ct -- CLAUDE.md); for m in .github/copilot-instructions.md; do [ -f "$m" ] || continue; md=$(git log -1 --format=%ct -- "$m"); if [ "$md" -ge "$cd_" ]; then echo "$m in sync"; else echo "$m STALE -> step 3"; fi; done; if [ -f AGENTS.md ]; then if grep -q "FROZEN MIRROR" AGENTS.md; then echo "AGENTS.md frozen by owner OK"; else echo "AGENTS.md not frozen (Codex-owned; ClaudeOS cannot edit it - owner pastes the step 3.4 header)"; fi; fi
echo; echo "dangling pointers (slash-qualified paths only; wiki/ and portal/ mentions skipped):"; grep -ohE '`\.?[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+`' CLAUDE.md .claude/context-map.md | tr -d '`' | sort -u | while read -r q; do case "$q" in *\**|*\{*|*\<*|wiki/*|portal/*|~/*) continue;; esac; [ -e "$q" ] || echo "  MISSING: $q"; done
echo; now=$(date +%s); for f in memory-bank/*.md; do [ "$f" = memory-bank/living-ledger.md ] && continue; t=$(git log -1 --format=%ct -- "$f"); echo "$f $(( (now - t) / 86400 ))d old"; done
```

**Step 1 — GSD planning truth.** `/gsd-core:health` (diagnose, then repair only what it names).
Never hand-edit PROJECT.md/STATE.md/ROADMAP.md outside GSD verbs.

**Step 2 — code-derived docs.** `/gsd-core:docs-update` for README, runbook-adjacent docs and
`docs/ai/` refresh; its verifier must pass. First run only: collapse the six non-ledger
`memory-bank/*.md` pages to ≤ 8-line pointer stubs (→ `docs/ai/architecture.md`,
`docs/ai/implementation-truth.md`, `.claude/project-state.md`, the ledger) after confirming
nothing in them is absent from `docs/ai/` — move any surviving fact there first, then stub.

**Step 3 — CLAUDE.md trim + mirror regeneration.**
1. Move, never delete: each deep section (pipeline data-flow, env-var catalog, cron/timeout
   tables, ecosystem inventories) goes to its owner (`docs/ai/architecture.md`,
   `docs/ai/implementation-truth.md`, `.github/prompts/configuration-environment.md`) and
   CLAUDE.md keeps a one-line pointer. Every guardrail sentence must still resolve to a home
   (CLAUDE.md, a rule, or `docs/ai/safe-commands.md`) — grep for it after the move.
2. Target ≤ 150 lines; show the diff before writing.
3. Regenerate `.github/copilot-instructions.md` from the trimmed CLAUDE.md (summary form: role,
   the hard guardrails, validation commands, pointers). Never hand-edit it.
4. `AGENTS.md` (owner, by hand, once): the harness-boundary hook denies every ClaudeOS write to
   `AGENTS.md` (confirmed 2026-09-02 — Write and Bash both blocked), so the session must NOT try
   to edit it. Put the header below in the PR body and ask Juan to paste it over the whole file;
   later runs leave it alone and the drift check recognises the marker. ClaudeOS must not invoke
   Codex for any of this.

   ```markdown
   # AGENTS.md — FROZEN MIRROR
   > FROZEN MIRROR — frozen 2026-09-02. Do not edit, regenerate, or sync this file.
   > Canonical rules: `CLAUDE.md` + `.claude/rules/*.md`. Implementation truth: `docs/ai/`.
   > Status: `.claude/project-state.md`. History and decisions: `memory-bank/living-ledger.md`.
   > Kept only as a stable entry point for tools that look for AGENTS.md; never regenerated.
   ```

**Step 4 — project-state cut.** Keep the header block + "Latest work" + "Next" + protected areas
(≤ 120 lines). Everything older is already in the ledger; verify each dropped dated line has a
ledger header (`grep -n "\[YYYY-MM-DD HH:MM\]" memory-bank/living-ledger.md`) before removing it.

**Step 5 — snapshot docs.** `docs/AI_CONTEXT_RESUME.md`: newest snapshot on top, ≤ 25 lines;
`docs/PROJECT_BRIEF.md`: refresh via `global-docs-handoff-writer` if older than the current
milestone (cadence: every milestone close).

**Step 6 — pointer validation.** Re-run Step 0. Zero `MISSING:` lines; context map read order
matches reality; `.claude/rules/*.md` still ≤ 60 lines each.

**Step 7 — write-back + PR.** Ledger entry (what moved where), `.claude/project-state.md`,
`docs/CHANGELOG_CONTEXT.md`, vault project page one-liner + `wiki/log.md`. Docs-only PR;
never push to `master`; `haiku-verifier` checks the pointer list; Opus reviewer optional.

## Guardrails

- Docs-only. No application code, no `.github/workflows/*`, no env files, no secrets, no PII
  (public repo: aliases only, per the ledger's public-repo identifier rule).
- **Move, never delete** guardrail text. A guardrail whose only home was CLAUDE.md must land
  in a rule or `docs/ai/` before the CLAUDE.md line goes.
- Never `/init` over CLAUDE.md. Never hand-edit a mirror. Never delete ledger history.
- Show the diff for every existing file before rewriting it.
- `.claude/rules/*.md` auto-load into every context: keep them pointer-sized.
- Harness boundary: `AGENTS.md`/`.codex/` are foreign; no Codex invocation to sync them, and no
  ClaudeOS write to `AGENTS.md` at all (the hook denies it — hand the freeze header to Juan).
- GSD files change only through GSD verbs (`health`, `phase`, `complete-milestone`).

## Verification checklist

- [ ] Step 0 re-run: no `MISSING:`; CLAUDE.md ≤ 150; project-state ≤ 120; mirrors in sync or frozen.
- [ ] Every guardrail sentence removed from CLAUDE.md greps to a new home.
- [ ] `/gsd-core:health` clean; `/gsd-core:docs-update` verifier passed.
- [ ] `cd website && npm run build` if any runbook page was touched.
- [ ] Ledger + project-state + changelog + vault updated; PR opened (not pushed to `master`).

## Common failure modes

- Trimming CLAUDE.md by deleting the change-detection-key or `@cell` rule instead of moving it.
- Hand-editing `copilot-instructions.md` "just this once" — it drifts again within a week.
- Cutting project-state history without confirming the ledger already has it.
- Leaving `memory-bank/*` pages pointed at from CLAUDE.md after retiring them (dangling).
- Running mid-phase: GSD `STATE.md` churn collides with the docs PR.
- Trying to write `AGENTS.md` from the session — the harness-boundary hook denies it; give Juan
  the step 3.4 header instead of retrying.

## Good output (example)

Step 0 table with every cap OK, mirrors "in sync"/"frozen", zero `MISSING:`; a docs-only PR
whose body pastes that table, lists each moved section as `CLAUDE.md § X → docs/ai/Y § Z`, and
links the ledger entry. CLAUDE.md reads as rules + pointers; nothing a session needs was lost.

## Bad output (example)

CLAUDE.md at 140 lines because the "Critical Pitfalls" block was deleted; `copilot-instructions.md`
edited by hand with a different cron table; project-state cut to 90 lines with three dated
decisions that never made it to the ledger; `memory-bank/systemPatterns.md` still pointed at from
the context map but retired. Any one of these rejects the PR.

## Decisions (Juan, 2026-09-02 — extraction read-back)

1. **`AGENTS.md` is frozen** with a `FROZEN MIRROR` pointer header; never regenerated, never
   synced via Codex. Frozen by Juan by hand — run 1 found the harness-boundary hook denies
   ClaudeOS writes to the file.
2. **`memory-bank/*` non-ledger pages collapse to pointer stubs** (≤ 8 lines) after any surviving
   fact is moved to `docs/ai/`; the Living Ledger stays in `memory-bank/` as canonical.
3. **Cadence: milestone close + any Step 0 breach.** Phase closes only run the Step 0 check.
4. **Caps: CLAUDE.md ≤ 150 lines, `.claude/project-state.md` ≤ 120 lines** — enforced by the
   check; a breach triggers steps 3 / 4.

No open questions remain for the first run.

## Output format

Step 0 table (before + after) · list of moves (`from § → to §`) · PR link · ledger entry id.

## Memory writeback

Ledger entry per run; project-state "Latest work" line; vault skill registry entry once the
draft is accepted (`wiki-skill-registry-update`); vault project page one-liner + `wiki/log.md`.

## Model routing

Fable main session runs Step 0, decides moves, and owns the PR. A Sonnet worker may do the
mechanical section moves and mirror regeneration from an approved move list. `haiku-verifier`
checks pointers and caps. Opus review only if the trim touches billing guardrail text.
