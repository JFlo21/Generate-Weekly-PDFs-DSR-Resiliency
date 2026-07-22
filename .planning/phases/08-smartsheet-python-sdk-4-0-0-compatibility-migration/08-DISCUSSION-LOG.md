# Phase 08: smartsheet-python-sdk 4.x Compatibility Migration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-21
**Phase:** 08-smartsheet-python-sdk-4-0-0-compatibility-migration
**Areas discussed:** Target version & pin shape, Wheel-bug posture in CI, Behavior-neutrality proof depth, Rollout & rollback strategy

**Mode note:** Advisor mode (research-backed comparison tables). The four
gsd-advisor-researcher subagents failed to spawn (transient org
billing/access issue, resolved later in session); research was performed
inline by the main session instead — PyPI JSON wheel-size verification,
upstream CHANGELOG.md review for 4.0.1→4.3.0, and repo inspection of
`scripts/run_6_gates.sh`, `pipeline/retry.py`, `tests/test_smartsheet_retry.py`,
and the workflow install steps.

---

## Target version & pin shape

| Option | Description | Selected |
|--------|-------------|----------|
| ==4.3.0 exact | Deterministic; all deltas reviewed 2026-07-21; future bumps are deliberate PRs | ✓ |
| ==4.0.2 exact | Closest to June research; starts 3 minors behind with no risk benefit | |
| >=4.3,<5 range | Auto-takes future 4.x — re-opens the unreviewed-release path that caused the June crash | |
| >=4.0.2,<5 range | Widest compat; same unreviewed-drift risk, worse | |

**User's choice:** ==4.3.0 exact (recommended option)
**Notes:** Extends the Living Ledger 260608-gwm transport-dep rule from
"upper-bound" to "exact-pin + deliberate reviewed bumps".

---

## Wheel-bug posture in CI

| Option | Description | Selected |
|--------|-------------|----------|
| No workflow change | Wheel bug fixed in 4.0.1 (#144); exact pin freezes a verified-good immutable artifact | ✓ |
| Add import-smoke line | One-line post-install verification in both workflows | |
| Keep --no-binary | Carry the sdist workaround despite the root cause being fixed | |

**User's choice:** No workflow change (recommended option)
**Notes:** Evidence: PyPI wheel sizes — 4.0.0 = 7,842 B (broken) vs
4.0.1–4.3.0 = 259–271 KB (healthy). Import-smoke idea preserved as a
deferred checklist item for future bump PRs.

---

## Behavior-neutrality proof depth

| Option | Description | Selected |
|--------|-------------|----------|
| 6 gates + live probe | Full Phase 09 harness + read-only real-Smartsheet probe on 4.3.0 (covers mocked-ApiError blind spot), ~15 min | ✓ |
| 6 gates + SKIP_UPLOAD A/B | Also full read-only pipeline runs on 3.x vs 4.3.0 with output compare, ~40 min | |
| pytest + TEST_MODE only | Lightest; accepts live-transport blind spot | |
| Max: everything | All oracles, ~1 hour | |

**User's choice:** 6 gates + live probe (recommended option)
**Notes:** Grounding: TEST_MODE synthetic path never touches the real SDK;
retry tests build `error.result` with `mock.Mock()` — neither catches live
SDK drift, hence the live probe.

---

## Rollout & rollback strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Dry-run + timed merge + canary | SKIP_UPLOAD branch run → weekday merge after green cron → one watched manual dispatch | ✓ |
| Canary dispatch only | Merge anytime, dispatch one manual run and watch | |
| Passive watch | Merge; next scheduled cron + Sentry import-crash alert as tripwire | |

**User's choice:** Dry-run + timed merge + canary (recommended option)
**Notes:** Avoid merging in the Sunday-night window before the Monday
05:00 UTC weekly deep run. Rollback = revert PR (restores <4.0.0 pin; pip
cache auto-busts on requirements.txt hash).

---

## Claude's Discretion

- requirements.txt comment wording (record review date + ledger pointer)
- Live-probe shape: throwaway vs committed `scripts/` utility (read-only either way)
- Living Ledger entry wording; CLAUDE.md local-install note refresh
- Whether Gate 6 + the D-06 SKIP_UPLOAD dry-run satisfies SDK-06 or a formal A/B compare is warranted

## Deferred Ideas

- CI post-install import-smoke verification — rejected this phase (redundant with exact pin); revisit on future SDK bump PRs if packaging anomalies reappear.
