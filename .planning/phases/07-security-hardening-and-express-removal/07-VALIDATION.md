---
phase: 07
slug: security-hardening-and-express-removal
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-02
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `07-RESEARCH.md` §"Validation Architecture". Plans attach
> concrete validation requirements per SEC requirement; this map is
> populated by the planner with the real per-task rows.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | vitest (portal-v2, bumped to ^4 in 07-04) + standalone Node/TS live-security probe in `scripts/` |
| **Config file** | `portal-v2/vite.config.ts` (vitest config inline); probe is run-standalone (no test runner) |
| **Quick run command** | `cd portal-v2 && npm test` |
| **Full suite command** | `cd portal-v2 && npm test` + `npx tsx scripts/security-probe.ts` (live env vars) |
| **Estimated runtime** | ~10–60 seconds (unit) + live probe network latency |

---

## Sampling Rate

- **After every task commit:** Run `cd portal-v2 && npm test` (for portal-v2 edits)
- **After every plan wave:** Run the full suite + the live security probe against `poeyztlmsawfoqlanucc`
- **Before `/gsd-verify-work`:** Full suite green + live probe assertions all pass + live SPA smoke test
- **Max feedback latency:** ~60 seconds (unit) — live probe is gated to wave verification, not per-task

---

## Per-Task Verification Map

> One row per task across all 4 plans. SEC-01/05 → live probe assertions;
> SEC-02 → vercel.json header assertion + live header-presence/walkthrough;
> SEC-03 → grep gates; SEC-04 → security-reviewer + gsd-secure-phase audit
> dispositions in 07-SECURITY.md; Express removal → grep-gate + SPA smoke test.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | SEC-02 | T-07-02-clickjack / -xss / -mime / -downgrade / -referrer-leak / -csp-breakage | vercel.json carries the 4 named headers + a full-allowlist Report-Only CSP (frame-ancestors 'none', Supabase REST+WSS, hCaptcha, Sentry, img blob:); SPA rewrite intact; no enforcing CSP key yet | unit (node JSON assertion) + build | `cd portal-v2 && node -e "<vercel.json header/CSP/rewrite assertion>"` ; `cd portal-v2 && npm run build` | ✅ exists (modified) | ✅ green |
| 07-01-02 | 01 | 1 | SEC-02 | T-07-02-csp-breakage / -sentry-region | Live deploy shows ZERO Report-Only CSP console violations across Realtime ws, hCaptcha, Sentry, signed-URL download, Vite assets — gates the enforce-flip | manual (checkpoint:human-verify) | re-confirmed in 07-04 via `curl -sI <VERCEL_URL> \| grep -iE 'content-security-policy'` | n/a (live deploy) | ✅ green |
| 07-02-01 | 02 | 1 | SEC-01, SEC-05 | T-07-03-probe-service-role / -probe-leaks-rows | security-probe.ts has all 4 assertions (SEC-01a/b/c + SEC-05/SEC-01d), exit-code contract, diagnostic-only Sentry-exemption JSDoc, ZERO service_role references | unit (node shape gate) + tsc | `cd scripts && node -e "<probe-shape + no-service_role gate>"` ; `cd scripts && npx tsc --noEmit security-probe.ts ...` | ❌ W0 — create `scripts/security-probe.ts` | ✅ green |
| 07-02-02 | 02 | 1 | SEC-01, SEC-05 | T-07-03-anon-read / -pending-read / -anon-storage / -pending-signurl / -signurl-overexposure | Live probe: anon REST → []; anon Storage → 400/403; pending JWT → 0 rows; pending createSignedUrl → denied; SEC-05 TTL=300 single-object | live probe (checkpoint:human-verify) | `npx tsx scripts/security-probe.ts` (live env vars) → EXIT:0 + 4 PASS ; `grep -n "SIGNED_URL_TTL" portal-v2/src/hooks/useDownloadArtifact.ts` → 300 | ❌ W0 — depends on 07-02-01 | ✅ green |
| 07-03-01 | 03 | 2 | SEC-03, SEC-02 | T-07-04-silent-mock / -residual-coupling | All Express coupling severed from portal-v2/src (mockData USE_MOCK regated on VITE_USE_MOCK; useRuns + api.ts + 5 dead components removed; CommandPalette api.search stubbed to empty Promise; vite proxy + .env.example cleaned) | unit/build (vitest + tsc build) | `cd portal-v2 && npm run build && npm test` | ✅ exists (edited/deleted) | ✅ green |
| 07-03-02 | 03 | 2 | SEC-03, SEC-02 | T-07-04-dead-surface / -secret-leak / -spa-404 / -csp-enforce-breakage / -orphan-service | D-02 grep-gate + SEC-03 secret gate both empty; portal/ git-removed; 07-01 zero-violation walkthrough confirmed before flip; CSP flipped to enforcing; SPA rewrite intact | grep gate + build (bash) | `bash -c '<grep-gate + secret-gate + portal-absent + 07-01-SUMMARY walkthrough confirm + CSP-enforced + rewrite-intact>'` | ✅ portal/ deleted; vercel.json edited | ✅ green |
| 07-03-03 | 03 | 2 | SEC-02, Express removal (D-02) | T-07-04-spa-404 / -csp-enforce-breakage / -silent-mock | Live SPA serves real (non-mock) rows; download works; /dashboard deep-link no 404; enforcing CSP blocks nothing; Cmd+K palette opens to empty state without crash | manual (checkpoint:human-verify) | re-confirmed in 07-04: `curl -sI <VERCEL_URL>/dashboard` → 200/3xx ; `curl -sI <VERCEL_URL> \| grep -i 'content-security-policy:'` (enforcing) | n/a (live deploy) | ✅ green |
| 07-04-01 | 04 | 3 | SEC-04 | T-07-05-cve-runtime / -cve-devtool / -cve-moderate-defer | Critical/high CVEs remediated on portal-v2 + website; vitest bumped to ^4+; 107 tests green; both builds green; moderates deferred + logged | unit/build + audit (npm) | `cd portal-v2 && npm audit --audit-level=high --omit=dev` ; `node -e "<vitest >=4 version assertion>"` ; `npm test` ; `cd website && npm run build` | ✅ portal-v2/package.json (modified) | ✅ green |
| 07-04-02 | 04 | 3 | SEC-04 | T-07-05-realtime-d04 / -unverified-mitigation / -header-regression | 07-SECURITY.md has all 8 sections + T-07- IDs + useRealtimeArtifacts D-04 cite + threats_open:0 + status:verified; security-reviewer skill + gsd-secure-phase 07 find no open HIGH/critical | doc gate (bash) | `bash -c '<07-SECURITY.md section + T-07- + D-04 cite + threats_open:0 + status:verified gate>'` | ❌ W0 — `07-SECURITY.md` created by this task | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Nyquist note: every code-producing task has an `<automated>` verify; the three
`checkpoint:human-verify` tasks (07-01-02, 07-02-02, 07-03-03) are inherently
live-deploy / live-network confirmations and each has an automated re-confirmation
gate downstream in 07-04 (header curl, deep-link curl) or in its own task
(07-02-02's `npx tsx` exit-code + grep). No 3 consecutive tasks lack an automated
verify.*

---

## Wave 0 Requirements

- [x] `scripts/security-probe.ts` — live RLS/signed-URL assertions (anon key + pending-role JWT only; never service_role). **Created by 07-02 Task 1 (Wave 1).**
- [x] `pending`-role test account provisioned + JWT acquisition path (per D-08; pre-created Supabase user + GitHub Actions Secrets — operator `user_setup` in 07-02). **Done — `hello@linetec.com` (role=pending) used in the 07-02 live probe (EXIT:0).**
- [x] PLAN.md `<threat_model>` blocks — required for `gsd-secure-phase 07` to operate. **Present in all 4 plans (07-01..07-04).**
- [x] `07-SECURITY.md` — created by 07-04 Task 2 (`gsd-secure-phase 07`); `threats_open: 0`, `status: verified` (2026-06-03).

*`scripts/security-probe.ts` and `07-SECURITY.md` are net-new artifacts created
within this phase (07-02 / 07-04 respectively); the existing 107-test vitest
infrastructure covers all portal-v2 component/hook behavior — no new unit tests
required beyond the probe.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions | Automated Backstop |
|----------|-------------|------------|-------------------|--------------------|
| Live probe one-time sign-off recorded in 07-SECURITY.md | SEC-01, SEC-05 | Live-deploy human confirmation per D-07 | Run probe against live `poeyztlmsawfoqlanucc`; record outcome | `npx tsx scripts/security-probe.ts` EXIT:0 + 4 PASS (07-02-02) |
| CSP Report-Only → enforce flip with zero console violations | SEC-02 | Requires observing the live app (Realtime ws, hCaptcha, Sentry, downloads, Vite assets) | Load live deploy, confirm zero CSP console violations, then flip header (gated) | `curl -sI <VERCEL_URL> \| grep -iE content-security-policy` (07-04) |
| Live SPA smoke test (real data, download, deep-link, no CSP breakage) | SEC-02, Express removal | Requires the live deploy + a logged-in session | Login → real rows → download → deep-link refresh → no CSP-blocked resource | `curl -sI <VERCEL_URL>/dashboard` → 200/3xx (07-04) |
| security-reviewer audit disposition | SEC-04 | Skill-driven adversarial audit + human sign-off on findings | Invoke `security-reviewer` skill + `gsd-secure-phase 07`; resolve HIGH/critical; document in 07-SECURITY.md | bash section/threats_open gate on 07-SECURITY.md (07-04-02) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (`scripts/security-probe.ts` → 07-02-01; `07-SECURITY.md` → 07-04-02; pending-role account → 07-02 user_setup)
- [x] No watch-mode flags
- [x] Feedback latency < 60s (unit suite ~10s; live probe gated to wave verification)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated — per-task map populated, Wave 0 statuses set, nyquist_compliant: true.

---

## Validation Audit 2026-06-05

Retroactive Nyquist audit of the executed phase (`/gsd-validate-phase 07`,
State A). Every per-task requirement was cross-referenced to its executed
verification artifact; key artifacts were independently re-confirmed this session.

| Metric | Count |
|--------|-------|
| Requirements / tasks audited | 9 |
| COVERED | 9 |
| PARTIAL | 0 |
| MISSING (gaps found) | 0 |
| Gaps resolved | 0 |
| Escalated | 0 |

**Independent re-confirmation (2026-06-05):**
- SEC-02 — live `curl -sI` on the production deploy: all 5 headers present, CSP
  **enforcing** (no `-Report-Only`).
- SEC-03 — `portal/**` glob returns no files (backend physically removed).
- 07-03-01 / 07-04-01 — `portal-v2` vitest re-run: **113 passed (20 files), exit 0**
  (includes the SEC-04 HIGH-03 AuthGuard regression test).
- SEC-01/05 + SEC-04 — `scripts/security-probe.ts` and `07-SECURITY.md`
  (`threats_open: 0`) present; Wave 0 artifacts complete.

**Result:** Phase 07 is **Nyquist-compliant** — all 9 tasks have an automated
verify or a manual checkpoint with an automated downstream backstop; no 3
consecutive tasks lack an automated verify. No test generation required.

*Status column flipped ⬜ pending → ✅ green to reflect the executed/verified
state; planning-time `⬜ pending` flags were never updated post-execution.*
