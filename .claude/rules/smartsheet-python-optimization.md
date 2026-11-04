---
paths:
  - "**/*.py"
---
# Smartsheet & Python Optimization Rules (pointer)

Scope: **new** Python scripts only. The production engine `generate_weekly_pdfs.py` /
`pipeline/` stays on `openpyxl` under its own guardrails (`safe_merge_cells()`, never
`oddFooter.right.text`, `PARALLEL_WORKERS ≤ 8`, the `helper_dept` / `helper_foreman`
exclusion) — never switch it to `xlsxwriter`. Full text with the code idioms:
`.github/instructions/smartsheet-python-optimization.instructions.md`.

1. **Bulk sheet extraction** — `smartsheet.Sheets.get_sheet(sheet_id)` then `sheet.rows`;
   no row-by-row pagination on primary extraction paths. 300 req/min: rely on the SDK's
   built-in 429 retries (no custom retry loops); cap parallel workers at 8. Never invent
   column names — verify against the `_validate_single_sheet()` mappings in
   `pipeline/discovery.py`. **Never** use, write or suggest the Smartsheet `@cell` function
   in Python code or API payloads — it is UI-only and fails server-side.
2. **High-performance Excel for new scripts** — `xlsxwriter` in streaming mode
   (`Workbook(path, {"constant_memory": True})` or `df.to_excel(path, engine="xlsxwriter")`);
   vectorize with `pandas` / `pandera` before the write phase, no per-row loops while
   writing. `XlsxWriter` is **not** in `requirements.txt`: add it (and any
   `requirements-*.txt` lockfile) in the same PR as the first script that imports it.
   Never mix engines inside one output file.
3. **Attachments back to Smartsheet** — only through the SDK's
   `Attachments.attach_file_to_row(...)` (or the sheet-level equivalent) inside a
   `sentry_sdk.start_span` + `capture_exception()` boundary; delete first, then upload;
   standardized `environment` / `release` tags; never swallow exceptions — re-raise or
   return a typed failure result.
