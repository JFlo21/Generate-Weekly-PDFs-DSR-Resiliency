---
name: force-week-regeneration
description: Use when forcing regeneration of Excel for a past week-ending or specific Work Requests after a data correction, or when change-detection is skipping a group that should regenerate. Covers REGEN_WEEKS, RESET_HASH_HISTORY, RESET_WR_LIST, KEEP_HISTORICAL_WEEKS, and the GitHub Actions advanced_options parser. High-error, billing-visible — read the warnings.
---

# Force past-week / WR regeneration

Operator recipe for overriding SHA256 change-detection. **Billing-visible output**
— scope tightly and prefer a dry run (`SKIP_UPLOAD=true`) first.

## Key switches
| Var | Purpose |
|---|---|
| `REGEN_WEEKS` | MMDDYY list of week-endings to force-regenerate (e.g. `081725,082425`). |
| `RESET_HASH_HISTORY=true` | Full regeneration. **Required in CI** — hash history is ephemeral there. |
| `RESET_WR_LIST` | Limit the reset to specific WRs. |
| `KEEP_HISTORICAL_WEEKS` | How many weeks of history to retain. |
| `FORCE_GENERATION=true` | Bypass the unchanged-hash skip. |

Local example (dry run first):
```bash
SKIP_UPLOAD=true REGEN_WEEKS=081725 RESET_WR_LIST=WR_12345 python generate_weekly_pdfs.py
```

## GitHub Actions: the `advanced_options` parser
`weekly-excel-generation.yml` packs rarely-used controls into ONE input parsed as
`key:value,key:value` (GitHub's 10-input limit). Do **not** delete this parser.
```
max_groups:50,regen_weeks:081725;082425,reset_wr_list:WR123;WR456
```
(values within a key are `;`-separated; pairs are `,`-separated.)

## ⚠️ Guardrails
- **Never shorten the change-detection key.** It includes `WR, week, variant,
  foreman, dept, job` — shortening it back to `(WR, week, variant, foreman)`
  breaks helper-file regeneration for past weeks. See `memory-bank/living-ledger.md`.
- Helper rows require both `helper_dept` and `helper_foreman`; dual-checkbox rows
  appear only in helper files (prevents double-counting).
- See `.github/prompts/change-detection-troubleshooting.md` before changing behavior.
