# Phase 11 advisor research — Parity proof harness (INC-04)

> Output of a `gsd-advisor-researcher` (Sonnet, calibration `full_maturity`) dispatched during
> `/gsd-discuss-phase 11` on 2026-08-26 05:38Z. **Not a decision.** Preserved across the pause so
> the resumed discussion can present it without re-running the research. Juan has not picked yet.
> Files it read: `scripts/compare_control_run.py`, `pipeline_memory/schema.sql`,
> `.planning/phases/10-run-memory-foundation-shadow-writes/10-06-SUMMARY.md`,
> `pipeline/change_detection.py`.

| Option | Pros | Cons | Complexity | Recommendation |
|--------|------|------|------------|----------------|
| **Shadow-incremental** (compute both paths in-process from the same fetched snapshot inside the existing full run) | One Smartsheet read feeds both paths — no gap, so the Phase 10 "live edits between runs" lesson is sidestepped by construction; reuses `calculate_data_hash()` (`pipeline/change_detection.py`), already in-memory pre-write, so no second Excel pass; every scheduled run yields one streak data point; mirrors the proven Phase 10 shadow pattern (compute, compare, never act on divergence, fail open) | Proves candidate-group-list + pre-write content-hash agreement, not byte-identical `.xlsx` (formatting-only incremental bugs could slip); needs "never a vacuous PASS" discipline like `compare_control_run.py`; requires `row_state` populated → `RUN_MEMORY_WRITE_ENABLED` ON first | 2-3 files (`pipeline/orchestrate.py` hook, new comparison module, `run_ledger.notes` write). Risk: comparison-logic bugs masking divergence; must be sub-budgeted (mirror `ATTACHMENT_PREFETCH_MAX_MINUTES`) so it never threatens `TIME_BUDGET_MINUTES=165` | **Recommended** — the only topology that produces the literal requirement (≥5 consecutive *scheduled* runs) within budget without new infrastructure risk |
| **Dual-output** (generate both sets to separate directories, diff with `scripts/compare_control_run.py`) | Reuses the battle-tested comparator (20 unit tests + real 209k-row validation in 10-06, openpyxl wall-clock canonicalization); verifies actual `.xlsx` content, catching formatting-only bugs | Doubles openpyxl generation + audit cost per affected group — real risk against the 165-min budget on the 2-hourly cadence; within ONE session against the SAME snapshot the live-edit drift disappears, leaving only the doubled write/audit time | 3-5 files (duplicate output-dir wiring, second audit pass or explicit skip, in-process comparator call). Risk: budget headroom, temp-dir cleanup, double-counting the attachment prefetch cache | Keep in reserve for a higher byte-level bar — pair it with the weekly deep run (budget slack; stays full per D-07), not every 2-hourly run |
| **Alternating runs** (odd incremental / even full, compare consecutive artifacts) | Cheapest per run; trivial to implement | Structurally the shape Phase 10 already proved unreliable: two SEPARATE runs ~48–68 min apart produced 13/13 only-in-one-side drift + 3 `run_summary` mismatches from real edits, none pipeline bugs; on the 2-hourly cadence real divergence and harmless drift are indistinguishable, so the 5-run streak resets for the wrong reason and likely never completes; halves how often the incremental path is exercised | 1-2 files. Risk: undecidable evidence | **Not recommended** — falsified by Phase 10's own documented lesson |
| **Replay harness** (capture a full run's fetched rows + memory snapshot, replay the incremental algorithm offline) | Fully deterministic; zero risk to billing output or the time budget; clean bed for algorithm debugging | Does not satisfy "≥5 consecutive SCHEDULED runs"; requires capture/replay tooling 10-06 explicitly names as absent; a second execution path that must itself be proven faithful | 4-6+ files (capture format, storage, replay CLI, fidelity tests). Risk: new maintained subsystem | Useful as a pre-flight/CI supplement to catch algorithm bugs before they cost a scheduled-run streak point — not a substitute for shadow-incremental |

**Rationale (advisor):** Cross-run byte parity is structurally unattainable once Smartsheet edits
happen between separately scheduled runs (Phase 10, proven on real data), so shadow-incremental is
the only topology that yields the literally required evidence within `TIME_BUDGET_MINUTES=165`:
both paths computed from one snapshot inside the run that is already happening, comparison built on
`calculate_data_hash()` (the pipeline's own change-detection primitive) rather than a second openpyxl
pass. Rule alternating runs out. Dual-output stays in reserve for a byte-level bar on the weekly
deep run only. A replay harness is future value for offline debugging, not scheduled-run evidence.
Persist the per-run verdict in `run_ledger.notes` JSONB (already the documented home for
`execution_type` and memory counters; `run_summary.json`'s 21-key contract is frozen — Gate 6) as
`parity_verdict` / `parity_details`; compute "5 consecutive" by scanning the newest `run_ledger`
rows (filtered to `production_frequent` scheduled runs) backward until the first non-pass — the
streak resets naturally on divergence with no dedicated counter column.
