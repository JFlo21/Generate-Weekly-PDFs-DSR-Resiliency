-- ============================================================
-- Canonical DDL for the ``pipeline_memory`` Supabase schema.
--
-- This file is documentation-grade SQL. It is NOT auto-applied by the
-- Python pipeline -- apply it manually in the Supabase SQL Editor
-- (Project Settings -> SQL Editor) the first time you wire the
-- pipeline_memory integration to a new project, and again whenever
-- this file is updated to add a column (every statement below is
-- reapply-safe: CREATE ... IF NOT EXISTS, CREATE OR REPLACE FUNCTION,
-- and DROP POLICY IF EXISTS before every CREATE POLICY).
--
-- PREREQUISITE (do this BEFORE the first shadow write -- D-02, and the
-- exact PGRST106 footgun that bit the 2026-04-24 billing_audit
-- rollout, CLAUDE.md Living Ledger entry [2026-04-24 10:50]):
--   Supabase -> Project Settings -> API -> Data API Settings ->
--     "Exposed schemas"
--   add ``pipeline_memory`` to the list, save, then click
--   "Reload schema cache" (or run ``NOTIFY pgrst, 'reload schema';``).
-- Without this step PostgREST returns HTTP 406 / PGRST106 on every
-- call. The Python client treats PGRST106/301/302 as fail-open
-- (WARNING + counter + Sentry breadcrumb, never an exception on the
-- Excel path) -- see ``pipeline_memory/client.py`` -- but the schema
-- stays silently unwritten until this step is done.
--
-- SCHEMA PLACEMENT (D-01, locked in
-- .planning/phases/10-run-memory-foundation-shadow-writes/10-CONTEXT.md):
-- this is a NEW, INDEPENDENT schema from ``billing_audit`` -- separate
-- Python client, separate kill switch (pipeline_memory/client.py never
-- imports billing_audit.client; see that module's docstring). Keeps
-- the newest, least-proven, highest-volume write path (~208k upserts
-- every 2h) out of the schema holding CLAUDE.md-protected billing data.
--
-- The Python writer/reader contract is enforced in
-- ``pipeline_memory/writer.py``. If you add or rename a column here,
-- you MUST update that module in the SAME PR (D-03) -- the deployed
-- schema and the Python code share an implicit contract that this
-- file documents. See the closing comment block for the full list.
--
-- SCOPE (Phase 10 / MEM-01..03 only -- see .planning/phases/
-- 10-run-memory-foundation-shadow-writes/COVERAGE.md): this file ships
-- the five MEM-01 tables (sheet_registry, row_state, row_event,
-- group_state, run_ledger) and the upsert_rows_bulk write RPC. It does
-- NOT ship ``wr_week_ownership`` or ``audit_finding`` /
-- ``audit_finding_event`` from the design-spec draft -- those are
-- scoped to Phases 12/13 by CONTEXT.md <domain>. It does NOT modify
-- ``billing_audit/schema.sql`` or ``billing_audit.group_content_hash``
-- (D-03) -- retiring the existing hash store is explicitly deferred to
-- Phase 11+ after parity.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS pipeline_memory;

-- ── sheet_registry ───────────────────────────────────────────
-- One row per source sheet; the durable analog of
-- generated_docs/discovery_cache.json. Shadow mode: written by a
-- later plan's discovery-phase hook, not yet read back by anything
-- (Phase 10 keeps discover_source_sheets() as the live path).
--
-- kind CHECK deliberately omits a 'vac_crew' value present in the
-- original design-spec draft (docs/superpowers/specs/
-- 2026-08-24-supabase-run-memory-design.md section 3). VAC-crew rows
-- are a ROW-LEVEL, column-presence-driven flag on primary/
-- subcontractor sheets (``sheet_has_vac_crew_columns`` in
-- pipeline/discovery.py), not a fourth discovered sheet-id bucket --
-- see 10-RESEARCH.md Assumption A4. A sheet is never itself "kind
-- vac_crew"; that value could never be written and would be dead.
-- VAC-crew capability stays discoverable from ``column_mapping``.
CREATE TABLE IF NOT EXISTS pipeline_memory.sheet_registry (
    sheet_id            BIGINT      PRIMARY KEY,
    name                TEXT        NOT NULL,
    kind                TEXT        NOT NULL
        CHECK (kind IN ('primary', 'subcontractor', 'original_contract')),
    folder_id           BIGINT,
    column_mapping      JSONB       NOT NULL,
    last_sheet_version  BIGINT,
    last_read_at        TIMESTAMPTZ,
    last_full_read_at   TIMESTAMPTZ,
    active              BOOLEAN     NOT NULL DEFAULT TRUE,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── row_state ────────────────────────────────────────────────
-- CURRENT state, one row per (sheet_id, row_id); upsert, never
-- duplicated. ``foreman_observed`` / ``helper_observed`` /
-- ``vac_crew_observed`` MUST be the RAW value observed on the row at
-- write time (e.g. the raw ``Foreman`` column), never a resolved /
-- sentinel-substituted value like ``__effective_user`` (which falls
-- back to the literal string 'Unknown Foreman' when blank) -- see
-- 10-RESEARCH.md Pitfall 2 (CRITICAL) and
-- .planning/debug/unknown-foreman-helper-shadow-2026-08-24.md for the
-- historical defect this column set exists to avoid repeating.
--
-- content_hash is scoped to business-content columns only and
-- deliberately EXCLUDES row_modified_at / first_seen_run /
-- last_seen_run / last_changed_run -- including any of those would
-- make the hash change on every run regardless of billing content,
-- producing a row_event on every re-read (10-RESEARCH.md Pitfall 3).
-- The exact field tuple + fixed enumeration order is the Python
-- writer's contract (pipeline_memory/writer.py, wired in plan 10-02).
CREATE TABLE IF NOT EXISTS pipeline_memory.row_state (
    sheet_id            BIGINT      NOT NULL,
    row_id              BIGINT      NOT NULL,
    wr                  TEXT        NOT NULL,
    week_ending         DATE,
    snapshot_date       DATE,
    cu                  TEXT,
    pole                TEXT,
    work_type           TEXT,
    quantity             NUMERIC,
    units_total_price   NUMERIC,
    units_completed     BOOLEAN     NOT NULL DEFAULT FALSE,
    foreman_observed    TEXT,
    helper_observed     TEXT,
    helper_completed    BOOLEAN,
    helper_dept         TEXT,
    helper_job          TEXT,
    vac_crew_observed   TEXT,
    vac_completed       BOOLEAN,
    row_modified_at     TIMESTAMPTZ,
    content_hash        TEXT        NOT NULL,
    first_seen_run      TEXT        NOT NULL,
    last_seen_run       TEXT        NOT NULL,
    last_changed_run    TEXT        NOT NULL,
    deleted_at          TIMESTAMPTZ,
    PRIMARY KEY (sheet_id, row_id)
);

CREATE INDEX IF NOT EXISTS idx_row_state_wr_week
    ON pipeline_memory.row_state (wr, week_ending);

-- ── row_event ────────────────────────────────────────────────
-- HISTORY, append-only, written ONLY when a row's content_hash
-- changes (never duplicated per run) -- server-side diff, enforced by
-- upsert_rows_bulk below.
--
-- D-05 (LOCKED, .planning/phases/10-run-memory-foundation-shadow-
-- writes/10-CONTEXT.md): a SINGLE UNPARTITIONED table, NOT the design
-- draft's ``partition by range (observed_at)``. pg_partman is not
-- installable on hosted Supabase (compiled extension), so native
-- partitioning would mean a bespoke pg_cron create/drop function whose
-- failure mode is a hard INSERT failure on the production writer;
-- projected volume (~208k day-one, ~4-5M rows / single-digit GB over
-- 24 months) does not justify it. A plain identity PRIMARY KEY on
-- event_id replaces the draft's composite (event_id, observed_at) key.
-- Revisit trigger (explicit, not open-ended): Phase 11 measured volume
-- >= ~10x this projection, or table size in the tens of GB.
--
-- ``wr`` and ``week_ending`` are REAL columns here (not only inside
-- after_image) so Phase 12's ownership-history lookups can hit the
-- (wr, week_ending) index directly.
--
-- D-04 (reserved only this phase): ``source`` + ``source_ref`` let a
-- later Phase-12 backfill tag imported history distinctly from live
-- writes. Phase 10 writes ONLY 'live'.
CREATE TABLE IF NOT EXISTS pipeline_memory.row_event (
    event_id     BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sheet_id     BIGINT      NOT NULL,
    row_id       BIGINT      NOT NULL,
    run_id       TEXT        NOT NULL,
    observed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    change_kind  TEXT        NOT NULL
        CHECK (change_kind IN ('insert', 'update', 'delete', 'reconcile')),
    wr           TEXT,
    week_ending  DATE,
    after_image  JSONB       NOT NULL,
    source       TEXT        NOT NULL DEFAULT 'live'
        CHECK (source IN ('live', 'backfill_artifacts',
                           'backfill_hash_history', 'operator')),
    source_ref   TEXT
);

CREATE INDEX IF NOT EXISTS idx_row_event_observed_at
    ON pipeline_memory.row_event (observed_at);
CREATE INDEX IF NOT EXISTS idx_row_event_sheet_row
    ON pipeline_memory.row_event (sheet_id, row_id);
CREATE INDEX IF NOT EXISTS idx_row_event_wr_week
    ON pipeline_memory.row_event (wr, week_ending);

-- ── group_state ──────────────────────────────────────────────
-- Per generated file; supersedes (in a LATER plan, once wired --
-- shadow-only in Phase 10) billing_audit.group_content_hash and the
-- attachment pre-fetch cache.
--
-- PRIMARY KEY includes target_sheet_id -- a promotion over the design
-- draft's (wr, week_ending, variant, identifier), per this plan's
-- assumption_delta_decision: a ``reduced_sub`` / ``reduced_sub_helper``
-- group fans out into TWO upload tasks (TARGET_SHEET_ID and
-- SUBCONTRACTOR_PPP_SHEET_ID, pipeline/upload.py lines ~300-347), each
-- producing its own attachment with its own id. Without target_sheet_id
-- in the key, the second leg's attachment_id would silently overwrite
-- the first's.
CREATE TABLE IF NOT EXISTS pipeline_memory.group_state (
    wr                  TEXT        NOT NULL,
    week_ending         DATE        NOT NULL,
    variant             TEXT        NOT NULL,
    identifier          TEXT        NOT NULL,
    target_sheet_id     BIGINT      NOT NULL,
    content_hash        TEXT        NOT NULL,
    row_count           INT         NOT NULL,
    attachment_id       BIGINT,
    attachment_name     TEXT,
    last_generated_run  TEXT,
    last_verified_run   TEXT,
    source              TEXT        NOT NULL DEFAULT 'live'
        CHECK (source IN ('live', 'backfill_artifacts',
                           'backfill_hash_history', 'operator')),
    source_ref          TEXT,
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (wr, week_ending, variant, identifier, target_sheet_id)
);

-- ── run_ledger ───────────────────────────────────────────────
-- One row per run (billing_audit.pipeline_run stays per WR/week --
-- this is run-LEVEL, not WR-level). Wired end-to-end in plan 10-01:
-- pipeline/orchestrate.py::main() calls run_ledger_start() right after
-- the "weekly run started" log event and run_ledger_finish()
-- immediately before the frozen 21-key run_summary.json write.
--
-- mode is always 'full' in Phase 10 (D-07: the weekly deep run stays
-- the full reconciliation and no run yet performs an incremental
-- read). notes carries the run's execution_type (manual /
-- production_frequent / weekend_maintenance / weekly_comprehensive,
-- read from the EXECUTION_TYPE env var the workflow already computes)
-- plus the memory-write counters -- deliberately NOT added to
-- run_summary.json (that 21-key contract is frozen; Gate 6 fails on
-- extra keys).
CREATE TABLE IF NOT EXISTS pipeline_memory.run_ledger (
    run_id            TEXT        PRIMARY KEY,
    mode              TEXT        NOT NULL
        CHECK (mode IN ('incremental', 'full', 'targeted')),
    started_at        TIMESTAMPTZ,
    finished_at       TIMESTAMPTZ,
    release           TEXT,
    sheets_checked    INT,
    sheets_changed    INT,
    rows_seen         INT,
    rows_changed      INT,
    groups_affected   INT,
    groups_generated  INT,
    status            TEXT,
    notes             JSONB
);

-- ── upsert_rows_bulk (RPC) ───────────────────────────────────
-- The write path a later plan (10-02) calls: ONE RPC per sheet, doing
-- the row_state upsert + conditional row_event insert server-side
-- (diff by content_hash, never per-row round trips from Python --
-- MEM-03 bulk requirement).
--
-- SECURITY (T-10-03, ASVS V5): explicit typed jsonb_to_recordset(...)
-- column list, never dynamic SQL and never trusting client-shaped
-- jsonb structurally. LANGUAGE plpgsql with SET search_path = '' (the
-- mutable-search-path advisor finding already fixed on every
-- billing_audit RPC) -- every object reference below is therefore
-- schema-qualified. VOLATILE (the default; NOT STABLE like the
-- analog's read-only RPCs -- this one writes).
--
-- Row-level semantics:
--   - row_event: inserted ONLY for rows whose content_hash differs
--     from the stored row_state.content_hash (or that have no prior
--     row_state row at all). change_kind = 'insert' when no prior row
--     existed, 'update' otherwise. after_image carries every business
--     column plus source = 'live'.
--   - row_state: always upserted (last_seen_run always advances);
--     content_hash, the business columns, and last_changed_run are
--     updated ONLY when the hash actually differs, so a re-read with
--     no Smartsheet edits touches last_seen_run only and MEM-02's
--     "second run adds zero row_event rows" invariant holds.
--     first_seen_run is set on insert only (ON CONFLICT never
--     overwrites it).
--   - deleted_at is NEVER written here -- full-read deletion
--     reconciliation is Phase 11 INC-03 (explicit opt-out, see
--     COVERAGE.md).
--
-- Returns the AFFECTED (wr, week_ending) set: for every row whose hash
-- changed, both its NEW (wr, week_ending) pair and its PREVIOUS stored
-- pair when the row's week_ending moved -- Phase 11 INC-02 depends on
-- the previous week being present so the old file can be regenerated
-- too.
CREATE OR REPLACE FUNCTION pipeline_memory.upsert_rows_bulk(
    p_sheet_id BIGINT,
    p_run_id   TEXT,
    p_rows     JSONB
)
RETURNS TABLE (wr TEXT, week_ending DATE)
LANGUAGE plpgsql
VOLATILE
SET search_path = ''
AS $$
BEGIN
    RETURN QUERY
    WITH incoming AS (
        SELECT
            q.row_id, q.wr, q.week_ending, q.snapshot_date, q.cu, q.pole,
            q.work_type, q.quantity, q.units_total_price, q.units_completed,
            q.foreman_observed, q.helper_observed, q.helper_completed,
            q.helper_dept, q.helper_job, q.vac_crew_observed,
            q.vac_completed, q.row_modified_at, q.content_hash
        FROM jsonb_to_recordset(p_rows) AS q(
            row_id             BIGINT,
            wr                 TEXT,
            week_ending        DATE,
            snapshot_date      DATE,
            cu                 TEXT,
            pole               TEXT,
            work_type          TEXT,
            quantity           NUMERIC,
            units_total_price  NUMERIC,
            units_completed    BOOLEAN,
            foreman_observed   TEXT,
            helper_observed    TEXT,
            helper_completed   BOOLEAN,
            helper_dept        TEXT,
            helper_job         TEXT,
            vac_crew_observed  TEXT,
            vac_completed      BOOLEAN,
            row_modified_at    TIMESTAMPTZ,
            content_hash       TEXT
        )
    ),
    prior AS (
        SELECT rs.row_id,
               rs.content_hash AS prior_hash,
               rs.week_ending  AS prior_week_ending
        FROM pipeline_memory.row_state AS rs
        WHERE rs.sheet_id = p_sheet_id
          AND rs.row_id IN (SELECT i.row_id FROM incoming AS i)
    ),
    changed AS (
        SELECT
            i.*,
            p.prior_hash,
            p.prior_week_ending,
            (p.row_id IS NULL) AS is_new
        FROM incoming AS i
        LEFT JOIN prior AS p ON p.row_id = i.row_id
        WHERE p.prior_hash IS DISTINCT FROM i.content_hash
    ),
    ins_events AS (
        INSERT INTO pipeline_memory.row_event (
            sheet_id, row_id, run_id, change_kind, wr, week_ending,
            after_image, source
        )
        SELECT
            p_sheet_id,
            c.row_id,
            p_run_id,
            CASE WHEN c.is_new THEN 'insert' ELSE 'update' END,
            c.wr,
            c.week_ending,
            jsonb_build_object(
                'wr', c.wr,
                'week_ending', c.week_ending,
                'snapshot_date', c.snapshot_date,
                'cu', c.cu,
                'pole', c.pole,
                'work_type', c.work_type,
                'quantity', c.quantity,
                'units_total_price', c.units_total_price,
                'units_completed', c.units_completed,
                'foreman_observed', c.foreman_observed,
                'helper_observed', c.helper_observed,
                'helper_completed', c.helper_completed,
                'helper_dept', c.helper_dept,
                'helper_job', c.helper_job,
                'vac_crew_observed', c.vac_crew_observed,
                'vac_completed', c.vac_completed,
                'row_modified_at', c.row_modified_at,
                'content_hash', c.content_hash
            ),
            'live'
        FROM changed AS c
        RETURNING 1
    ),
    ins_state AS (
        INSERT INTO pipeline_memory.row_state (
            sheet_id, row_id, wr, week_ending, snapshot_date, cu, pole,
            work_type, quantity, units_total_price, units_completed,
            foreman_observed, helper_observed, helper_completed,
            helper_dept, helper_job, vac_crew_observed, vac_completed,
            row_modified_at, content_hash, first_seen_run, last_seen_run,
            last_changed_run
        )
        SELECT
            p_sheet_id, i.row_id, i.wr, i.week_ending, i.snapshot_date,
            i.cu, i.pole, i.work_type, i.quantity, i.units_total_price,
            i.units_completed, i.foreman_observed, i.helper_observed,
            i.helper_completed, i.helper_dept, i.helper_job,
            i.vac_crew_observed, i.vac_completed, i.row_modified_at,
            i.content_hash, p_run_id, p_run_id, p_run_id
        FROM incoming AS i
        ON CONFLICT (sheet_id, row_id) DO UPDATE SET
            last_seen_run = p_run_id,
            wr = CASE WHEN pipeline_memory.row_state.content_hash
                           IS DISTINCT FROM EXCLUDED.content_hash
                      THEN EXCLUDED.wr ELSE pipeline_memory.row_state.wr END,
            week_ending = CASE WHEN pipeline_memory.row_state.content_hash
                                    IS DISTINCT FROM EXCLUDED.content_hash
                               THEN EXCLUDED.week_ending
                               ELSE pipeline_memory.row_state.week_ending END,
            snapshot_date = CASE WHEN pipeline_memory.row_state.content_hash
                                       IS DISTINCT FROM EXCLUDED.content_hash
                                  THEN EXCLUDED.snapshot_date
                                  ELSE pipeline_memory.row_state.snapshot_date END,
            cu = CASE WHEN pipeline_memory.row_state.content_hash
                           IS DISTINCT FROM EXCLUDED.content_hash
                      THEN EXCLUDED.cu ELSE pipeline_memory.row_state.cu END,
            pole = CASE WHEN pipeline_memory.row_state.content_hash
                             IS DISTINCT FROM EXCLUDED.content_hash
                        THEN EXCLUDED.pole ELSE pipeline_memory.row_state.pole END,
            work_type = CASE WHEN pipeline_memory.row_state.content_hash
                                   IS DISTINCT FROM EXCLUDED.content_hash
                              THEN EXCLUDED.work_type
                              ELSE pipeline_memory.row_state.work_type END,
            quantity = CASE WHEN pipeline_memory.row_state.content_hash
                                  IS DISTINCT FROM EXCLUDED.content_hash
                             THEN EXCLUDED.quantity
                             ELSE pipeline_memory.row_state.quantity END,
            units_total_price = CASE WHEN pipeline_memory.row_state.content_hash
                                           IS DISTINCT FROM EXCLUDED.content_hash
                                      THEN EXCLUDED.units_total_price
                                      ELSE pipeline_memory.row_state.units_total_price END,
            units_completed = CASE WHEN pipeline_memory.row_state.content_hash
                                         IS DISTINCT FROM EXCLUDED.content_hash
                                    THEN EXCLUDED.units_completed
                                    ELSE pipeline_memory.row_state.units_completed END,
            foreman_observed = CASE WHEN pipeline_memory.row_state.content_hash
                                          IS DISTINCT FROM EXCLUDED.content_hash
                                     THEN EXCLUDED.foreman_observed
                                     ELSE pipeline_memory.row_state.foreman_observed END,
            helper_observed = CASE WHEN pipeline_memory.row_state.content_hash
                                         IS DISTINCT FROM EXCLUDED.content_hash
                                    THEN EXCLUDED.helper_observed
                                    ELSE pipeline_memory.row_state.helper_observed END,
            helper_completed = CASE WHEN pipeline_memory.row_state.content_hash
                                          IS DISTINCT FROM EXCLUDED.content_hash
                                     THEN EXCLUDED.helper_completed
                                     ELSE pipeline_memory.row_state.helper_completed END,
            helper_dept = CASE WHEN pipeline_memory.row_state.content_hash
                                     IS DISTINCT FROM EXCLUDED.content_hash
                                THEN EXCLUDED.helper_dept
                                ELSE pipeline_memory.row_state.helper_dept END,
            helper_job = CASE WHEN pipeline_memory.row_state.content_hash
                                    IS DISTINCT FROM EXCLUDED.content_hash
                               THEN EXCLUDED.helper_job
                               ELSE pipeline_memory.row_state.helper_job END,
            vac_crew_observed = CASE WHEN pipeline_memory.row_state.content_hash
                                           IS DISTINCT FROM EXCLUDED.content_hash
                                      THEN EXCLUDED.vac_crew_observed
                                      ELSE pipeline_memory.row_state.vac_crew_observed END,
            vac_completed = CASE WHEN pipeline_memory.row_state.content_hash
                                       IS DISTINCT FROM EXCLUDED.content_hash
                                  THEN EXCLUDED.vac_completed
                                  ELSE pipeline_memory.row_state.vac_completed END,
            row_modified_at = CASE WHEN pipeline_memory.row_state.content_hash
                                         IS DISTINCT FROM EXCLUDED.content_hash
                                    THEN EXCLUDED.row_modified_at
                                    ELSE pipeline_memory.row_state.row_modified_at END,
            content_hash = CASE WHEN pipeline_memory.row_state.content_hash
                                      IS DISTINCT FROM EXCLUDED.content_hash
                                 THEN EXCLUDED.content_hash
                                 ELSE pipeline_memory.row_state.content_hash END,
            last_changed_run = CASE WHEN pipeline_memory.row_state.content_hash
                                          IS DISTINCT FROM EXCLUDED.content_hash
                                     THEN p_run_id
                                     ELSE pipeline_memory.row_state.last_changed_run END
        RETURNING 1
    )
    SELECT c.wr, c.week_ending
    FROM changed AS c
    UNION
    SELECT c.wr, c.prior_week_ending
    FROM changed AS c
    WHERE c.prior_week_ending IS NOT NULL
      AND c.prior_week_ending IS DISTINCT FROM c.week_ending;
END;
$$;

GRANT EXECUTE ON FUNCTION pipeline_memory.upsert_rows_bulk(BIGINT, TEXT, JSONB)
    TO service_role;

-- ── Privileges -- service_role, the pipeline's only writer ───────
-- Supabase's service_role BYPASSES RLS but is NOT a superuser: on a
-- schema outside ``public`` it holds no USAGE and no table privileges
-- until granted. Verified live on 2026-08-25 (plan 10-06 Task 2): after
-- the first apply every table reported SELECT/INSERT/UPDATE = false for
-- service_role, so every shadow write would have failed with 42501
-- (fail-open, so silently). Mirrors billing_audit's explicit per-table
-- GRANTs; the ALTER DEFAULT PRIVILEGES lines cover tables and identity
-- sequences added to this schema later. DELETE is deliberately NOT
-- granted -- Phase 10 never deletes from Python, and retention runs
-- under pg_cron as the table owner.
GRANT USAGE ON SCHEMA pipeline_memory TO service_role;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA pipeline_memory
    TO service_role;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA pipeline_memory TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA pipeline_memory
    GRANT SELECT, INSERT, UPDATE ON TABLES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA pipeline_memory
    GRANT USAGE ON SEQUENCES TO service_role;

-- ── RLS -- service-role only (D-01, T-10-02) ─────────────────
-- Every table gets RLS enabled with a single service_role_all policy,
-- mirroring every existing billing_audit table. service_role bypasses
-- RLS in Postgres regardless (BYPASSRLS), so this policy is defensive
-- documentation + satisfies the Postgres advisor's "RLS enabled"
-- lint -- the load-bearing control is the explicit REVOKE below, which
-- closes the anon/authenticated surface for the schema PostgREST
-- exposure opens up.
ALTER TABLE pipeline_memory.sheet_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_memory.row_state      ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_memory.row_event      ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_memory.group_state    ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_memory.run_ledger     ENABLE ROW LEVEL SECURITY;

-- CREATE POLICY has no IF NOT EXISTS, so drop-then-create keeps this
-- file reapply-safe like every other statement in it. The momentary
-- policy-less window is inert: service_role bypasses RLS and no other
-- role holds grants on these tables (see REVOKE block below).
DROP POLICY IF EXISTS service_role_all ON pipeline_memory.sheet_registry;
CREATE POLICY service_role_all ON pipeline_memory.sheet_registry
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS service_role_all ON pipeline_memory.row_state;
CREATE POLICY service_role_all ON pipeline_memory.row_state
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS service_role_all ON pipeline_memory.row_event;
CREATE POLICY service_role_all ON pipeline_memory.row_event
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS service_role_all ON pipeline_memory.group_state;
CREATE POLICY service_role_all ON pipeline_memory.group_state
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS service_role_all ON pipeline_memory.run_ledger;
CREATE POLICY service_role_all ON pipeline_memory.run_ledger
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- T-10-02 (critical, STRIDE Elevation of Privilege): exposing
-- pipeline_memory to PostgREST (the D-02 prerequisite above) also
-- makes it REACHABLE by every portal client (anon, authenticated)
-- unless explicitly closed. No USAGE ON SCHEMA is ever granted to
-- those roles above; these REVOKEs are the explicit, reapply-safe
-- (REVOKE on a privilege that was never granted is a no-op, not an
-- error) belt-and-suspenders close, including for any table added to
-- this schema in the future via ALTER DEFAULT PRIVILEGES.
REVOKE ALL ON SCHEMA pipeline_memory FROM anon, authenticated;
REVOKE ALL ON ALL TABLES IN SCHEMA pipeline_memory FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA pipeline_memory
    REVOKE ALL ON TABLES FROM anon, authenticated;

-- ── Retention (D-06) ─────────────────────────────────────────
-- row_event grows unbounded without this: 24-month retention,
-- enforced by pg_cron, deleting in SMALL BOUNDED SLICES per invocation
-- (never one large purge) so autovacuum keeps pace with the bulk-RPC
-- write path above.
--
-- OPERATOR (Open Question 1, 10-RESEARCH.md): pg_cron project-level
-- enablement on poeyztlmsawfoqlanucc is UNVERIFIED as of this plan --
-- confirm at plan 10-06 Task 2's operator checkpoint. CREATE EXTENSION
-- IF NOT EXISTS is idempotent either way.
--
-- In Phase 10 this function deletes NOTHING -- no pipeline_memory row
-- is anywhere near 24 months old yet (the schema is new). It exists
-- now so the retention job ships in the SAME PR as the tables it
-- governs, per D-03.
CREATE EXTENSION IF NOT EXISTS pg_cron;

CREATE OR REPLACE FUNCTION pipeline_memory.purge_row_event_slice()
RETURNS void
LANGUAGE plpgsql
SET search_path = ''
AS $$
DECLARE
    -- Bounded per-invocation delete count. A single unbounded DELETE
    -- across a multi-million-row table would hold long locks and
    -- generate a bloat spike the bulk writer's autovacuum cannot keep
    -- pace with; small daily slices amortize the cost instead.
    _max_rows_per_invocation CONSTANT INT := 5000;
BEGIN
    DELETE FROM pipeline_memory.row_event
    WHERE ctid IN (
        SELECT ctid
        FROM pipeline_memory.row_event
        WHERE observed_at < (NOW() - INTERVAL '24 months')
        LIMIT _max_rows_per_invocation
    );
END;
$$;

-- cron.schedule(job_name, ...) is idempotent by job name (pg_cron
-- upserts an existing job of the same name rather than duplicating
-- it), keeping this reapply-safe alongside every other statement in
-- this file. Runs daily, off the pipeline's own 2-hourly cadence, so
-- retention never competes with a production run for I/O.
SELECT cron.schedule(
    'pipeline_memory_purge_row_event',
    '17 6 * * *',
    $$SELECT pipeline_memory.purge_row_event_slice();$$
);

-- ============================================================
-- Python <-> SQL contract (D-03): adding or renaming a column here
-- requires updating pipeline_memory/writer.py in the SAME PR. The DDL
-- is a versioned in-repo mirror shipped alongside its Python, never
-- applied ad hoc -- apply changes to a live Supabase project by hand,
-- from this file, after reviewing the diff.
--
-- Load-bearing column/parameter names the Python side already commits
-- to (verified against pipeline_memory/writer.py and
-- tests/test_pipeline_memory_shadow.py in plan 10-01):
--   run_ledger: run_id, mode, started_at, release, status (start);
--     finished_at, status, sheets_checked, rows_seen, rows_changed,
--     groups_generated, notes (finish). on_conflict="run_id".
--   upsert_rows_bulk RPC parameters: p_sheet_id, p_run_id, p_rows
--     (wired against real row payloads starting plan 10-02).
-- ============================================================
