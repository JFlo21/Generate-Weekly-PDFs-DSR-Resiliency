---
phase: quick-260601-iqq
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/test_subcontractor_pricing.py
  - tests/test_subproject_e_hash_store.py
autonomous: true
requirements:
  - fix-pre-push-gate-16-failures
must_haves:
  truths:
    - "python -m pytest tests/ exits 0 with zero failures"
    - "TestPhase1GapClosureLedgerEntryPresent reads from memory-bank/living-ledger.md"
    - "TestWorkflowPinned::test_authoritative_flag_pinned_on asserts value '1'"
  artifacts:
    - path: "tests/test_subcontractor_pricing.py"
      provides: "Updated _read_ledger() pointing to memory-bank/living-ledger.md"
      contains: "memory-bank/living-ledger.md"
    - path: "tests/test_subproject_e_hash_store.py"
      provides: "Updated TestWorkflowPinned asserting AUTHORITATIVE='1'"
      contains: "test_authoritative_flag_pinned_on"
  key_links:
    - from: "tests/test_subcontractor_pricing.py"
      to: "memory-bank/living-ledger.md"
      via: "_read_ledger() pathlib.Path"
      pattern: "living-ledger\\.md"
    - from: "tests/test_subproject_e_hash_store.py"
      to: ".github/workflows/weekly-excel-generation.yml"
      via: "assertIn string match"
      pattern: "SUPABASE_HASH_STORE_AUTHORITATIVE: '1'"
---

<objective>
Fix 16 pre-existing test failures that block the pre-push gate. Both failures are caused
by stale test code — not regressions from Phase 04 work. The test suite must return to
zero failures.

Purpose: Unblock the pre-push gate so further development can land cleanly.
Output: Two patched test files; full pytest suite green.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Repoint TestPhase1GapClosureLedgerEntryPresent to the relocated Living Ledger</name>
  <files>tests/test_subcontractor_pricing.py</files>
  <action>
The Living Ledger was relocated from CLAUDE.md into memory-bank/living-ledger.md on
2026-05-28 (documented in CLAUDE.md). The test class still reads CLAUDE.md, so all 5
test methods in TestPhase1GapClosureLedgerEntryPresent fail because the asserted strings
no longer exist there.

Two targeted edits — nothing else changes:

1. In the class docstring (lines 4147-4157), change the two occurrences of "CLAUDE.md
   Living Ledger" references:
   - Line 4148: change "a CLAUDE.md Living Ledger entry" to
     "a memory-bank/living-ledger.md Living Ledger entry"

2. In _read_ledger() (lines 4159-4167), replace the return statement body:
   FROM:
     # CLAUDE.md is at the repo root, sibling to
     # generate_weekly_pdfs.py.
     import pathlib
     repo_root = pathlib.Path(
         generate_weekly_pdfs.__file__,
     ).parent
     return (repo_root / 'CLAUDE.md').read_text(encoding='utf-8')

   TO:
     # Living Ledger was relocated from CLAUDE.md to
     # memory-bank/living-ledger.md on 2026-05-28.
     import pathlib
     repo_root = pathlib.Path(
         generate_weekly_pdfs.__file__,
     ).parent
     return (repo_root / 'memory-bank' / 'living-ledger.md').read_text(encoding='utf-8')

Do NOT touch any assertion strings, test method names, or any other test logic.
  </action>
  <verify>
    <automated>python -m pytest tests/test_subcontractor_pricing.py::TestPhase1GapClosureLedgerEntryPresent -q 2>&amp;1 | tail -5</automated>
  </verify>
  <done>All 5 methods in TestPhase1GapClosureLedgerEntryPresent pass (5 passed, 0 failed).</done>
</task>

<task type="auto">
  <name>Task 2: Update stale E-flag assertion in TestWorkflowPinned</name>
  <files>tests/test_subproject_e_hash_store.py</files>
  <action>
Sub-project E was activated after the D-09/D-10/D-11 validation gate. The workflow
(.github/workflows/weekly-excel-generation.yml line 478) now has
SUPABASE_HASH_STORE_AUTHORITATIVE: '1', but the test still asserts '0'. The test is stale.
Do NOT modify the workflow YAML — only update the test to reflect the intentional '1'
state.

Three targeted edits in tests/test_subproject_e_hash_store.py:

1. Class docstring of TestWorkflowPinned (line 567-568):
   FROM: """Task 10: both E flags are pinned in the weekly workflow env block
       (WRITE on, AUTHORITATIVE off — dormant ship)."""
   TO:   """Task 10: both E flags are pinned in the weekly workflow env block
       (WRITE on, AUTHORITATIVE on — E is active)."""

2. Method name rename (line 578):
   FROM: def test_authoritative_flag_pinned_off(self):
   TO:   def test_authoritative_flag_pinned_on(self):

3. Assertion value (line 579):
   FROM: self.assertIn("SUPABASE_HASH_STORE_AUTHORITATIVE: '0'", self._wf())
   TO:   self.assertIn("SUPABASE_HASH_STORE_AUTHORITATIVE: '1'", self._wf())

Do NOT touch test_write_flag_pinned_on, test_documented_in_environment_reference,
TestProductionInvariants, or any other class/method in this file.
  </action>
  <verify>
    <automated>python -m pytest tests/test_subproject_e_hash_store.py::TestWorkflowPinned -q 2>&amp;1 | tail -5</automated>
  </verify>
  <done>All 3 methods in TestWorkflowPinned pass (3 passed, 0 failed). Method
test_authoritative_flag_pinned_on exists; test_authoritative_flag_pinned_off does not.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| test code → filesystem | Tests read repo files at relative paths; no external input |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-iqq-01 | Tampering | test file edits | accept | Changes are purely mechanical path/string corrections; no logic altered |
</threat_model>

<verification>
Full suite must be green after both tasks:

```
python -m pytest tests/ -q 2>&1 | tail -10
```

Targeted confirmation:

```
python -m pytest tests/test_subcontractor_pricing.py::TestPhase1GapClosureLedgerEntryPresent tests/test_subproject_e_hash_store.py::TestWorkflowPinned -q
```

Expected: 8 passed (5 + 3), 0 failed, 0 errors.
</verification>

<success_criteria>
- python -m pytest tests/ exits 0 with zero failures (was 16 failures on origin/master)
- TestPhase1GapClosureLedgerEntryPresent._read_ledger() reads memory-bank/living-ledger.md
- TestWorkflowPinned has method test_authoritative_flag_pinned_on asserting value '1'
- No other test files are modified
- .github/workflows/weekly-excel-generation.yml is unmodified
- portal-v2/ and Phase 04 code are unmodified
</success_criteria>

<output>
After completion, create `.planning/quick/260601-iqq-fix-stale-living-ledger-test-file-paths-/260601-iqq-SUMMARY.md`
</output>
