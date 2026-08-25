---
phase: 10
slug: run-memory-foundation-shadow-writes
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-24
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 (already installed; `requirements.txt`) |
| **Config file** | none — no `pytest.ini` and no `[tool.pytest.ini_options]`; default `tests/` auto-discovery |
| **Quick run command** | `python -m pytest tests/test_pipeline_memory_shadow.py -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Phase gate command** | `bash scripts/run_6_gates.sh` |
| **Estimated runtime** | quick ~5 s · full suite ~60-90 s · six-gate harness ~3-5 min |

Note: there is no `tests/conftest.py` in this repository. Every new test module is
self-contained, mirroring `tests/test_billing_audit_shadow.py`.

---

## Sampling Rate

- **After every task commit:** the task's own `<automated>` commands, at minimum the
  quick run command.
- **After every plan wave:** `python -m pytest tests/ -v` plus
  `bash scripts/run_6_gates.sh`.
- **Before `/gsd:verify-work`:** the six-gate harness green AND
  `scripts/compare_control_run.py` green over a non-empty real-data artifact set
  (10-RESEARCH.md Pitfall 8 — Gate 6 alone runs `TEST_MODE` and cannot exercise the
  shadow-write path).
- **Max feedback latency:** ~5 s for the quick run; ~5 min for the full phase gate.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | MEM-01, MEM-03 | T-10-05 / T-10-01 | A pipeline_memory global-kill leaves the shipped audit writer operational; writer logs carry counts only | unit + gate | `python -m pytest tests/test_pipeline_memory_shadow.py -q` · AST client-isolation check · `bash scripts/run_6_gates.sh` | ❌ W0 | ⬜ pending |
| 10-01-02 | 01 | 1 | MEM-01 | T-10-02 / T-10-03 / T-10-07 | RLS enabled + `service_role_all` on all five tables; typed `jsonb_to_recordset`; bounded retention DELETE | structural | DDL structure check · scope check · `RLS_POLICIES=5` · `RLS_ENABLED=5` | ❌ W0 | ⬜ pending |
| 10-01-03 | 01 | 1 | MEM-01, MEM-02 | — | Python payload keys are a subset of the DDL column set; hash is order-stable | unit | `python -m pytest tests/test_pipeline_memory_shadow.py -q` · `python -m pytest tests/ -q` | ❌ W0 | ⬜ pending |
| 10-02-01 | 02 | 2 | MEM-02 | T-10-09 | The additive row_data key cannot move the group content hash | unit + gate | `python -m pytest tests/test_pipeline_memory_shadow.py -q` · bounded `git diff --numstat` on `pipeline/fetch.py` · `bash scripts/run_6_gates.sh` | ✅ (10-01-01) | ⬜ pending |
| 10-02-02 | 02 | 2 | MEM-02, MEM-03 | T-10-06 / T-10-01 / T-10-03 | `*_observed` values are raw and blank-tolerant; one aggregate WARNING, counts only | unit | `python -m pytest tests/test_pipeline_memory_shadow.py -q` · `python -m pytest tests/ -q` · writer boundary AST check | ✅ | ⬜ pending |
| 10-02-03 | 02 | 2 | MEM-02, MEM-03 | T-10-04 | Pre-flight guard plus per-iteration budget break; no additional Smartsheet call | unit + gate | `python -m pytest tests/ -q` · `git diff --exit-code` guard set · `bash scripts/run_6_gates.sh` | ✅ | ⬜ pending |
| 10-03-01 | 03 | 3 | MEM-01, MEM-03 | T-10-02 | `sheet_registry.kind` can only take a DDL-CHECK-legal value | unit + gate | `python -m pytest tests/ -q` · writer boundary AST check · `bash scripts/run_6_gates.sh` | ✅ | ⬜ pending |
| 10-03-02 | 03 | 3 | MEM-01, MEM-03 | T-10-10 / T-10-12 | The upload worker's status-string contract and delete-then-upload order are unchanged; side channel is lock-guarded | unit | `python -m pytest tests/test_skip_upload_delete_gating.py tests/test_orphaned_primary_attachment.py -q` · `python -m pytest tests/ -q` | ✅ | ⬜ pending |
| 10-03-03 | 03 | 3 | MEM-01, MEM-03 | T-10-11 | A memory-writer failure cannot stop either production flush | unit + gate | `python -m pytest tests/ -q` · `git diff --exit-code` guard set incl. `pipeline/upload.py` · `bash scripts/run_6_gates.sh` | ✅ | ⬜ pending |
| 10-04-01 | 04 | 1 | MEM-04 | T-10-13 / T-10-15 | No mutating SDK method is reachable; production sheet ids are refused | static + unit | `python -m py_compile scripts/mem04_experiment.py` · `--help` · read-only AST scan · `python -m pytest tests/test_mem04_formula_change.py -q` | ❌ W0 | ⬜ pending |
| 10-04-02 | 04 | 1 | MEM-04 | T-10-15 | An incomplete cassette can only yield `undetermined` | unit | `python -m pytest tests/test_mem04_formula_change.py -q` · `python -m pytest tests/ -q` | ❌ W0 | ⬜ pending |
| 10-04-03 | 04 | 1 | MEM-04 | T-10-01 | Report prints counts only; empty population reports `insufficient data` | static + unit | `python -m py_compile scripts/mem04_passive_compare.py` · `--help` · `python -m pytest tests/ -q` | ❌ W0 | ⬜ pending |
| 10-05-01 | 05 | 2 | MEM-04 | T-10-13 | Rig is sandbox-only, invented data, zero API writes | manual | N/A — `checkpoint:human-action`, `gate="blocking-human"` | N/A | ⬜ pending |
| 10-05-02 | 05 | 2 | MEM-04 | T-10-14 / T-10-15 | Cassettes scrubbed of production ids and real names before commit | unit + human-check | `python -m pytest tests/ -q` · cassette completeness check | ✅ (10-04) | ⬜ pending |
| 10-05-03 | 05 | 2 | MEM-04 | T-10-17 | Ledger append-only, one dated entry, `CLAUDE.md` untouched | structural + human-check | ledger content check · dated-entry check · `python -m pytest tests/ -q` | ✅ | ⬜ pending |
| 10-06-01 | 06 | 4 | MEM-03 | T-10-19 | An empty artifact set FAILs rather than passing vacuously | unit | `python -m py_compile scripts/compare_control_run.py` · `--help` · `python -m pytest tests/test_compare_control_run.py -q` | ❌ W0 | ⬜ pending |
| 10-06-02 | 06 | 4 | MEM-01 | T-10-02 / T-10-07 | Schema exposed but unreadable by anon/authenticated; retention DDL reviewed before it goes live | manual | N/A — `checkpoint:human-action`, `gate="blocking-human"` | N/A | ⬜ pending |
| 10-06-03 | 06 | 4 | MEM-01, MEM-02, MEM-03 | T-10-18 / T-10-20 | `hash_history.json` byte-identical after the dry-run sequence; the production workflow flag stays absent | integration + human-check | `scripts/compare_control_run.py` · `WORKFLOW_FLAG_ABSENT_OK` check · `git diff --exit-code` guard set · `ROLLOUT_LEDGER_OK` · `bash scripts/run_6_gates.sh` | ✅ (10-06-01) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Sampling continuity:** no three consecutive tasks lack an `<automated>` verify.
The only two tasks without one are the two `checkpoint:human-action` gates
(10-05-01 and 10-06-02); each is immediately followed by an automated task whose
`<precondition>` asserts the checkpoint's outcome before proceeding.

---

## Wave 0 Requirements

Created inside the wave-1 plans rather than as a separate prior wave, because each
new test module is authored red-first alongside the code it pins:

- [ ] `tests/test_pipeline_memory_shadow.py` — covers MEM-01, MEM-02, MEM-03
      (created in plan 10-01 Task 1, extended by 10-01 Task 3, 10-02 and 10-03)
- [ ] `tests/test_mem04_formula_change.py` — covers MEM-04 tooling discipline
      (created in plan 10-04 Task 2, extended by 10-04 Task 3 and 10-05 Task 2)
- [ ] `tests/test_compare_control_run.py` — covers the SC-4 comparison harness
      (created in plan 10-06 Task 1)
- [ ] `tests/fixtures/mem04/` — new fixture directory (plan 10-04, populated 10-05)
- [ ] Framework install: none — pytest 9.0.3 is already installed and in use
      project-wide; no new package is added by this phase

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Sandbox formula rig creation and the two triggering edits | MEM-04 | D-08 locks ZERO Smartsheet API writes; there is no permitted programmatic path | Plan 10-05 Task 1 `checkpoint:human-action` |
| Applying the DDL, exposing `pipeline_memory` to PostgREST, reloading the schema cache, confirming pg_cron | MEM-01 | No Supabase CLI or migration runner is configured in this repo; the DDL convention is apply-by-hand; production guardrails require Juan's approval for schema/RLS changes | Plan 10-06 Task 2 `checkpoint:human-action` |
| Confirming the MEM-04 verdict matches the observed UI behaviour | MEM-04 | The recalculation is observed in the Smartsheet UI; the UI observation wins on conflict with the script | Plan 10-05 Task 2 `<human-check>` |
| Confirming the shadow run actually wrote to Supabase, and the timing headroom | MEM-01, MEM-03 | Live row counts and wall-clock headroom require reading the production project and the run logs | Plan 10-06 Task 3 `<human-check>` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or a documented manual-only justification
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5 s (quick) / < 5 min (phase gate)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
