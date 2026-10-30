# Operational learnings (Lattice learning-harvest)

Actionable patterns harvested from completed cycles. One entry per pattern; tighten
or remove entries that stop being true. Repo-local; no secrets, no status.

## 2026-09-09 — Test the caller, not only the callee, for opt-in kwargs (plan 14-13 / O-14-E)

- **Pattern:** when a plan adds an opt-in parameter to a shared writer (here
  `upsert_sheet_registry(mapping_schema_by_sheet=...)`), the verification gate must
  assert that the production caller passes it. Writer-only tests passed for two days
  while production never wrote the value.
- **Detect:** for any new kwarg, grep the production call sites for the kwarg name; a
  source pin on the orchestrator (`inspect.getsource(orch.main)`) is the repo's cheap,
  established way to lock the wiring.
- **Design rule that fell out:** a cache-admission marker must be stamped only when the
  data it certifies is actually written in the same call (here: marker ⊆ sheets whose
  `column_mapping` is written), never on an echoed/stored value.

## 2026-09-09 — Log before you persist (plan 14-14 / PR #396 review round 2)

- **Pattern:** when a run adopts new state (here a frequent run adopting a freshly
  validated `column_mapping` + marker) and the process has an early-exit path between
  the first write and the later observability call, the write can land silently.
  Emit the drift log / breadcrumb immediately BEFORE the first persistence call, not
  at the end of the phase.
- **Detect:** for every "never silently" claim, find the first write that persists the
  adopted value and check that the log sits above it in the same block; an ordering
  pin on the orchestrator source (call index of the log < index of the first write)
  is the cheap lock when a behavioral `main()` test is not feasible.
- **Docs rule that fell out:** a closing condition must be satisfiable by the
  documented capability split — require the marker on all rows but the capability
  keys only on the sheets that physically carry them.

## 2026-09-10 — A parity net certifies only the files it lists; terminal states need definitive signals (Phase 14 code-review fix)

- **Pattern:** `tests/test_helper2_family_parity.py` existed to catch "Helper #1 literal
  without its Helper #2 sibling", yet CR-01 (`pipeline/pricing.py`) and WR-01
  (`pipeline/attribution.py`) slipped through 14 plans because neither file was in
  `PARITY_TABLE`. When adding a sibling variant, grep the whole repo for the Helper #1
  literals FIRST and add every hit to the parity table; a green parity test over an
  incomplete table is false assurance.
- **Pattern:** a capability probe must map only a definitive outcome (explicit success,
  exact rejection code) to a terminal state. Anything else is `inconclusive`: revert to
  `unknown`, bound the re-probes, keep waiters on one deadline. Round 1 of WR-03 pinned
  `supported` off a transient error and would have disabled the degrade path forever.
- **Pattern:** a degraded/fallback RPC call needs its own circuit-breaker op label; sharing
  the primary call's label lets the primary's failures trip the breaker that then blocks
  the fallback.
- **Process:** on protected billing code, an independent read-only production-risk pass
  after the fixer (not just the rubric verifier) is what caught both items — keep it.

- Same-function siblings defeat per-block parity: the `SUB_RATES_FP` gate and the HELPER2 meta block both live
  in `calculate_data_hash()`, so the parity net certified the function while one site lacked the Helper #2
  shadows (PR #402 Copilot round). Pricing site + hash-gate site are one unit; test each tuple member.
