-- ============================================================
-- billing_audit/helper2_attribution.sql
--
-- OWNER-APPLIED. Paste this file, step by step, into the Supabase SQL
-- Editor for the production Supabase project (poeyztlmsawfoqlanucc).
-- Nothing in this repo executes any statement in this file at
-- runtime -- no Python script, pipeline module, or CI job ever runs
-- this SQL. Juan applies it by hand after the Phase 14 Plan 09 Task 2
-- decision checkpoint authorizes it, in a quiet window outside the
-- weekly-excel-generation.yml cron schedule (chosen at that
-- checkpoint, not by this file).
--
-- APPLIED 2026-09-08 16:55:11Z as Supabase migration
-- 20260908165511_helper2_attribution_columns_and_rpcs, owner-delegated to
-- the Claude session over the Supabase MCP connection (decision record
-- D-14-07-APPLIED in .planning/phases/14-foreman-helper-2/14-DECISIONS.md,
-- which also lists the three deviations that preserved the live
-- definitions). Read-back: D-14-07-VERIFIED. This file stays the
-- reviewable source; re-running it is idempotent for STEP 1 only.
--
-- Phase 14 (Foreman Helper #2), requirement HLP-06. Gives Helper #2
-- its own frozen attribution role: two additive nullable columns on
-- ``billing_audit.attribution_snapshot``, two new named parameters on
-- ``freeze_attribution``, and both read-surface lookup functions
-- (``lookup_attribution``, ``lookup_attribution_bulk``) recreated with
-- the matching return columns.
--
-- THE DOCUMENTED FAILURE MODE THIS FILE EXISTS TO AVOID: Postgres
-- ``CREATE OR REPLACE FUNCTION`` cannot change a function's RETURNS
-- TABLE column set. A migration written the obvious way (a bare
-- CREATE OR REPLACE) succeeds with NO ERROR and deploys NOTHING --
-- exactly what happened to ``lookup_attribution`` on 2026-05-27
-- (billing_audit/schema.sql, the incident note above that function).
-- Both lookup functions below are DROP FUNCTION IF EXISTS, then
-- CREATE FUNCTION -- never CREATE OR REPLACE, on either. "The SQL ran
-- without complaint" is never evidence this landed -- see STEP 5's
-- read-back queries and Plan 09 Task 3's owner-observed verification.
--
-- WHAT THIS FILE DOES NOT DO: it does not touch
-- billing_audit.backfill_attribution or attribution_snapshot's
-- Phase 12 ownership-provenance columns (the row-level source/run-id
-- tags and their per-role JSONB map). Those belong to a separate
-- Phase 12 migration and are out of scope here.
--
-- PER-ROLE WRITE GUARANTEE (Phase 12 decision D-12-A, applies here
-- too): freeze_attribution must write ONLY the two Helper #2 columns
-- it is given. It must never clear or overwrite the existing primary,
-- helper, or VAC-crew columns of the same row -- first-write-wins is
-- scoped PER ROLE, not per row.
--
-- Run STEP 1 through STEP 5 in order, top to bottom. STEP 2 contains
-- a MANUAL sub-step (2b) that cannot be run as pasted -- read it
-- before running anything in STEP 2. Run `NOTIFY pgrst, 'reload
-- schema';` after STEP 4 (included at the end of STEP 4, and again at
-- the end of STEP 5) so PostgREST picks up the new function shapes
-- immediately.
--
-- POST-APPLICATION VERIFICATION: STEP 5 below is read-only and proves
-- the two lookup functions return the new columns. It is NOT a
-- substitute for Plan 09 Task 3's four owner-observed checks (both
-- lookup functions return the columns on a real row; the table has
-- both columns; a Helper #2 freeze on a test row leaves
-- frozen_primary / frozen_helper / frozen_vac_crew byte-identical;
-- the next real run logs no Helper #2 capability-degrade warning).
-- Do not claim this migration succeeded until those four checks are
-- recorded in .planning/phases/14-foreman-helper-2/14-DECISIONS.md as
-- D-14-07-VERIFIED.
-- ============================================================


-- ── STEP 1 -- ADD THE TWO HELPER #2 COLUMNS ──────────────────
-- Additive, nullable, no key/index/constraint/data migration -- old
-- code ignores these columns, new code tolerates their absence.
-- IF NOT EXISTS makes this step safe to re-run.
-- Naming mirrors the existing per-role convention already deployed on
-- this table (frozen_primary, frozen_helper, frozen_helper_dept,
-- frozen_vac_crew -- confirmed by lookup_attribution's CASE
-- expressions in billing_audit/schema.sql).
ALTER TABLE billing_audit.attribution_snapshot
    ADD COLUMN IF NOT EXISTS frozen_helper2 TEXT;
ALTER TABLE billing_audit.attribution_snapshot
    ADD COLUMN IF NOT EXISTS frozen_helper2_dept TEXT;

-- STEP 1 VERIFY -- expect exactly two rows back, both nullable TEXT.
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'billing_audit'
  AND table_name = 'attribution_snapshot'
  AND column_name IN ('frozen_helper2', 'frozen_helper2_dept')
ORDER BY column_name;


-- ── STEP 2 -- EXTEND freeze_attribution WITH THE TWO HELPER #2 PARAMETERS ──
-- freeze_attribution's BODY is owner-applied and lives in Supabase
-- only (billing_audit/schema.sql's freeze_attribution contract-as-
-- comment block) -- it has never been checked into this repository,
-- because it carries business-logic attribution rules owned by the
-- data team rather than the pipeline. This file cannot literally
-- contain (and must never fabricate) that real per-role write logic,
-- so this step is split into an automated read (2a) and a MANUAL
-- edit (2b) that only Juan can complete correctly.
--
-- STEP 2a -- Run this FIRST and read its output. It returns the
-- CURRENT deployed body of billing_audit.freeze_attribution, exactly
-- as Postgres would recreate it verbatim.
SELECT pg_catalog.pg_get_functiondef(p.oid) AS current_freeze_attribution_definition
FROM pg_catalog.pg_proc AS p
JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
WHERE n.nspname = 'billing_audit'
  AND p.proname = 'freeze_attribution';

-- STEP 2b -- MANUAL STEP, NOT EXECUTABLE SQL AS WRITTEN BELOW. Copy
-- STEP 2a's output into a text editor and build the real statement by
-- hand from it -- do NOT paste the block below into the SQL editor
-- and run it as-is. The `<<...>>` placeholder is deliberately invalid
-- SQL so an accidental verbatim run fails loudly with a syntax error
-- instead of silently deploying a stub in place of the real
-- attribution logic.
--
-- The typed parameter list below is the ONLY part of this block this
-- repo can state with certainty -- it is copied directly from
-- billing_audit/writer.py:freeze_row's params dict and from the 12
-- pre-existing parameters already documented in
-- billing_audit/schema.sql's freeze_attribution contract block.
-- Preserve every existing parameter's name, type, and position
-- EXACTLY as STEP 2a printed them (the deployed order puts p_pole,
-- p_cu, p_work_type before the role parameters -- it is not the
-- listing order in billing_audit/schema.sql). The two new parameters
-- go LAST: Postgres rejects a non-defaulted parameter after a
-- defaulted one ("input parameters after one with a default value
-- must also have defaults"), and PostgREST matches RPC arguments by
-- NAME, so their position never affects the writer's call. Both new
-- parameters carry DEFAULT NULL on purpose:
-- PostgREST resolves a named-argument RPC call only when every
-- parameter WITHOUT a default is supplied, so without the defaults the
-- currently deployed writer (which still sends the 12 pre-Phase-14
-- parameters) would get PGRST202 on every freeze between this apply
-- and the code merge. The defaults are what make `sql-first` safe;
-- tests/test_helper2_attribution_sql_contract.py pins them.
--
-- DROP FUNCTION also removes any GRANT on the old function -- after
-- completing 2b, re-apply whatever GRANT EXECUTE ... TO service_role
-- (or equivalent) the current definition carried; STEP 2a's output
-- does not include GRANTs (pg_get_functiondef returns only the
-- CREATE OR REPLACE FUNCTION statement), so check
-- information_schema.role_routine_grants for billing_audit /
-- freeze_attribution before STEP 2a if the exact grantee is not
-- already known.
--
-- DROP FUNCTION IF EXISTS billing_audit.freeze_attribution(TEXT, DATE, BIGINT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT);
--
-- CREATE FUNCTION billing_audit.freeze_attribution(
--     p_wr                TEXT,
--     p_week_ending       DATE,
--     p_smartsheet_row_id BIGINT,
--     p_pole              TEXT,
--     p_cu                TEXT,
--     p_work_type         TEXT,
--     p_primary           TEXT,
--     p_helper            TEXT,
--     p_helper_dept       TEXT,
--     p_vac_crew          TEXT,
--     p_release           TEXT,
--     p_run_id            TEXT,
--     p_helper2           TEXT DEFAULT NULL,
--     p_helper2_dept      TEXT DEFAULT NULL
-- )
-- <<PASTE STEP 2a's RETURNS clause and $$ ... $$ body here UNCHANGED,
--   THEN add exactly two per-role writes inside it, mirroring the
--   existing frozen_helper / frozen_helper_dept writes byte-for-byte
--   in shape:
--     - frozen_helper2      <- p_helper2,      the SAME first-write-
--       -wins predicate class already guarding frozen_helper (D-12-A:
--       write ONLY this named column from this parameter; never touch
--       frozen_primary, frozen_helper, or frozen_vac_crew because
--       p_helper2 was supplied).
--     - frozen_helper2_dept <- p_helper2_dept, mirroring
--       frozen_helper_dept the same way.
--   Do not reorder, rename, or remove any existing parameter or
--   column write. Do not change what the function does to
--   frozen_primary, frozen_helper, or frozen_vac_crew.>>


-- ── STEP 3 -- lookup_attribution (single-row read surface) ──
-- The DROP is REQUIRED for the reason stated in the file header and
-- in billing_audit/schema.sql's incident note above this function:
-- CREATE OR REPLACE cannot change RETURNS TABLE columns. Same
-- sentinel-nulling CASE idiom as the currently-deployed version,
-- copied verbatim, with two new CASE expressions appended for the two
-- new columns. The deployed function carries a pinned search_path
-- (advisor remediation, 2026-05-19); DROP + CREATE without it would
-- regress the function_search_path_mutable advisor, so it is kept.
DROP FUNCTION IF EXISTS billing_audit.lookup_attribution(TEXT, DATE, BIGINT);

CREATE FUNCTION billing_audit.lookup_attribution(
    p_wr                TEXT,
    p_week_ending       DATE,
    p_smartsheet_row_id BIGINT
)
RETURNS TABLE (
    primary_foreman TEXT,
    helper          TEXT,
    helper_dept     TEXT,
    vac_crew        TEXT,
    source_run_id   TEXT,
    helper2         TEXT,
    helper2_dept    TEXT
)
LANGUAGE sql
STABLE
SET search_path TO 'billing_audit', 'public', 'extensions', 'pg_temp'
AS $$
    SELECT
        CASE WHEN s.frozen_primary     LIKE '#%' OR btrim(s.frozen_primary)     = '' THEN NULL ELSE s.frozen_primary     END AS primary_foreman,
        CASE WHEN s.frozen_helper      LIKE '#%' OR btrim(s.frozen_helper)      = '' THEN NULL ELSE s.frozen_helper      END AS helper,
        CASE WHEN s.frozen_helper_dept LIKE '#%' OR btrim(s.frozen_helper_dept) = '' THEN NULL ELSE s.frozen_helper_dept END AS helper_dept,
        CASE WHEN s.frozen_vac_crew    LIKE '#%' OR btrim(s.frozen_vac_crew)    = '' THEN NULL ELSE s.frozen_vac_crew    END AS vac_crew,
        s.source_run_id,
        CASE WHEN s.frozen_helper2      LIKE '#%' OR btrim(s.frozen_helper2)      = '' THEN NULL ELSE s.frozen_helper2      END AS helper2,
        CASE WHEN s.frozen_helper2_dept LIKE '#%' OR btrim(s.frozen_helper2_dept) = '' THEN NULL ELSE s.frozen_helper2_dept END AS helper2_dept
    FROM billing_audit.attribution_snapshot AS s
    WHERE s.wr                = p_wr
      AND s.week_ending       = p_week_ending
      AND s.smartsheet_row_id = p_smartsheet_row_id
    LIMIT 1;
$$;

GRANT EXECUTE ON FUNCTION billing_audit.lookup_attribution(TEXT, DATE, BIGINT) TO service_role;


-- ── STEP 4 -- lookup_attribution_bulk (bulk-prefetch read surface) ──
-- Has the IDENTICAL RETURNS TABLE restriction as STEP 3's function --
-- DROP FUNCTION IF EXISTS first, never CREATE OR REPLACE. Same
-- CASE-block idiom (D-01: one source of truth), two new columns
-- appended.
DROP FUNCTION IF EXISTS billing_audit.lookup_attribution_bulk(jsonb);

CREATE FUNCTION billing_audit.lookup_attribution_bulk(
    p_wr_weeks jsonb   -- e.g. '[{"wr":"90001","week_ending":"2026-04-19"}, ...]'
)
RETURNS TABLE (
    wr                TEXT,
    week_ending       DATE,
    smartsheet_row_id BIGINT,
    primary_foreman   TEXT,
    helper            TEXT,
    helper_dept       TEXT,
    vac_crew          TEXT,
    source_run_id     TEXT,
    helper2           TEXT,
    helper2_dept      TEXT
)
LANGUAGE sql
STABLE
SET search_path TO 'billing_audit', 'public', 'extensions', 'pg_temp'
AS $$
    SELECT
        s.wr,
        s.week_ending,
        s.smartsheet_row_id,
        -- EXACT same CASE blocks as lookup_attribution above (D-01: one source of truth)
        CASE WHEN s.frozen_primary     LIKE '#%' OR btrim(s.frozen_primary)     = '' THEN NULL ELSE s.frozen_primary     END,
        CASE WHEN s.frozen_helper      LIKE '#%' OR btrim(s.frozen_helper)      = '' THEN NULL ELSE s.frozen_helper      END,
        CASE WHEN s.frozen_helper_dept LIKE '#%' OR btrim(s.frozen_helper_dept) = '' THEN NULL ELSE s.frozen_helper_dept END,
        CASE WHEN s.frozen_vac_crew    LIKE '#%' OR btrim(s.frozen_vac_crew)    = '' THEN NULL ELSE s.frozen_vac_crew    END,
        s.source_run_id,
        CASE WHEN s.frozen_helper2      LIKE '#%' OR btrim(s.frozen_helper2)      = '' THEN NULL ELSE s.frozen_helper2      END,
        CASE WHEN s.frozen_helper2_dept LIKE '#%' OR btrim(s.frozen_helper2_dept) = '' THEN NULL ELSE s.frozen_helper2_dept END
    FROM jsonb_to_recordset(p_wr_weeks) AS q(wr TEXT, week_ending DATE)
    JOIN billing_audit.attribution_snapshot AS s
      ON s.wr = q.wr AND s.week_ending = q.week_ending;
$$;

GRANT EXECUTE ON FUNCTION billing_audit.lookup_attribution_bulk(jsonb) TO service_role;

NOTIFY pgrst, 'reload schema';


-- ── STEP 5 -- READ-BACK VERIFICATION (read-only) ─────────────
-- "The SQL ran without complaint" is never evidence here -- this
-- migration's documented failure mode produces no error at apply
-- time. Run these queries and read their actual output.
--
-- 5a -- confirm both new columns exist on the table.
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'billing_audit'
  AND table_name = 'attribution_snapshot'
  AND column_name IN ('frozen_helper2', 'frozen_helper2_dept')
ORDER BY column_name;

-- 5b -- confirm lookup_attribution's return SHAPE carries the two new
-- columns (a column that is ABSENT from the result set rather than
-- present-but-null is the silent non-deploy this file exists to
-- avoid). Substitute a real (wr, week_ending, smartsheet_row_id)
-- known to exist in attribution_snapshot.
SELECT * FROM billing_audit.lookup_attribution(
    '<a real wr>', '<a real week_ending date>', <a real smartsheet_row_id>
);

-- 5c -- same shape check for the bulk RPC.
SELECT * FROM billing_audit.lookup_attribution_bulk(
    '[{"wr":"<a real wr>","week_ending":"<a real week_ending date>"}]'::jsonb
);

-- Plan 09 Task 3 records the four owner-observed checks (including a
-- live freeze-and-read-back that proves the other three role columns
-- are untouched) in
-- .planning/phases/14-foreman-helper-2/14-DECISIONS.md as
-- D-14-07-VERIFIED. Queries 5a-5c above are a first-pass shape check,
-- not a substitute for that record.
