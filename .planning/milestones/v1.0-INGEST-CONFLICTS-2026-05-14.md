## Conflict Detection Report

Ingest mode: `new`. 48 docs classified (46 DOC, 2 SPEC, 0 ADR,
0 PRD, 0 UNKNOWN). No `locked: true` entries in the
classification set. No per-doc `precedence` overrides. Default
precedence `ADR > SPEC > PRD > DOC` applied.

### BLOCKERS (0)

None. The ingest set contains:

- Zero canonical ADRs and therefore zero LOCKED-vs-LOCKED ADR
  contradictions to resolve.
- Zero `UNKNOWN`-with-low-confidence classifications.
- Zero unparseable / missing classification entries.
- No existing `.planning/` context to contradict (mode `new`).
- No cycle was found that involves an ADR or a SPEC making
  contradictory technical claims; all detected cycles are
  bidirectional DOC↔DOC peer citations (see INFO section).

Status: nothing gates routing.

### WARNINGS (1)

[WARNING] Embedded ADR-equivalent rules in `CLAUDE.md` Living
Ledger are extracted by *this* synthesizer pass without ADR
file frontmatter or per-entry status fields
  Found: source `CLAUDE.md` "Living Ledger" section contains
    ~30 dated entries each ending in an explicit "New rule:"
    clause that binds future behavior of
    `generate_weekly_pdfs.py`. The classifier (per its
    `notes` field) flagged that these function as
    ADR-equivalent locked rules but the document itself was
    classified as `DOC` (not `ADR`) because it lacks the
    per-entry Context/Decision/Consequences template and
    canonical filename pattern.
  Impact: Downstream consumers (the Subcontractor Rate Logic
    phase, in particular) MUST treat every entry in
    `.planning/intel/decisions.md` under the "ADR-equivalent
    rules from `CLAUDE.md` Living Ledger" heading as
    operative-locked. The synthesizer has extracted them as
    such, with dates preserved. However, because the source
    is not itself a canonical ADR set, future automation
    cannot rely on the `locked: true` classification field
    to enforce them — the enforcement currently lives in the
    `decisions.md` heading and in this WARNING entry. If the
    project later decides to split the Living Ledger into
    per-entry ADR files under `memory-bank/adr/` or similar,
    re-classification would close this WARNING.
  source: `CLAUDE.md` (lines under "Living Ledger
    (Auto-Updated Context)"),
    `.planning/intel/classifications/CLAUDE-c1a0de00.json`
    field `notes`
  → User action requested: confirm whether the Living
    Ledger should be treated as ADR-equivalent for the
    upcoming Subcontractor Rate Logic phase (default
    assumed: yes; the synthesizer has proceeded on that
    assumption). If you want a stricter contract, split the
    Living Ledger into per-entry ADR files before the next
    re-run.

### INFO (8)

[INFO] No ADR or PRD source in ingest set; precedence ordering
unused in this pass
  Note: the ingest set is 100% DOC + SPEC, so the default
    `ADR > SPEC > PRD > DOC` precedence chain was inert. The
    only horizontal precedence interaction is "SPEC content
    is preferred over DOC content where they describe the
    same scope" — surfaced in the two SPEC files
    (`subcontractor-pricing-folder-discovery.instructions.md`,
    `railway-to-render-transition-plan.md`) and used to
    promote their content into `.planning/intel/constraints.md`
    and `.planning/intel/requirements.md` rather than only
    `.planning/intel/context.md`.
  source: 48 classification files in
    `.planning/intel/classifications/`

[INFO] Cycle in cross-ref graph — DOC↔DOC peer citation
  Found: `memory-bank/activeContext.md` cross-refs
    `docs/update-log-v2-dashboard-fixes.md`, which in turn
    cross-refs back to `memory-bank/activeContext.md`.
  Impact: This is a legitimate bidirectional citation
    between two operator-facing DOC sources describing the
    same in-flight work (the dashboard stabilization). They
    do not contradict each other; they cite each other for
    cross-reference. No synthesis loop is produced because
    each was extracted separately into
    `.planning/intel/context.md` under "Active in-flight work"
    and "Critical pitfalls".
  source: `memory-bank/activeContext.md`,
    `docs/update-log-v2-dashboard-fixes.md`

[INFO] Cycle in cross-ref graph — README + Azure setup peer
citation
  Found: `README.md` cross-refs `AZURE_PIPELINE_SETUP.md`,
    which cross-refs back to `README.md`.
  Impact: Documentation-only mutual reference. Both
    docs are extracted into `.planning/intel/context.md`
    under "Project overview / mission" and "Azure DevOps
    mirror".
  source: `README.md`, `AZURE_PIPELINE_SETUP.md`

[INFO] Cycle in cross-ref graph — Railway/Render plan + memory
bank + dashboard fixes
  Found: `memory-bank/activeContext.md` →
    `docs/update-log-v2-dashboard-fixes.md` →
    `docs/railway-to-render-transition-plan.md` →
    `memory-bank/activeContext.md`.
  Impact: Three-node cycle describing the same in-flight
    work (Railway → Render migration). The transition plan
    is the SPEC; the other two are status logs that cite it.
    No contradiction.
  source: same three files above

[INFO] Cycle in cross-ref graph — CLAUDE.md ↔ environment
reference
  Found: `CLAUDE.md` cross-refs
    `website/docs/reference/environment.md`, which cross-refs
    back to `CLAUDE.md`.
  Impact: The two docs cover overlapping env-var inventory
    for two audiences (CLAUDE for AI-agent guidance, the
    Docusaurus page for operators). Verified they agree on
    the LEGACY status of `RATE_CUTOFF_DATE`/`NEW_RATES_CSV`/
    `OLD_RATES_CSV` (2026-04-24 14:30 ledger entry is
    reflected in the environment reference's LEGACY
    admonition). No conflict.
  source: `CLAUDE.md` (Configuration section),
    `website/docs/reference/environment.md`

[INFO] Auto-resolved: SPEC reinforces a CLAUDE.md decision (no
override needed)
  Note: `.github/instructions/subcontractor-pricing-folder-discovery.instructions.md`
    states "subcontractor (Arrowhead) sheets always keep
    their SmartSheet pricing as-is — no rate recalculation
    is performed, regardless of whether `RATE_CUTOFF_DATE`
    is set". `CLAUDE.md` 2026-04-24 14:30 ledger entry
    retires CSV-side rate recalc entirely at the workflow
    layer. The two are aligned: SPEC scopes the carve-out
    for subcontractor sheets even if `RATE_CUTOFF_DATE`
    were re-introduced; the ledger entry pins
    `RATE_CUTOFF_DATE=''` in the weekly workflow. No
    override applied; both decisions are preserved in
    `decisions.md`.
  source: `.github/instructions/subcontractor-pricing-folder-discovery.instructions.md`,
    `CLAUDE.md` (Living Ledger 2026-04-24 14:30)

[INFO] Internal supersession within `CLAUDE.md` Living Ledger
recorded
  Note: ledger entry `[2026-04-23 21:00]` round-7 introduced
    a source-side WR collision quarantine key tuple
    `(sanitized_wr, week, variant)`. A later round-9 entry
    on the same date broadened that key to "the sanitized
    WR alone" because cross-week and cross-variant
    collisions still reached `target_map`. The synthesizer
    has recorded both in `decisions.md` with the explicit
    "supersedes" relationship on the round-9 entry. Only
    round-9 is the operative current rule; round-7 is
    preserved as historical context.
  source: `CLAUDE.md` (Living Ledger, 2026-04-23 21:00
    round-7 and round-9)

[INFO] One in-flight unresolved engineering follow-up surfaced
in the Railway/Render plan
  Note: `docs/railway-to-render-transition-plan.md` Phase 0
    step 3 says: "File a pre-migration ADR in
    `memory-bank/` noting the decision: Render Starter,
    in-memory LRU search, v1 download = original `.xlsx`."
    No such ADR currently exists in
    `memory-bank/`. The transition plan itself is acting as
    the de-facto SPEC. The synthesizer treats this as a
    deferred deliverable (deferred to the roadmapper to
    schedule), not a blocker.
  source: `docs/railway-to-render-transition-plan.md` (§5
    Phase 0 step 3); current `memory-bank/` file inventory
    (no `adr/` subdirectory or pre-migration ADR present)
