# Daily Code Review & Code Quality Audit — 2026-05-17

## Scope
Full review across all three repositories:
- Generate-Weekly-PDFs-DSR-Resiliency
- supabase-smartsheet-promax-offload
- Linetec-Resiliency-Promax

## 1. Executive Summary

The three repositories are actively maintained and functional. The most significant
recent change is a P0 hotfix in Generate-Weekly-PDFs (commit 74cd2aa) fixing a
substring-direction bug in `_resolve_row_price` that caused byte-identical AEP and
ReducedSub Excel files. That fix is correct and well-tested (14 new regression tests).

The most urgent security issues are concentrated in Linetec-Resiliency-Promax:
unauthenticated webhook endpoints, client-side-only 2FA verification, and CORS
wildcard on all edge functions. The supabase-smartsheet legacy scripts carry SQL
injection debt. Generate-Weekly-PDFs has a GitHub Actions script injection vector
in the advanced_options parser.

## 2. Top Findings (Ordered by Severity)

### CRITICAL

#### C-1: Smartsheet webhook has zero authentication (Linetec)
- **File:** `supabase/functions/smartsheet-webhook/index.ts:365-378`
- **Problem:** POST requests are processed directly into `work_orders` with no auth check,
  no HMAC signature verification, no API key validation.
- **Impact:** Any external actor can inject/modify work order data.
- **Fix:** Add Smartsheet HMAC-SHA256 signature verification via `Smartsheet-Hmac-SHA256` header.

#### C-2: 2FA verification is entirely client-side (Linetec)
- **File:** `src/hooks/use2FA.ts:105-133`, `src/components/TwoFactorVerify.tsx:19-42`
- **Problem:** The TOTP secret is fetched from Supabase, decrypted in the browser, and
  verified client-side. No server-side record that 2FA was passed. The encryption key
  is stored as exportable JWK in localStorage (`src/lib/encryption.ts:8-42`).
- **Impact:** 2FA can be trivially bypassed by modifying client-side JavaScript. The 3-attempt
  limit is also client-side only (React state, resets on page refresh).
- **Fix:** Move TOTP verification to a server-side edge function. The client should never
  have access to the TOTP secret.

#### C-3: Error response leaks stack traces in webhook (Linetec)
- **File:** `supabase/functions/smartsheet-webhook/index.ts:525-538`
- **Problem:** The 500 response includes `error.message` and `error.stack`.
- **Fix:** Return a generic error message. Log the stack trace server-side only.

### HIGH

#### H-1: GitHub Actions script injection via workflow_dispatch input (Generate-PDFs)
- **File:** `.github/workflows/weekly-excel-generation.yml:202-204`
- **Problem:** `${{ github.event.inputs.advanced_options }}` is directly interpolated
  into a `run:` block. An attacker with dispatch access can inject shell commands
  that exfiltrate `secrets.SMARTSHEET_API_TOKEN` and other secrets.
- **Fix:** Use an environment variable: `env: ADVANCED_OPTIONS: ${{ github.event.inputs.advanced_options }}`
  then reference `${ADVANCED_OPTIONS}` in the script.

#### H-2: Sentry `include_local_variables=True` leaks billing PII (Generate-PDFs)
- **File:** `generate_weekly_pdfs.py:994`
- **Problem:** All local variables at every stack frame are sent to Sentry on exception.
  This includes billing amounts, customer names, foreman names, WR numbers.
  The `_redact_exception_message` sanitizer does NOT scrub frame vars.
- **Fix:** Set `include_local_variables=False` or add a `before_send` hook that
  scrubs `event['exception']['values'][*]['stacktrace']['frames'][*]['vars']`.

#### H-3: SQL injection via f-strings in legacy sync scripts (supabase-smartsheet)
- **File:** `archived_promax_sync.py:296-307`, `smartsheet_sync.py:265-267,337-351`,
  `smartsheet_sync_unified.py:225-230,260-263`, `smartsheet_sync_wide.py:218-223`,
  `smartsheet_live_sync.py:227-229,259-262`, `project_list_sync.py:250-254`
- **Problem:** Column names from Smartsheet data are interpolated via f-strings/format
  into SQL CREATE TABLE, INSERT, and INDEX statements.
- **Fix:** Apply `psycopg.sql.Identifier()` pattern from `folder_sync.py` to all scripts.

#### H-4: Hardcoded Supabase project identifier in source (supabase-smartsheet)
- **File:** `test_new_sync.py:25,51,96`
- **Problem:** `postgres.poeyztlmsawfoqlanucc` is hardcoded as default DB user.
- **Fix:** Remove defaults, require env vars.

#### H-5: Origin validation uses `startsWith` — allows subdomain bypass (Linetec)
- **File:** `supabase/functions/create-user/index.ts:34`
- **Problem:** `sourceOrigin.startsWith(allowed)` matches `http://localhost:5173.evil.com`.
- **Fix:** Use strict equality: `sourceOrigin === allowed`.

#### H-6: CORS `Access-Control-Allow-Origin: *` on all 15 edge functions (Linetec)
- **File:** All `supabase/functions/*/index.ts`
- **Problem:** Every edge function allows all origins. Webhook endpoints should have
  no CORS headers; user-facing endpoints should restrict to production domain.

#### H-7: Password reset enforces only 6-char minimum (Linetec)
- **File:** `src/components/ForgotPassword.tsx:280`
- **Problem:** Reset form checks `password.length < 6` while signup requires 12+ chars
  with complexity. Users can downgrade password security through the reset flow.
- **Fix:** Use the same `validatePassword()` from `src/lib/passwordValidation.ts`.

#### H-8: Password generator uses Math.random() (Linetec)
- **File:** `src/lib/passwordGenerator.ts:15-18,29`
- **Problem:** `Math.random()` (not cryptographically secure) used for guaranteed
  category characters (lines 15-18) and the Fisher-Yates shuffle (line 29).
  Only the remaining characters use `crypto.getRandomValues()`.
- **Fix:** Replace all `Math.random()` with `crypto.getRandomValues()`.

#### H-9: `.env.email-config` contains real company email addresses (Generate-PDFs)
- **File:** `.env.email-config:10,34,35`
- **Problem:** Real `@linetecservices.com` addresses committed to repo.
- **Fix:** Add to `.gitignore` and replace with `@example.com` placeholders.

### MEDIUM

#### M-1: `recalculate_row_price` defaults to 'install' for unknown work types (Generate-PDFs)
- **File:** `generate_weekly_pdfs.py:1666-1671`
- **Problem:** Unlike `_resolve_row_price` which falls through to SmartSheet price,
  this function defaults to install rate for unrecognized work types.
- **Note:** Currently mitigated (function retired in workflow), but risk if re-enabled.

#### M-2: DB connection URLs don't URL-encode passwords in legacy scripts (supabase-smartsheet)
- **File:** 6 legacy scripts (all except `folder_sync.py`)
- **Problem:** Passwords with special characters could break or redirect connections.
- **Fix:** Apply `urllib.parse.quote_plus()` pattern from `folder_sync.py`.

#### M-3: Dead backup files in production directory (Linetec)
- **File:** `supabase/functions/smartsheet-webhook/index-backup.ts`, `index-optimized.ts`, `index-fixed.ts`
- **Fix:** Delete. Use git history for recovery.

#### M-4: Duplicate Supabase client instances (Linetec)
- **File:** `src/lib/supabase.ts` and `src/lib/supabaseClient.ts`
- **Problem:** Two separate client modules creating separate auth sessions.
  `supabase.ts` even creates a placeholder client pointing to `placeholder.supabase.co`.
- **Fix:** Consolidate to a single module.

#### M-5: 20+ `Deno.env.get(...)!` non-null assertions (Linetec)
- **File:** All edge functions
- **Problem:** Missing env vars crash with unhelpful errors.
- **Fix:** Validate env vars at startup, return clear 500 on missing.

#### M-6: `folder_sync.py` missing from Dockerfile (supabase-smartsheet)
- **File:** `Dockerfile:11-19`
- **Problem:** The primary entry point is not in the Docker image.

#### M-7: Broken `system-health-check.yml` references non-existent script (Generate-PDFs)
- **File:** `.github/workflows/system-health-check.yml:67`
- **Problem:** Runs `python validate_system_health.py` which doesn't exist.

#### M-8: XSS risk in markdown renderer (Linetec)
- **File:** `src/lib/markdownRenderer.tsx:43-56`
- **Problem:** `[text](javascript:alert(1))` in AI responses would execute.
- **Fix:** Validate URL protocol before rendering links.

#### M-9: check-rate-limit edge function has no authentication (Linetec)
- **File:** `supabase/functions/check-rate-limit/index.ts`
- **Problem:** Unauthenticated `clear` action can reset rate limits to enable brute force.

#### M-10: Console logging of user email in password reset (Linetec)
- **File:** `src/components/ForgotPassword.tsx:40-41`
- **Problem:** `console.log('Sending password reset email to:', email)` in production.

## 3. Code Quality Improvements

- **Generate-PDFs:** The 7,454-line `generate_weekly_pdfs.py` monolith is the biggest
  maintainability concern. Each Phase 1 feature adds hundreds of lines. Plan incremental
  extraction of pricing, discovery, Excel generation, and upload modules.
- **Generate-PDFs:** The CLAUDE.md Living Ledger is ~900 lines and growing. Consider
  extracting decision records to `.planning/decisions/`.
- **supabase-smartsheet:** Utility functions (`serialize_for_json`, `sanitize_column_name`)
  duplicated across 7-8 files. Extract to shared `utils.py`.
- **supabase-smartsheet:** `smartsheet_sync_unified.py:555-558` has duplicate variable
  assignment (assigned twice, never used).
- **Linetec:** The `src/lib/sanitization.ts` library is well-written. Good patterns.
- **Linetec:** The `EnhancedSupabaseClient` properly validates env vars at startup.

## 4. Security Review Summary

| Area | Generate-PDFs | supabase-smartsheet | Linetec |
|------|---------------|---------------------|---------|
| Auth/Session | Good (portal has bcrypt, session regeneration, CSRF, httpOnly cookies) | N/A (scripts, not web app) | Supabase-managed (good), but 2FA is client-side only (critical) |
| Secrets | `.env.email-config` has real emails; workflow has script injection | Hardcoded project ref in test file | .env.example is clean; no hardcoded keys |
| SQL Injection | N/A | Legacy scripts use f-string SQL (High) | N/A (uses Supabase client) |
| XSS | N/A | N/A | Markdown renderer allows javascript: URLs; sanitization lib is solid |
| CORS | N/A | N/A | Wildcard on all 15 edge functions |
| Input Validation | Good (path traversal prevention, PII scrubbing) | Good in folder_sync.py, weak in legacy | Good frontend sanitization, no webhook payload validation |

## 5. Testing Gaps

| Repo | Gap | Priority |
|------|-----|----------|
| Linetec | No tests for edge functions (webhook, batch-sync, create-user) | High |
| Linetec | No integration tests for auth flow (signup -> verify -> 2FA -> refresh) | High |
| Linetec | No server-side 2FA verification tests (because it doesn't exist) | Critical |
| supabase-smartsheet | Only `test_new_sync.py` exists. No unit tests for utilities or SQL | Medium |
| supabase-smartsheet | No tests for folder_sync.py cycle detection or recursive traversal | Medium |
| Generate-PDFs | Suite is strong (623 passed). Minor gap: no portal/ Express tests | Low |
| Generate-PDFs | No tests for `parse_price` edge cases (parenthetical negatives, intl) | Low |

## 6. Suggested Next Actions

1. **[P0] Add webhook authentication to `smartsheet-webhook/index.ts`** — most critical
   exploitable gap. Implement HMAC-SHA256 verification.

2. **[P0] Move 2FA verification server-side** — current client-side implementation
   provides false security. Create a Supabase edge function for TOTP verification.

3. **[P1] Fix GitHub Actions script injection** — use env variable for `advanced_options`
   instead of direct `${{ }}` interpolation in shell.

4. **[P1] Fix `create-user` origin validation** — change `startsWith` to strict equality.

5. **[P1] Remove hardcoded Supabase project ref** from `test_new_sync.py`.

6. **[P2] Restrict CORS headers** on sensitive edge functions. Remove from webhook endpoints.

7. **[P2] Apply consistent password validation** in the password reset flow.

## Daily Verdict

**Merge with fixes**

The recent `_resolve_row_price` hotfix (74cd2aa) in Generate-Weekly-PDFs is correct and
well-tested. No blockers in that repo for the recent changes. However, the Linetec
repository has critical security issues (unauthenticated webhook, client-side 2FA) that
should be fixed before any new production deployment. The supabase-smartsheet SQL injection
debt is partially mitigated by the fact that the primary entry point (folder_sync.py) is
correctly written, but legacy scripts remain a risk if still in active use. The GitHub
Actions script injection in Generate-PDFs should be fixed promptly as it can exfiltrate
all repository secrets.
