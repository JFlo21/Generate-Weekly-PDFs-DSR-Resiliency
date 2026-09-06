---
phase: "14"
slug: "foreman-helper-2"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-05"
populated: "2026-09-05"
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
>
> **Populated 2026-09-05 during plan revision** from the 30 tasks actually present in
> `14-01-PLAN.md` … `14-10-PLAN.md`. `status` stays `draft` because the transition to `validated`
> is owned by `/gsd:validate-phase` §6, not by the planner. `nyquist_compliant` stays `false` for
> the two reasons stated under **Validation Sign-Off** — do not flip it until both are actually
> resolved.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 (Python); Vitest via `npm --prefix portal-v2`; Docusaurus build via `npm --prefix website` |
| **Config file** | none — pytest defaults; `pyproject.toml` has no `[tool.pytest.ini_options]` section |
| **Quick run command** | `python -m pytest tests/test_foreman_helper_2.py -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Gate harness** | `bash scripts/run_6_gates.sh` (required after any module move; run at 14-07-03, 14-10-02) |
| **Estimated runtime** | UNMEASURED — this revision was planning-only and ran no tests. Measure `python -m pytest tests/ -q` at the first Wave 1 commit and record the number here. |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_foreman_helper_2.py -q`
- **After every plan wave:** Run `python -m pytest tests/ -q`
- **After any wave touching `pipeline/*` module boundaries:** also `bash scripts/run_6_gates.sh`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** UNMEASURED — see Test Infrastructure; record after the first full-suite run

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 14-01-01 | 01 | 1 | HLP-01, HLP-02, HLP-05 | T-14-01-01 / T-14-01-02 | Every helper2 identifier is sanitized through `_RE_SANITIZE_HELPER_NAME` before reaching a filename or group key; raw `__helper2_foreman` never does | e2e (tracer) | `python -m pytest tests/test_foreman_helper_2.py -q` | ❌ created by 14-01-01 | ⬜ pending |
| 14-01-02 | 01 | 1 | HLP-06, HLP-07 | T-14-01-05 | Legacy primary / Helper #1 / VAC identities are character-for-character unchanged when Helper #2 is absent (D-14-09) | regression | `python -m pytest tests/test_group_identity_and_header_foreman.py tests/test_change_detection_tiebreak.py tests/test_helper2_family_parity.py -q` | ⚠️ 2 of 3 exist; `test_helper2_family_parity.py` created by 14-01-02 (this task) | ⬜ pending |
| 14-01-03 | 01 | 1 | HLP-05 | T-14-01-02 / T-14-01-03 | A blank, `NA`, `#NO MATCH`, or FORMULA_ERROR_VALUES name fabricates no Helper #2 claim, group, or workbook | unit | `python -m pytest tests/test_foreman_helper_2.py -q` | ❌ created by 14-01-01 | ⬜ pending |
| 14-02-01 | 02 | 1 | HLP-06 | T-14-02-03 | Every first-run-suppression verdict cites the file and line range that produced it, so it can be re-derived | doc-assertion | `python -c "... '## A1' and '## A2' and 'parity' in 14-PENDING-RESOLUTIONS.md ..."` | ❌ created by 14-02-01 | ⬜ pending |
| 14-02-02 | 02 | 1 | HLP-06, HLP-07 | T-14-02-03 | Module-scope verdicts for `attribution.py` / `pricing.py` / `observability.py` are evidence-backed, not inherited assumptions | doc-assertion | `python -c "... '## A3' + three module paths in 14-PENDING-RESOLUTIONS.md ..."` | ❌ created by 14-02-01 | ⬜ pending |
| 14-02-03 | 02 | 1 | HLP-04, HLP-07 | T-14-02-01 / T-14-02-02 | Live probe is read-only and owner-run; column titles/ids/counts only, never a row value or a person's name | checkpoint (blocking-human) + doc-assertion | `python -c "... 'LIVE-COLUMN-PROBE: ANSWERED' and 'read-only' in 14-DECISIONS.md ..."` | ❌ created by 14-02-03 | ⬜ pending |
| 14-03-01 | 03 | 2 | HLP-02, HLP-05 | T-14-03-01 / T-14-03-02 | `p_helper2` joins the freeze payload AND the all-sentinel gate in one edit, so a Helper #2-only freeze is never short-circuited away | unit (tdd) | `python -m pytest tests/test_billing_audit_shadow.py -q -k "helper2 or sentinel"` | ✅ | ⬜ pending |
| 14-03-02 | 03 | 2 | HLP-06 | T-14-03-04 / T-14-03-05 | A pre-migration RPC parameter rejection degrades with a counted, redacted warning instead of raising or leaking RPC error text | unit (tdd) | `python -m pytest tests/test_billing_audit_shadow.py -q -k "degrade or unsupported or counter"` | ✅ | ⬜ pending |
| 14-03-03 | 03 | 2 | HLP-02, HLP-05 | T-14-03-01 / T-14-03-03 | `ROLE_BY_VARIANT` and `resolve_claimer` name the helper2 role explicitly; a Helper #2 freeze never overwrites another role | unit (tdd) | `python -m pytest tests/test_billing_audit_shadow.py -q -k "role_by_variant or resolve_claimer"` | ✅ | ⬜ pending |
| 14-04-01 | 04 | 2 | HLP-06 | T-14-04-01 / T-14-04-02 / T-14-04-04 | Additive nullable DDL only, owner-applied; the one-time `row_event` churn is quantified and approved before it is paid | checkpoint (blocking-human) + doc-assertion | `python -c "... 'D-14-08-APPLIED' in 14-DECISIONS.md ..."` | ❌ created by 14-02-03 | ⬜ pending |
| 14-04-02 | 04 | 2 | HLP-06 | T-14-04-02 / T-14-04-03 | `helper2_observed` stores the RAW cell value (no sentinel substitution); HASH_FIELDS is append-only so no existing member shifts | unit (tdd) | `python -m pytest tests/test_pipeline_memory_shadow.py -q` | ✅ | ⬜ pending |
| 14-04-03 | 04 | 2 | HLP-06 | T-14-04-02 | The two independent HASH_FIELDS enumerations are pinned equal by a drift-guard test | unit | `python -m pytest tests/test_pipeline_memory_shadow.py -q -k "mirror or mem04 or hash_fields"` | ✅ | ⬜ pending |
| 14-05-01 | 05 | 2 | HLP-01, HLP-06 | T-14-05-01 / T-14-05-02 | The orphan-supersede gate knows the Helper #2 family, so cleanup never deletes a live Helper #2 attachment | unit (tdd) | `python -m pytest tests/test_sentinel_superseded_cleanup.py -q` | ✅ | ⬜ pending |
| 14-05-02 | 05 | 2 | HLP-01, HLP-02 | T-14-05-03 | The three Helper #2 filename tokens parse in precedence order, so `normalize_variant` cannot misfile an artifact | unit (tdd) | `python -m pytest tests/test_publish_artifacts_to_supabase.py -q` | ✅ | ⬜ pending |
| 14-05-03 | 05 | 2 | HLP-02 | T-14-05-04 | Portal labels render the variant, never an unredacted person's name; the family-parity invariant covers the new entries | unit + build | `python -m pytest tests/test_helper2_family_parity.py -q` then `npm --prefix portal-v2 run build` | ❌ created by 14-01-02 | ⬜ pending |
| 14-06-01 | 06 | 3 | HLP-01, HLP-05 | T-14-06-01 | The subcontractor shadow partition emits Helper #2 keys as a parallel sibling block, never by widening the Helper #1 tuple | unit (tdd) | `python -m pytest tests/test_subcontractor_helper_shadow_rescue.py -q` | ✅ | ⬜ pending |
| 14-06-02 | 06 | 3 | HLP-01, HLP-02 | T-14-06-02 / T-14-06-04 | Header dispatch and nested filename parsing round-trip; the multi-foreman aggregated hash stays deterministic | unit (tdd) | `python -m pytest tests/test_subcontractor_helper_shadow_rescue.py -q -k "helper2 or filename or aggregate"` | ✅ | ⬜ pending |
| 14-06-03 | 06 | 3 | HLP-02, HLP-05 | T-14-06-03 / T-14-06-05 | The PPP dual-route gate routes the second leg correctly and new upload log lines carry no raw person's name | unit (tdd) | `python -m pytest tests/test_subcontractor_helper_shadow_rescue.py -q -k "upload or routing or ppp"` | ✅ | ⬜ pending |
| 14-07-01 | 07 | 3 | HLP-03 | T-14-07-02 / T-14-07-03 | The marker column is owner-approved; the degrade direction fails toward full validation, never toward silent cache admission | checkpoint (blocking-human) + doc-assertion | `python -c "... 'D-14-10-APPLIED' in 14-DECISIONS.md ..."` | ❌ created by 14-02-03 | ⬜ pending |
| 14-07-02 | 07 | 3 | HLP-03 | T-14-07-01 / T-14-07-02 | The sixth admission condition can only reject; a cache-admitted sheet never has its marker promoted; the unknown-column path warns once and does not raise | unit (tdd) | `python -m pytest tests/test_foreman_helper_2.py -q -k "skip_index or marker or mapping_schema or revalidation"` | ❌ created by 14-01-01 | ⬜ pending |
| 14-07-03 | 07 | 3 | HLP-03, HLP-04 | T-14-07-04 / T-14-07-05 | A read failure is never reported as a Helper #2 absence; the Intake-8 case is a fixture and never touches sheet `2244739192541060` | unit (tdd) + gate harness | `python -m pytest tests/test_foreman_helper_2.py -q` then `bash scripts/run_6_gates.sh` | ❌ created by 14-01-01 | ⬜ pending |
| 14-08-01 | 08 | 4 | HLP-05 | T-14-08-01 / T-14-08-02 | O-14-A is decided by its owner and recorded before any conflict-handling code exists; no rule is inferred | checkpoint (blocking-human) + doc-assertion | `python -c "... 'O-14-A' and 'RESOLVED' in 14-DECISIONS.md ..."` | ❌ created by 14-02-03 | ⬜ pending |
| 14-08-02 | 08 | 4 | HLP-05 | T-14-08-02 / T-14-08-03 / T-14-08-04 | The recorded rule is applied at one site per leg; one conflicted row never aborts the run; the unit reaches exactly one customer-facing file | unit (tdd) | `python -m pytest tests/test_foreman_helper_2.py -q -k "conflict or both_slots"` | ❌ created by 14-01-01 | ⬜ pending |
| 14-08-03 | 08 | 4 | HLP-03 | T-14-08-05 | Every Helper #2 counter is pre-seeded so the run_summary key set is invariant flag-on or flag-off (Gate 6 is key-set equality) | unit (tdd) + structure gate | `python -m pytest tests/test_foreman_helper_2.py -q -k "run_summary or counter"` then `python scripts/check_run_summary_structure.py` | ❌ created by 14-01-01 | ⬜ pending |
| 14-09-01 | 09 | 5 | HLP-06 | T-14-09-01 / T-14-09-03 | Both lookup functions are dropped before create (never a plain replace); parameter and return-column names equal what `billing_audit/writer.py` sends and reads | contract | `python -m pytest tests/test_helper2_attribution_sql_contract.py -q` | ❌ created by 14-09-01 | ⬜ pending |
| 14-09-02 | 09 | 5 | HLP-06 | T-14-09-01 / T-14-09-04 / T-14-09-05 | Production SQL is owner-applied in a chosen quiet window outside the cron schedule, with the rollback recorded before the change | checkpoint (blocking-human) + doc-assertion | `python -c "... 'D-14-07-APPLIED' in 14-DECISIONS.md ..."` | ❌ created by 14-02-03 | ⬜ pending |
| 14-09-03 | 09 | 5 | HLP-06 | T-14-09-02 / T-14-09-03 | The silent non-deploy is caught by owner read-back, not inferred; a Helper #2 freeze leaves `frozen_primary` / `frozen_helper` / `frozen_vac_crew` byte-identical (closes RESEARCH A4) | checkpoint (blocking-human) + doc-assertion | `python -c "... 'D-14-07-VERIFIED' in 14-DECISIONS.md ..."` | ❌ created by 14-02-03 | ⬜ pending |
| 14-10-01 | 10 | 6 | HLP-07 | T-14-10-03 / T-14-10-04 | The flag is spelled identically in all three catalogs; the documented rollback retains Helper #2 attachments and attribution rows | docs build + doc-assertion | `npm --prefix website run typecheck` then `npm --prefix website run build` | ✅ (website workspace) | ⬜ pending |
| 14-10-02 | 10 | 6 | HLP-07 | T-14-10-01 / T-14-10-03 | Every pilot command states what it reads, writes, and cleans up; upload suppression is never presented as "writes nothing" | integration (synthetic) + gate harness | `python -m pytest tests/ -q`, `TEST_MODE=true python generate_weekly_pdfs.py`, `python scripts/check_run_summary_structure.py`, `bash scripts/run_6_gates.sh` | ✅ | ⬜ pending |
| 14-10-03 | 10 | 6 | HLP-04, HLP-07 | T-14-10-02 / T-14-10-05 | The CI workflow file is inspect-only and provably unmodified; the one irreversible upload is owner-authorized or deferred | checkpoint (blocking-human) + diff gate | `python -c "... 'D-14-12-ROLLOUT' in 14-DECISIONS.md ..."` then `git diff --quiet -- .github/workflows/weekly-excel-generation.yml` | ❌ created by 14-02-03 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Automated Command column shows the primary check per task; several tasks carry additional
`<automated>` entries (full-suite sweeps, `py_compile` syntax gates). The plan file is authoritative
for the complete list and for every `<fails_when>` signal.*

---

## Wave 0 Requirements

No separate Wave 0 exists for Phase 14: every missing test module is created by a named task before
the first task that depends on it. Tracked here so the dependency is explicit rather than implied.

- [ ] `tests/test_foreman_helper_2.py` — **does not exist today.** Created by **14-01-01** (the Wave 1
      tracer). First consumed by 14-01-01 itself, then 14-01-03, 14-07-02, 14-07-03, 14-08-02, 14-08-03.
- [ ] `tests/test_helper2_family_parity.py` — **does not exist today.** Created by **14-01-02**
      (frontmatter `artifacts`), extended by 14-05-03 and again by 14-06-03. This is why 14-06
      `depends_on` includes `14-05`.
- [ ] `tests/test_helper2_attribution_sql_contract.py` — **does not exist today.** Created by
      **14-09-01**, consumed only by 14-09-01.
- [ ] `.planning/phases/14-foreman-helper-2/14-PENDING-RESOLUTIONS.md` — created by 14-02-01.
- [ ] `.planning/phases/14-foreman-helper-2/14-DECISIONS.md` — created by 14-02-03, appended to by
      14-04-01, 14-07-01, 14-08-01, 14-09-02, 14-09-03, 14-10-02, 14-10-03.

Existing infrastructure (pytest 9.0.3, the 59 modules under `tests/`, `scripts/run_6_gates.sh`,
`scripts/check_run_summary_structure.py`) covers everything else — no framework install is needed.

---

## Manual-Only Verifications

Seven owner-gated checkpoints, all carrying `gate="blocking-human"` so none is auto-resolved in
auto-mode. Each also has a document-assertion `<automated>` check, so the *record* is machine-verified
even though the *observation* cannot be.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Helper #2 column state on the production sheets (14-02-03) | HLP-04, HLP-07 | No agent may read production Smartsheet; the 2026-09-05 snapshot may have drifted | Read-only check of the six titles on Main ProMax `3239244454645636`, any partial column sets, the two known-absent sheets, and whether Resource Analyst col `1589780186173316` is still blank. Record titles/ids/counts only. |
| Additive `row_state` DDL + hash-inclusion choice (14-04-01) | HLP-06 | Supabase schema is a protected area; the hash choice trades one-time churn against a future correctness gap | Present the four columns, the quantified one-time `row_event` volume, and the three options; record `D-14-08-APPLIED`. |
| `sheet_registry` mapping-schema marker (14-07-01) | HLP-03 | Second protected-area schema change; the degrade direction decides slow-vs-silently-wrong | Present the marker shape options, the quantified one-time full-validation cost against the time budget, and the degrade direction; record `D-14-10-APPLIED`. |
| O-14-A both-slots-valid conflict rule (14-08-01) | HLP-05 | A business decision about money across three flows; deliberately OPEN by owner instruction | Present the four options with consequences and the two non-blocking follow-ups; record `O-14-A ... RESOLVED`. 14-08-02 stays blocked until it exists. |
| Applying `billing_audit/helper2_attribution.sql` (14-09-02) | HLP-06 | Protected-area production SQL; the drop-and-recreate window can fail a scheduled billing run | Owner reads the file, picks a quiet window outside the cron schedule and a deployment order, applies it, records `D-14-07-APPLIED` with rollback steps. |
| Post-migration read-back (14-09-03) | HLP-06 | The documented failure mode produces no error at apply time; the function bodies live in Supabase and cannot be inspected from the repo | Four read-only checks including a Helper #2 freeze leaving the other three role columns byte-identical; record `D-14-07-VERIFIED`. Closes RESEARCH Assumption A4 by observation or states it still open. |
| Rollout: flag default, workflow wiring, controlled upload (14-10-03) | HLP-04, HLP-07 | A real attachment on a real sheet is irreversible; CI workflow edits are a protected area | Present the three items and the two Smartsheet-side operational preconditions; record `D-14-12-ROLLOUT`. `git diff --quiet` proves the workflow file is unedited. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies — all 30 tasks carry at least one
      `<automated>` with a `<fails_when>` signal; the 7 checkpoints carry one in addition to their
      `<human-check>`
- [x] Sampling continuity: no 3 consecutive tasks without automated verify — zero gaps across all 30
- [x] Wave 0 covers all MISSING references — the three absent test modules are each created by a
      named task ahead of first use (14-01-01 ×1, 14-01-02 ×1, 14-09-01 ×1)
- [x] No watch-mode flags — every command is a single-shot run; no `--watch`, `--watchAll`, or
      `pytest-watch` appears in any plan
- [ ] Feedback latency < N s — **UNVERIFIED.** This revision was planning-only and ran no tests, so
      neither the quick-run nor the full-suite runtime has been measured. Measure both at the first
      Wave 1 commit and fill in Test Infrastructure and Sampling Rate.
- [ ] `nyquist_compliant: true` set in frontmatter — **NOT SET, deliberately.** Two preconditions are
      unmet: (1) feedback latency is unmeasured, above; (2) `wave_0_complete` is `false` because the
      three test modules listed under Wave 0 Requirements do not exist yet. Flip both only after the
      modules exist and the suite has been timed.

**Approval:** pending — `status` stays `draft` until `/gsd:validate-phase` §6 sets it.
