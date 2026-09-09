---
phase: 12-ownership-last-known-foreman-as-of-the-week
reviewed: 2026-09-04T06:59:17Z
depth: standard
scope: G-12-3 gap-closure delta (plans 12-07..12-10)
diff_base: 2c794a9
files_reviewed: 7
files_reviewed_list:
  - scripts/backfill_claim_time_attribution.py
  - tests/test_backfill_claim_time_attribution.py
  - billing_audit/own03_backfill_attribution.sql
  - billing_audit/schema.sql
  - tests/test_own03_backfill_sql_contract.py
  - tests/test_own04_documentation.py
  - website/docs/runbook/ownership-attribution.md
findings:
  critical: 1
  warning: 9
  info: 2
  total: 12
status: issues_found
---

# Phase 12: Code Review Report — G-12-3 Gap-Closure Delta

**Reviewed:** 2026-09-04T06:59:17Z
**Depth:** standard
**Scope:** This pass covers the **G-12-3 gap-closure delta only** (`git diff 2c794a9..HEAD`,
plans 12-07..12-10), using the full files for context. It **replaces** the 2026-09-03
full-phase REVIEW.md in the working tree; that earlier pass remains in git history.
**Files Reviewed:** 7
**Status:** issues_found

## Summary

The delta does three things: strips/refuses document extensions when source 3 recovers a
claimer from a `public.artifacts` filename (`_FILENAME_DOC_EXTENSION_RE`), adds a
`proposed_value` guard to the `--apply` payload builder, and adds a matching server-side
extension refusal to `billing_audit.backfill_attribution(jsonb)` STEP 4, pinned by a new
SQL contract test. All 110 tests + 53 subtests in the three related modules pass.

The fix is correct for the filename shape it was written against — but it was written
against the wrong shape. `pipeline/excel.py` emits **three** production filename shapes,
and the hash-suffix regex the parser depends on
(`_FILENAME_HASH_SUFFIX_RE = _[0-9a-fA-F]{6}\.xlsx$`) matches **none** of them: it encodes a
6-hex tail taken from a *test fixture*, while production embeds a **16-hex** `data_hash`
(`pipeline/change_detection.py:381`). For that shape the new extension strip removes `.xlsx`
and leaves the 16-char hash glued to the name, producing proposals like
`Unknown Foreman 0f1e2d3c4b5a6978` that both new guards — Python *and* SQL — classify as a
real person and write into `billing_audit.attribution_snapshot`, permanently (the RPC only
ever overwrites a sentinel). That is CR-01 and it is reproduced below.

Secondary concerns cluster in the new documentation tests, which couple the production
push/CI gate to `.planning/ROADMAP.md` and to the *newest* entry of
`memory-bank/living-ledger.md` — a file `CLAUDE.md` mandates appending to on every
architectural change. That test is guaranteed to fail on the next ledger entry.

Explicitly **not** re-reported per the review brief: the pre-existing
`_FILENAME_HASH_SUFFIX_RE` **over**-match on a six-hex-letter final name segment (separately
ticketed). CR-01 is the distinct **under**-match against production's 16-hex hash.

## Critical Issues

### CR-01: The 16-hex production hash tail defeats both new G-12-3 guards — corrupted claimer names can be permanently frozen

**File:** `scripts/backfill_claim_time_attribution.py:161`, `:992-1016`, `:1304-1307`;
`billing_audit/own03_backfill_attribution.sql:342`

**Issue:**
`_FILENAME_HASH_SUFFIX_RE = re.compile(r"_[0-9a-fA-F]{6}\.xlsx$")` — a **6**-hex tail. Its
own comment admits the provenance: *"see tests/test_sentinel_superseded_cleanup.py's fixture
filenames"* (`_aabbcc.xlsx`, `_ddeeff.xlsx`). Production does not emit that shape.
`pipeline/excel.py:409-414` emits three shapes:

```python
# 409  SUPABASE_HASH_STORE_AUTHORITATIVE -> clean, no timestamp/hash
output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}{variant_suffix}.xlsx"
# 412  data_hash present -> 16-hex hash tail
output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}_{timestamp}{variant_suffix}_{data_hash}.xlsx"
# 414  else -> timestamp, no hash
output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}_{timestamp}{variant_suffix}.xlsx"
```

`data_hash` is `hexdigest()[:16]` (`pipeline/change_detection.py:381, 479, 538, 545`) and
`pipeline/excel.py:411` says so in a comment: *"Use full 16-character hash"*. With 16 hex
chars there is no `_` six characters before `.xlsx`, so `_FILENAME_HASH_SUFFIX_RE` never
matches, execution falls into the **new** `else` branch, and only `.xlsx` is stripped.

Reproduced against the shipped code (read-only, no `--apply`):

```
$ python -c "from scripts.backfill_claim_time_attribution import _extract_claimer_from_filename as f, _desanitize; ..."
'Unknown_Foreman_0f1e2d3c4b5a6978' | sentinel= False | proposed= 'Unknown Foreman 0f1e2d3c4b5a6978'
'Avery_Example_0f1e2d3c4b5a6978'   | sentinel= False | proposed= 'Avery Example 0f1e2d3c4b5a6978'
'Unknown_Foreman'                  | sentinel= True  | proposed= 'Unknown Foreman'          # 6-hex fixture shape
'Unknown_Foreman'                  | sentinel= True  | proposed= 'Unknown Foreman'          # shape 409
'Unknown_Foreman'                  | sentinel= True  | proposed= 'Unknown Foreman'          # shape 414
```

The full guard chain fails open on that value:

1. `_extract_claimer_from_filename`'s residual-extension check (`:1014`) — no match, the
   tail is a hash, not an extension. The docstring's promise (*"such a candidate is not a
   person and must never reach `_resolve_single_name`"*) is not kept.
2. `_resolve_single_name` -> `is_sentinel_claimer("Unknown_Foreman_0f1e…")` -> normalizes to
   `"unknown foreman 0f1e2d3c4b5a6978"`, **not** in `_SENTINEL_CLAIMERS` -> proposed.
3. `_build_apply_payload`'s new G-12-3 guard (`:1304-1307`) — `is_sentinel_claimer` False,
   `_FILENAME_DOC_EXTENSION_RE.search` False -> **enters the payload**.
4. SQL STEP 4 (`own03_backfill_attribution.sql:327-346`) — `is_sentinel_value` False,
   `v_row.value ~* '\.(xlsx|xlsm|xls|csv|pdf|json)$'` False -> **UPDATE runs**.

The written value is then a *real* (non-sentinel) frozen name, so the RPC's
`is_sentinel_value(s.frozen_primary)` WHERE guard prevents any later backfill from
correcting it. Recovery requires the dated backup table. This is exactly the irreversible
billing-attribution corruption the two new guards exist to prevent.

**Exposure (stated honestly):** `.github/workflows/weekly-excel-generation.yml:491` has
`SUPABASE_HASH_STORE_AUTHORITATIVE: '1'` (since 1a1d2b8, 2026-05-28) and
`scripts/publish_artifacts_to_supabase.py` was added 2026-05-29, so `public.artifacts` rows
written since then use shape 409 and are safe today. But the workflow comment immediately
above that line documents a supported roll-back (*"token-named filenames resume"*), the flag
has already been flipped back and forth twice (42874f4, 2b890af), and any manually published
older file lands shape 412. A guard that is correct only while an env flag stays flipped is
not a guard on an irreversible production write.

**Fix:** Make the hash strip match production, and make the "not a person" check tail-shape
agnostic rather than extension-only.

```python
# Derive from pipeline/change_detection.py's hexdigest()[:16] and
# pipeline/excel.py:409-414 -- NOT from a test fixture. Accept the
# legacy 6-hex fixture width too so existing tests keep passing.
_FILENAME_HASH_SUFFIX_RE = re.compile(
    r"_[0-9a-fA-F]{6}(?:[0-9a-fA-F]{10})?\.xlsx$"
)

def _extract_claimer_from_filename(filename: str, token: str) -> str | None:
    idx = filename.find(token)
    if idx == -1:
        return None
    remainder = filename[idx + len(token):]
    match = _FILENAME_HASH_SUFFIX_RE.search(remainder)
    if match:
        name_part = remainder[: match.start()]
    else:
        name_part = _FILENAME_DOC_EXTENSION_RE.sub("", remainder, count=1)
    name_part = name_part.strip("_")
    if not name_part:
        return None
    if _FILENAME_DOC_EXTENSION_RE.search(name_part):
        return None
    # G-12-3 hardening: a trailing >=6-char pure-hex run is a content
    # hash, never a surname -- refuse rather than desanitize it into a name.
    if re.search(r"_[0-9a-fA-F]{6,}$", name_part):
        return None
    return name_part
```

and mirror the residual-hash refusal in `_build_apply_payload` (`:1304`) plus the SQL
validation loop (`own03_backfill_attribution.sql`, after the extension guard):

```sql
IF v_row.value ~ '(^|[[:space:]_])[0-9a-fA-F]{6,}$' THEN
    RAISE EXCEPTION
        'backfill_attribution: proposed value for role=% (wr=% week_ending=% smartsheet_row_id=%) ends in a content-hash token, refusing to write it',
        v_row.role, v_row.wr, v_row.week_ending, v_row.smartsheet_row_id;
END IF;
```

Extend `tests/test_own03_backfill_sql_contract.py` to pin the new SQL/Python pair the same
bidirectional way `test_sql_extension_list_matches_python_constant` pins the extension list.

## Warnings

### WR-01: The OWN-04 doc test asserts against the *newest* ledger entry — it breaks on the next mandated ledger append

**File:** `tests/test_own04_documentation.py:94-100`, `:180-186`
**Issue:** `_newest_ledger_entry()` returns only the text after the **last** `## [` heading
in `memory-bank/living-ledger.md`, and `test_records_phase_12_gap_closure_decisions` asserts
`D-12-C` / `D-12-D` appear there. The newest entry today is
`## [2026-09-04 10:05] Gap G-12-3 root cause and owner scope decisions D-12-C / D-12-D`
(line 9289). `CLAUDE.md` mandates appending every new architectural-standard entry *to the
BOTTOM* of that ledger — so the very next entry on **any** topic makes this assertion false.
That failure blocks `git push` (`.github/hooks/pre-push-tests.json`) and CI
(`.github/workflows/ci-checks.yml` runs `pytest tests`). This is a deterministic, imminent
break, not a hypothetical.
**Fix:** Search the whole ledger, or scope to the entry that owns the decision:

```python
def _gap_closure_ledger_entry() -> str:
    """The ledger entry that RECORDS D-12-C/D-12-D, wherever it sits."""
    text = _LEDGER.read_text(encoding="utf-8")
    starts = [m.start() for m in _LEDGER_ENTRY_HEADING.finditer(text)]
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        entry = text[start:end]
        if "D-12-C" in entry and "D-12-D" in entry:
            return entry
    raise AssertionError("no ledger entry records D-12-C/D-12-D")
```

### WR-02: The same doc test couples the push/CI gate to `.planning/ROADMAP.md`

**File:** `tests/test_own04_documentation.py:85-92`, `:120-127`, `:165-176`, `:190-215`
**Issue:** `_phase_12_section()` does `assert start, "### Phase 12 heading not found in
ROADMAP.md"` and every D-12-C/D-12-D/success-criterion-3 assertion reads from it.
`.planning/` is GSD session-managed working state; `/gsd:complete-milestone` and
`/gsd:cleanup` archive completed phase sections out of `ROADMAP.md`. When Phase 12 is
archived, `pytest tests/` fails for a reason unrelated to any source change — on a repo
where a green suite is the push gate. Planning artifacts are not a stable test contract.
**Fix:** Assert the decision record where it durably lives (the runbook page and the ledger),
and make the ROADMAP assertions skip rather than fail when the section is absent:

```python
def _phase_12_section() -> str:
    start = _PHASE_12_HEADING.search(_roadmap_text())
    if not start:
        pytest.skip("Phase 12 archived out of ROADMAP.md — durable record is the runbook page")
    ...
```

### WR-03: G-12-3 skips are misreported to the operator as `skipped_client_side_real_name`

**File:** `scripts/backfill_claim_time_attribution.py:1360-1372`
**Issue:** `_apply_backfill` derives the tally by subtraction:

```python
all_proposed = sum(1 for r in report_rows if r.get("status") == "proposed")
payload = _build_apply_payload(report_rows, run_id, include_blank_roles=...)
skipped_client_side_real_name = all_proposed - len(payload)
```

Rows the **new** `proposed_value` guard drops (`:1304-1307`) are now silently folded into
that counter. The label states the row was skipped because its *current* value is a real
name; the operator sees `skipped_client_side_real_name: N` in the apply report summary and
the run log for rows actually dropped because the *proposed* value was garbage. Under CR-01
conditions this is precisely the number an operator would need to see broken out.
**Fix:** Return the count from the builder instead of inferring it.

```python
def _build_apply_payload(...) -> "tuple[list[dict[str, Any]], int]":
    ...
    return payload, skipped_proposed_value_guard

# in _apply_backfill:
payload, skipped_proposed_value_guard = _build_apply_payload(...)
tallies["skipped_client_side_real_name"] = all_proposed - len(payload) - skipped_proposed_value_guard
tallies["skipped_proposed_value_guard"] = skipped_proposed_value_guard
```

(Note `tests/test_own03_backfill_sql_contract.py::test_build_apply_payload_keys_match_sql_column_list`
and three tests in `ApplyPathTests` call `_build_apply_payload` directly and must be updated
with the return-shape change.)

### WR-04: A guard-dropped row still reads as `status: proposed` with a blank `rpc_result`, indistinguishable from a chunk failure

**File:** `scripts/backfill_claim_time_attribution.py:1304-1307` + `main()` `row["rpc_result"] = outcome_by_key.get(key, "")`
**Issue:** The new guard filters at payload-build time only. The rewritten apply report still
carries the row as `status: proposed` with the offending `proposed_value`, and its
`rpc_result` is `""` — the same value a row gets when its whole chunk failed
(`local_exceptions`) or when the RPC response was rejected as partial. Three materially
different outcomes collapse to one blank cell in the operator-facing CSV.
**Fix:** Stamp the reason on the row the guard rejected, e.g. set
`row["rpc_result"] = "skipped_client_guard"` (or add a `skip_reason` column to
`_REPORT_COLUMNS + ("rpc_result",)`) so the report distinguishes "never sent" from "sent and
lost".

### WR-05: The SQL extension guard is weaker than its Python twin on padded values

**File:** `billing_audit/own03_backfill_attribution.sql:342`
**Issue:** `billing_audit/schema.sql` (delta) advertises the SQL guard as holding
*"independent of the Python caller"*, but the two are not equivalent:
- Python `re` treats `$` as matching before a trailing newline, so
  `"Unknown Foreman.xlsx\n"` is refused client-side but **accepted** by
  `v_row.value ~* '…$'` (Postgres POSIX `$` without the `n` flag matches only true
  end-of-string).
- `"Unknown Foreman.xlsx "` (trailing space) is accepted by **both** guards, then
  `is_sentinel_value`'s `btrim` reduces it to `unknown foreman.xlsx`, which is not in the
  vocabulary — so it is written.

STEP 3 already solved this exact class of problem for the sentinel predicate with an explicit
full-whitespace `btrim`; the new guard does not reuse it.
**Fix:**

```sql
IF pg_catalog.btrim(v_row.value, E' \t\r\n\f\v') ~* '\.(xlsx|xlsm|xls|csv|pdf|json)$' THEN
```

and mirror it on the Python side with `str(proposed).strip()` at
`scripts/backfill_claim_time_attribution.py:1304`.

### WR-06: The SQL/Python parity test pins only the extension token set, not the guard semantics

**File:** `tests/test_own03_backfill_sql_contract.py:369-402`
**Issue:** `test_sql_extension_list_matches_python_constant` extracts just the alternation
group from each pattern and compares the two token sets. It never asserts that the SQL
operator is case-insensitive (`~*` vs `~`), that either side is `$`-anchored, or that both
require the leading `\.`. Changing the SQL to `v_row.value ~ 'xlsx'` — no anchor, no
case-insensitivity, matching mid-string — keeps this test green while silently changing what
the server refuses. Since this file is the *only* automated check on an owner-applied SQL
file that nothing in the repo can execute, its assertions carry more weight than usual.
**Fix:** Assert the full normalized pattern and the operator:

```python
self.assertEqual(sql_pattern, r"\.(xlsx|xlsm|xls|csv|pdf|json)$")
self.assertIn("v_row.value ~*", self.body)          # case-insensitive operator, not ~
self.assertTrue(_FILENAME_DOC_EXTENSION_RE.flags & re.IGNORECASE)
self.assertTrue(_FILENAME_DOC_EXTENSION_RE.pattern.endswith("$"))
```

### WR-07: The new comment names the wrong mechanism for hash-less filenames, hiding the CR-01 exposure

**File:** `scripts/backfill_claim_time_attribution.py:163-165`
**Issue:** *"Live filenames written by `scripts/publish_artifacts_to_supabase.py::_parse_stable`
carry no hash tail."* `_parse_stable` (`publish_artifacts_to_supabase.py:148-164`) is a
read-only parser — it returns `{'work_request', 'week_ending'}` and writes nothing; the
`filename` column is stored verbatim from `local_path.name`
(`publish_artifacts_to_supabase.py:328`). The actual reason live names are hash-less is
`SUPABASE_HASH_STORE_AUTHORITATIVE: '1'` selecting `pipeline/excel.py:409`. Naming a parser
instead of an env-gated, reversible generation mode is what made the 16-hex shape look
impossible and let CR-01 through.
**Fix:** Rewrite the comment to cite `pipeline/excel.py:409-414` and
`.github/workflows/weekly-excel-generation.yml:491`, and state explicitly that shape 412
(16-hex hash) returns whenever that flag is rolled back.

### WR-08: The "both production shapes" parameterization covers neither hash-bearing production shape

**File:** `tests/test_backfill_claim_time_attribution.py:190-227`
**Issue:** `_artifact_filename_shapes` / `_artifact_filename_shape_pairs` claim to exercise
*"the two production filename shapes source 3 must handle identically"*, but
`hash_tail: str = "aabbcc"` is a **6**-hex fixture value, and the `"hashless"` shape omits
the timestamp segment. Neither corresponds to `pipeline/excel.py:412` (timestamp + 16-hex
hash) — the shape CR-01 breaks on. `test_extract_claimer_preserves_hash_suffix_behavior`
(`:1310`) likewise pins only `_aabbcc.xlsx`. The suite therefore certifies a shape matrix
that does not include the failing production case.
**Fix:** Add the real third shape and a red test for CR-01:

```python
def test_extract_claimer_strips_production_16_hex_hash(self):
    from scripts import backfill_claim_time_attribution as bf
    self.assertEqual(
        bf._extract_claimer_from_filename(
            "WR_1_WeekEnding_082425_120000_User_Avery_Example_0f1e2d3c4b5a6978.xlsx",
            "_User_",
        ),
        "Avery_Example",
    )

def test_extract_claimer_rejects_sentinel_behind_16_hex_hash(self):
    from scripts import backfill_claim_time_attribution as bf
    from billing_audit.writer import is_sentinel_claimer
    seg = bf._extract_claimer_from_filename(
        "WR_1_WeekEnding_082425_120000_User_Unknown_Foreman_0f1e2d3c4b5a6978.xlsx",
        "_User_",
    )
    self.assertTrue(seg is None or is_sentinel_claimer(seg))
```

Both fail on the current code.

### WR-09: The runbook's copy-pasteable apply command still names the WR the same page says has zero rows

**File:** `website/docs/runbook/ownership-attribution.md:240`, `:269` (vs `:213-216`)
**Issue:** The new "OWN-03 remediation scope" section records D-12-D and states *"the
originally named WR 19073866 has zero rows in every Supabase store the ladder reads"* — yet
the "Running the backfill" dry-run **and** `--apply` command blocks further down the same page
still read `--wr 19073866 --weeks 082425,083125,091425,092125`. An operator following the
runbook top-to-bottom runs the production write against a WR the page itself declares
unresolvable. `tests/test_own04_documentation.py::test_success_criterion_3_drops_the_unprovable_sample`
only forbids that WR inside ROADMAP success criterion 3, so nothing catches this.
**Fix:** Update both command blocks (and `scripts/backfill_claim_time_attribution.py:37`) to
WR `89829163`, and extend the doc test to forbid `19073866` anywhere on the page except in the
sentence that explains why it was dropped.

## Info

### IN-01: Front-matter assertion is exact-line membership on a 6-line window

**File:** `tests/test_own04_documentation.py:141-146`
**Issue:** `assert "id: ownership-attribution" in head` where `head` is
`...splitlines()[:6]` — a list membership test, so it demands an exactly-equal line. A
trailing space, or any front-matter key added ahead of `id:` that pushes it past line 6,
fails the test for a reason unrelated to its intent.
**Fix:** `assert any(line.strip() == "id: ownership-attribution" for line in head)`, or parse
the front-matter block between the two `---` fences.

### IN-02: The G-12-3 warning misattributes a malformed report row

**File:** `scripts/backfill_claim_time_attribution.py:1303-1307`, `:1320-1326`
**Issue:** A `status: proposed` row whose `proposed_value` is `None`/blank hits
`is_sentinel_claimer(None) -> True` and is counted into `skipped_proposed_value_guard`; the
WARNING then reports it as *"a sentinel or carried a document extension"*. A structurally
malformed report row and a G-12-3 hit are genuinely different problems and should not share
one counter.
**Fix:** Branch the blank case out with its own counter/message before the sentinel test.

---

_Reviewed: 2026-09-04T06:59:17Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
_Scope: G-12-3 gap-closure delta, diff_base 2c794a9_
_Evidence: `python -m pytest tests/test_backfill_claim_time_attribution.py tests/test_own03_backfill_sql_contract.py tests/test_own04_documentation.py -q` -> 110 passed, 53 subtests passed_
_No source files were modified by this review._
