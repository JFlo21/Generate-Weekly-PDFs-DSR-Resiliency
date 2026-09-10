---
phase: 14-foreman-helper-2
fixed_at: 2026-09-10T16:15:23Z
round2_fixed_at: 2026-09-10T16:33:34Z
review_path: .planning/phases/14-foreman-helper-2/14-REVIEW.md
iteration: 2
findings_in_scope: 5
fixed: 5
skipped: 0
round2_items_in_scope: 2
round2_fixed: 2
round2_skipped: 0
status: all_fixed
---

# Phase 14: Code Review Fix Report

**Fixed at:** 2026-09-10T16:15:23Z (round 1); 2026-09-10T16:33:34Z (round 2)
**Source review:** .planning/phases/14-foreman-helper-2/14-REVIEW.md
**Iteration:** 2
**Branch:** fix/phase-14-cr01-cr02-wr03 (off master `d08420f`)

**Summary:**
- Round 1 — findings in scope (fix_scope=critical_warning: CR-*, WR-*): 5
- Round 1 — fixed: 5, skipped: 0
- Round 2 — independent production-risk pass on the round-1 WR-03 change
  (`billing_audit/writer.py`) found 2 HIGH items; both fixed, 0 skipped.
  CR-01/CR-02/WR-01/WR-02 were not touched in round 2 (out of scope per the
  coordinator's instruction — they had already passed).

All fixes were applied with a RED (failing test against the pre-fix code) →
fix → GREEN (passing test) cycle, one atomic commit per finding, and are
verified against `pytest tests/ -v` (full suite), `py_compile`, `mypy`, and
`scripts/run_6_gates.sh`.

## Fixed Issues

### CR-01: Helper #2 subcontractor shadow files bill at the wrong price

**Files modified:** `pipeline/pricing.py`, `tests/test_subcontractor_pricing.py`
**Commit:** `0e10891`
**Applied fix:** `_resolve_row_price`'s two literal sites both gained the
Helper #2 siblings — the early gate (`pipeline/pricing.py:636`, now includes
`aep_billable_helper2`/`reduced_sub_helper2` alongside the Helper #1 tuple so
those rows reach the rate-matrix lookup instead of falling through to the raw
Smartsheet price) and the rate-class selection (`pipeline/pricing.py:678`, now
routes `aep_billable_helper2` to `new_{wt}_price` and `reduced_sub_helper2` to
`reduced_{wt}_price` — fixing both sites together was required per the
review, since adding only the first would have billed AEP-billable Helper #2
work at the reduced subcontractor rate).
**RED/GREEN evidence:** Added
`test_helper2_shadow_variants_also_diverge` to
`TestResolveRowPriceAbbreviatedWorkType` (mirrors the existing Helper #1
`test_helper_shadow_variants_also_diverge`, with `new_*`/`reduced_*` rates set
to different values so a fall-through to the wrong branch fails). Verified RED
by `git stash`-ing `pipeline/pricing.py` and running the new test
(`AssertionError: 999.99 != 100.0`), then GREEN with the fix restored (2
passed). Full `tests/test_subcontractor_pricing.py` run: 242 passed.

### CR-02: `EXCLUDE_WRS` / `WR_FILTER` do not recognize Helper #2 group keys

**Files modified:** `pipeline/grouping.py`, `tests/test_subcontractor_helper_shadow_rescue.py`
**Commit:** `f08d63e`
**Applied fix:** Added the three Helper #2 clauses
(`{wr}_HELPER2_`, `{wr}_REDUCEDSUB_HELPER2_`, `{wr}_AEPBILLABLE_HELPER2_`) to
BOTH `_key_matches_wr` and `_key_matches_excluded_wr`, and updated both
docstrings' shape lists from "eleven shapes" to "fourteen shapes" (listing the
three new Helper #2 shapes explicitly).
**RED/GREEN evidence:** Added a new test class
`TestHelper2WrFilterAndExcludeWrs` (modeled on
`tests.test_primary_claim_attribution.TestWrFilterMatchesUserVariant`) driving
the real `group_source_rows` path with a subcontractor Helper #2 row (emits
both `reduced_sub_helper2` and `aep_billable_helper2` shapes), a
non-subcontractor Helper #2 row (plain `helper2` shape), and a different-WR
control row. `test_wr_filter_retains_all_three_helper2_shapes` and
`test_exclude_wrs_drops_all_three_helper2_shapes` verified RED via
`git stash`-ing `pipeline/grouping.py` (both failed: WR_FILTER dropped the
shapes it should retain; EXCLUDE_WRS failed to drop the shapes it should
exclude), then GREEN with the fix restored. Full
`tests/test_subcontractor_helper_shadow_rescue.py` +
`tests/test_primary_claim_attribution.py` + `tests/test_foreman_helper_2.py`
run: 189 passed.

### WR-01: Subcontractor WR-scope builder omits the Helper #2 shadow variants

**Files modified:** `pipeline/attribution.py`, `tests/test_subcontractor_helper_shadow_rescue.py`
**Commit:** `4cc2cd0`
**Applied fix:** Added `'reduced_sub_helper2'` and `'aep_billable_helper2'` to
`_SUBCONTRACTOR_SCOPE_VARIANTS`, so a WR whose only completed subcontractor
rows this run are Helper #2 claims is now classified subcontractor-active and
the legacy off-contract / legacy-primary cleanup gates
(`pipeline/orchestrate.py`'s `_sub_scope`) fire for it.
**RED/GREEN evidence:** Extended `TestSubcontractorWrScopeVariantGate`'s
`test_collects_all_subcontractor_variants` with both Helper #2 shapes and
added `test_helper2_only_wr_classified_subcontractor_active`. Verified RED via
`git stash`-ing `pipeline/attribution.py` (both tests failed — the Helper #2
WR was silently excluded from the scope), then GREEN with the fix restored.
Full `tests/test_subcontractor_helper_shadow_rescue.py` +
`tests/test_incremental_read.py` run: 267 passed.

### WR-02: Helper-family parity test does not cover every literal-enumeration site

**Files modified:** `tests/test_helper2_family_parity.py`, `memory-bank/living-ledger.md`
**Commit:** `a7aef8a`
**Applied fix:** Added `'pipeline/pricing.py'` and `'pipeline/attribution.py'`
to `PARITY_TABLE`. `pipeline/attribution.py` needed one `KNOWN_DEFERRED` entry
for its bare `'helper'` literal at `_run_phase_1_1_hash_prune` — that literal
belongs to a pre-Helper-2, one-time versioned legacy-hash-key migration
(Phase 1.1 / SUB-12), not a variant-dispatch site, so it has no Helper #2
sibling to add (documented in the test file as a permanent structural
exception, not a later-plan-closes-it gap). Appended one
`[2026-09-10 15:30]` entry to the bottom of `memory-bank/living-ledger.md`
recording the standing rule: any new variant emitted by `group_source_rows`
must extend both WR matchers, both `_resolve_row_price` literal sites,
`_SUBCONTRACTOR_SCOPE_VARIANTS`, and `PARITY_TABLE` in the same PR.
**RED/GREEN evidence:** Added both files to `PARITY_TABLE` first, then
verified RED by `git checkout d08420f -- pipeline/pricing.py
pipeline/attribution.py` (pre-CR-01/WR-01 state) and running
`tests/test_helper2_family_parity.py` — 5 subtest failures (both new
literal-sibling gaps caught, exactly the class of bug this table exists to
catch). Restored `git checkout HEAD -- pipeline/pricing.py
pipeline/attribution.py` (CR-01/WR-01 already fixed and committed) and
re-ran — one further failure surfaced (the unrelated `'helper'` literal in
the hash-prune code), resolved with the `KNOWN_DEFERRED` entry. Final GREEN:
3 passed, 60 subtests passed.

### WR-03: `_helper2_rpc_unsupported` degrade flag is read outside its lock under a parallel executor

**Files modified:** `billing_audit/writer.py`, `tests/test_billing_audit_shadow.py`
**Commit:** `7c0fdec`
**Applied fix:** Implemented the review's Option 1. Replaced the bare
`_helper2_rpc_unsupported` boolean with a four-state
`_helper2_probe_state: Literal['unknown', 'probing', 'supported',
'unsupported']` guarded by `_helper2_capability_lock` +
`threading.Condition`. New `_resolve_helper2_capability(probe_fn)`: the first
caller to observe `'unknown'` claims `'probing'` and alone invokes the probe
(outside the lock; the outcome is published via `try/finally` so a probe
exception can never strand waiters); every other caller waits on the
condition bounded by `_HELPER2_PROBE_WAIT_TIMEOUT_SECONDS` (30s) and raises
`_Helper2ProbeTimeout` on expiry, which `freeze_row` treats as the existing
per-row retryable failure (`snapshots_errored`) — never a degraded persist.
`_mark_helper2_rpc_unsupported` keeps its one-time WARNING + counter log,
decoupled from the state transition. `_reset_helper2_capability_for_tests`
resets the new state.
**RED/GREEN evidence:** Updated the 4 existing degrade tests in
`FreezeRowHelper2DegradeTests` for the new state values/accessor names, then
added a new `FreezeRowHelper2ProbeConcurrencyTests` class with 4 threaded
tests:
- `test_concurrent_freeze_rows_send_exactly_one_probe` — 2 rows racing the
  very first Helper #2 freeze produce exactly one extra probe RPC call
  (`2N+1` total calls), never one per racing row.
- `test_concurrent_freeze_rows_waiters_follow_resolved_state` — every racing
  row, prober and waiter alike, ends up sending its successful write without
  the Helper #2 parameters (the resolved state), never a silently dropped or
  double-sent row.
- `test_resolve_helper2_capability_raises_on_waiter_timeout` — a waiter
  whose wait exceeds the bound raises `_Helper2ProbeTimeout`.
- `test_freeze_row_waiter_timeout_is_retryable_not_degraded` — a `freeze_row`
  call that hits a waiter timeout counts as `snapshots_errored`, never
  `helper2_attribution_degraded`.

  All 6 new/updated tests verified RED by `git stash`-ing
  `billing_audit/writer.py` (`AttributeError:
  <module 'billing_audit.writer'> does not have the attribute
  '_HELPER2_PROBE_WAIT_TIMEOUT_SECONDS'` and related failures), then GREEN
  with the fix restored (20 of 20 Helper2-tagged tests passed; ran the
  4-thread concurrency tests 5 times in a row with no flakes).

  Threaded tests use N=2 concurrent rows and inject a small (0.02s) uniform
  latency into the mock RPC to reliably force the interleaving that
  exercises the `Condition.wait_for` branch. N is intentionally 2, not
  larger: `billing_audit.client`'s PER-OP circuit breaker
  (`_CIRCUIT_BREAKER_THRESHOLD = 3`, pre-existing and unrelated to WR-03)
  trips after 3 consecutive `with_retry`-tracked failures for the same op and
  then fast-fails every subsequent call to that op for the rest of the
  process — 3+ truly concurrent rows racing the very first (universally
  failing, pre-migration) Helper #2 freeze would each contribute one
  `with_retry`-tracked initial failure before any degraded retry can
  succeed and reset the counter, tripping the breaker mid-test and turning
  it into an (unrelated) circuit-breaker test instead of a capability-probe
  test. This interaction is real and worth Juan's awareness for a genuinely
  busy production run's first few concurrent Helper #2 freezes against an
  un-migrated RPC, but it is out of scope for WR-03 (which is specifically
  about the probe-count race, not the breaker) and is not touched here.
  Documented in the test class's own comment.
**mypy:** the new `_resolve_helper2_capability` initially produced one new
finding (`Incompatible return value type` — mypy could not narrow the 4-value
`Literal` via an `in (...)` tuple check); restructured as two separate `==`
comparisons, which narrows cleanly. Final mypy delta on `billing_audit/writer.py`:
71 → 71 (neutral — the 3 remaining errors are pre-existing, unrelated
`Cannot assign to a type` findings in `billing_audit/client.py` and a
pre-existing `except ImportError: _APIError = ()` pattern elsewhere in
`writer.py`, confirmed present at the base commit `d08420f` before any of
this run's edits).

## Round 2

An independent production-risk pass reviewed the round-1 WR-03 change
(`billing_audit/writer.py`) and found two HIGH items. CR-01, CR-02, WR-01,
and WR-02 were confirmed passing and were NOT touched in round 2 (per the
coordinator's explicit instruction). Both items are in the same commit,
`7e9c56e`.

**Files modified:** `billing_audit/writer.py`, `tests/test_billing_audit_shadow.py`
**Commit:** `7e9c56e`

### Round-2 item 1: NEW REGRESSION — inconclusive probe pinned state to 'supported' forever

**Applied fix:** Made the capability probe tri-valued instead of boolean-ish.
`_probe_capability` (inside `freeze_row`) now returns one of `'unsupported'`
(confirmed PGRST202), `'supported'` (the bare re-invoke succeeded), or
`'inconclusive'` (any other exception — a transient 503/timeout/connection
reset, PGRST203, or anything else not definitively a Helper #2 signature
rejection). `_resolve_helper2_capability` wraps `probe_fn()` in
`except BaseException` (not just `Exception`) so even an unanticipated probe
crash resolves to `'inconclusive'` rather than propagating and stranding
waiters in `'probing'` forever — the exception is swallowed, never re-raised
(the row that triggered the probe already has its own `result is None` and
falls through to the existing per-row failure handling regardless). The
`finally` block publishes `'inconclusive'` by reverting the PERSISTED state
back to `'unknown'` (never a terminal state) and still calls `notify_all()`
so a waiter loops, re-reads `'unknown'`, and — if attempts remain — may
itself become the next prober with its own row's params. Re-probing is
bounded by a new module-level `_helper2_probe_attempts` counter (incremented
under the lock at the moment a caller claims `'probing'`) plus
`_HELPER2_PROBE_MAX_ATTEMPTS = 5`; once exhausted, a caller that observes
`'unknown'` returns `'inconclusive'` immediately WITHOUT sending an RPC call,
and the persisted state stays `'unknown'` (never a false `'unsupported'`).
Waiters compute a SINGLE deadline (`time.monotonic() +
_HELPER2_PROBE_WAIT_TIMEOUT_SECONDS`) once, before the wait loop, and pass
the shrinking remaining time to each `wait_for` call — a waiter's total wait
stays bounded by one 30s budget even across several `'probing'` →
`'unknown'` → `'probing'` cycles (as different rows each take one
inconclusive attempt), instead of re-arming a fresh 30s budget per cycle. In
`freeze_row`, `'inconclusive'` behaves exactly like `'supported'` did before:
`result` stays `None` and falls through to the existing failure handling
(`snapshots_errored`), never a degraded persist off of a non-confirmed
outcome. `_reset_helper2_capability_for_tests` now also resets
`_helper2_probe_attempts`.

**RED/GREEN evidence:**
- Updated `test_generic_rpc_failure_not_swallowed_by_degrade_path` (asserted
  `_helper2_probe_state == 'supported'` in round 1) to assert
  `== 'unknown'` and `_helper2_probe_attempts == 1`. RED confirmed via
  `git stash`-ing `billing_audit/writer.py` and re-running — the round-1 code
  produced `'supported'`, not `'unknown'` (`AssertionError: 'unknown' !=
  'supported'`), demonstrating the exact regression the round-2 pass found.
- New `test_inconclusive_then_pgrst202_resolves_unsupported_in_two_probes`:
  row 1 hits a generic (non-PGRST202, `23505`) failure → probe resolves
  `'inconclusive'`, state reverts to `'unknown'`, attempts=1. Row 2 then hits
  PGRST202 → its own probe resolves `'unsupported'`, attempts=2. Confirms the
  process re-probes instead of staying permanently pinned.
- New `test_attempts_cap_reached_stops_probing_state_stays_unknown`: with
  `_helper2_probe_attempts` pre-set to the cap, a failing row makes exactly
  ONE RPC call (its own initial attempt) — no probe is sent, the row falls
  through to `snapshots_errored`, and the persisted state stays `'unknown'`.
- New `test_probe_fn_raising_releases_waiters_to_unknown`: a threaded test
  where the prober's `probe_fn` raises `RuntimeError` — the prober's call
  returns `'inconclusive'` (does not propagate the exception), and a
  concurrent waiter that was blocked in `wait_for` is released, observes
  `'unknown'`, and becomes the next prober itself.
- All 4 tests verified RED against the round-1 code (`git stash`-ing
  `billing_audit/writer.py`): the attempts-cap and inconclusive-then-PGRST202
  tests failed with `AttributeError` (`_helper2_probe_attempts` /
  `_HELPER2_PROBE_MAX_ATTEMPTS` did not exist), and the raising-probe test
  failed with the `RuntimeError` propagating uncaught out of
  `_resolve_helper2_capability` and crashing the prober thread — exactly the
  "stranded waiter" failure mode the fix closes.
- GREEN: all 4 new tests + the updated test pass; ran the full
  `FreezeRowHelper2ProbeConcurrencyTests` class (8 tests, including the
  round-1 concurrency tests) 8 times in a row with no flakes.

### Round-2 item 2: ADJACENT LATENT DEFECT — degraded retry shared the full-params attempts' circuit breaker op

**Applied fix:** `_invoke_degraded`'s `with_retry` call now passes
`op="freeze_attribution_degraded"` instead of reusing
`op="freeze_attribution"`. The actual RPC function name invoked
(`.rpc("freeze_attribution", ...)`) is unchanged — only the internal
breaker-tracking/logging label passed to `with_retry` changed, isolating the
degraded retry's own circuit breaker from the (expected-to-fail, right after
a fresh un-migrated deploy) full-params attempts' breaker. Checked every
other `op="freeze_attribution"` reference in the test suite
(`test_breaker_is_per_operation`, the op-isolation tests around
`lookup_attribution`, the kill-switch tests in `TestLookupAttribution` and
the `with_retry` unit tests) — none assert on the degraded retry's internal
op label, so none needed updating.

**RED/GREEN evidence:** New
`test_degraded_retry_survives_freeze_attribution_breaker_trip` (mirrors the
established `test_breaker_is_per_operation` pattern): trips the
`'freeze_attribution'` breaker directly with
`_CIRCUIT_BREAKER_THRESHOLD` (3) consecutive permanent failures via
`ba_client.with_retry(..., op="freeze_attribution")`, confirms
`'freeze_attribution' in ba_client._open_circuits`, THEN calls `freeze_row`
for a Helper #2 row against a mock RPC that still rejects with PGRST202
whenever `p_helper2` is present. Verified RED by `git stash`-ing
`billing_audit/writer.py` — the round-1 code's degraded retry (still sharing
`op="freeze_attribution"`) was fast-failed by the already-open breaker,
`freeze_row` returned `False`. GREEN with the fix: `freeze_row` returns
`True` (the degraded retry executes and succeeds on its own untripped
`'freeze_attribution_degraded'` op), and
`ba_client._consecutive_failures.get('freeze_attribution_degraded', 0) == 0`
/ `'freeze_attribution_degraded' not in ba_client._open_circuits` confirm
the isolation.

**On raising N in the round-1 concurrency tests:** left at N=2. Their reason
for N=2 was never the circuit breaker — it was the deterministic-interleaving
technique (a small artificial delay so both racing threads reliably observe
`'unknown'` at the same time, exercising the actual `Condition.wait_for`
branch). Raising N now that the breaker isolation is fixed is possible but
was intentionally NOT done: for N > 2, some initial full-params attempts
could still be fast-failed by an incidentally-tripped `'freeze_attribution'`
breaker (their own attempts arriving after 3 unrelated concurrent failures),
which would make the existing `2N+1`-call formula assertion non-deterministic
for reasons unrelated to what those tests are proving. The breaker-isolation
property now has its own direct, fully deterministic unit test
(`test_degraded_retry_survives_freeze_attribution_breaker_trip` above)
instead.

### Round-2 mypy / lint

`_resolve_helper2_capability`'s signature widened to the tri-valued
`Literal['supported', 'unsupported', 'inconclusive']` for both its `probe_fn`
parameter and its own return type; `_probe_capability`'s return annotation
matches. `python -m mypy billing_audit/writer.py`: same 3 pre-existing,
unrelated errors as round 1 (0 new). `<=79` column check
(`len(line) > 79` in Python, not byte-length — some box-drawing/em-dash
comment lines in this file are >79 BYTES in UTF-8 but stay under 79
CHARACTERS): 0 new violations introduced by round 2 (3 pre-existing long
lines in `billing_audit/writer.py`, unrelated to this change, confirmed
present in the base commit `d08420f` shifted by line count).

### Round-2 validation

- `pytest tests/test_billing_audit_shadow.py -q`: **230 passed, 67 subtests
  passed** (up from round 1's 226 passed — 4 new tests).
- `pytest tests/ -q` (full suite): **2326 passed, 1 skipped** (up from round
  1's 2322 passed / 1 skipped — the same +4; 0 failed, 0 new skips; still
  well above the master baseline of 2304 passed / 1 skipped).
- `python -m py_compile generate_weekly_pdfs.py billing_audit/writer.py tests/test_billing_audit_shadow.py`: clean.
- `bash scripts/run_6_gates.sh`: **ALL 6 GATES PASSED** — Gate 1 AST import
  equality: 164 baseline names present; Gate 2 facade completeness: 101
  allowlist names resolve; Gate 3 pytest: 2326 passed / 1 skipped; Gate 4
  mypy delta: 71 → 71 (neutral, same as round 1); Gate 5 py_compile: clean;
  Gate 6 golden run_summary: structure matches baseline, 30 keys.

### Round-2 — could not do / left as-is

Nothing was skipped in round 2. One deliberate non-action, explained above:
did not raise N in the round-1 concurrency tests, since it was optional
("if that was the only reason for N=2") and the breaker-isolation property
now has a more direct dedicated test instead. No doc files
(`website/docs/runbook/foreman-helper-2.md` etc.) reference the internal
`op=` label used for the degraded-retry breaker, so none needed updating.

## Skipped Issues

None — all in-scope findings were fixed.

## Out of Scope (Info)

### IN-01: Runbook "operator note" claims are stated more strongly than the code guarantees

Not in `fix_scope` (`critical_warning` excludes Info-severity findings) —
not attempted this run. Per the review, this finding self-resolves once
CR-02 lands: `website/docs/runbook/foreman-helper-2.md:127-131`'s claim that
"none of these controls need to know about `helper2` as a variant" refers to
the `RESET_HASH_HISTORY` / `REGEN_WEEKS` / `RESET_WR_LIST` /
`FORCE_GENERATION` / `WR_FILTER` bullet list on that page — `WR_FILTER` is
now correctly Helper #2-aware after CR-02, so the claim is accurate again for
everything that page states. (`EXCLUDE_WRS` is not mentioned on that page at
all, so its own CR-02 fix does not change anything the runbook currently
claims.) No doc edit was made in this run; a future doc pass can drop this
note once re-verified.

## Validation

- `pytest tests/test_subcontractor_pricing.py -q` (CR-01): 242 passed.
- `pytest tests/test_subcontractor_helper_shadow_rescue.py tests/test_primary_claim_attribution.py tests/test_foreman_helper_2.py -q` (CR-02): 189 passed.
- `pytest tests/test_subcontractor_helper_shadow_rescue.py tests/test_incremental_read.py -q` (WR-01): 267 passed.
- `pytest tests/test_helper2_family_parity.py -q` (WR-02): 3 passed, 60 subtests passed.
- `pytest tests/test_billing_audit_shadow.py -q` (WR-03): 226 passed, 67 subtests passed.
- `pytest tests/ -q` (full suite): **2322 passed, 1 skipped** (baseline on
  master `d08420f`: 2304 passed / 1 skipped — the +18 delta is the new tests
  added by these five fixes; no failures, no new skips).
- `python -m py_compile generate_weekly_pdfs.py`: clean.
- `bash scripts/run_6_gates.sh`: **ALL 6 GATES PASSED**
  (Gate 1 AST import equality: 164 baseline names present; Gate 2 facade
  completeness: 101 allowlist names resolve; Gate 3 pytest: 2322 passed / 1
  skipped; Gate 4 mypy delta: 71 → 71, neutral; Gate 5 py_compile: clean;
  Gate 6 golden run_summary: structure matches baseline, 30 keys).
- Known pre-existing mypy error at `pipeline/orchestrate.py:2195`: not
  touched, not chased, per instructions.

## Nothing skipped, nothing weakened

No test assertions were loosened to make a fix pass (round 2 strengthened
one round-1 assertion — see the round-2 item 1 RED/GREEN evidence — it was
never weakened). No files outside the five findings' cited locations (plus
the required ledger entry, the two round-1 test files' import/setup edits,
and round 2's `billing_audit/writer.py` + `tests/test_billing_audit_shadow.py`)
were modified.

---

_Fixed: 2026-09-10T16:15:23Z (round 1); 2026-09-10T16:33:34Z (round 2)_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2_
