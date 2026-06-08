---
phase: quick-260608-gwm
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - requirements.txt
  - memory-bank/living-ledger.md
autonomous: true
requirements:
  - HOTFIX-CI-IMPORT-CRASH
user_setup: []

must_haves:
  truths:
    - "A fresh `pip install -r requirements.txt` resolves smartsheet-python-sdk to a 3.x release (never 4.0.0+)."
    - "`import smartsheet.exceptions as ss_exc` resolves under the resolved SDK version (the 3.x line ships smartsheet/exceptions.py)."
    - "generate_weekly_pdfs.py still compiles with no syntax change to its logic, ss_exc usage, or the retry re-export workaround."
    - "The pin rationale (excludes breaking 4.0.0 published 2026-06-08) is captured for future operators."
  artifacts:
    - path: "requirements.txt"
      provides: "Pinned smartsheet-python-sdk spec with a <4.0.0 upper bound"
      contains: "smartsheet-python-sdk>=3.1.0,<4.0.0"
    - path: "memory-bank/living-ledger.md"
      provides: "Dated operational rule: pin transport-critical deps with an upper bound"
      contains: "2026-06-08"
  key_links:
    - from: "requirements.txt"
      to: "generate_weekly_pdfs.py line 28 (import smartsheet.exceptions as ss_exc)"
      via: "CI fresh-install dependency resolution staying on the 3.x line"
      pattern: "smartsheet-python-sdk>=3\\.1\\.0,<4\\.0\\.0"
---

<objective>
Pin `smartsheet-python-sdk` to `>=3.1.0,<4.0.0` in requirements.txt so the
GitHub Actions weekly billing workflow stops crashing at import time on the
breaking SDK 4.0.0 release (published 2026-06-08).

Purpose: CI runs a fresh `pip install -r requirements.txt`. The unpinned
`>=3.1.0` spec pulled SDK 4.0.0, which removed `smartsheet.exceptions` (and
`Folders.get_folder`/`list_folders`, `Templates`, and changed pagination —
all surfaces this pipeline uses), crashing `generate_weekly_pdfs.py` at
line 28 before any billing work runs. The whole 3.x line ships the
`exceptions` module the retry blocks depend on.

Output: A one-line, fully reversible dependency pin plus a dated Living
Ledger rule. NO change to billing logic, `ss_exc` usage, or the SDK
retry-exception re-export workaround. A deliberate 4.0.0 migration is
explicitly OUT OF SCOPE (separate, larger effort).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md

<interfaces>
<!-- Exact current state of the file being changed and the consumer that crashes. -->
<!-- Executor must NOT touch generate_weekly_pdfs.py — these are shown for verification only. -->

requirements.txt (current lines 4-6 — the ONLY production change is line 6):
```
# Core Dependencies
# 3.1.0+ required for Folders.get_folder_children (replacement for deprecated get_folder)
smartsheet-python-sdk>=3.1.0
```

generate_weekly_pdfs.py (DO NOT MODIFY — these are the consumers that must keep resolving):
- line 28:   `import smartsheet.exceptions as ss_exc`
- lines 30-54: SDK retry-exception re-export workaround (sets ss_exc.* attrs onto the smartsheet module)
- lines ~8389, ~8397, ~8603, ~8620-8622, ~9835, ~9843: `except (ss_exc.RateLimitExceededError, ...)` retry blocks

tests/test_billing_audit_shadow.py line 64 also does `import smartsheet.exceptions as ss_exc`.

Living Ledger append format (memory-bank/living-ledger.md): append a NEW entry
to the BOTTOM, prepended with a `[YYYY-MM-DD HH:MM]` timestamp. Do NOT move
ledger content back into CLAUDE.md.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Pin smartsheet-python-sdk to exclude the breaking 4.0.0 release</name>
  <files>requirements.txt</files>
  <action>
    Change line 6 of requirements.txt from:
        smartsheet-python-sdk>=3.1.0
    to:
        smartsheet-python-sdk>=3.1.0,<4.0.0

    Keep the existing explanatory comment on line 5 coherent and extend it so
    a future operator understands BOTH bounds. Replace lines 5-6 with:

        # 3.1.0+ required for Folders.get_folder_children (replacement for deprecated get_folder)
        # Upper bound excludes the breaking 4.0.0 (2026-06-08) major release, which removed
        # smartsheet.exceptions + Folders.get_folder/list_folders + Templates and changed pagination.
        smartsheet-python-sdk>=3.1.0,<4.0.0

    Do NOT touch any other line in requirements.txt. Do NOT modify
    generate_weekly_pdfs.py, the ss_exc usage, or the retry re-export
    workaround. This is the only production change in this plan.
  </action>
  <verify>
    <automated>python -m py_compile generate_weekly_pdfs.py</automated>
    <automated>python -c "import re,sys; t=open('requirements.txt').read(); m=re.search(r'^smartsheet-python-sdk(.*)$', t, re.M); spec=m.group(1) if m else ''; ok=('<4.0.0' in spec and '>=3.1.0' in spec); print('SPEC:', spec.strip()); sys.exit(0 if ok else 1)"</automated>
  </verify>
  <done>
    requirements.txt line for smartsheet-python-sdk reads
    `smartsheet-python-sdk>=3.1.0,<4.0.0`; the get_folder_children rationale
    comment is preserved and the 4.0.0 exclusion rationale added;
    `python -m py_compile generate_weekly_pdfs.py` exits 0; the spec check
    exits 0 (both bounds present).
  </done>
</task>

<task type="auto">
  <name>Task 2: Confirm clean resolution (non-mutating) and record the pin rule in the Living Ledger</name>
  <files>memory-bank/living-ledger.md</files>
  <action>
    Step A — Verify the pin resolves to a 3.x version WITHOUT altering the
    local environment or upgrading any installed package. Prefer a dry-run:
        python -m pip install --dry-run -r requirements.txt
    `--dry-run` reports what WOULD be installed and does not modify the env.
    Confirm the report shows smartsheet-python-sdk at a 3.x version (newest
    allowed is 3.9.0) and NOT 4.0.0. If pip in this environment does not
    support `--dry-run`, fall back to a resolution-only check that does NOT
    install (e.g. `python -m pip index versions smartsheet-python-sdk` to
    confirm 3.x versions exist below the 4.0.0 ceiling) and note in the
    SUMMARY that the dry-run was unavailable. Under NO circumstance run a
    plain `pip install` that would upgrade the working environment.

    Step B — Append a NEW dated entry to the BOTTOM of
    memory-bank/living-ledger.md (do not move ledger content into CLAUDE.md),
    prepended with a `[YYYY-MM-DD HH:MM]` timestamp (use today's date,
    2026-06-08, and the current local time). The entry must capture the
    recurring operational rule, in narrative form:
      - WHAT: pinned smartsheet-python-sdk to `>=3.1.0,<4.0.0` in
        requirements.txt.
      - WHY: SDK 4.0.0 (published 2026-06-08) is a breaking major that removed
        `smartsheet.exceptions` (crashing generate_weekly_pdfs.py line 28 at
        import in CI's fresh `pip install`), and also removed
        Folders.get_folder/list_folders + Templates and changed pagination —
        broadly incompatible with this pipeline.
      - RULE: transport-critical / production-pipeline dependencies
        (smartsheet-python-sdk, and any SDK whose import this engine depends
        on) MUST carry an upper bound that excludes the next major, because CI
        fresh-installs and an unpinned `>=` silently pulls breaking majors on
        their publish day. A deliberate 4.0.0 migration is a separate planned
        effort, not a transitive auto-upgrade.
  </action>
  <verify>
    <automated>python -c "import sys,datetime; t=open('memory-bank/living-ledger.md',encoding='utf-8').read(); ok=('smartsheet-python-sdk>=3.1.0,<4.0.0' in t or '>=3.1.0,<4.0.0' in t) and '2026-06-08' in t; print('LEDGER_OK:', ok); sys.exit(0 if ok else 1)"</automated>
  </verify>
  <done>
    A `--dry-run` (or non-mutating fallback) confirms smartsheet-python-sdk
    resolves to a 3.x version (not 4.0.0) with no change to the local
    environment; memory-bank/living-ledger.md has a new bottom entry dated
    `[2026-06-08 HH:MM]` capturing the pin + the "upper-bound
    transport-critical deps" rule; the ledger check exits 0.
  </done>
</task>

</tasks>

<verification>
- `python -m py_compile generate_weekly_pdfs.py` exits 0 (no logic change).
- requirements.txt spec for smartsheet-python-sdk is `>=3.1.0,<4.0.0`.
- A non-mutating resolution check (`pip install --dry-run`) shows a 3.x
  version selected, never 4.0.0.
- `pytest tests/ -v` (full suite, per CLAUDE.md push gate) passes before
  pushing — confirms the test that imports `smartsheet.exceptions` still
  resolves and no regression was introduced. (Run from a normal shell; the
  pre-push Claude Code hook gates on this.)
- memory-bank/living-ledger.md has a new dated `[2026-06-08 HH:MM]` entry.
</verification>

<success_criteria>
- CI's fresh `pip install -r requirements.txt` can no longer resolve
  smartsheet-python-sdk 4.0.0; the import crash at line 28 is eliminated.
- Zero change to generate_weekly_pdfs.py logic, ss_exc usage, or the retry
  re-export workaround (fully reversible by deleting `,<4.0.0`).
- The pin rationale + recurring rule are recorded in the Living Ledger with a
  timestamp, satisfying the CLAUDE.md Autonomous Cloud Memory Injection rule.
</success_criteria>

<output>
After completion, create
`.planning/quick/260608-gwm-pin-smartsheet-python-sdk-4-0-0-to-fix-c/260608-gwm-SUMMARY.md`
</output>
