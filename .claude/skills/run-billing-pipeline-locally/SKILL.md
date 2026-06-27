---
name: run-billing-pipeline-locally
description: Use when running, dry-running, or test-running generate_weekly_pdfs.py locally — reproduce a single Work Request, validate a change without uploading to Smartsheet, or smoke-test before pushing. Covers TEST_MODE vs SKIP_UPLOAD, WR_FILTER/MAX_GROUPS scoping, and the py_compile + pytest gate.
---

# Run the billing pipeline locally

Read-only operator recipe. **Never edit `generate_weekly_pdfs.py` to make it
runnable** — use the env-var switches it already exposes.

## Pick the right mode
| Goal | Command | Notes |
|---|---|---|
| No Smartsheet token, fully synthetic | `TEST_MODE=true python generate_weekly_pdfs.py` | Safest. No API calls. |
| Real fetch, **no upload** (verify Excel output) | `SKIP_UPLOAD=true python generate_weekly_pdfs.py` | Needs `SMARTSHEET_API_TOKEN`. Writes to `generated_docs/`. |
| Scope to specific WRs | add `WR_FILTER=WR_12345,WR_67890` | Comma list. Combine with either mode. |
| Cap work for a fast loop | add `MAX_GROUPS=10` | |
| Force regen despite change-detection | add `FORCE_GENERATION=true` | For unchanged-hash groups. |

Examples:
```bash
TEST_MODE=true WR_FILTER=WR_12345 python generate_weekly_pdfs.py
SKIP_UPLOAD=true MAX_GROUPS=5 python generate_weekly_pdfs.py
```

## Always gate before pushing
```bash
python -m py_compile generate_weekly_pdfs.py     # syntax-only
pytest tests/ -v                                  # full suite — all must pass
pytest tests/test_subcontractor_pricing.py -v     # one file
pytest tests/ --cov                               # with coverage
```
`pytest tests/` must be green before any push (the repo intends a pre-push gate;
run it manually regardless).

## Related
- Full env reference: `.github/prompts/configuration-environment.md`
- Diagnostics: `python diagnose_pricing_issues.py`, `python run_info.py`
- For past-week / hash-reset regeneration use the **force-week-regeneration** skill.
