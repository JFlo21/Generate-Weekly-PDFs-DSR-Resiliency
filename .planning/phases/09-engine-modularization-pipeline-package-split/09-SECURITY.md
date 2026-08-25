---
phase: 09
slug: engine-modularization-pipeline-package-split
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-08-25
scope: gap-closure plans 09-07 / 09-08 (threat registers authored at plan time; Phase 09 proper was merged via PR #280 before GSD tracking)
---

# Phase 09 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register source: `<threat_model>` blocks in `09-07-PLAN.md` and `09-08-PLAN.md`.
> Verification depth: ASVS L1 (grep + executed acceptance criteria); all closures cite
> the commit or test that proves the mitigation is present.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| workstation / CI runner → `scripts/check_mypy_delta.sh` | Gate reads `tests/golden/mypy_baseline_count.txt` from the working tree and feeds it to a numeric shell compare | attacker/accident-controllable bytes (line endings, editors) |
| `tests/test_facade_harness.py` → `bash` subprocess | Tests execute the real gate script with caller-written fixture files | synthetic fixture files only |
| `scripts/run_6_gates.sh` → merge decision | Gate exit status drives the revert-not-patch policy for a billing-critical engine | pass/fail signal |
| `scripts/run_6_gates.sh` → Smartsheet production API | Gate 6 executes the real engine; before 09-08 it inherited ambient credentials | production sheet reads (now: none) |
| `tests/golden/mypy_baseline*.txt` → merge decision | Re-baselining permanently raises the accepted defect ceiling | baseline values |
| repo tree → `.planning/debug/*` | mypy capture copied into a committed artifact | file paths, line numbers, type names only |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-09-01 | Tampering | `check_mypy_delta.sh` count comparison | high | mitigate | `_assert_count` hard-fails on non-integer operands (`6a5d321`); `test_gate4_refuses_to_pass_on_malformed_baseline` ×3 | closed |
| T-09-02 | Tampering | `mypy_baseline_count.txt` byte content | high | mitigate | `.gitattributes` `tests/golden/*.txt text eol=lf` (`1bd0bee`) + CR-tolerant `tr -d ' \t\r\n'`; `test_gate4_fails_on_regression_with_crlf_baseline`, `test_golden_txt_baselines_*` (`d4e6911`) | closed |
| T-09-03 | Elevation of Privilege | new bypass surface in Gate 4 | high | mitigate | No env var / flag / positional arg added (diff `7633432..6a5d321` inspected by orchestrator; only `$1`/`$2` are function-locals) | closed |
| T-09-04 | Repudiation | frozen baseline values | medium | mitigate | 09-07 changed line endings only (`56` preserved); re-baseline landed as dedicated attributed commit `da7d73c` with ledger entry naming all 10 findings | closed |
| T-09-05 | Denial of Service | pytest runtime | low | accept | +8 harness tests; full suite 1388 in ~23 s | closed — accepted risk R-09-01 |
| T-09-06 | Information Disclosure | fixtures / ledger content | low | mitigate | Fixtures synthetic; ledger entries cite paths + gap id only, no tokens/IDs (reviewed at commit `a925453`, `da7d73c`) | closed |
| T-09-07 | Denial of Service | Smartsheet API quota / production data path | high | mitigate | Gate 6 prefixed `SMARTSHEET_API_TOKEN=` (`4441b52`); harness run proves `mode: synthetic`, `sheets_discovered: 0`, `api_calls: 0`; `test_gate6_invocation_pinned_to_synthetic_dataset` (`d4e6911`) | closed |
| T-09-08 | Tampering | tracked `generated_docs/hash_history.json` | high | mitigate | sha256 byte-identical before/after every Gate-6 run (09-08 Task 1 verify; orchestrator harness run `8ef7fd95…` both sides) | closed |
| T-09-09 | Tampering | `tests/golden/mypy_baseline*.txt` values | high | mitigate | Re-baseline gated behind `blocking-human` checkpoint; executed only after Juan's explicit `rebaseline` as separate commit `da7d73c` | closed |
| T-09-10 | Tampering | `.github/workflows/*` | high | mitigate | No workflow file in any phase commit (`git diff --name-only 7633432..HEAD` contains no `.github/`) | closed |
| T-09-11 | Repudiation | silent acceptance of a type regression | high | mitigate | Per-finding attribution `.planning/debug/mypy-delta-56-to-65-2026-08-24.md` (`76011aa`), machine-verified complete; ledger entry lists every accepted finding | closed |
| T-09-12 | Information Disclosure | `.planning/debug/mypy-current-2026-08-24.txt` | medium | mitigate | Raw mypy output only (paths, lines, types); no env values, row data, or sheet IDs | closed |
| T-09-13 | Spoofing | ambient-credential-dependent gate behavior | medium | mitigate | Gate-6 result no longer depends on whether a token is in scope (`4441b52`) | closed |
| T-09-SC | Tampering | npm/pip installs | n/a | accept | No packages installed by either plan | closed — accepted risk R-09-02 |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-09-01 | T-09-05 | A few seconds of added pytest runtime is the price of executing real gate bytes rather than a copy of the logic | plan 09-07 (Juan-approved planning) | 2026-08-24 |
| R-09-02 | T-09-SC | No dependency added; package-legitimacy gate not triggered | plans 09-07 / 09-08 | 2026-08-24 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-25 | 14 | 14 | 0 | orchestrator (ASVS L1 short-circuit; register authored at plan time) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-25
