# Refactor Assessment — `generate_weekly_pdfs.py`

_Read-only assessment · 2026-06-25 · 6-agent workflow, adversarially verified · **no code changed.**_

## Verdict: **SPLIT — yes, incremental & behavior-preserving**

Critic: **APPROVED** with **one required mitigation** (the cross-module `global`
rebind hazard, below). `preserves_public_api` was flagged **false** *until that
mitigation is folded into the plan* — the existing pytest suite would catch the
regression, but it must be designed in, not discovered as a red bar.

**No dead code to delete.** All 74 top-level symbols have ≥1 real reference. The
only safe-to-remove items are the `archive/` backup copies (zero runtime coupling)
— separate housekeeping, not part of the refactor. Size reduction comes from
**relocation, not deletion.**

---

## ⚠️ REQUIRED MITIGATION (critic, HIGH) — cross-module `global` rebind hazard

The file has **two** `global` statements that **reassign public-contract names at
runtime**:
- `discover_source_sheets` (line ~4504) rebinds `_FOLDER_DISCOVERED_SUB_IDS`,
  `_FOLDER_DISCOVERED_ORIG_IDS`, and **`SUBCONTRACTOR_SHEET_IDS`**
  (`SUBCONTRACTOR_SHEET_IDS = SUBCONTRACTOR_SHEET_IDS | _FOLDER_DISCOVERED_SUB_IDS`).
- `get_all_source_rows` (line ~5006) rebinds **`_RATES_FINGERPRINT`**.

All four are imported by tests and read **after** the mutating function runs. A
value-copy facade (`from pipeline.X import NAME` or `import *`) binds the *pre-run*
object, so `gwp.SUBCONTRACTOR_SHEET_IDS` / `gwp._RATES_FINGERPRINT` go **stale** →
those tests fail, and worse: if `SUBCONTRACTOR_SHEET_IDS` lives in `config.py` but
`discover_source_sheets` lives in `discovery.py`, the `global` rebinds *discovery's*
namespace, never config's → **silent subcontractor-vs-original billing
mis-classification in production.**

**Required fix (fold into GSD steps 5 & 7):**
1. **Co-locate** each runtime-reassigned global *with its mutating function* in the
   same module (keep `_FOLDER_DISCOVERED_*` + `SUBCONTRACTOR_SHEET_IDS` +
   `discover_source_sheets` together; `_RATES_FINGERPRINT` + `get_all_source_rows`
   together).
2. Expose these specific stateful names through a facade-module **`__getattr__`
   (PEP 562) live-proxy** to the owning submodule — **not** a value re-export.
3. Internal readers reference them as `module.NAME` attribute access, never
   `from module import NAME`.
4. Add regression tests: call `gwp.discover_source_sheets(...)` then assert
   `gwp.SUBCONTRACTOR_SHEET_IDS` reflects the merge; same for `_RATES_FINGERPRINT`
   after `get_all_source_rows`.

**Also:** the facade must use **explicit re-exports**, never `from pipeline.X import *`
— there is no `__all__`, so `*` would silently drop the ~50 underscore-prefixed
names that tests import directly. (`_billing_audit_writer` is a stable module
reference, safe to re-export by value — keep it out of the live-proxy set.)

---

## Proposed module tree

Keep `generate_weekly_pdfs.py` at root as the facade; create a sibling `pipeline/`
package. `audit_billing_changes.py` stays unchanged (already cohesive, 478 lines).

```
generate_weekly_pdfs.py    # FACADE: explicit re-exports of all 106 public names
                           #   + module __getattr__ live-proxy for the stateful
                           #   globals + `if __name__=="__main__": main()`
pipeline/
  __init__.py
  config.py          # _coerce_sheet_id, _DaemonThreadPoolExecutor, _parse_sheet_ids,
                     #   _sanitize_csv_path + module-level os.getenv() constants
                     #   (TARGET_SHEET_ID, PARALLEL_WORKERS cap, folder-ID lists,
                     #   TIME_BUDGET_* family, RATE_RECALC_* flags, VAC_CREW_* shims).
                     #   FOUNDATION — no inbound engine deps.
  observability.py   # 12 Sentry symbols incl. sentry_before_send_log PII backstop.
  utils.py           # is_checked, excel_serial_to_date, _resolve_rate_recalc_cutoff_date,
                     #   _weekly_would_trigger_fallback.
  pricing.py         # 14 pricing/rate symbols incl. recalculate_row_price
                     #   (RATE_RECALC_SKIP_ORIGINAL_CONTRACT guard). HIGH-RISK — move intact.
  discovery.py       # discover_folder_sheets, _title, _normalize_column_title_for_vac_crew,
                     #   discover_source_sheets (+ _validate_single_sheet). << co-locate the
                     #   _FOLDER_DISCOVERED_* + SUBCONTRACTOR_SHEET_IDS globals HERE.
  change_detection.py# calculate_data_hash (WR/week/variant/foreman/dept/job key — DO NOT
                     #   shorten), _compute_aggregated_content_hash, extract_data_hash_from_filename,
                     #   list_generated_excel_files, _resolve_unchanged_for_skip,
                     #   load/save_hash_history.
  identity.py        # build_group_identity. Coupled to change_detection + filename layout.
  cleanup.py         # cleanup_stale_excels, cleanup_untracked_sheet_attachments,
                     #   delete_old_excel_attachments, _has_existing_week_attachment,
                     #   purge_existing_hashed_outputs.
  attribution.py     # _build_*_wr_scope, _run_*_hash_prune, run_claimer_remediation,
                     #   load/save_billing_audit_row_cache.
  fetch.py           # get_all_source_rows. << co-locate _RATES_FINGERPRINT global HERE.
  grouping.py        # group_source_rows (helper dual-checkbox exclusion — KEEP exact),
                     #   validate_group_totals.
  excel.py           # safe_merge_cells, *_variant_suffix, generate_excel. openpyxl ONLY.
  upload.py          # create_target_sheet_map[_for], _build_upload_tasks_for_group.
  testmode.py        # _build_synthetic_rows, _run_synthetic_test_mode (TEST_MODE).
  orchestrate.py     # main (~2380 lines). Decompose INTERNALLY later, not in split PRs.
```

## Dead / legacy code

| symbol | kind | verdict |
|---|---|---|
| any top-level function/class | dead code | **KEEP** — zero removable; every symbol referenced (entry point / public API / internal call) |
| `VAC_CREW_SHEET_IDS`, `VAC_CREW_FOLDER_IDS` (lines 379–380) | test-compat shim | **KEEP** — labeled legacy but imported/asserted by `test_vac_crew.py` |
| `datetime.utcnow()` (line ~8956; `scripts/backfill_attribution_snapshot.py:222`) | deprecated API (Py3.12) | **needs-human-confirm** — behavior-adjacent, separate PR |
| `archive/*backup.py`, `archive/*complete_fixed.py`, `archive/Pasted-*.txt` | duplicate archive | **safe-to-remove (housekeeping)** — zero coupling; separate PR |

**Doc-correctness (write-back, not code):** `CLAUDE.md` describes `VAC_CREW_FOLDER_IDS`
as an active folder-discovery input — it has **zero production consumers**. Correct the doc.

## Risk & safeguards
- **Test net:** 19 test files + `analyze_*`/`diagnose_*`/`scripts` import the public API.
  After each move run `pytest tests/ -v`, `python -m py_compile generate_weekly_pdfs.py`
  (CI gate), `mypy` (lint gate). A broken re-export fails fast at import.
- **Byte-for-byte guards** (pure cut/paste, no logic delta in any relocation PR):
  `recalculate_row_price` (RATE_RECALC_SKIP_ORIGINAL_CONTRACT), `calculate_data_hash` +
  `build_group_identity` (change-detection key + WR sanitization + filename layout),
  `group_source_rows` (helper dual-checkbox exclusion), `generate_excel`
  (safe_merge_cells, no `oddFooter.right.text`), config (`PARALLEL_WORKERS ≤ 8`).
- **Circular imports:** `config.py` imports nothing in `pipeline/`. `identity.py` ↔
  `change_detection.py` are mutually coupled — keep adjacent, co-locate if a cycle appears.
  `orchestrate.py` imports everything; only the facade imports it.
- **Side-effect ordering & Sentry double-init:** module-level env parse / Sentry config /
  regex compile must run once in original order — preserve via facade import order; keep
  Sentry `init()` only on the orchestration/entry path. Snapshot a `TEST_MODE` run before/
  after each PR and diff `run_summary.json` structure.

## GSD execution plan (one cohesive group per step; tests green each step)
1. **Scaffold + baseline** — empty `pipeline/__init__.py`; record green (`pytest`, `py_compile`, `mypy`). [low]
2. **config.py** — constants + 4 helpers; facade imports first (import-order critical). [high]
3. **utils.py** (leaf). [low]
4. **observability.py** — Sentry group; no double-init on facade import. [med]
5. **pricing.py** — billing core, intact (RATE_RECALC guard). [high]
6. **change_detection.py + identity.py** together; hash key + filename byte-identical. [high]
   — **apply the `__getattr__`/co-location mitigation pattern starting here.**
7. **discovery.py** then **fetch.py** — co-locate the stateful globals (mitigation). [high]
8. **grouping.py** — helper dual-checkbox exclusion untouched. [high]
9. **excel.py** — safe_merge_cells / no oddFooter.right.text. [high]
10. **cleanup.py, upload.py, attribution.py, testmode.py.** [med]
11. **orchestrate.py** — move `main`; facade becomes thin. Full suite + `TEST_MODE` + `SKIP_UPLOAD` dry run. [high]
12. **(Optional, later phase)** internal decomposition of `main` / `group_source_rows` /
    `get_all_source_rows` into named private helpers. Separate GSD phase + review. [optional]
13. **(Optional housekeeping)** remove `archive/`; modernize `utcnow()`; fix `CLAUDE.md`
    `VAC_CREW_FOLDER_IDS` wording + the stale "~3,100 lines" (actually 10,476). [low]

## Prerequisite for symbol-assisted execution
Serena's LSP is set to **`cpp`** for this repo, so symbol-aware navigation/refactor
fails on Python. Point Serena at Python (pyright is installed) before relying on
symbol-level refactor tooling during execution. Not required for the assessment
(used `ast`), but recommended for the split PRs.
