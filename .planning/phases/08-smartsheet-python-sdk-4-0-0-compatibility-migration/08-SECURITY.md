---
phase: 08
slug: smartsheet-python-sdk-4-0-0-compatibility-migration
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-22
---

# Phase 08 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register authored at plan time (08-01-PLAN.md + 08-02-PLAN.md `<threat_model>` blocks).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| PyPI → local/CI pip install | Third-party package bytes cross into the runtime | SDK wheel (`smartsheet-python-sdk==4.3.0`) |
| requirements.txt → CI/local install resolution | The pin governs which SDK bytes reach production | Dependency resolution |
| SDK → billing engine retry path | `ApiError.error.result` internals consumed by `pipeline/retry.py` | API error shapes |
| Billing engine → real Smartsheet API | The D-05 live probe crosses into production data (read path) | Production billing rows / attachments |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-08-01 | Tampering | Re-export shim removal vs SDK internal retryable-exception lookup | mitigate | SDK 4.3.0 `smartsheet/smartsheet.py:301-302` resolves retryables via `importlib.import_module(__package__ + ".exceptions")` — the removed 3.x shim was a proven no-op. `pipeline/retry.py:67` unchanged (`import smartsheet.exceptions as ss_exc`). `generate_weekly_pdfs.py:17-24` clean. `pytest tests/test_smartsheet_retry.py` re-run live during audit: 17 passed. | closed |
| T-08-02 | Tampering | Gate 1 baseline edit masks a real dropped export | mitigate | `tests/golden/baseline_names.json` verified: 177 entries, `_exc_name` absent. `python scripts/check_api_equality.py` re-run live: `PASS: all 177 baseline names present`. | closed |
| T-08-SC | Tampering (supply chain) | pip install of `smartsheet-python-sdk==4.3.0` | mitigate (08-01) / accept (08-02) | `requirements.txt:9` exact pin `==4.3.0` (no range operators, `--no-binary` absent). Ledger `[2026-07-21 18:20]` records the additive-only 4.0.1→4.3.0 changelog review, wheel byte-size/yank verification, and the exact-pin rule. First-party SDK already in production; no new dependency. Accept half logged below. | closed |
| T-08-03 | Tampering / Integrity | Live probe writes to production Smartsheet under `SKIP_UPLOAD=true` | mitigate | **FIXED 2026-07-22 (this audit's follow-up, Juan-approved).** The declared mitigation ("probe writes nothing") was contradicted by code — `delete_old_excel_attachments()` ran unconditionally in `_upload_one` while `SKIP_UPLOAD` gated only the upload; materialized in the D-05 probe (2 attachments deleted on WR 89881161, self-healed by next cron). Fix: `dry_run: bool = False` parameter on `delete_old_excel_attachments`, `cleanup_untracked_sheet_attachments`, and `purge_existing_hashed_outputs` (`pipeline/cleanup.py`), wired `dry_run=SKIP_UPLOAD` at all five mutating call sites in `pipeline/orchestrate.py`. Invariant now absolute: `SKIP_UPLOAD=true` ⇒ zero Smartsheet mutations, while read-only skip decisions (legacy hash short-circuit) are preserved. TDD'd: `tests/test_skip_upload_delete_gating.py` (7 tests, RED→GREEN) + signature-pin update in `tests/test_security_audit_followup.py`. Full suite: 1171 passed + 130 subtests. | closed |
| T-08-04 | Tampering | Future unreviewed SDK release auto-enters production | mitigate | `requirements.txt:9` exact pin `==4.3.0` makes any bump a deliberate reviewed PR. Ledger `[2026-07-21 18:20]` documents the exact-pin rule for transport-critical dependencies. | closed |
| T-08-05 | Repudiation / DoS | Real 4.3.0 error-shape drift silently breaks retry/backoff | mitigate | 08-02-SUMMARY.md "D-05 Live Probe Result": operator-executed live run on 4.3.0 (2026-07-22 ~10:07 CDT) — 676 target-row + 545 PPP attachment-list calls through `pipeline/retry.py`, zero retry-path exceptions, real `ApiError.error.result` shape matched. Corroborated by ledger `[2026-07-22 10:20]` sign-off. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-08-01 | T-08-SC (accept half, 08-02) | `pip install smartsheet-python-sdk==4.3.0` pulls a third-party (Smartsheet, Inc.) artifact from PyPI. Compensating controls: first-party official SDK already in production (not newly introduced); exact pin prevents unreviewed auto-upgrade; PyPI artifacts immutable; 4.0.1→4.3.0 changelog reviewed additive-only; wheel byte-sizes healthy (259–271 KB), none yanked. | Juan (via 08-02-PLAN threat model) | 2026-07-22 |

*Accepted risks do not resurface in future audit runs.*

---

## Unregistered Flags (informational — future phase register candidates)

| Flag | Source | Note |
|------|--------|------|
| `TEST_MODE=true` with a real API token still performs real Smartsheet **reads** | `deferred-items.md` (found 2026-07-22 during Phase 08 goal verification) | `pipeline/orchestrate.py` takes the synthetic path only `if not API_TOKEN`; a repo-root `.env` token flips TEST_MODE into real discovery/fetch reads. Write-safety preserved (`if not TEST_MODE` gates target map / delete path; `dry_run` gates now add SKIP_UPLOAD coverage). WARNING, not a blocker — carry into the next phase's threat register. |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-22 | 6 | 5 | 1 (T-08-03) | gsd-security-auditor (sonnet) |
| 2026-07-22 | 6 | 6 | 0 | main session — T-08-03 fix implemented (Juan-approved), TDD'd, full suite green |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-22
