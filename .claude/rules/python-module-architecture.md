---
paths:
  - "**/*.py"
---

# Python Module Architecture

- Keep modules cohesive.
- Treat line count as a review signal, not a target.
- Before adding a new responsibility to an overloaded module, propose extraction.
- Use GSD + Karpathy discipline for non-trivial decomposition.
- Use Serena before moving symbols.
- Preserve imports, public APIs, CLI behavior, and tests.
- Avoid circular imports.
- Avoid generic utility dumping grounds.
- Keep entry points thin.
- Add/update tests before behavior-preserving refactors.
- Update docs/ai/architecture.md after structural changes.

Repo posture: `generate_weekly_pdfs.py` is a facade over the Phase 9 `pipeline/` package;
new behavior goes in the owning `pipeline/*`, `pipeline_memory/*`, or `billing_audit/*`
module, never back into the facade. The 6-gate harness (`bash scripts/run_6_gates.sh`)
includes an AST import-equality gate and a facade-completeness gate; run it after any
module move.
