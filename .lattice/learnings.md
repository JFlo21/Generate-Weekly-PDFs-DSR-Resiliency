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
