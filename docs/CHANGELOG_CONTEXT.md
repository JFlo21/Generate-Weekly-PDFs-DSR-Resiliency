# Changelog Context

> **Canonical change ledger: [`memory-bank/living-ledger.md`](../memory-bank/living-ledger.md).**
> Append dated `[YYYY-MM-DD HH:MM]` entries there — this repo keeps the *what changed
> and why* narrative in the Living Ledger, not split across separate files.
>
> This stub exists so the global context-continuity write-back order (which names
> `docs/CHANGELOG_CONTEXT.md`) resolves to a real path. The Stop hook
> (`require_context_update_on_stop.js`) recognizes **both** this file and the Living
> Ledger, so updating either satisfies it.

## 2026-08-27 — pipeline_memory client init fixed for supabase-py sync options (PR #356)
First run after the `RUN_MEMORY_WRITE_ENABLED` flip wrote no run memory: the base
`ClientOptions` passed by the WR-02 timeout wiring lacks `.storage`, which supabase-py
2.31's sync `create_client` reads. `pipeline_memory/client.py` now builds
`SyncClientOptions`, falls back to a bare client if the SDK rejects options, and logs the
exception message; a real-SDK construction test guards it. Billing was never affected.
See `memory-bank/living-ledger.md` `[2026-08-27 11:51]`.

## 2026-08-28 — one identity definition for Sites 1/2/3; header foreman = hash rule; deterministic legacy header (PR #362)
The three inline identity chains in `pipeline.orchestrate.main` (history key, attachment-cleanup
tuple, prune key) are now one module-level `derive_group_identity()` called with switches bound once,
so the CR-01 drift shape is no longer expressible and the sites are behaviourally tested for both
arrival orders. The primary workbook header's foreman is the hash's `FOREMAN=` rule (`canonical_foreman()`,
first non-empty claimer in canonical order) — owner-approved and reachable in production
(a whitespace-only `Foreman Assigned?` yields a blank `__current_foreman`; such a primary group used to
show a blank header foreman while its hash named a later row's), gated on `variant == 'primary'` —
helper, helper-shadow, vac_crew and subcontractor primary headers keep their partition key; hashes and identity
keys are byte-identical (golden digests). `canonical_first_row()` now
uses the extended total order in legacy mode too, so the legacy header is deterministic while the
legacy hash is untouched. Closes the three threads left open on #361.
See `memory-bank/living-ledger.md` `[2026-08-28 12:05]`. PR #362.

## 2026-08-27 — identity row = canonical row: Excel header + orchestrate Sites 1/2/3 (PR #361)
A helper group can hold rows from two departments (its key carries no dept/job). #359 made
the hash order-stable, but the workbook header and the three orchestrate identity sites
(main-loop `history_key`, `valid_wr_weeks`, `current_keys` prune) still read arrival-order
`group_rows[0]`, so a stable hash was looked up under an unstable key and the group could
regenerate every run. All of them now read `canonical_first_row()`; the sort key also carries
every Job # alias the header accepts and the legacy identity `User` (hash-neutral: both sit
after the hashed-field string). Round 3 (2026-08-28) appends the unjoined hashed fields
(`|`-serialization collisions) and the raw `Work Order #` as further hash-neutral tiebreakers, and
makes `header_job_number()` the single Job # alias resolver for both the Excel header and the sort
key (same aliases, same precedence, raw value preserved for the cell).
Hashes are byte-identical to master; any group whose identity row changes — helper groups with
mixed dept/job metadata AND primary groups with mixed `User`/claimer values — gets one final
regeneration (same hash, attachment replaced once), then stays stable. In legacy mode
(`EXTENDED_CHANGE_DETECTION=0`) the header/identity row is now the 5-key-sorted row instead of
the arrival-order row, so the same one-time effect applies there.
Declined: legacy-mode header determinism (rollback sort is frozen). Deferred to Juan: aligning
the header's foreman with the hash's first-nonempty `FOREMAN=` token (billing-output change), and
a behavioural Sites 1–3 test, which needs the three inline `main()` identity blocks extracted into
one shared helper (production refactor) — both done in the 2026-08-28 follow-up above.
See `memory-bank/living-ledger.md` `[2026-08-27 20:20]`.

## 2026-08-27 — Learn guides corrected against pipeline behaviour (PR #360 review round)
The new operator / engineer guides and the system overview copied several claims that the
code contradicts: the acceptance gate (WR + weekly date + Units Completed? + price > 0 in
`fetch.py:837`; CU / quantity / foreman do not gate), the group key (`(WR, week, variant,
claimer)` — dept/job never split a file), `wr_filter` (test-mode only, never attaches),
`reset_wr_list` (destructive and global), the real CDT/CST schedule windows and run times,
and where attribution freezes. All corrected with line anchors; `CLAUDE.md`'s six-field
grouping description carries the same drift and is a separate follow-up.
Rounds 3–18 (Copilot auto-reviews every push) added: Snapshot Date day-block filter, reset
purge scope (`WR_*.xlsx` on the target sheet only), `TEST_MODE` gates Supabase writes while
`SKIP_UPLOAD` alone does not, explicit-EMPTY env values (never "unset" — `load_dotenv()`
refills absent ones, `SENTRY_DSN` included), Sunday = 4 normal runs, frozen
`_Unknown_Foreman` attribution, filename-only attachment check, and — the open item — the
repository is PUBLIC while ~284 WR-like ids and ~20 personnel names sit in 106 tracked files
(committed `generated_docs/*.json`, tests, `.planning/`, blog); only the lines these rounds
touched are aliased. **Owner decision pending:** scrub tracked files / make the repo private /
rewrite history (#360 thread 3877686166).
See `memory-bank/living-ledger.md` `[2026-08-27 21:10]`.

## 2026-08-28 — sheet_registry upsert no longer 400s; RPC failures name their PostgREST code (PR #363)
Every frequent run since 2026-08-27 18:20Z failed the `pipeline_memory.sheet_registry` upsert:
registered sheets omit `column_mapping` while a newly discovered sheet carries it, postgrest-py
sends `columns=` as the union of the payload's keys, and PostgREST NULLed the `NOT NULL` column
on the UPDATE half (23502 → HTTP 400, never self-healing once the registry was one sheet
behind discovery). The writer now issues one upsert per key-set, so every request is
key-homogeneous and a registered row's stored mapping is left untouched as intended; the deep
run's homogeneous payload is still a single identical request. `with_retry` now logs
`code=<SQLSTATE/PGRST>` on the final failure and the message only for structural code classes
(the Actions logs are public; `details`/`hint` never). Billing output untouched; fail-open path.
See `memory-bank/living-ledger.md` `[2026-08-28 15:05]` (root cause) and `[2026-08-28 16:05]`;
PR #363.

## 2026-08-28 — billing_audit kill switch no longer logs server text (PR #364)
Twin of the #363 fix: `billing_audit/client.py::_disable_for_run` (PGRST106/301/302) used to put the
PostgREST `message` and `hint` into the public Actions warning and the Sentry breadcrumb. Those
fields are untrusted diagnostic text that can echo request or database data. The warning now
carries the code, the error type and the locally authored operator guidance only; nothing about
when the kill switch trips or what it disables changed. See `memory-bank/living-ledger.md`
`[2026-08-28 17:10]`; PR #364.

## 2026-08-28 — groups whose WR has no target-sheet row are not generated; listed as an error (PR #365)
Owner decision: a Work Request with no row on the target sheet is a data-entry error on the source
sheet, not a matching problem. Such groups (154 group-weeks per run) used to regenerate on every run
— "can't verify the attachment, safer to regenerate" — and then fail to upload; measured on a
like-for-like run pair, that cost ~13–15 minutes per run, almost all of it in the upload phase (the
generation itself was cheap). They are now skipped before the billing-audit snapshot and the hash decision, so
they are neither tracked in Supabase nor generated. Guards: the target map must be populated, the WR
must not be a target-sheet collision (quarantined keys keep the old "not found" outcome), `TEST_MODE`
and `SKIP_UPLOAD` dry runs are exempt, and a circuit breaker disables the skip for the whole run
(`🛑` ERROR, fall back to generate-and-warn) when more than `NO_TARGET_ROW_MAX_MISS_RATIO` (default
`0.5`, must be in `[0, 1]`) of the distinct WR values across all fetched source rows are absent from
the map — a populated-but-partial read must never become "never generate". Reported once per run as
an ERROR line with the counts (never the values — ERROR logs reach Sentry) followed by a WARNING line
with the offending values (capped at 25) — those two lines are the audit trail for the data owner.
The rule converges by itself when a row is added. Verified on the first post-merge scheduled run
(33219619070): 154 not generated, 0 not-found upload warnings, run 42 min vs 55 (PR #365 had estimated
~45 min from the generation cost alone; the corrected figure and its evidence are in
`memory-bank/living-ledger.md` `[2026-08-28 19:00]`, PR #368). Parity treats never-generated groups like withheld
ones; `run_summary.json` gains `groups_skipped_no_target_row` (22-key contract, golden updated).
Operators: expect `… N not generated (no target-sheet row)` in the phase summary, one `❌` line and
one `Work request values with no target-sheet row: …` line; the per-group `Work request … not found
in target sheet` upload warnings disappear. See `memory-bank/living-ledger.md` `[2026-08-28 18:05]`;
PR #365.

## 2026-08-28 — real identifiers aliased in the public tip; generated manifest/hash files untracked (PR #366)
The repository is public. Every real Work Request number and real crew name in tracked files is
now a consistent fictional alias, and `generated_docs/artifact_manifest.json` / `hash_history.json`
— runtime state CI regenerates every run — are no longer tracked. No production code path changed;
operators will notice only that ledger/runbook examples use `1xxxxxxx`-style WRs. Two real WRs
remain by owner choice: the `pipeline/excel.py` WR-keyed log line, the startup banner that names
them, and one `.github/prompts/testing-and-validation.md` fixture key. See
`memory-bank/living-ledger.md` `[2026-08-28 18:20]`; PR #366.

## 2026-08-28 — Notion gets the no-target-row counter (opt-in property); last real WR ids removed from the tree
The weekly workflow now exports `groups_skipped_no_target_row` to the Notion run sync, which writes it to the
Pipeline Runs database as the Number property `Groups No Target Row` **only if that property exists** — add it in
Notion to opt in; nothing changes until you do (Notion would otherwise reject the page). The startup banner and
`pipeline/excel.py` no longer name two historical Work Requests (the per-WR branch was a log line with no
behaviour). No pipeline behaviour change. See `memory-bank/living-ledger.md` `[2026-08-28 20:15]`; PR #369.
