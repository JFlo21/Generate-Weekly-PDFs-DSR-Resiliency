# Quick Task: Fix missing OLD_RATES_CSV default + modernize Sentry — Research

**Researched:** 2026-06-03
**Domain:** Python billing pipeline (rate-CSV loading) + Sentry SDK 2.x instrumentation
**Confidence:** HIGH (Part A traced in-codebase; Part B verified against official changelog/docs)

## Summary

The `OLD_RATES_CSV` "bug" is real but **its production blast radius is effectively zero today** — and that is the single most important fact for choosing the fix. The default file `'CU List - Corpus North & South.csv'` was never committed, so every run logs a `Failed to ... from <path>` error. But the production workflow has pinned `RATE_CUTOFF_DATE: ''` since 2026-04-24, which gates off the *only* meaningful consumer of that CSV (`load_rate_versions → build_cu_to_group_mapping`). The unconditional `original_rates = load_contract_rates(OLD_RATES_CSV)` at :4845 feeds `revert_subcontractor_price`, which **is never called anywhere in the file** — it is dead-fed. So the FileNotFoundError is pure log noise / a false Sentry-able error, not a billing-output defect.

The correct fix is therefore the *least-invasive* one that respects the Living Ledger's "do NOT re-introduce these env vars" retirement decision: make a missing `OLD_RATES_CSV` a **clean, explicit, non-fatal skip** rather than a caught exception that masquerades as a failure. Do not point the default at Arrowhead or any other tracked CSV (that would silently change the CU→group mapping the retired feature uses if it were ever re-enabled, and would re-expand the retired feature's footprint).

For Sentry: the project is already on a mature 2.x setup. There is **no 3.0** (development stopped — stay on 2.x). Latest is **2.61.1**. The project's `>=2.35.0` floor already covers `enable_logs`/`before_send_log`. High-value, low-risk additions: the structured `sentry_sdk.logger` API (2.54.0), cron `monitor_config` config-as-code on the existing `capture_checkin`, an explicit `fingerprint` for the rate-load failure, a final run-summary `set_context`, and `scope.add_attachment` for a redacted run log. **Do NOT adopt `set_measurement` — it was deprecated in 2.28.0.**

**Primary recommendation:** Make `OLD_RATES_CSV` optional — skip the load (and emit one explicit, fingerprinted INFO/breadcrumb) when the resolved path does not exist — rather than relying on a caught `FileNotFoundError`. Add a final-run Sentry `set_context` summary and a fingerprinted capture for genuine rate-load failures. Keep `sentry-sdk>=2.35.0` (optionally floor-bump to `>=2.54.0` only if you adopt `sentry_sdk.logger`).

---

## 1. Bug Root-Cause & Blast Radius

### Root cause (confirmed in code)

- `generate_weekly_pdfs.py:408` — `OLD_RATES_CSV = _sanitize_csv_path('OLD_RATES_CSV', 'CU List - Corpus North & South.csv')`. The default file is not in the repo. [VERIFIED: codebase]
- `_sanitize_csv_path` (:393–405) treats an **empty env value as "use default"**: `raw = (os.getenv(env_var,'') or '').strip() or default`. So the production workflow's `OLD_RATES_CSV: ''` (`.github/workflows/weekly-excel-generation.yml:306`) does **not** disable the load — it resolves right back to the missing Corpus file. [VERIFIED: codebase + workflow]
- Both loaders catch *all* exceptions (`except Exception as e: logging.error("Failed to ...")`) and **return an empty dict**:
  - `load_contract_rates` :1454–1456 → `return {}`
  - `build_cu_to_group_mapping` :1515–1517 → `return {}`
  A missing file raises `FileNotFoundError`, which is swallowed into a logged error + empty dict. [VERIFIED: codebase]

### Downstream impact — quantified

| Consumer | Call site | Gated by | Effect of empty dict | Production today |
|----------|-----------|----------|----------------------|------------------|
| `build_cu_to_group_mapping(OLD_RATES_CSV)` → `cu_to_group` | via `load_rate_versions()` :1957, called at :4852 | **`if RATE_CUTOFF_DATE:`** (:4851) | `recalculate_row_price` gets empty `cu_to_group`; every CU misses → `out_status='missing_rate'` → **SmartSheet price retained** (never zeroed) | **Never runs** — `RATE_CUTOFF_DATE=''` pinned since 2026-04-24 |
| `load_contract_rates(OLD_RATES_CSV)` → `original_rates` | :4845 (unconditional) | none | `original_rates={}`; only consumer is `revert_subcontractor_price` (:2101) | `revert_subcontractor_price` is **never called** anywhere → dead-fed value |

**Net blast radius on billing output: zero.** [VERIFIED: codebase grep — `revert_subcontractor_price` has no call sites; `load_rate_versions` only fires under `RATE_CUTOFF_DATE`, which is pinned empty.] Even in the hypothetical where `RATE_CUTOFF_DATE` were re-enabled, the empty-mapping path is *safe-by-design*: `recalculate_row_price` falls through to the SmartSheet price on any lookup miss (`_set_status('missing_rate')`, :2050/2066), and the startup banner (:726–734) loudly warns that the whole CSV-recalc path is retired. The actual harm today is **operational noise**: a recurring `logging.error("Failed to load rates from ...")` and `("Failed to build CU-to-group mapping from ...")` on every run — and, because `LoggingIntegration(event_level=logging.ERROR)` is configured (:1283–1285), each of those `logging.error` calls is a **Sentry event** firing every single run.

**So the real defect is: a benign missing-optional-file condition is being reported to Sentry as a recurring ERROR.** [VERIFIED: codebase — LoggingIntegration event_level=ERROR]

### Why NOT to point the default at a tracked file

The tracked `CU List Contract - Arrowhead Contract.csv` is a subcontractor/Arrowhead file with a *different* purpose. Using it as the `OLD_RATES_CSV` default would (a) silently feed a different CU→group mapping into the retired recalc feature if it were ever switched on, changing billing math, and (b) re-expand the footprint of a feature the Living Ledger [2026-04-24 14:30] explicitly retired ("do NOT re-introduce `RATE_CUTOFF_DATE` / `NEW_RATES_CSV` / `OLD_RATES_CSV`"). Semantically incorrect and against the retirement decision. [CITED: memory-bank/living-ledger.md 2026-04-24 14:30]

---

## 2. Recommended Bug Fix

**Primary approach: make `OLD_RATES_CSV` (and by symmetry the other two retired rate CSVs) OPTIONAL — load only if the resolved path exists; otherwise skip cleanly with ONE explicit, fingerprinted, non-error signal.** This is option (c) from the brief, with a small dose of (b)'s instrumentation. It is the most additive/surgical choice, it matches the workflow's *intent* (`OLD_RATES_CSV: ''` was meant to disable, but `_sanitize_csv_path` defeated it), and it converts a recurring Sentry ERROR into a benign, debuggable INFO/breadcrumb. It does **not** invent new rate logic or re-expand the retired feature.

### Exact touch points

1. **Add an existence guard in the two loaders** (or a shared pre-check) so a missing path returns `{}` *without* taking the `except Exception` error path:
   - `load_contract_rates` — `generate_weekly_pdfs.py:1432–1456`
   - `build_cu_to_group_mapping` — `generate_weekly_pdfs.py:1493–1517`

   Sketch (per loader, top of function body, before `open()`):
   ```python
   if not os.path.isfile(filepath):
       # Optional/retired rate CSV absent (e.g. pinned-empty OLD_RATES_CSV
       # resolving to its uncommitted default). Benign — skip cleanly.
       logging.info(f"Rate CSV not present, skipping load: {filepath}")
       sentry_add_breadcrumb(
           "rate_loading", "rate CSV absent — skipped",
           level="info", data={"path_present": False},
       )
       return rates           # {} for load_contract_rates / mapping
   ```
   Note: `sentry_add_breadcrumb` already exists (:972) and no-ops without a DSN, so this is safe in tests and local runs. **Do not put the file path into a `logging.error`** — keep it INFO so `LoggingIntegration(event_level=ERROR)` does not fire an event, and the path is not row-PII (it is a static config filename, but INFO keeps it out of the event stream regardless).

2. **Distinguish "absent (benign)" from "present but malformed (real error)".** The existing `except Exception` should remain for genuine parse failures of a file that *does* exist — that is still worth a Sentry ERROR, ideally with an explicit fingerprint so it groups stably (see §4, "fingerprint"). No change to the `except` body is required for the bug, but adding a `fingerprint=['rate-csv-load-failure', <fn-name>]` via `sentry_capture_with_context` (:982) is a cheap, high-value upgrade.

3. **Do NOT change the default string at :408 and do NOT touch the workflow pins.** Leaving `OLD_RATES_CSV: ''` and the `'CU List - Corpus North & South.csv'` default in place preserves the documented one-line revert path (Living Ledger [2026-04-24]); the existence guard simply makes "default file absent" a no-op instead of a logged failure.

### Test approach (TDD against existing patterns)

The pattern already exists — extend it, don't invent it:
- `tests/test_subcontractor_pricing.py:43` `test_missing_file_returns_empty` already asserts `load_contract_rates('/nonexistent/path.csv') == {}`.
- `tests/test_subcontractor_pricing.py:759` `test_missing_file_returns_empty` already asserts `build_cu_to_group_mapping('/nonexistent/old.csv') == {}`.

These two tests **already pass** and will keep passing (empty-dict contract preserved). Add assertions that the missing-file path does **not** emit a `logging.error` (i.e., it takes the new benign branch, not the `except`). Use `assertLogs`/`assertNoLogs` at ERROR level:
```python
def test_missing_file_is_benign_not_error(self):
    with self.assertNoLogs(level="ERROR"):
        rates = generate_weekly_pdfs.load_contract_rates("/nonexistent/path.csv")
    self.assertEqual(rates, {})
```
Run: `pytest tests/test_subcontractor_pricing.py -v` (per CLAUDE.md). `assertNoLogs` requires Python 3.10+ (CLAUDE.md floor is 3.10; CI is 3.12). [VERIFIED: codebase tests + CLAUDE.md]

---

## 3. Sentry SDK Currency

| Fact | Value | Source |
|------|-------|--------|
| Latest released version | **2.61.1** (2.61.0 had the last feature batch) | [VERIFIED: getsentry/sentry-python CHANGELOG.md] |
| Is there a 3.x? | **No stable 3.0 — development stopped; switch back to latest 2.x** | [CITED: Sentry Help Center "What Is the Status of Python SDK Version 3.0"; GH Discussion #3936] |
| Project's current floor | `sentry-sdk>=2.35.0` (requirements.txt:2) — covers `enable_logs`/`before_send_log` | [VERIFIED: codebase + CHANGELOG 2.35.0] |
| `enable_logs` / `before_send_log` as top-level init options | **2.35.0** (#4644) | [VERIFIED: CHANGELOG 2.35.0] |
| Structured `sentry_sdk.logger.info/warning/error(msg, **attrs)` with `{placeholder}` syntax | usable from **2.54.0** (logger examples in changelog); Logs product itself shipped behind `enable_logs` from 2.35.0 | [VERIFIED: CHANGELOG 2.54.0; CITED: docs.sentry.io/platforms/python/logs] |
| Separate ignore lists for events/breadcrumbs vs Sentry logs | **2.56.0** (#5698) — relevant if you ever tune log filtering | [VERIFIED: CHANGELOG 2.56.0] |
| `scope.add_attachment` | available across 2.x; hardened pre-2.x-era (graceful path-not-found #3337, broadened type #3342) | [VERIFIED: CHANGELOG; ctx7 `sentry_sdk.attachments.Attachment`] |
| `capture_checkin` (crons) | **>=1.45.0** (project far exceeds) | [CITED: docs.sentry.io/platforms/python/crons] |
| `set_measurement()` | **DEPRECATED in 2.28.0** (#3934) — do not adopt | [VERIFIED: CHANGELOG 2.28.0] |

**Version-gating bottom line for the planner:** Everything recommended below works on the **existing `>=2.35.0`** floor EXCEPT the structured `sentry_sdk.logger` placeholder API, which is cleanest from **2.54.0**. If you adopt that one item, floor-bump to `sentry-sdk>=2.54.0` (still 2.x, no breaking migration). Otherwise no requirements change is needed.

---

## 4. Prioritized Sentry Improvements

> All sketches honor the existing helpers (`sentry_add_breadcrumb` :972, `sentry_capture_with_context` :982, `sentry_capture_message_with_context` :1020) and the PII guardrails. None require a DSN to be safe in tests (helpers no-op when `SENTRY_DSN` is unset).

| # | Improvement | Value to THIS pipeline | Code sketch | Min SDK | PII risk |
|---|-------------|------------------------|-------------|---------|----------|
| 1 | **Fingerprint the rate-load failure** | Genuine (present-but-malformed) rate-CSV errors group as ONE stable issue instead of being lumped with unrelated `logging.error`s; won't auto-resolve oddly | In the `except` of `load_contract_rates`/`build_cu_to_group_mapping`: `sentry_capture_with_context(e, context_name="rate_loading", context_data={"file_present": os.path.isfile(filepath)}, tags={"phase":"rate_load"}, fingerprint=["rate-csv-load-failure", fn_name])` (helper at :982 already sets scope.fingerprint) | **2.35.0** (existing) | LOW — pass `_redact_exception_message(e)` (:937) into context_data, never raw `str(e)` |
| 2 | **Final run-summary `set_context`** | Attaches rows-processed / sheets-discovered / groups-generated / files-uploaded / skipped counts to the run so any later error carries the run shape; also a single capture_message summary | At end of `main()`: `sentry_sdk.set_context("run_summary", {"sheets_discovered": n_sheets, "groups_generated": n_groups, "files_uploaded": n_up, "skipped_unchanged": n_skip, "rate_recalc_active": bool(RATE_CUTOFF_DATE)})` then optional `sentry_capture_message_with_context("Weekly run complete", level="info", context_name="run_summary", context_data=...)` | **2.35.0** (existing) | LOW — **counts only, never names/WR/prices**. No per-group dict, no WR list. |
| 3 | **Config-as-code cron `monitor_config`** | The existing `capture_checkin` becomes self-describing: schedule (`0 13,15,17,19,21,23,1 * * 1-5`), `timezone:"America/Chicago"`, `checkin_margin`, `max_runtime` (align with `timeout-minutes: 195`) live in code, reviewable in git | `monitor_config = {"schedule": {"type":"crontab","value": CRON}, "timezone":"America/Chicago", "checkin_margin": 5, "max_runtime": 195, "failure_issue_threshold": 1, "recovery_threshold": 1}` then `capture_checkin(monitor_slug=..., status=MonitorStatus.IN_PROGRESS, monitor_config=monitor_config)` | **1.45.0** (existing) | NONE — schedule metadata only |
| 4 | **Tags for run mode** | One-click filtering of Sentry issues by run flavor (regen vs normal, grouping mode) | `sentry_sdk.set_tag("res_grouping_mode", RES_GROUPING_MODE); set_tag("wr_filter_active", str(bool(WR_FILTER))); set_tag("force_generation", str(FORCE_GENERATION))` near existing tags (:1391–1394) | **2.35.0** (existing) | MEDIUM — **set `wr_filter_active` as a BOOL, never the WR list itself**. WR numbers are row-PII. |
| 5 | **`scope.add_attachment` for a redacted run log** | Richer debugging: attach the discovery summary / a redacted tail of the run log to the *error* event so on-call sees context without log-diving | In the failure path: `with sentry_sdk.new_scope() as scope: scope.add_attachment(bytes=redacted_summary.encode(), filename="run-summary.txt"); sentry_sdk.capture_exception(e)` | ~2.x (existing) | HIGH — attachment bytes **bypass `before_send_log`**. Must run content through `_redact_exception_message`-style scrubbing first; attach **counts/summary only**, never raw log lines containing WR/foreman/prices. |
| 6 | **Span attributes for KPIs (NOT `set_measurement`)** | Per-run KPIs (rows/sec, groups generated, attachments uploaded, prefetch-budget consumed) on the main transaction span for trend visibility | `span = sentry_sdk.get_current_span(); span and span.set_data("groups_generated", n_groups)` (SDK 2.x: `set_data`; 3.x would be `set_attribute`) | **2.35.0** (existing); avoid `set_measurement` (dep. 2.28.0) | LOW — numeric KPIs only |
| 7 | **(Optional) structured `sentry_sdk.logger`** | For *new* non-PII operational logs only, gives searchable attributes in the Logs UI without the breadcrumb path | `sentry_sdk.logger.info("rate load skipped: {present}", present=False)` | **2.54.0** (floor-bump) | HIGH if misused — gated by `SENTRY_ENABLE_LOGS` *and* `before_send_log`; this API path does **not** automatically run through `_PII_LOG_MARKERS` unless it flows through the `logging` integration. Prefer the existing `logging`+`before_send_log` path for anything that could touch row data. |

**Recommended adopt-now set (zero requirements bump, maximum safety/value):** #1, #2, #3, #4. Treat #5 as optional-with-redaction, #6 as a nice-to-have, #7 as out-of-scope for this quick task (introduces a floor bump and a logging path that sidesteps the established sanitizer).

---

## 5. Pitfalls & Safety

### PII (the dominant constraint here)
- **`SENTRY_ENABLE_LOGS` stays OFF by default** — do not change it. INFO-path logs in this engine embed row PII; `before_send_log` (:1228) + `_PII_LOG_MARKERS` (:1046) are the backstop. [CITED: CLAUDE.md; codebase]
- **`set_context`/`set_tag`/`add_attachment` BYPASS `before_send_log`.** That hook only sanitizes the *Logs* product, not event contexts/tags/attachments. Anything you put in #2/#4/#5 must be **counts, booleans, and pre-redacted strings only** — never WR numbers, foreman/dept/job names, customer names, or dollar amounts. Use `_redact_exception_message` (:937) for any exception text in context_data (the codebase comment at :912–920 makes this exact point).
- **Do not log the file path at ERROR level** in the new benign branch — keep it INFO so `LoggingIntegration(event_level=ERROR)` (:1283) does not turn a benign skip into a Sentry event.

### Production safety (CLAUDE.md)
- **Additive / surgical only.** The fix adds an existence guard and instrumentation; it does not alter the empty-dict contract, the recalc math, grouping, hashing, filenames, or attachment logic. `recalculate_row_price`'s safe SmartSheet-price fall-through is unchanged. [CITED: CLAUDE.md "Do Not Break Production"]
- **Preserve the revert path.** Leave the `:408` default string and the workflow's three pinned-empty rate vars in place — the Living Ledger documents a deliberate one-line revert (`${{ vars.<NAME> || '' }}`). Do not "fix" by re-introducing or repurposing the vars. [CITED: living-ledger.md 2026-04-24 14:30]
- **No new rate logic.** Do not add CU→group fallbacks, alternate default files, or auto-discovery for the retired CSVs.

### Sentry-specific
- **Never use `set_measurement`** (deprecated 2.28.0). Use span `set_data` for KPIs. [VERIFIED: CHANGELOG 2.28.0]
- **No 3.0 migration.** 3.0 is abandoned; do not plan against `set_attribute`/OTel-3.x APIs. Stay 2.x. [CITED: Sentry Help Center #42382711364379]
- **Keep `requirements.txt` at `>=2.35.0`** unless you adopt improvement #7 (then `>=2.54.0`). All recommended adopt-now items work on the current floor.

### What NOT to touch
- The `_sanitize_csv_path` empty-string→default behavior (shared with `SUBCONTRACTOR_RATES_CSV`/`NEW_RATES_CSV`; the CodeQL taint pattern depends on returning the resolved path). The existence guard belongs in the *loaders*, not in `_sanitize_csv_path`.
- The existing `before_send_filter`, `before_send_log`, `_PII_LOG_MARKERS`, `traces_sampler`, and the `sentry_sdk.init(...)` block — they are mature and correct. Add to them; don't rewrite them.
- `@cell` — never reference (no Smartsheet formula work in this task anyway). [CITED: CLAUDE.md]

---

## Sources

### Primary (HIGH)
- `generate_weekly_pdfs.py` (lines 380–471, 714–755, 900–1412, 1432–1517, 1947–2138, 4845–4852) — code-traced [VERIFIED]
- `tests/test_subcontractor_pricing.py:43,759` — existing missing-file tests [VERIFIED]
- `.github/workflows/weekly-excel-generation.yml:304–306` — `OLD_RATES_CSV: ''` pin [VERIFIED]
- `memory-bank/living-ledger.md` [2026-04-24 14:30] — rate-recalc retirement + "do NOT re-introduce" rule [VERIFIED]
- getsentry/sentry-python `CHANGELOG.md` (raw, master) — versions 2.35.0 / 2.54.0 / 2.56.0 / 2.28.0, latest 2.61.1 [VERIFIED]
- Context7 `/getsentry/sentry-python` — `sentry_sdk.attachments.Attachment`, `Monitor` class [VERIFIED]

### Secondary (MEDIUM)
- https://docs.sentry.io/platforms/python/logs/ — enable_logs / sentry_sdk.logger, min 2.35.0 [CITED]
- https://docs.sentry.io/platforms/python/crons/ — `monitor_config` keys, capture_checkin min 1.45.0 [CITED]
- https://docs.sentry.io/platforms/python/migration/2.x-to-3.x — set_measurement→set_data→set_attribute path [CITED]
- Sentry Help Center "Python SDK 3.0 status" / GH Discussion #3936 — 3.0 abandoned [CITED]

## Metadata
- **Bug analysis:** HIGH — fully traced in-codebase incl. dead-fed `revert_subcontractor_price` and `RATE_CUTOFF_DATE` gating.
- **Sentry currency:** HIGH — versions/deprecations from official changelog; 3.0-abandoned from official help center.
- **PII guidance:** HIGH — derived from existing in-code sanitizers and CLAUDE.md.
- **Valid until:** 2026-07-03 (Sentry 2.x is stable/slow-moving; bug analysis is codebase-pinned).
