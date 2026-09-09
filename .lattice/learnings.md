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
