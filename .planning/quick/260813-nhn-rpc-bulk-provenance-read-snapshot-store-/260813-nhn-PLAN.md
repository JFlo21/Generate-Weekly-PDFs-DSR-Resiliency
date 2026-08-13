---
phase: quick-260813-nhn
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - audit_billing_changes.py
  - tests/test_rate_sanity_audit.py
  - tests/test_snapshot_store.py
  - billing_audit/schema.sql
  - billing_audit/snapshot_store.py
  - memory-bank/living-ledger.md
  - .planning/STATE.md
autonomous: true
requirements: [P2-333, WR-05, WR-02, WR-02b]
user_setup:
  - service: supabase
    why: "billing_audit.lookup_snapshot_provenance_bulk RPC is DDL; the pipeline never runs DDL (schema.sql header). Manual apply by Juan in the Supabase SQL Editor, then NOTIFY pgrst, 'reload schema'."
    env_vars: []
    dashboard_config:
      - task: "Apply the appended lookup_snapshot_provenance_bulk block from billing_audit/schema.sql, then reload the PostgREST schema cache"
        location: "Supabase Dashboard -> SQL Editor (then Project Settings -> API -> Reload schema cache)"

estimate:
  tokens: 95000
  raw_tokens: 95000
  tasks: 6
  confidence: low        # 0 calibration samples available -> lowest tier

must_haves:
  truths:
    - "With RATE_RECALC_WEEKLY_FALLBACK off, a blank-snapshot post-cutoff row on a sheet that DOES map Snapshot Date is classified out of scope with reason pre_cutoff_or_undated (P2/#333)."
    - "A row carrying a post-cutoff Snapshot Date stays IN scope regardless of the flag — the flag gates only the weekly fallback branch."
    - "fetch_snapshot_provenance returns only success / no_row / fetch_failure / unavailable and never raises — identical before and after the RPC lands (D-04)."
    - "With the RPC deployed, provenance reads issue chunked POSTs and no two-.in_ GET is sent."
    - "With the RPC NOT deployed (PGRST202), the chunked .in_ fallback returns the same rows and emits exactly one WARNING per process (D-05)."
    - "upsert_snapshot_provenance of N records issues ceil(N / _UPSERT_CHUNK) upsert calls, preserves on_conflict='sheet_id,row_id', and never raises (D-02)."
    - "No grouping, pricing, hashing, filename, or upload code path is touched (D-06)."
  artifacts:
    - audit_billing_changes.py
    - tests/test_rate_sanity_audit.py
    - tests/test_snapshot_store.py
    - billing_audit/schema.sql
    - billing_audit/snapshot_store.py
    - memory-bank/living-ledger.md
  key_links:
    - "audit_billing_changes._rate_sanity_in_scope -> generate_weekly_pdfs.RATE_RECALC_WEEKLY_FALLBACK (facade constant, frozen at import — NOT a per-call os.getenv)."
    - "snapshot_store.fetch_snapshot_provenance status string -> pipeline/snapshot_drift.py:551 (`status not in ('unavailable','fetch_failure')`) — a new status would be silently reported as available."
    - "_PROVENANCE_RPC constant value must match the function name created in billing_audit/schema.sql byte-for-byte."
    - "RPC calls use op='lookup_snapshot_provenance_bulk'; the fallback select keeps op='fetch_snapshot_provenance' — per-op circuit-breaker isolation (billing_audit/client.py:565-583, D-13)."
---

<objective>
Close the three deferred billing-audit shadow-layer follow-ups in the sequence the
research proved is load-bearing: P2 flag parity -> characterization oracle ->
SQL -> RPC reader gated by that oracle -> upsert chunking -> docs.

Purpose: the snapshot-drift shadow layer was sized against ~550 grouped rows but
actually runs against `all_rows` (~199,717 on the 2026-08-12 live run). The
two-`.in_` GET is a ~3.4-4 MB querystring and is very likely already failing in
production as `fetch_failure` -> seed-only degrade, i.e. the drift audit never
establishes a baseline. This is a repair, not a polish. The P2 fix closes a
separate scope-gate divergence where the audit can report a mismatch on a row
production deliberately did not recalculate.

Output: one flag-parity fix, a 22-case characterization suite, one appended SQL
function, an RPC-first chunked reader with a chunked degrade path, a chunked
upsert, and a Living Ledger entry.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/quick/260813-nhn-rpc-bulk-provenance-read-snapshot-store-/260813-nhn-RESEARCH.md
@.planning/STATE.md
@CLAUDE.md
</context>

<locked_decisions>
Non-negotiable scope decisions carried from the task brief. Cite the ID in
commit bodies where relevant.

- **D-01** WR-03 RLS lines stay OUT of this change (Juan's DDL decision).
  Note-only: mention in the Living Ledger entry so Juan can fold them into the
  same manual pass if he chooses. Do NOT write them into `schema.sql`.
- **D-02** Chunking `upsert_snapshot_provenance` IS in scope (T5). Same root
  cause as WR-02: ~200 B/record x ~2x10^5 records = a ~40 MB POST body.
- **D-03** `SET search_path` stays a deliberate non-deviation: neither existing
  RPC sets it, the new body is fully schema-qualified and INVOKER. A file-wide
  hardening decision, not a one-function exception.
- **D-04** `rpc_missing` NEVER leaves `snapshot_store`. The externally visible
  vocabulary stays exactly `success` / `no_row` / `fetch_failure` /
  `unavailable` — `pipeline/snapshot_drift.py:551` computes
  `available = status not in ('unavailable','fetch_failure')`, so any new
  status is silently reported as *available*.
- **D-05** `schema.sql` is manual-apply only. The Python MUST behave correctly
  BOTH before and after Juan applies the function; the fallback path is the
  NORMAL state until then. Log the degrade ONCE per process, not per call.
- **D-06** Report-only boundary: no change to grouping, pricing, hashing,
  filenames, or upload. Audit kill switches keep their current meaning; no new
  environment variable is introduced.
</locked_decisions>

<source_audit>
Multi-source coverage audit. Every item maps to a task; no item is deferred.

| Source | Item | Covered by |
|---|---|---|
| GOAL | Close deferred billing-audit shadow-layer follow-ups | T1-T6 |
| REQ  | P2 / #333 — rate-sanity weekly fallback must honor `RATE_RECALC_WEEKLY_FALLBACK` | T1 |
| REQ  | WR-05 — direct characterization coverage for `snapshot_store.py` | T2 |
| REQ  | WR-02 — RPC bulk provenance read (SQL + Python) | T3, T4 |
| REQ  | WR-02b (sibling defect) — chunk `upsert_snapshot_provenance` | T5 |
| RESEARCH | §A.4 SQL block, `RETURNS SETOF`, INVOKER, `GRANT ... service_role` | T3 |
| RESEARCH | §A.5 degrade path, PGRST202 probe template (`billing_audit/writer.py:898-931`), op isolation, chunk constants, one-time log | T4 |
| RESEARCH | §B.4 facade-constant AND placed in `_rate_sanity_in_scope` (not the column-index helper) | T1 |
| RESEARCH | §B.5 hermetic `setUp` patch + R11/R12/R13 | T1 |
| RESEARCH | §C.3 F1-F13 / U1-U4 / I1-I4 / M1 characterization list | T2 |
| RESEARCH | §C.4 A1-A8 RPC tests; A9 upsert-chunk test | T4, T5 |
| CONTEXT | D-01 RLS out (note-only) | T3 note, T6 ledger |
| CONTEXT | D-02 upsert chunking in scope | T5 |
| CONTEXT | D-03 no `SET search_path` | T3 |
| CONTEXT | D-04 status vocabulary frozen | T4 |
| CONTEXT | D-05 manual-apply, correct before AND after, log once | T3, T4 |
| CONTEXT | D-06 report-only boundary | all tasks (verify gate) |

Exclusions (not gaps): WR-03 RLS enablement — explicitly Juan's DDL decision,
recorded as note-only per D-01. Research "Open question 1" (grep a live Actions
log to confirm the read is already failing) — an operator observation, not a code
deliverable; recorded in the Living Ledger entry as the confirmation step.
</source_audit>

<tasks>

<task type="auto" tdd="true">
  <name>T1: Gate the rate-sanity weekly fallback on RATE_RECALC_WEEKLY_FALLBACK (P2/#333)</name>
  <files>tests/test_rate_sanity_audit.py, audit_billing_changes.py</files>
  <read_first>
    .planning/quick/260813-nhn-.../260813-nhn-RESEARCH.md §B (B.1-B.5)
    audit_billing_changes.py:118-161 (`_rate_sanity_in_scope`)
    pipeline/fetch.py:276, 389-403 (the production gate this must mirror)
    tests/test_rate_sanity_audit.py:24-45 (RateSanityTestBase), :544-546, :656-713 (R6/R7)
  </read_first>
  <behavior>
    RED first — write these three before touching `audit_billing_changes.py`:
    - R11 (the RED test): flag OFF, sheet 777 DOES map a Snapshot Date column,
      row has a blank Snapshot Date and a post-cutoff Weekly Reference Logged
      Date -> `_detect_rate_sanity_mismatches` returns `[]`,
      `_rate_sanity_out_of_scope == 1`, and
      `_rate_sanity_out_of_scope_by_reason['pre_cutoff_or_undated'] == 1`.
      Fixture = R7's (tests/test_rate_sanity_audit.py:689-713) with the flag
      flipped. This test FAILS on today's code.
    - R12 (over-correction guard): flag OFF, row carries a post-cutoff
      `Snapshot Date` -> still IN scope, exactly 1 mismatch. The flag gates only
      the fallback branch; `pipeline/utils.py:117-119` returns on the snapshot
      branch before the fallback branch is reached.
    - R13 (conjunction guard): flag ON, sheet maps NO Snapshot Date column ->
      still out of scope. Pins AND, not OR.
    Hermeticity: add to `TestRateSanityScopeHardening.setUp` (currently
    tests/test_rate_sanity_audit.py:544-546) a
    `mock.patch.object(generate_weekly_pdfs, 'RATE_RECALC_WEEKLY_FALLBACK', True)`
    started with `self.addCleanup(patcher.stop)`. That makes R6-R10 hermetic
    against a dev shell exporting the variable as off (the constant is frozen at
    import — `pipeline/pricing.py:64-66`), without editing five test bodies.
    R11/R12 override it locally with their own `mock.patch.object(..., False)`.
    `generate_weekly_pdfs` is already imported at tests/test_rate_sanity_audit.py:20 —
    no new import.
  </behavior>
  <action>
    GREEN step, after the three tests are red/green as specified: in
    `_rate_sanity_in_scope` (audit_billing_changes.py:149-152), extend the
    `weekly_fallback_enabled` expression so the facade constant
    `_gwp.RATE_RECALC_WEEKLY_FALLBACK` is the FIRST conjunct, ANDed with the
    existing `snapshot_column_index` presence check. `_gwp` is already bound at
    :141 — add no import. Keep the expression inside `bool(...)`.

    Read the facade constant, NOT `os.getenv`, and NOT a new module-level
    constant in `audit_billing_changes.py`. Rationale per RESEARCH §B.4: the
    audit must reproduce what production DID, and production used the value
    frozen at import (`pipeline/pricing.py:64-66`, re-exported at
    `generate_weekly_pdfs.py:194`). A per-call environment read would let the two
    disagree mid-run and re-introduce the same defect class from the other side.
    Same convention as the neighbouring `_gwp._AEP_BILLABLE_CUTOFF` read at :156.

    Put the AND at this call site, NOT in `_rate_sanity_snapshot_column_index`
    (:80-97) — that helper maps sheet to column presence and is flag-independent,
    exactly mirroring production's `sheet_has_snapshot_date_column`
    (pipeline/fetch.py:276) where the AND happens at the call site
    (pipeline/fetch.py:389-403).

    Update the F1 bullet of the `_rate_sanity_in_scope` docstring
    (audit_billing_changes.py:134-138) to name BOTH conjuncts; the existing
    `pipeline/fetch.py:276, 389-402` citation stays accurate.

    Scope guard (D-06): this task touches only scope classification. Do not
    modify `_rate_sanity_expected_price`, the tolerance helper, any counter, or
    any pricing/grouping path.
  </action>
  <verify>
    <automated>python -m pytest tests/test_rate_sanity_audit.py -v</automated>
    <automated>python -m py_compile audit_billing_changes.py</automated>
    <automated>python -c "import re,sys; s=open('audit_billing_changes.py',encoding='utf-8').read(); body=s[s.index('def _rate_sanity_in_scope'):s.index('def _rate_sanity_is_mismatch')]; code=[l for l in body.splitlines() if not l.lstrip().startswith('#')]; assert sum('_gwp.RATE_RECALC_WEEKLY_FALLBACK' in l for l in code)==1, 'facade constant not read exactly once in _rate_sanity_in_scope'; assert not any('getenv' in l for l in code), 'per-call env read introduced'; print('OK')"</automated>
  </verify>
  <done>
    R11 fails on the pre-fix code and passes after; R12 and R13 pass; R6-R10
    still pass and are now hermetic against the environment. `_rate_sanity_in_scope`
    reads `_gwp.RATE_RECALC_WEEKLY_FALLBACK` exactly once and performs no
    environment read. Committed alone: `fix(audit): honor weekly-fallback flag`.
  </done>
</task>

<task type="auto">
  <name>T2: Characterization suite for snapshot_store.py — green on UNMODIFIED code</name>
  <files>tests/test_snapshot_store.py</files>
  <read_first>
    .planning/quick/260813-nhn-.../260813-nhn-RESEARCH.md §C.1-§C.3
    billing_audit/snapshot_store.py (all 189 lines)
    billing_audit/client.py:221-307 (get_client, reset_cache_for_tests), :539-739 (with_retry)
    tests/test_billing_audit_shadow.py:141-220 (`_make_fake_supabase_client` chain shape to extend)
  </read_first>
  <action>
    Expand `tests/test_snapshot_store.py` (currently 47 lines, 2 IN-05 tests —
    keep both verbatim) into the full characterization suite. This suite is the
    behavioural ORACLE for T4's refactor: it MUST be written against, and pass
    on, the UNMODIFIED `billing_audit/snapshot_store.py`. Do not edit
    `snapshot_store.py` in this task.

    Mocking boundary: patch `billing_audit.snapshot_store.get_client` ONLY and
    let the real `with_retry` execute (pure Python; it sleeps only on the
    transient path). Call `billing_audit.client.reset_cache_for_tests()`
    (billing_audit/client.py:297-307) in `setUp` and via `addCleanup` so
    `_open_circuits`, `_consecutive_failures`, and `_global_disable_reason` do
    not leak between tests. Build the fake client by extending the
    `.schema(...).table(...).select(...)...execute()` chain shape already proven
    at tests/test_billing_audit_shadow.py:141-220 rather than inventing a new
    harness. No Supabase call is reachable — the client is a Mock.

    Cases, exactly as enumerated in RESEARCH §C.3 (13 + 4 + 4 + 1 = 22):
    `fetch_snapshot_provenance` F1-F13; `upsert_snapshot_provenance` U1-U4;
    `insert_snapshot_drift_events` I1-I4; module contract M1
    (`snapshot_store.sanitized_wr is writer._sanitized_wr`, guarding the
    `noqa: F401` re-export at snapshot_store.py:31).

    Two that carry the contract and must be written precisely:
    - F13 asserts `select` was called with the exact `_PROVENANCE_COLUMNS`
      string (9 columns, matching the table at billing_audit/schema.sql:355-366).
    - U3 asserts `.upsert(records, on_conflict="sheet_id,row_id")` verbatim —
      this pins the PK contract against schema.sql:365.

    Name each test so the case ID is recoverable (e.g. `test_f7_...`,
    `test_u3_...`). Put the three function groups in three classes plus a module
    contract class, so T4 can append a separate RPC class without touching a
    single existing line.

    If any case goes RED on the unmodified module, STOP and surface it in the
    task summary as a pre-existing defect — do not silently "fix"
    `snapshot_store.py` to make a characterization test pass. That inverts the
    oracle.
  </action>
  <verify>
    <automated>python -m pytest tests/test_snapshot_store.py -v</automated>
    <automated>python -c "import subprocess; r=subprocess.run(['git','diff','--quiet','HEAD','--','billing_audit/snapshot_store.py']); assert r.returncode==0, 'snapshot_store.py was modified in the oracle task'; print('snapshot_store.py untouched')"</automated>
    <automated>python -c "import subprocess,sys; out=subprocess.run([sys.executable,'-m','pytest','tests/test_snapshot_store.py','--collect-only','-q'],capture_output=True,text=True).stdout; n=sum(1 for l in out.splitlines() if '::test_' in l); assert n>=22, f'expected >=22 collected tests, got {n}'; print('collected', n)"</automated>
  </verify>
  <done>
    At least 22 tests collected and all green with `billing_audit/snapshot_store.py`
    byte-identical to HEAD. Committed alone:
    `test(billing-audit): characterize snapshot_store`. Record the commit SHA in
    the task summary — T4 uses it as the regression anchor.
  </done>
</task>

<task type="auto">
  <name>T3: Append the lookup_snapshot_provenance_bulk RPC to billing_audit/schema.sql</name>
  <files>billing_audit/schema.sql</files>
  <read_first>
    .planning/quick/260813-nhn-.../260813-nhn-RESEARCH.md §A.4 (the SQL block, verbatim, plus the design-choice table)
    billing_audit/schema.sql:1-24 (manual-apply header), :244-254 (OPERATOR note + the CREATE OR REPLACE return-type footgun), :257-330 (the two existing RPC blocks — the style template), :355-399 (the two snapshot tables; EOF is line 399)
  </read_first>
  <action>
    Append the SQL block from RESEARCH §A.4 at end of file, after the
    `snapshot_drift` GRANT (currently the last statement, billing_audit/schema.sql:397-399),
    matching this file's chronological-append convention. Reproduce the block as
    written in the research — it was authored against the two existing RPC blocks
    for byte-level style parity.

    Properties that must hold and why (all already encoded in the research
    block — verify, do not re-derive):
    - `jsonb` array of sheet/row pairs consumed via `jsonb_to_recordset` JOINed
      to the table on the PK, mirroring `lookup_attribution_bulk`
      (billing_audit/schema.sql:299-328). Exact-tuple match, so the response
      carries only requested rows instead of the sheet x row cross-product the
      current reader discards client-side.
    - `RETURNS SETOF billing_audit.snapshot_provenance` rather than an explicit
      column list — the reader wants all 9 columns, and a composite return
      sidesteps the documented "CREATE OR REPLACE cannot change return columns"
      trap (billing_audit/schema.sql:248-254, the 2026-05-27 incident where a
      multi-role `lookup_attribution` silently never deployed). No DROP FUNCTION
      line is needed.
    - `LANGUAGE sql` + `STABLE`, INVOKER rights (no explicit security clause) —
      byte-consistent with both existing RPCs. `service_role` already holds
      SELECT on the table, so definer rights would add a privilege-escalation
      surface for zero benefit.
    - `GRANT EXECUTE ... TO service_role;` immediately after, matching
      billing_audit/schema.sql:285 and :330.
    - An `OPERATOR:` comment ending in the PostgREST schema-cache reload
      instruction, matching :244-246 / :294-298 / :340-347.
    - Per D-03, no `SET search_path` clause — this is a deliberate file-wide
      consistency choice, not an oversight.
    - No index — the JOIN hits the PK `(sheet_id, row_id)` (schema.sql:365).

    Per D-01, do NOT add row-level-security statements for the two snapshot
    tables in this task; that is Juan's separate DDL decision and is recorded as
    note-only in T6.

    Nothing in CI executes this file (see its header at :1-24), so there is no
    runtime test. Verification is a structural read against the two existing RPC
    blocks plus the automated checks below.
  </action>
  <verify>
    <automated>python -c "s=open('billing_audit/schema.sql',encoding='utf-8').read(); code='\n'.join(l for l in s.splitlines() if not l.lstrip().startswith('--')); assert code.count('CREATE OR REPLACE FUNCTION billing_audit.lookup_snapshot_provenance_bulk')==1, 'function block missing or duplicated'; assert 'RETURNS SETOF billing_audit.snapshot_provenance' in code; assert 'GRANT EXECUTE ON FUNCTION billing_audit.lookup_snapshot_provenance_bulk' in code; assert 'jsonb_to_recordset' in code; print('OK')"</automated>
    <automated>python -c "s=open('billing_audit/schema.sql',encoding='utf-8').read(); code='\n'.join(l for l in s.splitlines() if not l.lstrip().startswith('--')); assert 'SECURITY DEFINER' not in code, 'definer rights introduced'; assert 'search_path' not in code, 'D-03 violated'; print('OK')"</automated>
    <human-check>Read the appended block side by side with billing_audit/schema.sql:257-285 and :299-330 and confirm style parity: same comment banner shape, same LANGUAGE/STABLE lines, same GRANT form, an OPERATOR note ending in the schema-cache reload instruction.</human-check>
  </verify>
  <done>
    billing_audit/schema.sql ends with exactly one lookup_snapshot_provenance_bulk
    block plus its GRANT; no definer rights, no search_path clause (D-03), no
    row-level-security statements (D-01). Nothing else in the file changed.
    Committed alone (operator-facing surface):
    `feat(billing-audit): add provenance bulk RPC DDL`.
  </done>
</task>

<!-- planner-discipline-allow: search_path -->
<!-- planner-discipline-allow: rpc_missing -->
<!-- Both negative gates strip SQL/Python comment lines before matching, so the
     literals may legitimately appear in explanatory comments. -->

<task type="auto" tdd="true">
  <name>T4: RPC-first chunked provenance reader with chunked PGRST202 fallback (WR-02)</name>
  <files>tests/test_snapshot_store.py, billing_audit/snapshot_store.py</files>
  <precondition>The T2 characterization suite is committed and green; `git diff --quiet HEAD -- tests/test_snapshot_store.py` holds at task start (T3 touched only schema.sql). Halt if the working tree already carries edits to either file.</precondition>
  <read_first>
    .planning/quick/260813-nhn-.../260813-nhn-RESEARCH.md §A.3, §A.5, §C.4
    billing_audit/writer.py:866-868, 898-931 (the proven PGRST202 degrade-probe template — copy this shape, do not invent one)
    billing_audit/client.py:310-391 (`_classify_postgrest_error`), :539-583 (per-op breaker), :723-739 (with_retry swallows the reason code — why the probe exists), :180 and :410-412 (`_global_disable_logged`, the one-time-log pattern to mirror)
    billing_audit/snapshot_store.py:43-127 (the reader being refactored)
    pipeline/snapshot_drift.py:545-575 (the consumer; :551 is the status-vocabulary constraint)
  </read_first>
  <behavior>
    RED first — append a new test class to `tests/test_snapshot_store.py` (append
    only; do not edit one existing line):
    - A1: RPC available -> `.rpc('lookup_snapshot_provenance_bulk', {...})` is
      called and the `.table().select()` chain is NOT.
    - A2: payload shape — every element of `p_keys` is a dict of exactly
      `sheet_id` and `row_id`, both `int`.
    - A3: RPC raises a PGRST202-shaped error -> falls back to the select path and
      returns `success`; the returned status is one of the original four and is
      never the internal missing-function marker (D-04).
    - A4: two `fetch_snapshot_provenance` calls in one process with the RPC
      missing -> exactly ONE warning record (assert via `assertLogs` on the
      module logger, count records at WARNING level).
    - A5: RPC raises a TRANSIENT error until retries exhaust -> `fetch_failure`
      and NO select fallback (assert the table chain was never touched). A
      transient outage must not double the request volume.
    - A6: RPC chunking — patch `_RPC_CHUNK_SIZE` to 500, pass 1200 keys, assert
      exactly 3 rpc invocations and that results from all three merge into one
      dict.
    - A7: fallback chunking — RPC missing, 1000 keys, `_FALLBACK_ROW_ID_CHUNK`
      at its module default of 200 -> exactly 5 select invocations, and the
      `sheet_id` list is passed WHOLE on each chunk (only the row axis chunks).
    - A8: op isolation — RPC failures raise
      `billing_audit.client._consecutive_failures['lookup_snapshot_provenance_bulk']`
      and leave the `fetch_snapshot_provenance` entry at 0.
    Tests patch module constants with `mock.patch.object` rather than hardcoding
    production chunk sizes into assertions, so tuning a constant later does not
    break the suite.
  </behavior>
  <action>
    Refactor `fetch_snapshot_provenance` (billing_audit/snapshot_store.py:43-127)
    to try the RPC first and degrade to a chunked select. Follow RESEARCH §A.5
    exactly.

    Add module constants next to `_PROVENANCE_COLUMNS`: the RPC name (value must
    equal the function created in T3 byte-for-byte), an RPC chunk size of 5000
    (~50 B per pair -> ~250 KB body), a fallback row-id chunk of 200 (~3.4 KB of
    ids, under a 4 KB request line), and a module-level boolean latch for the
    one-time degrade log.

    Structure: two private helpers, `_fetch_via_rpc(client, wanted)` and
    `_fetch_via_in_(client, wanted)`, each returning `(rows, status)`; the public
    function keeps its unchanged prologue (empty keys -> `({}, 'no_row')`; client
    acquisition and the disable-reason peek INSIDE the try, the IN-05 fix that
    tests/test_snapshot_store.py exists to pin) and its shared tail (dict->list
    normalization, `int()` coercion of response ids, `wanted` filter, empty ->
    `no_row`, else `success`). Everything stays inside the outer
    `try/except Exception` at :75/:118 — the NEVER-raises contract is the
    boundary contract, not a caller-side courtesy.

    RPC transport: `client.schema('billing_audit').rpc(name, {'p_keys': [...]}).execute()`
    — supported on the pinned `supabase==2.31.0` (`Client.schema()` returns the
    postgrest client, which carries `.rpc`), already the production shape at
    billing_audit/writer.py:900-903. `rpc` posts params as a JSON body, so there
    is no URL-length exposure.

    Degrade detection: `with_retry` returns a bare `None` and discards the reason
    code (billing_audit/client.py:723-739), so recover the code with the bounded
    one-shot probe already proven at billing_audit/writer.py:907-931 — re-invoke
    once outside `with_retry`, classify with `_classify_postgrest_error`, and
    treat the missing-function code as the degrade signal. That code classifies
    as permanent-and-not-a-global-kill, so it costs exactly one attempt, never a
    retry storm. Any other failure is `fetch_failure` with NO fallback.

    Keep the missing-function marker strictly internal to this module (D-04). The
    returned status is always one of the four existing strings, because
    pipeline/snapshot_drift.py:551 computes availability as
    `status not in ('unavailable','fetch_failure')` — a fifth string would be
    silently reported as available.

    Op isolation (D-13, billing_audit/client.py:565-583): the RPC call uses a
    DISTINCT op name equal to the RPC function name; the fallback select keeps
    the EXISTING `op='fetch_snapshot_provenance'`. Sharing one op would burn the
    select path's breaker on RPC-missing failures before the fallback ever runs.

    The fallback MUST chunk (D-05). An unchunked fallback simply reproduces the
    multi-megabyte querystring that motivated the whole change. Chunk on the
    row-id axis only; the sheet-id set is ~13 values (~250 B) and stays whole on
    every chunk. Merge chunk results, then apply the shared tail once.

    One-time log: guard the degrade WARNING with the module-level latch,
    mirroring `_global_disable_logged` (billing_audit/client.py:180, :410-412).
    The message states that the function is not deployed and that the run is
    using the chunked select path with unchanged billing behaviour. Log no row
    data, no ids, no WR values — aggregate wording only (PII discipline). Expose
    a small reset used by tests, or have tests reset the module attribute
    directly.

    Preserve `int()` coercion on response ids — PostgREST can serialize BIGINT as
    a string. Preserve `_PROVENANCE_COLUMNS` on the fallback select. PEP 8, type
    hints, lines at or under 79 columns, matching the existing module.
  </action>
  <verify>
    <automated>python -c "import subprocess,sys; r=subprocess.run(['git','diff','HEAD','--','tests/test_snapshot_store.py'],capture_output=True,text=True); dels=[l for l in r.stdout.splitlines() if l.startswith('-') and not l.startswith('---')]; assert not dels, 'T2 oracle was edited: %d deleted lines' % len(dels); print('oracle intact, additions only')"</automated>
    <automated>python -m pytest tests/test_snapshot_store.py -v</automated>
    <automated>python -m pytest tests/test_snapshot_drift_audit.py -v</automated>
    <automated>python -m py_compile billing_audit/snapshot_store.py</automated>
    <automated>python -c "import re; src=open('billing_audit/snapshot_store.py',encoding='utf-8').read(); code='\n'.join(l for l in src.splitlines() if not l.lstrip().startswith('#')); import ast; ast.parse(src); rets=set(re.findall(r'return \{\}, \"(\w+)\"|return result, \"(\w+)\"', code)); flat={x for t in rets for x in t if x}; assert flat <= {'no_row','fetch_failure','unavailable','success'}, 'status vocabulary widened: %s' % flat; assert max(len(l) for l in src.splitlines())<=79, 'line over 79 cols'; print('vocabulary + width OK')"</automated>
  </verify>
  <done>
    The T2 oracle re-runs unchanged (zero deleted lines) and stays green; A1-A8
    pass; the drift-audit suite passes; every literal status returned by the
    module is one of the four existing strings; no line exceeds 79 columns.
    Committed alone: `perf(billing-audit): rpc-first provenance read`.
  </done>
</task>

<task type="auto" tdd="true">
  <name>T5: Chunk upsert_snapshot_provenance (sibling defect, D-02)</name>
  <files>tests/test_snapshot_store.py, billing_audit/snapshot_store.py</files>
  <read_first>
    .planning/quick/260813-nhn-.../260813-nhn-RESEARCH.md §A.2 (sibling-defect paragraph) and §C.4 A9
    billing_audit/snapshot_store.py:130-157 (the writer being chunked)
    pipeline/snapshot_drift.py:180-201 (`_provenance_record` — the ~200 B, 9-field record being batched)
  </read_first>
  <behavior>
    RED first: A9 — patch the upsert chunk constant to 1000, call
    `upsert_snapshot_provenance` with 2500 records, assert exactly 3 upsert
    invocations, that the concatenation of the three record batches equals the
    input in order, and that every call still passes the same conflict-target
    string. Plus a regression case: a chunk whose `execute()` raises must not
    raise out of the function and must not abort the remaining chunks.
    U1-U4 from T2 must still pass unmodified.
  </behavior>
  <action>
    Add a module-level upsert chunk constant of 1000 and batch the write in
    `upsert_snapshot_provenance` (billing_audit/snapshot_store.py:130-157). At
    live scale (~2x10^5 records x ~200 B) the current single body is roughly
    40 MB in one POST — the same root cause as WR-02, on the write side.

    Preserve every element of the existing contract: early return on an empty
    record list before any client acquisition, one `get_client()` call for the
    whole batch (never per chunk, never per row), the conflict target string
    passed verbatim so the primary key contract against schema.sql:365 is
    unchanged, `with_retry` with the existing op name, and the fail-safe
    `try/except` that logs and returns rather than raising. A failing chunk is
    logged and the loop continues — a partial durable write is strictly better
    than none, and the reader already treats a missing key as first-sight.

    Leave `insert_snapshot_drift_events` alone: it is bounded by
    `SNAPSHOT_DRIFT_MAX_ROWS` (40) and needs no chunking.
  </action>
  <verify>
    <automated>python -m pytest tests/test_snapshot_store.py -v</automated>
    <automated>python -m py_compile billing_audit/snapshot_store.py</automated>
    <automated>python -c "src=open('billing_audit/snapshot_store.py',encoding='utf-8').read(); assert 'on_conflict=\"sheet_id,row_id\"' in src, 'conflict target changed'; assert max(len(l) for l in src.splitlines())<=79; print('OK')"</automated>
  </verify>
  <done>
    A9 and the failing-chunk regression pass; U1-U4 still pass unmodified; the
    conflict target string is byte-identical to before. Committed alone:
    `perf(billing-audit): chunk provenance upsert`.
  </done>
</task>

<task type="auto">
  <name>T6: Living Ledger entry + STATE bookkeeping</name>
  <files>memory-bank/living-ledger.md, .planning/STATE.md</files>
  <read_first>
    CLAUDE.md "AUTONOMOUS CLOUD MEMORY INJECTION" (dated-entry format and the append-to-bottom rule)
    memory-bank/living-ledger.md (last ~40 lines, for entry shape)
    .planning/STATE.md:179-222 (Blockers/Concerns and the Quick Tasks Completed table)
  </read_first>
  <action>
    Append ONE dated `[YYYY-MM-DD HH:MM]` entry at the BOTTOM of
    memory-bank/living-ledger.md (never inline it into CLAUDE.md) covering, in
    the ledger's established narrative style:
    - The scale correction that drives everything: the shadow layer runs against
      `all_rows` (~199,717 on the 2026-08-12 live run, ledger line 5497), not the
      ~550 grouped rows the original sizing assumed — an off-by-~360x estimate.
      Record the durable RULE: any bulk Supabase read or write in this pipeline
      must be sized against `all_rows`, and must chunk.
    - The rate-sanity rule: the audit mirrors production's scope gate, so it
      reads the facade constant frozen at import rather than the environment at
      call time; a per-call environment read would let audit and production
      disagree mid-run.
    - The status-vocabulary rule: `snapshot_store` degrade markers stay internal;
      the four-value external vocabulary is load-bearing for
      pipeline/snapshot_drift.py:551.
    - The op-isolation rule: a fallback path must use a DISTINCT breaker op from
      the primary, or the primary's breaker is burned before the fallback runs.
    - The operator step and the D-01 note: the new RPC is manual-apply; Juan may
      fold WR-03's row-level-security enablement for the two snapshot tables into
      the same pass if he wants it — deliberately NOT written into schema.sql
      here.
    - The confirmation step still open from the research: grep a recent weekly
      Actions log for the provenance-read failure line
      (billing_audit/client.py:723-726) to confirm whether the two-`.in_` read was
      already failing in production — reframes this work from optimization to
      repair.

    Then update .planning/STATE.md: add a `260813-nhn` row to the Quick Tasks
    Completed table (description, date, the five commit SHAs, directory link),
    add "Operator: apply `lookup_snapshot_provenance_bulk` RPC to Supabase and
    reload the PostgREST schema cache" to Blockers/Concerns, and refresh
    `last_activity` / the Last activity line.
  </action>
  <verify>
    <automated>python -c "import re; s=open('memory-bank/living-ledger.md',encoding='utf-8').read(); m=re.findall(r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}\]', s); assert m, 'no dated entries found'; assert 'lookup_snapshot_provenance_bulk' in s[-6000:], 'new entry missing or not at bottom'; print('ledger OK,', len(m), 'entries')"</automated>
    <automated>python -c "s=open('.planning/STATE.md',encoding='utf-8').read(); assert '260813-nhn' in s; assert 'lookup_snapshot_provenance_bulk' in s; print('STATE OK')"</automated>
  </verify>
  <done>
    One new dated ledger entry at the bottom of memory-bank/living-ledger.md
    carrying the four durable rules plus the operator note; STATE.md has the
    quick-task row and the new operator blocker. Committed alone:
    `docs(billing-audit): log provenance RPC rules`.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| pipeline -> Supabase/PostgREST | `service_role` credentials cross here; request bodies carry Smartsheet row ids and WR values |
| SQL function -> `billing_audit` schema | New executable object in a production schema, applied manually by the operator |
| module logger -> Sentry / Actions logs | Degrade WARNINGs are emitted on a path that has access to row-level billing data |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-nhn-01 | Elevation of Privilege | `billing_audit.lookup_snapshot_provenance_bulk` | high | mitigate | INVOKER rights (no definer clause), matching both existing RPCs; `service_role` already holds SELECT on the table, so definer rights would add escalation surface for zero benefit. Gated by the T3 comment-filtered negative check. |
| T-nhn-02 | Tampering | function name resolution inside the SQL body | medium | accept | Body is fully schema-qualified and runs as INVOKER; neither existing RPC pins the resolution path. Deviating on one function is rejected (D-03); a file-wide hardening pass is the correct remedy and is noted for Juan. |
| T-nhn-03 | Information Disclosure | one-time degrade WARNING in `snapshot_store` | medium | mitigate | Message is aggregate-only — states that the function is not deployed and the run used the select path. No row ids, WR values, or record contents are logged. Latched to one emission per process, so it cannot become a high-volume PII channel. |
| T-nhn-04 | Denial of Service | provenance read/write payload size | high | mitigate | RPC chunking (5000 pairs/POST), fallback row-id chunking (200 ids/GET), upsert chunking (1000 records/POST). Removes the ~3.4 MB querystring and the ~40 MB body at live `all_rows` scale. |
| T-nhn-05 | Denial of Service | circuit-breaker exhaustion via shared op name | medium | mitigate | RPC uses a distinct breaker op from the fallback select (D-13, billing_audit/client.py:565-583), so a missing function cannot burn the fallback's breaker before it runs. Pinned by test A8. |
| T-nhn-06 | Repudiation / silent failure | four-value status vocabulary | high | mitigate | Degrade markers stay internal (D-04); pipeline/snapshot_drift.py:551 would report any new status as *available*, silently masking an outage. Pinned by test A3 and the T4 vocabulary gate. |
| T-nhn-07 | Tampering | audit vs production scope divergence | medium | mitigate | The audit reads the same import-frozen facade constant production used, so the two cannot disagree mid-run. Pinned by R11/R12/R13. |

**Supply chain:** no package-manager install is performed by this plan — no
`requirements.txt` / `package.json` change, no new dependency. The `T-{phase}-SC`
package-legitimacy threat and its blocking human checkpoint are therefore not
applicable; if any task discovers it needs a new package, stop and re-plan.
</threat_model>

<verification>
Run after every task, and again at the end of the plan:

1. `python -m py_compile audit_billing_changes.py billing_audit/snapshot_store.py`
2. `python -m pytest tests/test_rate_sanity_audit.py tests/test_snapshot_store.py tests/test_snapshot_drift_audit.py -v`
3. `python -m pytest tests/ -q` — full suite green (the pre-push gate,
   `.github/hooks/pre-push-tests.json`)
4. `python -m py_compile generate_weekly_pdfs.py` — facade still imports
5. Diff scope gate (source/test files only):
   `git diff --name-only <base>..HEAD -- . ":(exclude).planning"` must list at
   most: `audit_billing_changes.py`, `billing_audit/schema.sql`,
   `billing_audit/snapshot_store.py`, `tests/test_rate_sanity_audit.py`,
   `tests/test_snapshot_store.py`, `memory-bank/living-ledger.md`.
   `.planning/STATE.md` is planning bookkeeping and is excluded from this gate by
   design — it is the one file outside the source list that T6 may touch.
6. Report-only boundary (D-06): the diff touches no grouping, pricing, hashing,
   filename, attachment, or upload code path. `pipeline/` is not in the file list
   at all.

Ordering gate (the load-bearing one): T2 must be committed and green BEFORE T4
begins, and T4's first verify step proves zero deleted lines in
`tests/test_snapshot_store.py` — that is the evidence the oracle judged the
refactor rather than the refactor rewriting its oracle.
</verification>

<success_criteria>
- R11 fails on pre-fix code and passes after; R12/R13 green; R6-R10 hermetic and
  still green.
- `_rate_sanity_in_scope` reads `generate_weekly_pdfs.RATE_RECALC_WEEKLY_FALLBACK`
  exactly once and performs no per-call environment read.
- At least 22 characterization tests pass against an unmodified
  `billing_audit/snapshot_store.py` at T2, and the identical bodies pass again
  after T4 and T5 with zero deleted lines.
- `billing_audit/schema.sql` gains exactly one
  `lookup_snapshot_provenance_bulk` function plus its GRANT, with INVOKER rights,
  no path-resolution clause (D-03), and no row-level-security statements (D-01).
- `fetch_snapshot_provenance` returns only `success` / `no_row` /
  `fetch_failure` / `unavailable` (D-04) and never raises, both with the RPC
  deployed and with it absent (D-05).
- RPC path issues chunked POSTs and no `.in_` GET; the degrade path is chunked on
  the row-id axis and logs exactly one WARNING per process.
- `upsert_snapshot_provenance` issues `ceil(N / chunk)` calls, keeps its conflict
  target byte-identical, and never raises (D-02).
- `python -m pytest tests/ -q` fully green; `python -m py_compile` clean on the
  engine facade and both edited modules.
- Six commits, one per task, Conventional Commits with subjects at or under 50
  characters.
- One dated Living Ledger entry at the bottom of `memory-bank/living-ledger.md`;
  STATE.md carries the quick-task row and the new operator blocker.
</success_criteria>

<output>
Create `.planning/quick/260813-nhn-rpc-bulk-provenance-read-snapshot-store-/260813-nhn-SUMMARY.md`
when done. Record: the six commit SHAs, the T2 commit SHA used as the regression
anchor, any characterization case that went RED on unmodified code (pre-existing
defect — surfaced, not silently fixed), and the operator action still outstanding
(apply the RPC + reload the PostgREST schema cache).
</output>

