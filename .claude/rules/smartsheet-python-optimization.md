# Smartsheet & Python Optimization Rules

> **Scope:** These rules apply to *new* Python scripts in this
> repository. The existing production engine
> `generate_weekly_pdfs.py` is built on `openpyxl` and is governed by
> its own guardrails (`safe_merge_cells()`, the `oddFooter.right.text`
> pitfall, `PARALLEL_WORKERS ≤ 8`, the `helper_dept`/`helper_foreman`
> exclusion rule). Any migration of that engine is a separate planned
> effort — do **not** silently switch it to `xlsxwriter`.

## 1. Bulk Sheet Extraction

**Rule.** When fetching data from Smartsheet, **do not paginate**
row-by-row for primary extraction paths. Use the bulk sheet pull and
let the SDK return the full sheet in a single response.

- Use `smartsheet.Sheets.get_sheet(sheet_id)` as the primary
  extraction call. Access `sheet.rows` directly afterwards.
- Respect the **300 req/min** Smartsheet rate limit; rely on the
  SDK's built-in 429 retry handling rather than adding custom retry
  loops.
- If you need parallelism across multiple sheets, cap concurrent
  workers at **8** (`PARALLEL_WORKERS ≤ 8`) to stay within quota.
- Never invent column names — verify against
  `_validate_single_sheet()` mappings in `generate_weekly_pdfs.py`
  (synonyms for `Weekly Reference Logged Date`, `helper_dept`,
  `helper_foreman`, `Job #`, etc.).
- **Never** use, write, or suggest the Smartsheet `@cell` function in
  Python code or API payloads — it is a UI-only formula and will
  fail server-side.

## 2. High-Performance Excel Generation

**Rule.** For *new* scripts producing Excel output, prefer
`xlsxwriter` in streaming (constant-memory) mode over row-by-row
`openpyxl` writes.

- Use one of the following idioms:

  ```python
  # Direct xlsxwriter
  import xlsxwriter
  workbook = xlsxwriter.Workbook(
      path, {"constant_memory": True}
  )
  ```

  ```python
  # pandas bridge
  df.to_excel(path, engine="xlsxwriter", index=False)
  ```

- `constant_memory=True` flushes rows to disk as they are written,
  keeping memory flat for large exports — required for any export
  expected to exceed a few thousand rows.
- Vectorize transformations **before** writing. Use `pandas` /
  `pandera` for shaping; avoid per-row Python loops inside the write
  phase.
- For the existing `generate_weekly_pdfs.py` pipeline, continue to
  use `openpyxl` with `safe_merge_cells()`. Do not mix engines
  inside a single output file.

## 3. Injecting Attachments Back to Smartsheet

**Rule.** All Smartsheet attachment uploads in new scripts must go
through the SDK's `Attachments.attach_file_to_row(...)` (or the
sheet-level equivalent) and must be wrapped in a Sentry-instrumented
error boundary so failures surface instantly and are rollback-safe.

- Canonical call shape:

  ```python
  import sentry_sdk
  from smartsheet import Smartsheet

  client = Smartsheet(api_token)

  with sentry_sdk.start_span(
      op="smartsheet.attach_file",
      description=f"row={row_id} sheet={sheet_id}",
  ):
      try:
          client.Attachments.attach_file_to_row(
              sheet_id,
              row_id,
              (file_name, file_stream, content_type),
          )
      except Exception:
          sentry_sdk.capture_exception()
          raise
  ```

- When replacing an existing attachment, **delete first, then
  upload** (mirrors the production pattern in
  `generate_weekly_pdfs.py`).
- Standardize Sentry `environment` and `release` tags across all
  scripts so alert routing stays consistent.
- Never swallow exceptions silently. Either re-raise after
  `capture_exception()` or return a typed failure result that the
  caller can act on.
