# Project State — Generate-Weekly-PDFs-DSR-Resiliency

_Last updated: 2026-08-28 12:05 CDT (17:05Z) · **overwrite-in-place each session** (this is the
canonical "where the project stands" landing spot for the global Stop
write-back reminder). Keep it terse; link to history rather than duplicating it._

_Latest ledger entry: `memory-bank/living-ledger.md` `[2026-08-27 21:10]` (verified pipeline truths from the
#360 review rounds — acceptance gate, group key, TEST_MODE/Supabase, Snapshot Date, reset purge, stale
attachment, public-repo identifier rule). Earlier: `[2026-08-27 20:20]` (identity row = canonical row,
ships with PR #361), `[2026-08-27 16:10]` (hash sort tiebreaker, #359).
`pipeline_memory` schema is LIVE on Supabase `poeyztlmsawfoqlanucc` (service_role-only). **Write path ON in
production** since #353 (`673f7b2`, `RUN_MEMORY_WRITE_ENABLED: '1'` on the `Generate reports` step only);
`RUN_MEMORY_INCREMENTAL_ENABLED` stays OFF. **Merged:** #351, #354, #353 (the flip), #356 (sync-client
fix — memory writes confirmed on run #2801), #358 (parity "actual" = queued-for-upload set + shadow
budget 25), #355 (docs/hook), #359 (hash sort tiebreaker). **Merged 2026-08-28 03:37Z: #360** Learn docs (`5d7b7ce`). **Merged 2026-08-28: #361** (`eb8338f`). **OPEN (Juan merges): #362** `fix/identity-helper-header-foreman` — identity row =
canonical row — its ledger/state/changelog are supersets of master's copies, so it merges clean. Phase 11 EXECUTING — **7/8 plans done**; **11-08 INC-05 retirement DEFERRED by owner** (needs
≥5 consecutive `parity_verdict = pass` on `production_frequent` runs; the streak was NOT re-checked
this session — read the latest `run_ledger.notes` before resuming). Then: checklist item 6 SQL +
items 2–3 → re-open the 11-07 decision → `/gsd-execute-phase 11` resumes at 11-08 as its own PR._

## Latest work (2026-08-28 12:05 CDT) — #361 MERGED (`eb8338f`); #362 open: one `derive_group_identity()` for Sites 1/2/3, header foreman = hash rule (owner-approved), deterministic legacy header; OWNER DECISION pending on repo-wide identifier scrub
- **#362** `fix/identity-helper-header-foreman` (`49373fd`, branch of master `b23b7af`): closes #361's three open threads. `derive_group_identity(first_row, **_identity_switches)` replaces the three inline identity chains in `main()` (switches bound once after the facade prelude); `canonical_foreman()` = hash `FOREMAN=` rule, now also the PRIMARY workbook header foreman (approved by Juan 2026-08-28; **inert in production** — `grouping.py:1166` never leaves `__current_foreman` blank — and deliberately not applied to helper-shadow/subcontractor headers, whose raw `Foreman` is the primary crew; hashes/identity keys byte-identical, golden digests); `canonical_first_row()` uses the extended total order in legacy mode too (legacy hash untouched). New `tests/test_group_identity_and_header_foreman.py` (15 tests, 144 subtests: verbatim reference chain, two-order keys, wiring, golden digests, legacy, primary-only header rule); 7 older source pins re-pointed. 1794 passed, 1 skipped; 0 added lines >79 chars. Independent review: haiku-verifier PASS ×6; production-risk-reviewer P0 none, P1 (helper-shadow header exposure) fixed, P2s applied/recorded. Ledger `[2026-08-28 12:05]`.
- **Merged:** #355 (`81eb82b`) and #359 (`a8d6795`, hash sort tiebreaker); master at `263dc34`.
- **#361** `fix/excel-header-canonical-row` **MERGED** → master `eb8338f` (code = `79e5411` + `2c51a38` + the round-3 commit of 2026-08-28; master merged in at `a68e0ad` after #360 landed — ledger/state conflicts kept this branch's copies). **Round 3 (2026-08-28):** Work Order alias + `|`-serialization tiebreakers appended to the hash-neutral sort key; `header_job_number()` is the ONE Job # alias resolver (Excel header + sort key, raw value kept for the cell); 4 new tests; 1779 pass, 0 overlong added lines. The three threads left open there are closed by the follow-up PR (bullet above). Azure DevOps mirror check fails on every PR build incl. merged #360 — pre-existing. Earlier this cycle: Greptile re-check already fixed; fictional fixture names; ledger count; changelog + safety check widened to primary/legacy one-time regeneration:
  Excel header + orchestrate Sites 1/2/3 read `canonical_first_row()`; Job # aliases AND the legacy
  identity `User` appended to the (hash-neutral) sort key; Greptile line-length fixed; PR body's
  Production Safety Check rewritten to cover identity/cleanup/prune effects + rollout expectation.
  Threads: Greptile, Copilot ×3, Codex P1, Codex Job-alias → fixed **and resolved**; Codex legacy-mode
  P2 → declined with rationale (left open); Codex first-nonempty-foreman P2 → **deferred to Juan**
  (billing-output change; left open). CI green on `79e5411`; `2c51a38` re-running at handoff. Greptile
  retrigger needs a browser login (307 → /login) — click "Re-trigger Greptile" in the PR body if it
  doesn't re-review on its own. Azure DevOps mirror check fails on every PR build (also docs-only
  #360) — pre-existing, not required (branch unprotected). 1779 tests pass. Ledger `[2026-08-27 20:20]`.
- **#360** `docs/learning-guides` **MERGED** at `344b14d` → master `5d7b7ce` (2026-08-28 03:37Z): **nineteen review rounds done** —
  Copilot auto-reviews every push here, so each fix commit drew a smaller follow-up round (4: purge
  scope = `WR_*.xlsx` on the target sheet only, no `$0` line for an admitted row, `EXCLUDE_WRS` /
  `max_groups` DO narrow an attaching run, `pipeline_memory` edge bidirectional; 5: `workflow_dispatch`
  needs write access, "normal manual run" excludes `test_mode`, cadence "up to seven a day", parity
  "actual" = groups queued for upload, computed before the upload phase; 6: **real WR + foreman name
  removed from the public guides** → `12345678` / `Jane_Doe`; the merged blog post
  `2026-08-27-parity-actual-uploaded-set.md:70` still names the real WR — follow-up; 7: local-run
  recipes use explicit EMPTY env values, never "unset" — `load_dotenv()` refills absent vars from
  `.env`; second real WR removed; `regen_weeks` cannot rebuild an emptied week; 8: Sunday has FOUR
  normal runs (Sat 3), `SKIP_UPLOAD` recipe carries the empty Supabase values inline, and the ledger
  is now carried on #360 too; 9: a plain manual run repeats the unchanged-hash skip (escalate for
  `regen_weeks`), output consumers split (`run_summary.json` → Notion; workbooks →
  `publish_artifacts_to_supabase.py` → Supabase `artifacts` → portal-v2), counts labelled normal-run; 10: VAC files are `_VacCrew_<name>` in production, `row_event`
  only on changed hash; 11: ledger `[20:20]` marked "ships with #361, pending merge" so #360 landing
  first cannot state a false production rule; 12: `_Unknown_Foreman` attribution is FROZEN
  first-write-wins — escalate, filling the foreman later won't rename it; hand-edited workbooks under the
  generated name survive unchanged-hash runs (filename-only check); withheld WRs need a target-row fix; 13: `Dept #` + `N/A` column in the layout; this file's
  timestamp corrected to wall-clock — earlier stamps this evening ran ~50 min fast; 14: `SENTRY_DSN=` in every local recipe,
  `_Unknown_Foreman` -> escalate immediately; 15: subcontractor rows with blank helper fields go to
  `_ReducedSub_User_…`, never the plain main file; 16/18: repo is PUBLIC — ids/names aliased ONLY on the ledger/state lines these rounds
  touched; a tree-wide count found 284 WR-like ids + 20 personnel names in 106 tracked files (committed
  `generated_docs/*.json` manifests, tests, `.planning/`, blog, `orchestrate.py`) + git history + old PR
  threads → **Juan decides: scrub tracked files / make repo private / rewrite history** (#360 thread
  3877686166 left open for that); 17: stale intro status rewritten, ledger "unset" → explicit-empty, changelog post says
  "key modules"; 18: names on touched ledger lines + every id in this file aliased, rule made truthful; 19: master
  merged into #360 (ledger conflict = aliased `[16:10]` entry, kept ours), merged #359 key now documented
  with the helper tiebreakers). Ledger `[21:10]` rounds 3–19.
  Round 2 (`2a271c8`): 35 Copilot/Codex/Greptile findings checked against the code; 34 fixed, 1
  declined (Greptile "reorganise the engineer guide", left open for Juan). Round 3 (Copilot
  re-review of `2a271c8`, 3 comments + 4 suppressed, all valid, fixed in `f20036e`): Snapshot Date
  must parse inside the Monday–Sunday week to appear in a day block while the total still counts
  it (`excel.py:722-736` / `:505`); billing period = week ending − 6, never Snapshot Date;
  `reset_hash_history` = global attachment purge before any group (`orchestrate.py:2374-2385`,
  destructive); a unit moved out of a week that then has no rows leaves a stale attachment
  (`cleanup.py:455-471`, `orchestrate.py:4157-4159`); acceptance gate lives in Phase 2 fetch, not
  grouping; **correction of my round-2 text: `TEST_MODE` DOES gate every `billing_audit` /
  `pipeline_memory` write (`not TEST_MODE` :3333/:3352/:1934) — only a non-test `SKIP_UPLOAD` run
  reaches `freeze_row` (:3441)**. Key round-2 truths: gate = WR + weekly date + Units Completed? +
  price > 0 (`fetch.py:837`; CU/qty/foreman don't gate); group key `(WR, week, variant, claimer)`;
  `wr_filter` only in TEST_MODE (no attaching scope); `reset_wr_list` destructive/global; real
  CDT/CST windows; runtime 40–60 (≤~75). `npm run typecheck`/`build` green both rounds; threads
  replied with the SHA and resolved (only the Greptile one open). **State file AND ledger are now byte-identical
  on #360, #361 and the main tree** — either merge order is clean for it; keep it that way (edit in
  the main tree, copy to both worktrees). Note: `CLAUDE.md` still describes grouping as
  `(WR, week_ending, variant, foreman, dept, job)` — same drift, not touched in #360 (follow-up).
- **Next:** Juan merges #362 → first `production_frequent` run after it: expect
  `<WR-A>/080226` to `Skip` and no mixed-dept helper churn (watch `billing_audit.pipeline_run`
  hashes + `group_state.last_generated_run`). Owner call pending on the header-foreman rule (Codex P2
  on #361, deferred). Then Phase 11 checklist items resume (≥5 `pass` parity verdicts → 11-08).

## Previous (2026-08-27 16:20 CDT) — three PRs queued: #355 (docs, rebased/mergeable) → #358 (parity actual = uploaded set + shadow 25) → #359 (hash sort tiebreaker, owner-approved)
- **#359** `fix/data-hash-sort-tiebreaker`: `_extended_row_fields()` extracted; EXTENDED sort key +
  hashed-field string + foreman + helper foreman/dept/job as tiebreakers (merged form `a8d6795`);
  legacy untouched. Full suite green; new
  `tests/test_change_detection_tiebreak.py` pins order-independence for ties AND byte-identity for
  tie-free groups. Post-merge validation: one-time bounded regeneration bump, then `Skip` on
  `<WR-A>/080226`. Ledger `[2026-08-27 16:10]`.
- **#355** rebased onto master in a worktree (conflicts: state file → master's; ledger → both entries
  kept, `[00:15]` before `[11:51]`); force-pushed with lease; now MERGEABLE.
- **Merge order matters** (all three touch the ledger tail / state file): #355 → #358 → #359; the
  remaining branches get rebased after each merge (merge watcher armed this session).
- **Then:** first `production_frequent` run after all three → expect `actual_withheld_excluded≈150`,
  read side ≈121 sheets probed, verdict `pass` → streak clock; `group_state` COALESCE-preserve proof
  (checklist 3b). Scheduler: 17:00Z/19:00Z missed; 21:00Z watched.

## Previous (2026-08-27 15:35 CDT) — PR #358 open: parity "actual" = uploaded set + shadow budget 25; hash-alternation churn diagnosed (sort-key tie), fix awaiting approval
- **#358** `fix/parity-actual-uploaded-set-and-shadow-budget` (`659a9be`, carries #357's docs commit):
  `_shadow_parity_input_sets()` drops generated-but-withheld groups from both sides
  (`parity_details.actual_withheld_excluded`); `RUN_MEMORY_SHADOW_MAX_MINUTES: '25'` on `Generate
  reports` (owner-approved). Suite 1760 passed / 1 skipped; runbook build green; YAML parsed.
- **Diagnosed, NOT fixed (needs approval — change-detection primitive):** `<WR-A>/080226` and a
  small set of uploaded old-week groups alternate between two content hashes with no data change
  (`billing_audit.pipeline_run`, constant `assignment_fp`). Cause: `calculate_data_hash` sorts on
  `(WR, Snapshot Date, CU, Pole/Point, Quantity)`; rows tying on that key but differing in a hashed
  field keep parallel-fetch arrival order (stable sort) → hash flips → durable store rewritten →
  regenerate + re-upload every run. Incremental would not regenerate them → real `only_in_actual`
  every run → `pass` impossible until fixed. Proposed: append the per-row hashed-field string as a
  sort tiebreaker (groups without differing ties keep byte-identical hashes; flipping groups change
  once). Validate on a known-good sample first.
- **Scheduler:** 17:00Z and 19:00Z crons missed (Actions "operational" on githubstatus); 21:00Z watched.
- **Next:** Juan merges #358 (closes #357's scope) → approve/decline the tiebreaker fix → first
  `production_frequent` run after both shows `actual_withheld_excluded≈150`, read side probed ≈121
  sheets, verdict `pass` → streak clock starts. Then COALESCE-preserve proof (checklist item 3b).

## Previous (2026-08-27 14:35 CDT) — #356 MERGED; first real memory run #2801 confirmed writes + IN-01 proof; parity `fail` is a comparator/budget problem, not a selector defect
- **#356 merged** (`8904008`; master `5a9bbf3`). Manual dispatch #2801 (33102956870, `success`, 53 min):
  `26 sheet(s) written, 0 errored … confirmed=True`; `run_ledger` `33102956870.1` `sheets_changed=26`,
  `mem_confirmed=true`. `group_state` holds 4 uploaded groups with `attachment_id`s verified against
  Smartsheet (checklist items 2–3 first half done; COALESCE-preserve half = next run).
- **`parity_verdict=fail`, structural:** (1) `_shadow_actual_hashes` includes the 154 withheld
  quarantine groups (`_NO_MATCH`/`Unknown_Foreman`, regenerated every run, never uploaded) →
  `group_key_set_mismatch` on every run; "actual" must be the uploaded set. (2) read side abandons
  65/121 sheets inside `RUN_MEMORY_SHADOW_MAX_MINUTES=10` → `skipped` → overall can never be `pass`;
  ~25 min needed. The 40 `only_in_candidate` groups were the 08-25→today baseline gap (self-heals).
  **Owner decisions needed:** comparator "actual" definition (D-07 refinement) and the shadow budget
  (workflow env — protected). Ledger `[2026-08-27 14:35]` has the full evidence.
- **Open:** churn group `<WR-A>/080226` re-uploaded every run since 15:57Z despite an unchanged
  authoritative hash — investigate before 11-08. Scheduler: 17:00Z + 19:00Z crons missed; watcher armed.
- **Next:** Juan decides the two comparator changes → small PR (parity.py/orchestrate.py + tests +
  env) → streak clock restarts on the first `production_frequent` run after it. #355 still open.

## Previous (2026-08-27 11:58 CDT) — post-flip run wrote NO run memory (supabase-py AttributeError); fix on PR #356, awaiting merge
- **Merged since last entry:** #354 (`46b64ac`, review fixes), #353 (`673f7b2`, the flip —
  `RUN_MEMORY_WRITE_ENABLED: '1'` on the `Generate reports` step only). #355 (docs: `sheets_errored`
  column fix, handoff, PreCompact hook script) still OPEN.
- **Incident:** first run carrying the flip (manual dispatch 33090659647, success on billing) logged
  `⚠️ Supabase client init failed … (AttributeError)` → 0 sheets written / 113 errored /
  `confirmed=False` / parity skipped / no `run_ledger` row. `billing_audit`'s own client worked.
  Root cause reproduced locally on `supabase==2.31.0`: WR-02 passed the base `ClientOptions` to the
  sync `create_client`, which needs `SyncClientOptions` (`.storage`). Mocked tests never ran the
  real constructor.
- **Fix — PR #356** (`fix/pipeline-memory-sync-client-options`, `1c23980`): `SyncClientOptions`
  first with fallbacks; bare-client retry if the SDK rejects options; warnings carry `Type: message`;
  real-SDK construction regression test + fallback test; runbook symptom row; ledger
  `[2026-08-27 11:51]`. Greptile P2 (missing changelog) fixed in `f37c0ee`: synthesized post
  `website/blog/2026-08-27-pipeline-memory-client-init-fix.md`; all repo checks green, only the
  pre-existing Azure mirror check red. Suite **1754 passed / 1 skipped / 141 subtests**; `npm run build` green.
- **Scheduler:** cron recovered on its own — scheduled run 33094866957 queued 16:45Z (GitHub-side
  outage this morning, not the repo). It runs unfixed `master`, so expect the same warning once more.
- **Session config:** `.claude/settings.local.json` `autoCompactWindow: 500000` + PreCompact
  `precompact-vault-log.js` (vault `[2026-08-27e]` proves it fires). Local checkout is on the #356
  branch; `generated_docs/hash_history.json` is the owner's dirty file — never sweep it.
- **Next:** Juan merges #356 → first scheduled `production_frequent` run must show `0 errored …
  confirmed=True` + a `run_ledger` row (item-6 SQL in `docs/run-memory-write-flip-checklist.md`) →
  five `pass` verdicts → re-open the 11-07 decision → resume Phase 11 at 11-08. Residual: supabase-py
  deprecates `timeout`; next SDK bump moves it to `httpx_client`.

## Previous (2026-08-26 23:40 CDT) — #353 review findings resolved: code fixes in #354, docs on #353; both PRs mergeable, nothing merged
- **Findings (all valid):** Greptile P1 ×3 (partial reads → false deletions in the deep-run
  reconciliation; empty `row_event` evidence → vacuous parity `pass`; missing runbook changelog),
  Codex P1 ×2 (memory-write ambiguity — already fixed in `66ce083`; delta rows that LOSE their
  WR/date dropped before the upsert → prior group never regenerates), Copilot ×3 (stale
  stacked-branch wording, "both blocks" rollback, unmet pre-merge gate). Cursor's Medium-High
  was against the pre-rebase 49-file diff. Azure DevOps mirror check fails on `master` too —
  pre-existing.
- **#354 (code, TDD, verified):** `fetch.get_last_full_read_failed_sheet_ids()` + reconciliation
  skip (`sheets_skipped_failed_read`) + `_resolved_mode == 'full'` gate; `get_changed_row_ids_by_sheet`
  → `None` on failure, `run_shadow_delta_reads` `skipped` for none/empty/unprobed evidence,
  `pass` needs `rows_asserted > 0`; `map_delta_sheet_rows(dropped_row_ids=)` +
  `reader.get_row_state_pairs_for_rows` + PHASE 2a union / `trigger_prior_identity_lookup_failed`.
  RED→GREEN; suite **1752 passed / 1 skipped / 141 subtests**; `run_6_gates.sh` ALL PASSED; haiku-verifier
  PASS 6/6; boundary + protected paths clean.
- **#353 (docs, `379ca5a`):** blog post `website/blog/2026-08-27-run-memory-write-flip.md`,
  Operations runbook section + rollback row, Environment reference Phase 11 section, checklist
  corrections (requires #354 first). `npm ci && npm run typecheck && npm run build` green. All
  review threads answered (disposition comment + 4 thread replies).
- **Local:** on `fix/deep-run-partial-reads-parity-evidence`; `website/node_modules` + `build/`
  now present (ignored). Uncommitted, untouched by design: `generated_docs/hash_history.json`.

## Previous (2026-08-26 21:30 CDT) — #351 MERGED; flip PR rebased as #353 (2 files, mergeable); local on `master`
- #351 squash-merged as `82ce830` and its branch deleted → GitHub auto-closed the stacked #352
  (`CONFLICTING`). Parked `generated_docs/hash_history.json`, rebased the single flip commit
  `435958a` → `2675aa5` onto `origin/master` (`7b4239c`), force-pushed with lease, opened **#353**
  (`master` base, diff = workflow + checklist only, flag resolves to `'1'` on `Generate reports`
  only, YAML validated). Local checkout switched to `master` (= origin); stale local branches
  `feat/phase-11-incremental-read` / `ops/run-memory-write-flip` left for Juan to prune.
- Verified on `master`: `RUN_MEMORY_WRITE_ENABLED` absent from the workflow (code default `'0'`),
  `upsert_rows_bulk_result` + `trigger_memory_write_unconfirmed` present. Repo secrets present:
  `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SMARTSHEET_API_TOKEN`, `SENTRY_DSN` — nothing to add.

## Previous (2026-08-26 18:50 CDT) — Greptile P1 on #351 FIXED: unconfirmed memory write can no longer masquerade as "nothing changed"
- **Defect (Greptile P1, `pipeline/orchestrate.py` PHASE 2a):** `upsert_rows_bulk` returned an empty
  set for six reasons (empty input, no client, writes disabled, all row-ids bad, every chunk failed,
  genuinely nothing changed) and a *partial* chunk failure returned a silent subset; the incremental
  path read any of those as a legitimate no-change run → zero groups regenerated → stale billing
  Excel/attachments. Dormant today (both flags OFF) but a must-fix before `RUN_MEMORY_INCREMENTAL_ENABLED`.
- **Fix (additive, fail-closed):** `pipeline_memory.writer.upsert_rows_bulk_result()` reports
  `status ∈ ok|noop|unavailable|disabled|partial|failed` next to the set (`upsert_rows_bulk` is now a
  thin wrapper, contract unchanged); `_run_memory_write_phase` folds every sheet's status, writer
  exceptions, the pre-flight skip and the mid-loop budget break into `memory_confirmed` +
  `unconfirmed_reason` (+ `sheets_unconfirmed` / `sheets_unwritten`); `_run_phase2_incremental`
  returns `ok=False` with `trigger_memory_write_unconfirmed` BEFORE reading `affected` (legacy dict
  without the flag = unconfirmed); the 11-05 shadow comparator reports `skipped` /
  `memory_write_unconfirmed` instead of a spurious parity `fail`; both `run_ledger_finish` sites
  persist notes `mem_confirmed`. Full-mode generate/upload/cleanup untouched.
- **Evidence:** new `MemoryResultAmbiguityTests` (20 tests: writer vocabulary, phase flag, PHASE 2a
  escalation, `main()` wiring by source inspection) + 6 existing mocks moved to the new contract;
  suite **1725 passed / 1 skipped / 141 subtests**; `run_6_gates.sh` ALL PASSED (mypy 65→65);
  `schema.sql` / `.github/workflows/` / golden baseline untouched. Committed to
  `feat/phase-11-incremental-read` (PR #351); #352 stacks on it unchanged.

## Previous (2026-08-26 17:42 CDT) — `/gsd-execute-phase 11` waves 5–7 DONE (7/8 plans); 11-08 DEFERRED by owner decision
0. **Resume:** Juan answered "approve" to the 11-05 Task 1 `blocking-human` write-flip gate with the
   gate evidence explicitly NOT met (flip PR unmerged; `pipeline_memory` populated only by Phase 10's
   manual rollout — `row_state` 209,464, `sheet_registry` 120/120 watermarked, `run_ledger` 1 real
   manual success with `sheets_changed: 0`, `group_state` 0). That approval was carried forward to the
   same-class `<precondition>`s in 11-06/11-07 Task 1 (recorded verbatim in each SUMMARY). Dispatch
   unchanged: `gsd-core:gsd-executor` on sonnet, sequential on the main tree (`worktree.base-check`
   degrade, HEAD ≠ `origin/HEAD`), `AUTO_MODE=false`; 11 new commits on `feat/phase-11-incremental-read`.
1. **Plans landed:** 11-05 `62b2364` (`pipeline/parity.py`: `compare_shadow_parity`,
   `run_shadow_delta_reads`, `combine_verdicts`; sub-budgeted shadow hook after the group loop gated
   full-mode + write-flag-on + incremental-off + not TEST_MODE; `RUN_MEMORY_SHADOW_{MAX_MINUTES,
   RPC_TIMEOUT_SEC,GENERATION_HEADROOM_MIN}`; `parity_verdict`/`parity_details` folded into
   `run_ledger.notes`, never `run_summary.json`; D-08 changed-row source = existing
   `pipeline_memory.row_event`; 30 tests) · 11-06 `4341511` (`get_row_state_row_ids`,
   `mark_rows_deleted`, `weekly_comprehensive`-gated `_reconcile_deep_run_deletions` +
   `_repair_group_state_for_affected_pairs` + `column_mapping` refresh with drift breadcrumb; zero
   schema change; 44 tests; **`.planning/WINDOWS.md` id 2 OPEN** — a group whose *last* row is deleted
   gets no `group_state` repair) · 11-07 `1eab3db` (`get_parity_streak` D-09: pass counts / fail resets
   / skipped excluded, auditable dict or `None`; 11 tests; Task 2 decision **`defer`** recorded with the
   live streak table + re-authorisation path for 11-08's opening gate).
2. **Gates:** orchestrator `py_compile` + `pytest -x` after each wave 1650 → 1694 → **1705 passed /
   1 skipped / 141 subtests**; each executor `scripts/run_6_gates.sh` ALL PASSED (mypy 65→65);
   `pipeline_memory/schema.sql`, `.github/workflows/`, `tests/golden/run_summary_baseline.json`
   untouched; every commit staged by explicit path (this file, `hash_history.json`, the ledger never
   swept in). Post-wave test gates green at each of the 3 waves.
3. **11-08 (INC-05 retirement) NOT executed** — owner chose `defer`: D-12's five-consecutive-`pass`
   condition is structurally unsatisfiable until the flip PR merges and the 11-05 shadow runs on
   schedule, and retiring on this branch would bundle the removals with the incremental-read work
   (forbidden by 11-07's own prohibition). Phase 11 stays EXECUTING at 7/8; INC-05 open; no
   VERIFICATION.md (phase gates run only once no incomplete plan remains). **Next:** (a) owner flip PR
   (`RUN_MEMORY_WRITE_ENABLED='1'` in both `env:` blocks, per `docs/run-memory-write-flip-checklist.md`)
   → (b) ship this branch so the shadow hook runs on scheduled `production_frequent` runs → (c) ≥5
   consecutive `pass` verdicts via `get_parity_streak()`, the `group_state` attachment-id proof, and the
   "before" wall clock vs the 94-min baseline (run `32743959053`) → (d) re-open the 11-07 Task 2 decision
   in `11-07-SUMMARY.md` (option id + real streak output) → (e) `/gsd-execute-phase 11` resumes at 11-08
   as its **own PR, never bundled**. 11-08 also owns the Phase 11 Living Ledger entry; an interim entry
   `[2026-08-26 17:42]` covers waves 5–7. Uncommitted, untouched by design: this file,
   `generated_docs/hash_history.json`, `memory-bank/living-ledger.md` (pre-existing edits + the interim entry).

## Previous (2026-08-26 14:56 CDT) — `/gsd-execute-phase 11` waves 1–4 DONE (4/8 plans); PAUSED at 11-05 Task 1 `blocking-human` write-flip gate
0. **Resume:** Juan's "continue" taken as `approved` for the 11-01 tracer gate → continuation executor ran
   Tasks 2–3. Dispatch unchanged: `gsd-core:gsd-executor` on sonnet, sequential on the main tree
   (`worktree.base-check` degrade, HEAD ≠ `origin/HEAD`), `AUTO_MODE=false`, all commits on
   `feat/phase-11-incremental-read` (now HEAD `20f0dac`, 26 commits ahead of the plan-set base `b4c0f88`).
1. **Plans landed:** 11-01 `f4a5baf` (WR-04 `run_ledger.sheets_changed` on both finish paths `7ffa57a`;
   IN-01 `docs/run-memory-write-flip-checklist.md` `a67cb39`; ledger entry; review-followups todo closed) ·
   11-02 `3505158` (`pipeline_memory/reader.py`, `pipeline.fetch.fetch_sheet_delta`, `resolve_run_mode`
   with the 7 D-02 triggers, capture-time watermarks, `run_ledger.mode`/`notes.fallback_reason`;
   `RUN_MEMORY_INCREMENTAL_ENABLED` default OFF; mypy Gate-4 fix `ab75dfa`) · 11-03 `de44662` (D-06:
   `keep_historical` threaded to both `cleanup_untracked_sheet_attachments` call sites, hash-history
   prune gated on `_resolved_mode == 'full'`) · 11-04 `20f0dac` (PHASE 2a/2b split,
   `map_affected_to_sheets`, `_filter_groups_to_affected`, scoped counters; **D-05 approved partial**
   recorded under INC-02 in REQUIREMENTS.md — checkbox intentionally unticked).
2. **Gates (orchestrator-run after each wave):** `py_compile` clean; `pytest -x` 1531 → 1574 → 1592 →
   **1620 passed / 1 skipped / 141 subtests**; schema-drift / codebase-drift / ui-safety all `block=false`;
   each executor also ran `scripts/run_6_gates.sh` ALL PASSED (mypy 65→65). Protected files untouched
   waves 2–4: `pipeline/{grouping,excel,pricing,attribution}.py`, `.github/workflows/`,
   `pipeline_memory/schema.sql`. Note: the 11-02/03/04 `type="tracer"` tasks were self-verified by the
   executor without a human pause (only 11-01's surfaced) — flag if you want tracers to gate again.
3. **Paused — `blocking-human` (never auto-approved):** 11-05 Task 1 needs the owner-approved
   `RUN_MEMORY_WRITE_ENABLED='1'` flip PR against `weekly-excel-generation.yml` (protected area, not part
   of any Phase 11 plan) merged, one real `production_frequent` run populating `run_ledger` /
   `row_state` / `sheet_registry` in `poeyztlmsawfoqlanucc`, and checklist items 2–3 (upload-enabled
   control run, `group_state` attachment-id proof). Waves 6–8 chain on 11-05. **Next:** work the
   checklist → re-run `/gsd-execute-phase 11` → answer "approved". Uncommitted, untouched by design:
   this file and `generated_docs/hash_history.json`.

## Previous (2026-08-26 12:35 CDT) — `/gsd-execute-phase 11` STARTED: wave 1/8 plan 11-01 at tracer checkpoint (1/3 tasks)
0. **Dispatch settings (evidence from this run):** executor `sonnet` (project config), branching `none` —
   all commits stay on `feat/phase-11-incremental-read`; isolation auto-degraded to **sequential on the
   main tree** (`worktree.base-check`: HEAD `b4c0f88` ≠ `origin/HEAD` `3183687`, #683/#3659) — no
   worktrees, no merges; `AUTO_MODE=false` so every `autonomous:false` / tracer checkpoint surfaces to
   Juan; code-review hook active at `execute:post`. Executor prompts pass reference paths (not inlined
   ~100 KB) per the prompt-caching overlay — the `gsd-executor` definition already embeds its protocol.
1. **11-01 Task 1 (WR-01) DONE — `4323cec` `fix(11-01): parse decorated Quantity/Units Total Price on
   memory write path`.** `pipeline/orchestrate.py` `_run_memory_write_phase` stashes `__mem_quantity`
   (`pipeline.pricing._parse_quantity`) + `__mem_units_total_price` (`parse_price`) per row (empty →
   `None`, not pricing's 0.0 default); `pipeline_memory/writer.py` `_row_to_payload` reads only those
   keys (no raw-cell fallback, import boundary intact); 4 regression tests in
   `tests/test_pipeline_memory_shadow.py` (RED verified via stash, then GREEN). Orchestrator spot-check:
   `81 passed, 3 subtests`, writer boundary `WRITER_BOUNDARY_OK`, `py_compile` exit 0. No live
   Smartsheet/Supabase call; `RUN_MEMORY_WRITE_ENABLED` stays OFF.
2. **Paused:** plan 11-01 `type="tracer"` human-verify gate (blocking) — awaiting Juan's "approved" to run
   Task 2 (WR-04 `run_ledger.sheets_changed` on both finish paths) and Task 3 (flip checklist doc,
   IN-01 COALESCE verification, Living Ledger entry, resolve
   `.planning/todos/pending/2026-08-25-run-memory-review-followups.md`). `.planning/STATE.md` carries
   the executor's uncommitted position update. Remaining: waves 2-4 autonomous → wave 5 human-verify
   (flip PR merged + one real run) → 07/08 `checkpoint:decision`.

## Previous (2026-08-26 09:15 CDT) — `/gsd-plan-phase 11` COMPLETE: research → 8 plans / 8 waves → checker PASSED (iteration 2), all gates green
0. **Research:** `gsd-phase-researcher` (Sonnet) wrote `11-RESEARCH.md` (617 lines, HIGH confidence) —
   no new deps; inventoried every `all_rows` consumer after PHASE 2; the one new risk: three end-of-run
   maintenance blocks in `orchestrate.py` (`valid_wr_weeks`, both `cleanup_untracked_sheet_attachments`
   sites, hash-history prune ~3164-3259) iterate all groups unconditionally and would delete live
   attachments/history for untouched groups in incremental mode unless gated (fix reuses
   `KEEP_HISTORICAL_WEEKS` + `_time_budget_exceeded`); `pipeline_memory` has no reader → new `reader.py`.
   Nyquist `11-VALIDATION.md` seeded; `11-PATTERNS.md` (12/14 analogs). Spec-less edge probe: 7 rows
   (INC-01/02/03 unclassified → flagged assumptions; INC-04 ×3 + INC-05 ×1 authored into must_haves).
1. **Plans (Opus planner, `afbde00` → revised `41e03fb` → `f6f941b`):** strictly linear 8 waves —
   01 WR-01/WR-04/IN-01 + flip checklist doc + ledger entry · 02 delta read + 7 D-02 triggers +
   capture-time watermark + `run_ledger.mode` (`pipeline_memory/reader.py` NEW) · 03 D-06 preservation
   gates (dominant risk, test-first) · 04 PHASE 2a/2b split + affected-set→sheet mapping + scoped regen
   (INC-02 partial recorded in REQUIREMENTS.md) · 05 **human-verify gate** (write flip merged + one real
   run) then `pipeline/parity.py` shadow comparator + D-08 shadow delta reads · 06 deep-run
   reconciliation (deletions / `column_mapping` refresh / formula-only) · 07 D-09 streak scan +
   **checkpoint:decision** · 08 INC-05 retirement (own PR, re-checks the streak at execution time) +
   closing ledger entry. `autonomous: false` on 05/07/08. Checker iteration 1: 0 blockers / 4 warnings
   (split 07→07/08, `run_6_gates.sh` moved from task-level verifies to plan-level gates, RESEARCH open
   questions marked RESOLVED, Living Ledger tasks added) → iteration 2 **VERIFICATION PASSED**.
   Gates: requirements 5/5, decisions 12/12, gap-analysis 17/17, path probe 75/75 none.
   `COVERAGE.md` written (36 capabilities / 16 reasoned opt-outs). STATE "Ready to execute" (8 plans).
   **Next:** `/clear` → `/gsd-execute-phase 11` — waves 1-4 autonomous; execution halts at wave 5 until
   Juan merges the `RUN_MEMORY_WRITE_ENABLED` flip PR (cut from plan 01) and one real run populates
   `pipeline_memory`. Protected-area edits (workflow env block) remain behind `checkpoint:decision`.
   Open advisory: RESEARCH Assumption A4 (no second `hash_history` prune site) rests on a grep sweep —
   plan 03's tests must prove it; plan 08 sits at the scope-warning threshold by D-12 design.

## Previous (2026-08-26 07:30 CDT) — `/gsd-discuss-phase 11` COMPLETE: 4/4 areas decided, `11-CONTEXT.md` written, pause artifacts cleared
0. **Resumed** from `11-DISCUSS-CHECKPOINT.json` (no advisor re-dispatch; the four `11-ADVISOR-*.md`
   tables were presented in one pass). Juan took the advisor recommendation in all four areas plus
   three follow-ups → **D-01..D-12** in
   `.planning/phases/11-incremental-read-affected-group-regeneration/11-CONTEXT.md` (`72ab958`);
   alternatives preserved in `11-DISCUSSION-LOG.md`. Locks in one line each:
   **watermark** = fixed `SAFETY_WINDOW_MINUTES=15`, `last_read_at` captured before the read and
   persisted as-is (spec §4's persist-time `now − window` is superseded), seven FULL-read escalation
   triggers in the same change, deletions never on the frequent path (deep run writes
   `row_state.deleted_at`); **regen** = Option C hybrid (affected `(wr, week)` set from
   `upsert_rows_bulk` selects sheets → scoped full re-fetch → unmodified grouping/excel path; zero
   schema change; Option B `row_state`-exclusive deferred; INC-02's "rows from row_state" clause is an
   approved partial); **parity** = shadow-incremental in-process on the same snapshot (group-key set +
   `calculate_data_hash()` equality, verdict in `run_ledger.notes`, never `run_summary.json`; shadow
   also issues the real delta reads with a read-side assertion; sub-budgeted, never a vacuous pass;
   streak = consecutive `production_frequent` evaluated runs, `skipped` excluded); **rollout** = plan 01
   fixes WR-01/WR-04/IN-01 and the `RUN_MEMORY_WRITE_ENABLED` workflow flip is a separate owner-gated
   PR cut from it; `RUN_MEMORY_INCREMENTAL_ENABLED` default OFF, `production_frequent`-only, fallbacks
   visible via `run_ledger.mode`; INC-05 retirement is its own PR strictly after the ≥5-run streak.
   `.planning/HANDOFF.json`, `.continue-here.md`, checkpoint removed; STATE session recorded (`b9f50d1`).
   **Next:** `/gsd-plan-phase 11` (researcher must inventory `orchestrate.py` `all_rows` consumers for
   D-06 scoping; planner inserts a human-verify before the first plan that needs populated memory).
   Protected-area edits (workflow env block / execution-type step) still pause for Juan.

## Previous (2026-08-25 23:55 CDT) — PR #350 MERGED (Phase 10 on master); local master re-synced; post-merge gate green
0. **Merge:** https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/pull/350 squash-merged as
   `99dc25d` (2026-08-26 04:47Z; 55 branch commits incl. the Greptile fixes `6965f95`); `docs-changelog.yml`
   stub + Notion-worker runbook update (`e203e3c`, `81d3b46`) landed on top. Local `master` was 0 ahead /
   4 behind → `git merge --ff-only origin/master` (no divergence this time — the branch was cut from a
   pushed master); `feat/phase-10-run-memory` deleted (remote auto-deleted; squash-merge "not merged to
   HEAD" warning expected, content equivalence verified: branch tip vs master differed only by the two
   post-merge docs commits). **Gate on merged tree:** `pytest tests/ -q` → **1525 passed, 1 skipped,
   135 subtests, 23 s**. Working tree carries only the pre-existing local `generated_docs/hash_history.json`
   prune-marker diff (untouched, leave or discard). Stray local branch `cursor/sync-job-run-logs-803d`
   (Cursor bot) — deleted below. **Next:** `/gsd-plan-phase 11` (Incremental Read + Affected-Group
   Regeneration, INC-01..05) on `feat/phase-11-incremental-read`; flag-flip-PR preconditions unchanged
   (WR-01, WR-04, IN-01, low-activity comparator rerun, `group_state` attachment-id proof).
1. **PR triage resolved (2026-08-26 00:25 CDT, Juan: "let's resolve this"):** Seer #343/#347/#348
   CLOSED (false `statusCode` premise, verified on SDK 4.3.0; master already correct + test-pinned) and
   #346 CLOSED (empty revert). Dependabot #344 (tsx 4.22.4→4.23.12) + #345 (supabase-js 2.107→2.112.3)
   MERGED — `scripts/`-only (sole consumer `security-probe.ts`), CI green; their `code/snyk` ERROR and
   Azure-mirror FAILURE are systemic on Dependabot branches (no secrets; the same Azure check also
   failed at 13 s on the merged #350). Cursor #328/#331/#338 CLOSED — three competing versions of a new
   bot-generated `docs/sync-job-run-logs.md` that already documents the removed Express portal; the
   runbook is maintained by the Notion worker. Local `master` → `fb11109`; `feat/phase-11-incremental-read`
   rebased (`7982b0f`) and pushed; stray `cursor/sync-job-run-logs-803d` deleted. **Backlog NOT touched:
   44 open PRs remain** — ~24 Dependabot (majors: pandas 3, mypy 2, React 19, TS 7, actions v7 bumps),
   Seer #321/#322 (likely superseded by merged #341), #287/#290/#291 (column_ids serialization),
   Copilot #75–#275, and Juan's own #91/#137/#138/#139/#149/#166/#282. Needs its own triage pass.
2. **PAUSED mid `/gsd-discuss-phase 11` (2026-08-26 00:40 CDT, `/gsd-pause-work`):** `/gsd-plan-phase 11`
   found no CONTEXT.md → Juan chose discuss first. Advisor mode (calibration `full_maturity`): todo
   `run-memory-review-followups` FOLDED; all four gray areas selected (read watermark & safety window;
   affected-group regen & row source; parity proof harness; rollout/kill switch/retirement order);
   all four `gsd-advisor-researcher` tables returned and are persisted as
   `.planning/phases/11-*/11-ADVISOR-*.md`. **No decision locked, no CONTEXT.md yet.** Handoff:
   `.planning/HANDOFF.json` + `.planning/phases/11-*/.continue-here.md` + `11-DISCUSS-CHECKPOINT.json`.
   **Resume:** `/gsd-resume-work` or `/gsd-discuss-phase 11` → Resume → present tables (no re-dispatch).

## Previous (2026-08-25 21:50 CDT) — Phase 10 CLOSED: `/gsd-verify-work 10` 2/2 decided, verification passed, transition to Phase 11
0. **UAT:** `verify:pre` api-coverage gate blocked on `COVERAGE.md` cell lengths → trimmed (`8486113`).
   Test 1 (SC4 byte-identical) — Juan accepted the canonicalized-content proof; low-activity rerun →
   flag-flip-PR precondition. Test 2 (`group_state` attachment id) — Juan: defer → recorded as pass
   (decision test) + Deferred Follow-Ups (`60e66fc`, `1679829`); `phase uat-passed` treats any
   `skipped` as a blocker (GSD gap, ledger lesson). `10-VERIFICATION.md` → `passed`; predicate 0 blockers.
   **Transition:** `phase.complete 10` (STATE only; ROADMAP/PROJECT hand-evolved; handoff removed);
   ROADMAP row 10 = 6/6 ✅ 2026-08-25; PROJECT.md Current State + 2 decision rows; ledger `[21:50]`.
   **Next:** PR #350 opened (https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/pull/350) → Seer PR triage (#343/#346/#347/#348) →
   `/gsd-plan-phase 11`. Flag-flip-PR preconditions: WR-01 (todo `8b844a6`), comparator rerun in a
   low-activity window, `group_state` attachment-id proof on first real upload.
1. **Seer PR triage (22:15 CDT, read-only — nothing closed yet):** #343/#347/#348 all assume the
   SDK exposes `statusCode` (camelCase); verified FALSE on installed `smartsheet-python-sdk 4.3.0`
   (`ErrorResult.status_code` only, `hasattr(ErrorResult, "statusCode")` → False) and master's
   `pipeline/fetch.py::_is_auth_api_error` + `tests/test_fetch_auth_errors.py` already cover both
   paths → **close, don't merge**. #346 (Seer's own revert) has an empty diff → close as no-op. The
   Sentry symptom `ApiError: 0: Unknown error` is a status-0 result, not a 401/403 — separate
   root-cause if it recurs. **PR #350 CI:** re-triggered on `d9b1779`; the Azure mirror check
   (`JFlo21.Generate-Weekly-PDFs-DSR-Resiliency`) failed at 15 s on the first push and is
   re-running — check before merge. Dependabot #344/#345 routine.
2. **PR #350 Greptile findings fixed (23:25 CDT, ledger `[2026-08-25 23:25]`):** all three valid.
   (1) = WR-03 CLOSED — `main()` `finally` writes `run_ledger_finish(status="failed")` on
   `_session_failed` (guarded, fail-open; `RunLedgerFailurePathTests`). (2) `mem04_passive_compare`
   compares `row_modified_at` as parsed UTC instants (`_parse_timestamp`; handles `Z`/`+00:00`/
   `+00:00Z`/fractional/naive). (3) `compare_control_run` reports `duplicate identity` in a
   directory instead of silently keeping the last file. TDD RED 8 → GREEN; suite 1525 passed /
   135 subtests; 6 gates ALL PASSED; haiku-verifier PASS. Todo: WR-02/WR-03 struck; WR-01/WR-04/
   IN-01 remain flag-flip-PR preconditions.

## Previous (2026-08-25 20:30 CDT) — `/gsd-execute-phase 10` COMPLETE (6/6 plans, 4 waves, sequential); tail gates done; verification human_needed
0. **Execution:** 10-01 → 10-04 → 10-02 → 10-05 (Juan: "you run this for me" → Claude built the
   MEM-04 sandbox rig via Smartsheet MCP + SDK, ran probes a–f; verdict **PASS**, D-09 OPEN) →
   10-03 → 10-06 (Juan applied `schema.sql` + exposed the schema; Claude found and fixed the
   missing service_role GRANTs `2df3b25`, Juan applied them; four real `SKIP_UPLOAD` runs proved
   neutrality/idempotence/fail-open; two live-only bugs fixed `514589a`, `cf3568b`).
   **Tail gates:** post-merge gates green every wave; code review 0C/4W/1I (`7e86f46`, follow-ups
   todo `8b844a6`); regression 978 passed / 17 files; Nyquist validated, 0 gaps (`c292d5d`);
   security 21/21 closed after T-10-04 per-RPC timeout wired (`b48efd7`, haiku-verifier PASS)
   → `10-SECURITY.md` (`eda4110`); gsd-verifier **human_needed 11/13** → `10-UAT.md` (`bf9f919`).
   Suite **1514 passed / 1 skipped / 135 subtests**; 6 gates ALL PASSED; mypy 65→65; protected
   files untouched. **Next:** `/gsd-verify-work 10` — (1) accept canonicalized-content proof for
   SC4 "byte-identical" or require a low-activity rerun; (2) carry `group_state` attachment-id
   proof to the flag-flip PR. Then push branch → PR → Seer PR triage (#343/#346/#347/#348).
   Operational notes: two diagnostic `run_ledger` rows remain in prod (no DELETE grant by design);
   rig sheets `6295051624730500` / `4909062725521284` left in the `Sandbox` workspace (disposable).

## Previous (2026-08-25 01:40 CDT) — PR #349 merged; local `master` re-synced; post-merge gate green
0. **Merge:** https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/pull/349 squash-merged as
   `c409c32` (32 commits `7e7c818`..`bb1a064`); `docs-changelog.yml` stub `22ab153` on top. Local `master`
   had diverged (ahead 29 / behind 17) because the branch was cut from unpushed local commits —
   verified `git diff bb1a064 c409c32` empty, then `git reset --keep origin/master` (kept the
   uncommitted `hash_history.json` edit). `feat/phase-09-gap-closure` deleted (remote auto-deleted).
   **Gate on merged tree:** `pytest tests/ -q` → 1388 passed, 1 skipped (Windows exec-bit, `1071fef`),
   132 subtests, 25 s. Also on master now: #341 (Sentry auth-noise, `pipeline/fetch.py`), #342
   (cloud-agent install). **Open PRs to triage:** Seer #343/#346/#347/#348 all touch Smartsheet
   auth-error detection and partly contradict each other (#341 already landed) — likely close, not
   merge; Dependabot #344/#345 (`scripts/` tsx, supabase-js) routine. Next unchanged:
   `/gsd-core:gsd-execute-phase 10` (optional `/gsd-core:gsd-complete-milestone` first).

## Previous (2026-08-25 01:10 CDT) — `/gsd-execute-phase 09 --gaps-only` COMPLETE: G-09-MOD-06 closed, `rebaseline` executed, tail gates green, phase closed
000000000000000000000000. **Wave 2 resumed:** Juan replied `rebaseline` → continuation
   executor recorded it (`6c6ca41`/`a1499d6`); orchestrator regenerated the golden
   baseline with the gate's own invocation (65 lines, LF) and committed it with the
   attributed ledger entry + a todo for the single class-A finding (`da7d73c`).
   `bash scripts/run_6_gates.sh` → **ALL 6 GATES PASSED in 32 s** (Gate 4 `65 -> 65`;
   Gate 6 synthetic, 0 API calls, hash_history sha unchanged). **Tail gates:** Nyquist
   +8 pin tests (`d4e6911`, harness file 21 tests) + `09-VALIDATION.md` (`178148b`);
   `09-SECURITY.md` threats_open 0 (`c631a43`); regression gate 726 passed on prior-phase
   files; `09-REVIEW.md` 0 critical / 3 warning / 1 info — Gate 4 follow-ups tracked
   as a todo (`b9e1643`); ui-review skipped (no frontend surface); **gsd-verifier
   passed 6/6** → `phase.complete` (`410235e`). Suite: **1386 passed + 132 subtests**.
   ROADMAP/STATE/PROJECT evolved by hand (this ROADMAP layout isn't parsed by
   `roadmap.analyze`). Vault: project page §"Phase 09 gap closure executed", dashboard
   row, log `[2026-08-25a]`. Pushed as https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/pull/349. `generated_docs/hash_history.json` still
   carries the pre-existing local prune-marker diff (untouched, leave or discard).

## Previous (2026-08-24 23:30 CDT) — `/gsd-execute-phase 09 --gaps-only` Wave 1 DONE, Wave 2 at checkpoint (7 commits `7633432`..`76011aa`)
0000000000000000000000. Sequential mode (base-check auto-degrade: HEAD ≠ origin/HEAD).
   Pre-dispatch hygiene commit `7633432` (ledger/state/config from earlier
   sessions). **09-07 complete** (`c4fb38a` RED → `6a5d321` GREEN → `1bd0bee`
   LF pin → `a925453` ledger → `dd3a9fb` SUMMARY): Gate 4 now hard-fails on
   non-integer operands (`_assert_count`) and strips CR/tab; 5 fail/pass-
   capability tests run the real script bytes; `tests/golden/*.txt text eol=lf`.
   Post-wave gate: py_compile OK, **1380 passed + 132 subtests**. Measured
   handoff: `FAIL: mypy error lines increased (56 -> 65)` exit 1. **09-08
   Tasks 1–2 complete** (`4441b52` Gate 6 pinned `SMARTSHEET_API_TOKEN=` →
   synthetic path, PASS 21 keys in 2 s, mode=synthetic/sheets=0/api_calls=0,
   hash_history sha256 unchanged; `76011aa` attribution report
   `.planning/debug/mypy-delta-56-to-65-2026-08-24.md`: 10 new findings =
   1 A (`billing_audit/snapshot_store.py:370`, runtime-guarded) / 2 B / 7 C /
   0 D, none from Phase 09 — all from post-09 quick tasks). **Task 3 checkpoint
   open** (see header). `run_6_gates.sh` intentionally still red at Gate 4
   until the decision is implemented. Observation to carry: baseline stores
   Windows `\` paths → Gate 4 FAIL-diff would be noise on Linux CI.

## Previous (2026-08-24 14:35 CDT) — DIAGNOSIS ONLY: `_User_<NAME>` (WR <WR>) root-caused; helper-sheet gaps traced to data gates
0000000000000000. GSD debug session
   `.planning/debug/unknown-foreman-helper-shadow-2026-08-24.md`
   (status root_cause_found; no code/data/workflow change). (1) The
   source sheets' `Foreman` column is a WR-level RA lookup that blanks
   when a WR is archived; `freeze_row` then froze the literal
   `'Unknown Foreman'` sentinel as the claimer (first-write-wins,
   2026-04-24 backfill run 24912872441) and `resolve_claimer` never
   re-resolves it → 5,824 snapshot rows / 93 WRs affected; ~154
   garbage-claimer primaries regenerate every run. Fix direction
   (needs Juan): null the sentinel at freeze + treat frozen sentinel
   as no_history + approved remediation SQL + durable "last known
   foreman" source for archived WRs. (2) Helper sheets: scheduled run
   32743959053 evaluated all 166+5 helper groups (0 dropped); missing
   helper files are data-gated (`Helper Dept #` formula blank — WRs
   <WR>/<WR> — or `Foreman Helping?` blank). Need one concrete
   (WR, week, helper, run) example for the "only after full regen"
   claim. Ledger entry `[2026-08-24 14:35]`; wiki project page + log
   updated. Manual run 32748717671 (Juan, 16:04 UTC) was still
   in_progress at last check.

## Previous (2026-08-24 22:00 CDT) — `/gsd-verify-work 09` DONE: retroactive verification → gaps_found (Gate 4 vacuous); gap-closure plans 09-07/09-08 **checker PASSED** (`c8986b6`, addendum `8af3dfb`)
000000000000000000000. Phase 09 had NO GSD artifacts on disk (never committed;
   PR #280 `889ca2e` merged 2026-06-27; ROADMAP still `[ ]`). Created
   `.planning/phases/09-engine-modularization-pipeline-package-split/`;
   `gsd-verifier` (sonnet) wrote `09-VERIFICATION.md` — **retroactive**,
   5/6 must-haves verified against code (MOD-01..05), **MOD-06 FAILED**:
   `scripts/check_mypy_delta.sh` cannot fail — `tests/golden/mypy_baseline_count.txt`
   is CRLF on this `core.autocrlf=true` checkout, `tr -d ' \n'` leaves `\r`,
   the `-gt` test errors inside an `if` → falls through to PASS while mypy
   drifted **56 → 65** (bug present since Phase 09's own merge `5005040`; no
   Gate-4 fail-capability test exists). Live gates today: G1/G2/G3(1375)/G5
   PASS; **G6 PASS on the synthetic path** (`SMARTSHEET_API_TOKEN=""` — with
   the `.env` token present, `TEST_MODE` does a full 118-sheet/208,511-row
   production READ (orchestrate.py:299); that stalled run was killed, no
   writes possible: SKIP_UPLOAD + no Supabase creds locally). Gap-closure
   plans (opus, `c8986b6`): **09-07** (Gate-4 fail tests RED→GREEN, harden
   script, `tests/golden/*.txt eol=lf`, ledger rules; autonomous) → **09-08**
   (pin Gate 6 token-blank, attribute the 9 new mypy errors, **blocking-human**
   decision fix-types / rebaseline / split). Expect the harness RED at Gate 4
   after 09-07 until Juan's 09-08 decision — that is correct. Latent: mypy
   baseline stores Windows backslash paths (Linux diff noise) — flagged, not
   planned. Next: checker verdict → `/gsd-core:gsd-execute-phase 09 --gaps-only`
   → re-run `/gsd-verify-work 09` → then Phase 10 execution. Harness is NOT
   invoked by any GitHub workflow (developer-side only).

## Previous (2026-08-24 18:30 CDT) — Phase 10 plan-phase (docs only; no code/schema/workflow)
00000000000000000000. `/gsd-core:gsd-plan-phase 10` running (agent-teams OFF; single
   orchestrator). Done so far: `10-RESEARCH.md` (sonnet researcher, commit
   `2c86ca5`; HIGH confidence stack/architecture, MEDIUM pg_cron project state +
   MEM-04 SDK shape), `10-VALIDATION.md` Nyquist draft (`7621e82`), and
   `10-PATTERNS.md` (sonnet pattern mapper, `25ffbdb`; 10 files → analogs). Two
   planner-critical pitfalls surfaced: `row_state.foreman_observed` must store the
   RAW `Foreman` cell, never `__effective_user` (the `'Unknown Foreman'` sentinel
   defect); the `pipeline_memory` writer needs its OWN client/kill-switch state,
   not `billing_audit.client`'s schema-agnostic global disable. Spec-less edge
   probe: 6 unresolved items (MEM-01/03/04 unclassified; MEM-02 adjacency/empty/
   ordering) handed to the planner. **Plans landed** (opus planner, 42 min,
   commits `4ccb54c` + `cc65b71`): 6 plans / 4 waves — 10-01 tracer
   (`pipeline_memory/` pkg, independent fail-open client, full DDL, `run_ledger`,
   flag default OFF) ∥ 10-04 (MEM-04 read-only probe CLI + cassette harness);
   10-02 (`row_state`/`row_event` chunked bulk write, own sub-budget) ∥ 10-05
   (MEM-04 experiment, **blocking-human**: Juan hand-edits the sandbox rig);
   10-03 (`sheet_registry` + `group_state`); 10-06 (control-vs-shadow byte proof,
   **blocking-human** DDL apply + PostgREST expose + retention-job review). Planner
   decisions: `group_state` PK promoted to `(wr, week_ending, variant, identifier,
   target_sheet_id)` (reduced_sub fan-out); `run_summary.json` stays 21 keys
   (counters → `run_ledger.notes`); `upsert_rows_bulk` always chunks at 500;
   `sheet_registry.kind` drops `vac_crew`. Also `COVERAGE.md` + filled
   `10-VALIDATION.md`. **Plan-checker: iteration 1 = 1 BLOCKER + 3 warnings**
   (10-06 scoped real-data `SKIP_UPLOAD` runs with `WR_FILTER`, which
   `grouping.py:1222` only honors under `TEST_MODE` → fixed to `MAX_GROUPS`;
   added `git diff --exit-code -- billing_audit/` guards; Nyquist latency
   rationale + sub-30s first checks; RESOLVED markers on RESEARCH open
   questions; DDL checkpoint cross-refs corrected to 10-06 T2) → revision
   `321f595` → **iteration 2 = VERIFICATION PASSED** (1 cosmetic warning:
   PATTERNS.md rows, fixed). Gates: requirements 4/4, decisions 9/9,
   gap-analysis 13/13, verify-path probe 59/59 clean. STATE.md → "Ready to
   execute" (6 plans); ROADMAP annotated (4 waves); final commit `94b6d80`.
   **Phase 10 is PLANNED — next: `/gsd-core:gsd-execute-phase 10`.** Planner
   flag still stands: `STATE.md` reads `current_phase: 9` — run
   `/gsd-verify-work 09` first for a clean handoff (10-01 Task 1 has a
   `run_6_gates.sh`-must-pass precondition on an unmodified checkout).
   Next after planning: `/gsd-core:gsd-execute-phase 10` (Phase 09 already merged).

## Previous (2026-08-24 17:05 CDT) — Phase 10 discuss-phase DONE; CONTEXT.md locked (docs only, no code/schema/workflow)
0000000000000000000. `/gsd-discuss-phase 10` (advisor mode, 3 sonnet research
   packets) produced `.planning/phases/10-run-memory-foundation-shadow-writes/
   10-CONTEXT.md` + `10-DISCUSSION-LOG.md` (commit `11f6c8d`) and a STATE.md
   session row (`481a02a`). Locked: **#2** new `pipeline_memory` schema in
   `poeyztlmsawfoqlanucc`, service-role-only RLS, versioned SQL mirror,
   PostgREST exposed-schema step explicit (PGRST106 runbook); **#5-prov**
   `source` CHECK enum + nullable `source_ref` on row_event/group_state;
   **#3** row_event = single UNPARTITIONED table (pg_partman is not
   installable on hosted Supabase), indexes observed_at/(sheet_id,row_id)/
   (wr,week_ending), 24-mo pg_cron sliced DELETE; **#4** weekly deep run
   stays the full reconcile, no schedule change; **MEM-04** = hybrid proof —
   Juan hand-builds 2 disposable sandbox sheets, READ-ONLY script records
   `if_version_after`/`rows_modified_since` as a replayable pytest cassette +
   passive shadow-run comparison; zero Smartsheet API writes. Rollout posture
   (flag off in code, workflow flip in a separate PR, write sub-budget) left
   as Claude's discretion with conservative defaults. Next: `/clear` →
   `/gsd-plan-phase 10`. Still uncommitted: ROADMAP v1.4 diff + untracked
   spec; `.claude/project-state.md` + ledger edits from this session.

## Previous (2026-08-24 15:58 CDT) — Phase 10 plan-phase PAUSED at context gate; three blockers fixed (no code)
000000000000000000. `/gsd-plan-phase 10` ran init (reqs MEM-01..04, models
   sonnet/opus/sonnet, security hook ASVS L1 block-on-high, UI gate
   frontend=false, drift skipped) and stopped at the no-CONTEXT gate —
   Juan chose "discuss-phase first". Empty phase dir created:
   `.planning/phases/10-run-memory-foundation-shadow-writes/`. Fixes
   applied afterwards: (1) `.claude/settings.local.json` (gitignored)
   sets `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=0` for THIS repo only —
   GSD orchestration stalls under agent-teams (open-gsd/gsd-core#1355);
   global `~/.claude/settings.json` still has it "1" for other repos;
   takes effect on the NEXT session. (2) v1.4 MEM/INC/OWN/AUD reqs
   merged into `.planning/REQUIREMENTS.md` (+16 traceability rows,
   coverage line) and committed with the milestone copy — commit
   `7e7c818` on master, NOT pushed — so plan-phase Step 13 coverage
   gate can see them. (3) ROADMAP Phase 10/12/13 "Depends on" and spec
   §8 now tag each Juan decision with the phase it gates: Phase 10 =
   #2 schema placement, #3 row_event retention, #4 deep run = full
   reconciliation (+#5 only as a provenance column); #1 → Phase 12,
   #5 backfill → Phase 12, #6 → Phase 13. ROADMAP.md and the spec
   remain UNCOMMITTED (ROADMAP carries Juan's earlier ~1,000-line v1.4
   draft diff; spec is untracked). Next: restart session (so the env
   override loads) → `/gsd-discuss-phase 10` → `/gsd-plan-phase 10`
   (research=yes already chosen). Note: Phase 09 MOD-01..11 are also
   absent from REQUIREMENTS.md (pre-existing, untouched).

## Previous (2026-08-24 15:30 CDT) — v1.4 "Supabase Run Memory" PLANNED (GSD draft, no code)
00000000000000000. Juan asked for a Supabase-as-memory redesign: per-row
   state + history every run (no duplicates), incremental Smartsheet
   reads, regenerate only affected (WR, week) files, "last known foreman
   as of the week" ownership, audit findings that persist until fixed.
   Written: spec `docs/superpowers/specs/2026-08-24-supabase-run-memory-design.md`
   (schema draft `pipeline_memory.*`, run algorithm, ownership ladder,
   audit lifecycle, evidence table from run 32743959053: fetch 33 min /
   207,844 rows, attachment pre-fetch 20 min, 12,227 freeze RPCs,
   3,091 hash GETs), `.planning/milestones/v1.4-REQUIREMENTS.md`
   (MEM/INC/OWN/AUD), ROADMAP.md Phases 10–13 + Progress rows.
   Verified: SDK 4.3.0 `get_sheet(if_version_after=, rows_modified_since=)`
   + API `ifVersionAfter`/`rowsModifiedSince` (Context7). BLOCKED on
   Juan's spec §8 decisions (ownership semantics vs Foundation A
   first-write-wins, schema placement, retention, deep-run
   reconciliation, backfill sources). Next: `/gsd:plan-phase 10` after
   decisions; `/lattice-init` before implementation.

## Previous (2026-08-15 01:12 CDT) — #340 MERGED (`96e42cb`); local repo tidied; #338 last open PR
000000000000000. Juan merged+deleted #340. Local: 5 [gone] branches
   deleted (260812-isx…260814-health-guardrail-hardening), 9 stale
   remote refs pruned, master ff'd to `644b1af`. Health system now
   COMPLETE on master: entry point (#339) + verified green manual run
   31860218831 (OK) + hardened dispositions (#340). Open: #338 only
   (docs, `8c06bdb`). Watch: Aug 16 ~02:20 UTC cron = first scheduled
   green expected.

## Previous (2026-08-14 23:10 CDT) — PR #340 OPEN: guardrail-check hardening (#339 follow-up)
00000000000000. Juan approved closing the warm follow-ups → **PR #340**
   (`06b979d`, branch feat/260814-health-guardrail-hardening): absent
   TIME_BUDGET_MINUTES in the production workflow now WARNs (engine
   default 0 = budget disabled = 180-min hard-kill risk; worker-key
   absence stays a note — default 8 AT cap, asymmetry documented
   in-code); worker counts <1 WARN as non-positive. +4 tests (0/neg/
   boundary-1/absent split); at-cap fixture given valid budget. Suite
   1375+132 green; live smoke vs real workflow still OK. ctx.client
   pre-auth cosmetic finding intentionally SKIPPED (triaged, closed).
   Commit-body test count "1378" is a typo (1375 correct — noted in
   PR body). Pending: Juan merges #338 + #340; watch tomorrow's
   ~02:20 UTC cron for first scheduled green.

## Previous (2026-08-14 22:05 CDT) — #339 MERGED (`2cb20ab`); FIRST GREEN health run verified; #338 refreshed
0000000000000. Juan merged #339 (02:48 UTC). Manual dispatch run
   31860218831 on merged master = **success, Overall status: OK** —
   first green system-health run ever; all checks passed incl. the
   new production-workflow guardrail parse (8/8/165/180). Nightly
   02:20 UTC Aug 15 run had fired 28 min PRE-merge on 864cf09 (last
   legacy failure — expected). #338 follow-up done: merged master
   into the branch (brings shipped script; prevents another
   stale-base bot round) + replaced the KNOWN BROKEN callout with a
   dated FIXED note citing #339 + run 31860218831; pushed `8c06bdb`,
   awaiting Juan's merge. Post-merge bot refinements on #339 code
   (absent-TIME_BUDGET leniency vs pipeline/config.py:106 default;
   0/negative worker counts pass cap; ctx.client set pre-auth)
   remain UNTRIAGED — offered as a small follow-up PR on master.

## Previous (2026-08-14 17:55) — GSD quick 260814-me8: #339 vacuous-guardrail Greptile fix pushed (`881a1ef`); MERGEABLE
000000000000. Ran via GSD quick lane (opus planner → sonnet executor →
   haiku verifier, all PASS): new `check_production_workflow_config`
   in validate_system_health.py parses weekly-excel-generation.yml
   DIRECTLY (stdlib regex; comment-stripped; `\|\| 'N'` GitHub-
   expression fallbacks resolved as the scheduled-run value) and
   grades PARALLEL_WORKERS/_DISCOVERY ≤8 + TIME_BUDGET_MINUTES
   strictly < max timeout-minutes; missing workflow file = CRITICAL;
   values redacted/truncated before report echo. Env check kept,
   relabeled process-env-only. Commits `9690cdd` (code, 14 new tests
   → 35 in file) + `881a1ef` (GSD docs: PLAN/SUMMARY/STATE row).
   Suite 1371+132 green; live smoke vs real workflow = STATUS_OK
   (8/8/165/180, no current drift). Workflow file untouched
   (protected). GSD artifacts ride PR #339 via tracked .planning/.
   Note: gsd-tools shim at ~/.claude redirects to a BROKEN .codex
   plugin cache copy (missing lib/cli-exit.cjs); worked around via
   ~/.claude/plugins/cache/gsd-core/.../bin/gsd-tools.cjs — repair
   pending (npm install && npm run build:lib in the codex cache).

## Previous (2026-08-14 15:35) — #338 stale-base Greptile finding resolved by merging master into the branch (`4e4d039`)
00000000000. Round-2 Greptile finding on #338 ("PRICE_VARIANCE_IN_RISK
   not implemented") was a STALE-BASE artifact: the branch forked at
   `3711b92`, before #336's squash (`359a073`) added
   `_price_variance_in_risk`. Doc text is correct against master, so
   the fix was merging origin/master into the branch (clean, no
   conflicts) — NOT rewording the doc to describe pre-#336 behavior.
   Suite 1336+132 green on the merged branch; #338 MERGEABLE at
   `4e4d039`. Lesson: verify bot findings against the branch's
   merge-base before "fixing" docs that are right on master.

## Previous (2026-08-14 15:05) — PR #339 OPEN: maintained validate_system_health.py (nightly workflow fix)
0000000000. **#337 MERGED by Juan (19:15 UTC).** Then Juan approved
   adding the missing health entry point → **PR #339** opened:
   `validate_system_health.py` + 21 offline tests + gitignore +
   ledger entry. Matches system-health-check.yml's EXISTING contract
   (always writes generated_docs/system_health.json, exits 0 when
   written; evaluate step owns pass/fail) → **workflow file untouched**
   (protected area). Read-only, ≤2 API calls/run, no secrets/PII in
   output. Full suite 1357 passed +132 subtests; local smoke run
   verified (facade probe green after Windows UTF-8 subprocess fix —
   lesson in ledger). **Pending:** Juan merges #338 + #339, then
   remove the KNOWN BROKEN callout from docs/sync-job-run-logs.md;
   first green nightly run confirms end-to-end.

## Previous (2026-08-14 14:35) — #338 Greptile fixes pushed (`fd55190`); MERGEABLE
000000000. All 3 Greptile findings on **#338** (docs/sync-job-run-logs.md)
   verified VALID against master and fixed, docs-only: (1) audit risk
   is a per-RUN count ladder (0/≤3/>3 via `_risk_level_for`), not
   per-anomaly dollar-delta — doc now says so + price-variance
   report-only default; (2) `validate_system_health.py` does NOT
   exist → system-health-check.yml fails nightly (last 3 runs
   failure) — documented KNOWN BROKEN, intended-vs-actual;
   **follow-up decision for Juan: add the entry point or repoint the
   workflow (protected area)**; (3) Snyk: only code/iac tests carry
   `|| true`; monitor + SARIF upload unguarded; missing token ≠
   silent skip. No workflow/code touched.

## Previous (2026-08-14 13:30) — #337 Greptile fix pushed (`874020e`); still MERGEABLE
00000000. Greptile finding on **#337** fixed (valid): the new hold-gate
   ledger entry cited `snapshot_drift.py` line numbers (465 gate /
   512 log) — replaced with symbol refs (`_apply_holds()` gate +
   "🔒 Snapshot-drift hold" INFO line, verified still the ONLY
   changed_by log site). Docs-only commit `874020e` via temp
   worktree; older merged ledger entries left as-is (append-only).
   Repo-local `core.longpaths=true` set (Windows checkout fix).

## Previous (2026-08-14 13:15) — PR #336 MERGED (squash 359a073); #337 conflict pre-resolved → MERGEABLE; vault synced
0000000. Juan merged **#336** (price-variance demotion live on master —
   next scheduled run should report risk_level LOW/MEDIUM with
   anomalies ~575 still visible report-only). **#337** updated:
   merged origin/master into the branch, resolved the expected
   living-ledger EOF conflict (both blocks kept, chronological,
   merge commit `553a068`) → GitHub reports MERGEABLE; one-click
   for Juan once checks finish. Second brain synced: project page
   close-out (Open items → CLOSED, durable lessons 4–7) +
   wiki/log.md 2026-08-14 entry. Local master pulled to `afceb29`.

## Previous (2026-08-14 MIDDAY) — queue executed: PR #336 (demote price-variance from risk) + PR #337 (hold gate ON) both OPEN; mismatches=0 confirmed
000000. **Run 31813915527 (15:19 UTC): rate-sanity mismatches=0** —
   both repairs verified at production scale; no new automation-race
   hits. Drift run 3: candidates=110 all legit (manual=40,
   unclassified=70, self_fire=0, holds=0). **PR #336**
   (`feat/260814-demote-price-variance-risk`): `_total_issues_for_risk`
   shared helper + `PRICE_VARIANCE_IN_RISK` (default false); detector
   stays report-only; 13 new tests; suite 1336+132 green; ledger
   `[2026-08-14 11:10]`; Greptile review fixes pushed (`f9e82ad`):
   typed test helpers + flag documented in configuration-environment.md
   + `price_variance_in_risk` advanced_options dispatch passthrough. **PR #337**
   (`feat/260814-enable-drift-hold-gate`): SNAPSHOT_DRIFT_HOLD_ENABLED
   → 'true' in workflow env + IN-04 resolved (changed_by kept —
   automation-only by construction, verified); ledger `[11:25]`.
   **Merge #336 FIRST; #337 will then show a trivial ledger conflict
   (both append at EOF) — keep both blocks, chronological order.**
   After merge: expect audit risk_level LOW/MEDIUM (anomalies still
   reported ~575), holds=0 steady state.

## Previous (2026-08-14 AM) — both underbilled rows REPAIRED (Juan-approved API re-save) + drift steady state ACHIEVED
00000. **Repair executed + verified** (ledger `[2026-08-14 10:05]`):
   <WR> → $113.68 (Backup 83; wk-08-09 Excel REGENERATED by run
   31805121266); <WR> → $1,179.36 (Backup 73; wk-08-16 file
   regenerates next scheduled run via hash change). Working idiom:
   same-value write = Smartsheet no-op; text→number Quantity
   type-flip forces recalc. Snapshot Dates NOT re-stamped; no
   automation revert on either edit (consistent with the 08-13
   automation fix). Run 31805121266: rate-sanity mismatches=1 (row 1
   pre-run fix) → expect 0 next run. **Drift steady state:
   candidates=0 seeded=155 unchanged=200,765 holds=0 → hold-gate PR
   (SNAPSHOT_DRIFT_HOLD_ENABLED) unblocked, awaiting Juan.**

## Previous (2026-08-13 NIGHT) — 2 rate-sanity mismatches IDENTIFIED (read-only repro) + legacy-detector verdict: era gate insufficient
0000. **Juan confirmed the Smartsheet automation UI trigger fix is DONE**
   (queue item 4 → future repair sweep unblocked). Read-only local
   repro (scratchpad driver, detector-only) matched burn-in counters
   and identified the 2 mismatches — **both underbilled exactly one
   unit** (actual = rate × (qty−1), stale Install-Quantity formula
   class): WR <WR> / SAA-DE-20 / Inst / qty 2 ($56.84 vs
   $113.68; ProMax Backup 82/83 + Intake Promax 9) and WR <WR> /
   DEC-20AL-C / Inst / qty 4 ($884.52 vs $1,179.36). **Juan action:**
   check Quantity vs Install Quantity on those rows, re-save to
   recalc — upstream fix only. **Legacy `_detect_price_anomalies`
   measured:** 575 → 239 flags under the rate-sanity era gate (risk
   still HIGH); per-(WR,CU) re-base explodes (5,192–6,968) —
   recommendation: retire/demote (exclude from risk ladder or
   env-flag off), needs Juan's go. NEW gap: audit's "AUDIT: Risk"
   Sentry alert produces ZERO org events in 7d (suspect oversized
   audit_results context dropped at ingest + T-ISX-01 tension).
   No production code changed. Ledger `[2026-08-13 23:00]`.
   **ROOT CAUSE CONFIRMED via cell history (`[2026-08-14 00:50]`):**
   both mismatches = automation-triggered recalc racing a human qty
   edit (correct price reverts 2-3s later to stale-qty price).
   Exact rows: Backup 83 row 5538447881863044 (<WR>, wk 08-09,
   already underbilled $56.84) + Backup 73 row 1166598725369732
   (<WR>, **wk 08-16 CURRENT — re-save before next run** or it
   bills $294.84 short). Both predate Juan's 08-13 automation fix;
   rate-sanity counters on future runs verify whether the race died.

## Previous (2026-08-13 EVE) — #334 MERGED + **billing_audit DDL APPLIED TO PRODUCTION** → PR #335 OPEN (schema.sql mirror)
000. **DDL LIVE (Juan-approved, via Supabase MCP):** 3 migrations on
   project `poeyztlmsawfoqlanucc` — drift tables
   (`snapshot_provenance`, `snapshot_drift`) + `lookup_snapshot_
   provenance_bulk` RPC + search_path pin. WR-03 RESOLVED at apply:
   RLS + `service_role_all` policies on both new tables (sibling
   parity). Verified live: tables/RLS/policies present, RPC callable
   (0 rows = correct empty state), `pgrst_ddl_watch` auto-reloaded
   PostgREST, advisors clean of new findings. schema.sql mirrored →
   **PR #335 OPEN** (`chore/260813-schema-sql-mirror-applied-ddl`,
   c6fa488; suite re-run 1323+132). **BURN-IN RUN 1 CLEAN** (GH run
   31761117011): drift seeded 200,765 / candidates=0 / holds=0, RPC
   active (no PGRST202); rate-sanity mismatches=2 (was 115,272),
   out_of_scope=115,340. NEW FINDING: risk HIGH now driven by LEGACY
   price-variance detector (575 anomalies, unscoped) — candidate
   follow-up needs Juan's go. Hold gate stays OFF until a few clean
   runs. Ledger `[2026-08-13 22:00]`. Remaining Juan items:
   Smartsheet automation UI trigger fix + remediation prompt (still
   REQUIRED before any snapshot-date repair sweep); IN-04 PII call.

## Previous (2026-08-13 PM) — #332 & #333 MERGED → PR #334 MERGED: RPC bulk provenance read + audit follow-ups (GSD 260813-nhn)
00. **GSD quick task 260813-nhn → PR #334 OPEN** (branch
   `feat/260813-nhn-snapshot-store-followups`, 8 commits
   8918dea..6e78ab3). Closed: P2/#333 weekly-fallback flag parity
   (`RATE_RECALC_WEEKLY_FALLBACK` AND column mapping); WR-05 24-test
   snapshot_store characterization oracle; WR-02 RPC bulk provenance
   read — `lookup_snapshot_provenance_bulk(p_keys jsonb)` appended to
   billing_audit/schema.sql (manual apply WITH the 2 jqx blocks, then
   `NOTIFY pgrst, 'reload schema'`), Python RPC-first w/ PGRST202
   probe → CHUNKED .in_ fallback capped at `_FALLBACK_MAX_CHUNKS=50`;
   sibling fix: upsert chunked (1000/POST). Safety review
   (SAFE-WITH-NOTES) fix round `d63457c`: zero-row RPC corroboration
   probe (mis-applied RPC returning [] can no longer rebase every
   baseline — empty-table probe distinguishes genuine first sight),
   fallback cap, log fix. RESEARCH quantified: at 199,717 keys the
   old two-.in_ read = ~3.4-4MB GET (would fail on DDL apply);
   upsert = ~40MB POST. Status vocabulary frozen at
   success/no_row/fetch_failure/unavailable. Suite **1323+132**
   (39 new); haiku PASS 8/8 + re-verify PASS; no pipeline/ changes.
   WR-03 RLS deliberately NOT included (Juan's DDL call). IN-04
   (changed_by email at INFO) still open — Juan's PII-posture call.
   **Next: Juan reviews/merges PR #334.**
0. **GSD quick task 260813-m5j (research→plan→execute→verify):** the two
   post-merge #332 review findings fixed on
   `feat/260813-m5j-rate-sanity-scope-hardening` → **PR #333 OPEN**.
   KEY RESEARCH CORRECTION: Copilot's "restrict to subcontractor
   membership" was INVERTED — the incident sheet (Backup 86,
   1824542300262276) is one of 110/115 NON-subcontractor sheets; the
   gate now EXCLUDES `__is_subcontractor` rows (reason
   `subcontractor_basis`). Codex F1: weekly fallback fail-closed via
   `_rate_sanity_snapshot_column_index()` from source_sheets
   column_mapping (latent today: 115/115 sheets map Snapshot Date).
   VAC-on-non-sub stays in scope (test R4). Suite 1284+132,
   haiku-verifier PASS 8/8. Commits 4245450/a7c27b2/63c38c7/ca77332.
   **Next: Juan reviews/merges PR #333.**
1. **Rate-sanity scoping (task 4 of the 08-13 list, Juan's GO):**
   `_rate_sanity_in_scope()` in `audit_billing_changes.py` reuses the
   SUB-01/D-08 era gate (`_resolve_rate_recalc_cutoff_date`, cutoff
   `_AEP_BILLABLE_CUTOFF` 2026-04-12, weekly-ref fallback). Pre-cutoff/
   undatable rows → new `rate_sanity_out_of_scope` counter, never
   checked. Kills the 58% old-rates false-positive class (115,272/
   199,717 rows) that pinned risk HIGH every CI run. TDD, 8 new tests.
2. **jqx review nits closed:** IN-01 utcnow → now(utc); IN-02 module
   logger; IN-03 cross-pin comments; IN-05 snapshot_store NEVER-raises
   made real + first direct tests (`tests/test_snapshot_store.py`,
   chips at WR-05); IN-07 shared `_risk_level_for()`. NOT done: IN-04
   (PII posture — Juan), WR-02 (RPC), WR-03 (RLS/DDL — Juan).
3. **WR_FILTER skill-doc fixed** (TEST_MODE-only, grouping.py:1222) +
   runbook blog rewritten for scoping + ledger `[2026-08-13 15:30]`.
4. **Suite 1274 passed** (1263 + 11 new), py_compile clean. Branch
   `feat/260813-rate-sanity-current-cycle-scope`, 3 commits
   (93a32dd feat / 5320b1f fix / 6e51313 docs; IN-07 diff rides in
   the feat commit). **Next: Juan reviews/merges PR #332.** Juan's own
   ops queue unchanged: Smartsheet automation UI fix → remediation
   prompt on other DB sheets → apply 2 DDL blocks in
   billing_audit/schema.sql → burn-in → enable hold gate.

## Previous work (2026-08-12) — SAA-DE-20 overbill root-caused (upstream data, not code) + Snapshot Date automation defect proven + quick task 260812-isx in flight
1. **Field-reported wrong pricing solved:** WR <WR> / Point 27 /
   SAA-DE-20 showed 3 EA @ $341.04 (should be 3 × $56.84 = $170.52).
   Root cause: stale Smartsheet `Install Quantity` formula cell on
   "Resiliency Promax Database Backup 86" (Quantity edited 6→3 on
   2026-08-06, formula never recalculated). Contract rate and Python
   pipeline both verified CORRECT (primary variant is pass-through by
   design). Juan re-saved the row → now $170.52; next cron regenerates
   the WE 080926 file via hash change. Full evidence chain in
   `memory-bank/living-ledger.md` `[2026-08-12 13:40]`.
2. **Snapshot Date automation defect proven via cell history:** the
   per-sheet "record a date" automation uses a row-change trigger with
   "Units Completed? is checked" as a condition, so ANY edit (even
   same-value saves and bulk touches) re-stamps Snapshot Date to today
   → units jump billing weeks → audit errors. Fix is UI-side per sheet:
   field-scoped trigger ("Units Completed? changes to Checked") +
   "Snapshot Date is blank" write-once condition; fix the template
   sheet so backup copies inherit it. Recommendation delivered to Juan;
   NOT yet applied (his action).
3. **SESSION HANDOFF (2026-08-12 ~16:35 CDT) — resume points:**
   - **PR #329 Greptile fixes DONE + PUSHED** (`64d7249`/`e003124`/
     `8802e98`, suite 1230+130). Latent quirk untouched:
     risk_trend.json write no-ops on fresh generated_docs/.
   - **Quick task 260812-jqx EXECUTED (reviews in flight):** branch
     `feat/260812-jqx-snapshot-drift-audit` stacked on isx tip
     `3f7be82`. Commits: `8db2845` (planning docs), `55329a1` (drift
     detection, zero extra API calls: pipeline/snapshot_drift.py +
     billing_audit/snapshot_store.py + additive schema.sql + config +
     orchestrate seam), `c58a9bd` (cell-history classifier, 40-row cap
     ~2s pacing sub-budget), `0a68aeb` (hold-prior-week override +
     audit risk wiring + post-seam Sentry capture on holds), `0b5051a`
     (SUMMARY docs). Full suite **1257 passed + 132 subtests** (27 new
     tests), zero regressions; grouping/excel zero hunks; orchestrate
     2 hunks. Deviations: test-only budget-boundary flake fix;
     plan-check Sentry warning honored. Locked decisions held: hold
     gate default OFF, never hold manual edits, fail-open gating/
     fail-closed logging, no AUDIT_SHEET_ID mutation, DDL manual-apply.
     **Reviews DONE:** gsd-verifier 8/8 zero gaps; haiku rubric 10/10
     PASS; code review 2 Critical / 5 Warning / 7 Info → fix round
     `a56190c` (CR-01 upsert gated on fetch status — no baseline
     rebase on failed read), `81da106` (CR-02 null-prior-date holds
     skipped), `7a58c62` (WR-01 unparseable ts → unclassified;
     window env-tunable SNAPSHOT_DRIFT_UNITS_WINDOW_MINUTES default
     15; WR-04 test pacing zeroed). Suite **1262 + 132 subtests**
     (~13s). Deferred to PR follow-ups: WR-02 (bulk .in_ → RPC),
     WR-03 (RLS on new tables — Juan's DDL call), WR-05 (direct
     snapshot_store tests), info nits. **SHIPPED: PR #330 → master**
     (#329 was squash-merged as `647a688` at 20:33Z, isx branch
     deleted; jqx rebased onto origin/master — new SHAs
     b115e63..d3333e4 + this ledger commit — suite re-run green
     post-rebase, force-pushed with lease). Local master is stale;
     `git switch master && git pull` when convenient.
     **Greptile round (post-open): `4104ca1`** — unclassified drifts
     no longer rebase the provenance baseline (classification-aware
     finalization; unclassified rows retry next run). Suite 1263+132.
     **Live dry run (SKIP_UPLOAD, 53min):** drift audit no-op path
     verified on 199,815 real rows (CR-01 skip observed live);
     FINDING: #329 rate-sanity flags 115,272/199,717 rows (58% — old
     historical rates vs New-Rates basis) → risk_level HIGH every CI
     run; no Smartsheet writes exist (AUDIT_SHEET_ID never written);
     Juan to choose kill-switch vs scoping follow-up. Also:
     WR_FILTER only works with TEST_MODE (grouping.py:1222) — the
     run-billing-pipeline-locally skill table is wrong on this.
   - **A1/A4 VERIFIED LIVE (WINDOWS #1 closed):** read-only probes
     with Juan's token proved newest-first history + automation
     identity, captured the full Point 27 drift-and-revert chain, and
     CORRECTED the signature: automation batches stamps (legit writes
     up to 4m22s after the check → 15-min window), and Weekly
     Reference Logged Date is automation-WRITTEN (repair must revert
     it too). Ledger `[2026-08-12 17:05]`. Backup 86 scanned clean
     (no stamps ≥ 08-08). Note: Juan's `.env` names the token
     `SMARTSHEET_API_KEY`; the pipeline reads `SMARTSHEET_API_TOKEN`.
   - **Juan's own actions pending:** Smartsheet automation trigger fix
     in UI per living-ledger [2026-08-12 13:40] (field-scoped trigger
     + "Snapshot Date is blank" condition, per sheet + template) —
     REQUIRED before any snapshot-date repair sweep (writes would be
     re-stamped); run the remediation prompt with a Smartsheet-capable
     AI; review/merge PR #329; later: apply jqx DDL (2 blocks in
     billing_audit/schema.sql), verify A1/A4, enable hold gate after
     burn-in.
4. **Quick task 260812-isx (GSD quick) COMPLETE → PR #329 OPEN:**
   report-only rate-sanity audit check (Units Total Price vs expected
   New-Rates rate × Quantity via `_SUBCONTRACTOR_RATES`, kill-switch
   `RATE_SANITY_AUDIT_ENABLED`). Commits a7f5d77/2cb9897/ad3fa19 +
   docs c61bacb on branch `feat/260812-isx-rate-sanity-audit`
   (local master reset to origin/master — nothing pushed to main).
   Full suite 1228 passed + 130 subtests, 0 regressions; independent
   haiku-verifier PASS 8/8 (report-only, no hunks in pipeline/ or
   generate_weekly_pdfs.py). Next: Juan reviews/merges PR #329; apply
   the Snapshot Date automation UI fix per living-ledger
   `[2026-08-12 13:40]`.

## Previous work (2026-07-22) — Phase 08 SDK 4.3.0 migration EXECUTED (both plans)
1. **Phase 08 executed via `/gsd-execute-phase 08`** on branch
   `feat/phase-08-sdk-430-migration` (unpushed; no PR yet). Wave 1 (08-01,
   merge `6334531`): SDK 4.3.0 installed (env upgrade 3.9.0→4.3.0), dead
   27-line 3.x re-export shim removed from `generate_weekly_pdfs.py`, Gate 1
   baseline 178→177 (`_exc_name`), six gates ALL PASSED + full suite green.
   Wave 2 (08-02, merge `72f72ef`): `requirements.txt` pin lifted to exact
   `smartsheet-python-sdk==4.3.0`, Living Ledger entries added, D-06/D-07
   rollout+rollback runbooks captured in `08-02-SUMMARY.md`.
2. **D-05 live read-only probe: APPROVED by Juan** (bounded
   `SKIP_UPLOAD=true WR_FILTER=... MAX_GROUPS=5` run, real transport, 2,771
   groups validated, 5 Excel generated, zero SDK error-shape drift).
   **Finding:** `SKIP_UPLOAD=true` is NOT fully read-only — the
   delete-old-attachment step still ran (WR <WR> weeks 072025/081725
   deleted; hash withheld → next weekday cron regenerates + re-uploads
   automatically; Juan chose wait-for-cron). Logged in phase
   `deferred-items.md` + Living Ledger; follow-up fix candidate: gate the
   delete on SKIP_UPLOAD too.
3. **Test hermeticity fix (`4aa19ff`):**
   `tests/test_entrypoint_no_double_import.py` now sets
   `SMARTSHEET_API_TOKEN=''` (was `pop()`) — the engine's `load_dotenv()`
   re-injected the token from Juan's new repo-root `.env`, flipping the
   banner test into a real multi-minute API fetch (180s timeout). Empty
   string survives dotenv (no override) and stays falsy → synthetic path.
   Post-merge gate green: 1164 passed + 130 subtests.
4. **Security gate CLEARED (2026-07-22 PM): `/gsd:secure-phase 08` run.**
   gsd-security-auditor verified 5/6 threats closed; the 6th (T-08-03,
   `SKIP_UPLOAD=true` still ran the attachment DELETE — materialized in
   the D-05 probe) was **fixed same-session, Juan-approved**: `dry_run`
   param on `delete_old_excel_attachments` /
   `cleanup_untracked_sheet_attachments` / `purge_existing_hashed_outputs`
   (`pipeline/cleanup.py`), wired `dry_run=SKIP_UPLOAD` at all 5 mutating
   call sites in `pipeline/orchestrate.py`. New invariant (ledger
   `[2026-07-22 14:37]`): SKIP_UPLOAD=true ⇒ zero Smartsheet mutations.
   TDD'd (`tests/test_skip_upload_delete_gating.py`, 7 tests; signature
   pin → v6); full suite **1171 passed + 130 subtests**. Threat register:
   `.planning/phases/08-*/08-SECURITY.md` (6/6 closed, threats_open: 0).
   Deferred item "SKIP_UPLOAD deletes prior attachments" marked RESOLVED.
5. **Nyquist gate CLEARED (2026-07-22 PM): `/gsd:validate-phase 08` run.**
   0 gaps; all 6 task commands re-run live and green (six gates PASSED —
   note: gate run took ~35 min because TEST_MODE + `.env` token does real
   reads; unset the token for local gate runs). New automated row
   08-SEC-T1 covers the SKIP_UPLOAD zero-mutation invariant. Commits
   `fa80b48` (validation), `8777246` (security docs), `442cb92` (fix).
6. **UAT COMPLETE (2026-07-22 ~16:30 CDT): `/gsd-verify-work 08` — 6/6
   passed, 0 issues** (commit `d78e7d5`). Full-UAT in
   `.planning/phases/08-*/08-UAT.md`; the old 1-test `08-HUMAN-UAT.md`
   closed (its attachment-loss check = Test 5, Juan-confirmed: WR
   <WR> self-healed via cron, WR <WR>/<WR> intact).
   `08-VERIFICATION.md` flipped `human_needed` → `passed` (the human
   gate it awaited was exactly Test 5). Roadmap/STATE/PROJECT transition
   had already run in the prior session — no re-transition.
7. **PR #286 OPEN** (branch pushed 2026-07-22 ~16:40 CDT). **Review fix
   shipped (quick task 260722-nst, ~17:35 CDT):** the 6th mutating call
   site — `run_claimer_remediation` in the isolated REMEDIATE_CLAIMERS
   branch (`pipeline/orchestrate.py` ~452) — now uses
   `dry_run=REMEDIATION_DRY_RUN or SKIP_UPLOAD` (test `458d7e5`, fix
   `60d0473`, docs `1b6ff9a`; TestRemediationGatesOnSkipUpload pins it;
   8/8 gating tests green; haiku-verifier PASS 4/4). SKIP_UPLOAD=true ⇒
   zero mutations now covers ALL 6 call sites. **Next per D-06:** merge
   in a weekday daytime window right after a green scheduled run, then
   fire ONE watched `workflow_dispatch` canary; then
   `/gsd-verify-work 09`. Also: Juan's `.env` line-1 token
   surfaced in an editor selection into chat — rotation recommended.
   Carry-forward WARNING for next phase's register: `TEST_MODE=true` with
   a real token still performs real Smartsheet reads.

## Current milestone
**v1.3.1 — Smartsheet API resilience & silent-failure hardening** (follow-up to
Phase 09, **✅ COMPLETE & MERGED, PR #281 → `8c51a3c`** on 2026-07-01 UTC).
Shipped from `fix/api-resilience-silent-failures` (cut fresh from
`origin/master`; branch deleted on merge). Three change areas, all TDD'd, all 6
gates green, PII scrubs dummy-transport-verified:
1. **Transient-retry resilience (the API errors).** New `pipeline/retry.py`
   `smartsheet_call_with_retry()` — retries the transients the SDK does NOT
   itself drive to success (generic `ApiError` **code 4000**, server timeout,
   rate limit, network drops), **bounded total sleep** so it can't blow
   `ATTACHMENT_PREFETCH_MAX_MINUTES` / `TIME_BUDGET_MINUTES`, **raises on
   exhaust**. Applied to the hot bare call sites (`fetch.py` per-sheet
   `get_sheet`, `discovery.py` folder browse + validate `get_sheet`); the
   discovery drop handler (was silent `return None`) now **escalates via
   `observability.sentry_capture_sheet_drop`** — a SANITIZED `capture_message`
   (NOT `capture_exception`, which would attach `include_local_variables`
   frames holding sampled billing-row PII) that TAGS the event
   `error_location=discovery_sheet_drop`; the global `before_send` hook
   (`_scrub_sheet_drop_frame_vars`) then strips every frame's data-bearing
   fields from that tagged event (a scope event-processor runs too early —
   `attach_stacktrace` appends the thread stacktrace after scope processors
   run) — so a dropped source sheet (= missing billing) is loud without
   exfiltrating row data. The 3 duplicate inline
   retry blocks in `orchestrate.py` (target/PPP attachment prefetch + upload)
   were **consolidated** into the helper. The upload worker is **behavior-
   preserving** vs the original inline loop (passes the prefetch cache every
   attempt). Codex flagged a retry idempotency gap in `SUPABASE_HASH_STORE_
   AUTHORITATIVE` clean-filename mode (ON in prod), but it is **not solvable by
   attachment inspection** (clean names carry no timestamp/hash, so a freshly
   committed file is indistinguishable from a stale same-identity one — both
   delete-then-reupload and preserve-on-identity are unsafe). Kept the safe
   baseline (benign self-healing duplicate on a rare retry, reconciled next
   run); the proper fix (upload-then-delete-by-attachment-age) changes the
   delete→upload guardrail and is **deferred to a dedicated PR**. Now-dead
   `time` / `ss_exc` imports removed.
2. **F1 (pre-existing deferred finding) fixed.** `grouping.py` sub-helper
   `no_history` fallback was silent — `resolve_claimer` returns
   `('use', current, 'current', 'no_history')` and the `action=='use'` branch
   zeroed the reason, so the per-WR WARNING never fired. One-line propagate-
   the-reason fix + reason-branched remediation (`no_history` vs `fetch_failure`
   vs `unavailable`); the 2 dead-path tests (mocked an impossible `action`)
   rewritten to the **real** `resolve_claimer` contract (red-first proven).
3. **Sentry PII hardening across all THREE data planes** (review-driven).
   Row PII (WR/week/foreman/dept/job/price) must never reach Sentry. Closed:
   (a) **event frames** → `before_send` `_scrub_sheet_drop_frame_vars` (a scope
   event-processor runs too early — `attach_stacktrace` appends thread frames
   after it); (b) **breadcrumb `message`** → `before_breadcrumb` drops any crumb
   whose message hits `_PII_LOG_MARKERS` (`LoggingIntegration(level=INFO)` turns
   every INFO/WARNING into a breadcrumb *unconditionally*, independent of the
   `SENTRY_ENABLE_LOGS` gate); (c) **breadcrumb `data`** → same hook strips
   row-identifier keys via the new `_PII_BREADCRUMB_DATA_KEYS` registry (manual
   crumbs carry PII in `data` under a benign message — e.g. the skip/regenerate
   crumbs). All three empirically verified with a real `sentry_sdk.Client` +
   dummy transport.

**Deferred (dedicated PR):** the retry-idempotency gap in
`SUPABASE_HASH_STORE_AUTHORITATIVE` clean-filename mode is **not solvable by
attachment inspection** (clean names carry no timestamp/hash, so a freshly
committed file is indistinguishable from a stale same-identity one). Kept the
safe behavior-preserving baseline (benign self-healing duplicate on a rare
retry, reconciled next run); the proper fix (upload-then-delete-by-attachment-
age) changes the delete→upload guardrail.

**Status:** MERGED. `run_6_gates.sh` exit 0 at merge (G1 178 names · G2 108
facade · **G3 1149 pytest** +130 subtests · G4 mypy 56→56 · G5 py_compile · G6
21-key TEST_MODE run). **All findings across 8 reviewer passes resolved**
(4 real Codex fixes: before_send frame scrub · attribution `unavailable`≠
`no_history` · breadcrumb message-scrub · breadcrumb data-scrub; 2 sys.path
test bootstraps; 3 Copilot doc-accuracy nits incl. the retry.py 4000-vs-
InternalServerError contract). 0 unresolved review threads; final Copilot
review generated no new comments. Production guardrails UNCHANGED (change-key,
delete→upload order, `@cell`=0, `PARALLEL_WORKERS≤8`, filename/attachment). See
`memory-bank/living-ledger.md` (newest entries) for the full what/why/rules.

## Active work
**🔧 WR <WR> missing-rows bug: ROOT CAUSE CONFIRMED, fix in PR (2026-07-06).**
Not attribution/filtering — a crash-consistency bug in the Sub-project E hash
store: failed run 28752355941 (7/5, runner lost) upserted the new group hash
during emission but died before the upload phase, so under authoritative clean
filenames the skip gate deadlocks ("unchanged + attachment exists") and the 7/5
ProMax rows never publish; regen can't recover. Fix: `orchestrate.py` defers hash
upserts and flushes ONLY after the group's upload legs succeed (withhold on
error/dry-run → regenerate next run). 4 regression tests; suite 1153 passed +130
subtests. **Pending:** merge fix PR (stacked on #282) → one-time remediation
`workflow_dispatch` `advanced_options=regen_weeks:070526` → verify the 7/5 rows in
the regenerated file → archive debug session `wr-<WR>-rows-not-pulled` +
apply the held second-brain write-back packet. Full rule: newest
`memory-bank/living-ledger.md` entry.

## History pointer
**Phase 09 — engine modularization (✅ COMPLETE & MERGED, PR #280 → `889ca2e`).**
10,476-line `generate_weekly_pdfs.py` → 13-module `pipeline/` package behind a
709-line thin facade, zero behavior change, 7 waves each 6-gate-verified. Full
wave-by-wave history in `memory-bank/living-ledger.md`.

_Paused alongside:_ **v1.2 — smartsheet-python-sdk 4.0.0 migration** (Phase 08).
SDK pinned `<4.0.0` in `requirements.txt` as a CI import hotfix; the breaking
4.0.0 migration is not yet executed. **Now unblocked** (Phase 09 merged) but
still touches the same engine — coordinate before starting.
