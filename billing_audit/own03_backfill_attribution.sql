-- ============================================================
-- billing_audit/own03_backfill_attribution.sql
--
-- OWNER-APPLIED. Paste this file, step by step, into the Supabase SQL
-- Editor for the production billing_audit project. Nothing in this
-- repo executes any statement in this file at runtime -- no Python
-- script, pipeline module, or CI job ever runs this SQL. Juan applies
-- it by hand after the Phase 12 Plan 03 Task 3 decision checkpoint
-- authorizes it.
--
-- Phase 12 (Ownership -- last known foreman as of the week),
-- requirement OWN-03. Implements the write path APPROVED 2026-09-02
-- 00:35 CDT: docs/superpowers/specs/2026-09-01-own-03-claim-time-
-- backfill-design.md Section 4 option 1 -- an owner-deployed RPC that
-- enforces "sentinel or NULL only" server-side, backed by a dated
-- backup table created before any row is touched.
--
-- D-12-A: this file does NOT create a wr_week_ownership table. OWN-01's
-- claimer ladder is served by billing_audit.attribution_snapshot plus
-- the two provenance columns this file adds (backfill_source,
-- backfill_run_id) -- see billing_audit/schema.sql's
-- "backfill_attribution (RPC)" contract-as-comment block for the full
-- documented contract.
--
-- Run STEP 0 through STEP 5 in order, top to bottom. Substitute
-- today's UTC date for the YYYYMMDD placeholder in STEP 1 before
-- running it. Run `NOTIFY pgrst, 'reload schema';` after STEP 5 (also
-- included at the end of this file) so PostgREST picks up the new
-- function and grant immediately.
-- ============================================================


-- ── STEP 0 -- CONFIRM COLUMN NAMES ───────────────────────────
-- billing_audit.attribution_snapshot's DDL is data-team-owned and is
-- NOT defined anywhere in this repo (billing_audit/schema.sql:213-220
-- -- the pipeline's contract with this table is the column names
-- documented there, not the full DDL). Run this query FIRST and read
-- its output before running STEP 1 or any later step.
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'billing_audit'
  AND table_name = 'attribution_snapshot'
ORDER BY ordinal_position;

-- STEP 0b -- CONFIRM KEY UNIQUENESS (Opus integration review, MEDIUM-1).
-- The RPC in STEP 4 joins p_rows back to the rows it updated on
-- (wr, week_ending, smartsheet_row_id, role). If the live table holds
-- more than one row for a key, the RPC returns more result rows than
-- p_rows and the 12-01 CLI counts the chunk as failed (exit 6) AFTER
-- those UPDATEs already committed -- an operator could then re-run
-- against rows already written. This query MUST return zero rows
-- before STEP 4; if it returns any, stop and reconcile the duplicates
-- with the data team first.
SELECT wr, week_ending, smartsheet_row_id, count(*) AS duplicate_rows
FROM billing_audit.attribution_snapshot
GROUP BY wr, week_ending, smartsheet_row_id
HAVING count(*) > 1
ORDER BY duplicate_rows DESC
LIMIT 20;

-- This file ASSUMES the three write-side role columns returned above
-- are named frozen_primary, frozen_helper and frozen_vac_crew, per
-- docs/superpowers/specs/2026-09-01-own-03-claim-time-backfill-design.md
-- Section 4 and the CASE expressions already reading them in
-- billing_audit.lookup_attribution (billing_audit/schema.sql:275-279).
-- If STEP 0's output disagrees, correct those three identifiers in
-- exactly one place -- the ADJUST HERE region at the top of STEP 4's
-- function body below -- and nowhere else in this file.
--
-- Note: billing_audit.lookup_attribution's RETURNED column names
-- (primary_foreman, helper, vac_crew) are THAT function's OUTPUT
-- contract, not this table's column names -- do not confuse the two
-- when reading STEP 0's output.


-- ── STEP 1 -- BACKUP ──────────────────────────────────────────
-- Copies the CURRENT attribution_snapshot into a dated backup table
-- before any write path touches it. Substitute today's UTC date
-- (YYYYMMDD, e.g. 20260903) for BOTH occurrences of the literal
-- placeholder in this step -- the CREATE TABLE and the GRANT below
-- (use the SQL editor's find/replace; running the GRANT with the
-- placeholder still in it fails with 42P01 "relation ... does not
-- exist", and running the CREATE with it creates a stray table
-- literally named attribution_snapshot_backup_yyyymmdd that the CLI
-- probe will never find). Idempotent: CREATE TABLE IF NOT EXISTS --
-- re-running this exact statement on the same UTC date is a no-op, it
-- will NOT re-snapshot a table that already had writes applied to it
-- earlier today.
--
-- Rollback for a bad backfill run is an `UPDATE billing_audit.
-- attribution_snapshot ... FROM billing_audit.attribution_snapshot_
-- backup_<date>` restoring the affected rows from this table. Do NOT
-- DROP this table until the NEXT scheduled production run after the
-- backfill has been verified to have regenerated the expected files
-- correctly.
CREATE TABLE IF NOT EXISTS billing_audit.attribution_snapshot_backup_YYYYMMDD AS
SELECT * FROM billing_audit.attribution_snapshot;

-- scripts/backfill_claim_time_attribution.py's --apply precondition
-- probe reads this table as service_role; the CREATE TABLE ... AS
-- SELECT above does not itself grant read access to that role, so
-- this GRANT is required even though the table was just created in
-- the same SQL Editor session.
GRANT SELECT ON billing_audit.attribution_snapshot_backup_YYYYMMDD TO service_role;

-- STEP 1 VERIFY -- lists every backup table that exists. Expect exactly
-- the dated table you just created (attribution_snapshot_backup_
-- 20260903 for a 2026-09-03 UTC apply). A row named
-- attribution_snapshot_backup_yyyymmdd means the CREATE ran with the
-- placeholder unreplaced: drop that stray table (it is a copy, never
-- written to) and re-run STEP 1 with the date substituted in both
-- statements:
--   DROP TABLE IF EXISTS billing_audit.attribution_snapshot_backup_yyyymmdd;
SELECT c.relname AS backup_table
FROM pg_catalog.pg_class AS c
JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'billing_audit'
  AND c.relkind = 'r'
  AND c.relname LIKE 'attribution_snapshot_backup_%'
ORDER BY c.relname DESC;


-- ── STEP 2 -- PROVENANCE COLUMNS ─────────────────────────────
-- Three nullable provenance columns, added the same backfill-safe way
-- billing_audit.group_content_hash's content_hash/updated_at columns
-- were added (billing_audit/schema.sql:158-171): ADD COLUMN IF NOT
-- EXISTS so this step is safe to re-run against an already-migrated
-- table.
--
-- backfill_source / backfill_run_id are ROW-level: they describe the
-- MOST RECENT backfill write to the row. Because the RPC in STEP 4
-- updates one ROLE column per payload row, a row whose primary and
-- helper were filled by different sources (or different runs -- e.g.
-- sources 1-4 today, source 5 next week) would otherwise lose the
-- earlier role's provenance (Greptile, PR #388 issue 1). So every
-- write ALSO merges a per-role entry into backfill_provenance:
--   {"primary":  {"source": "backfill_artifacts",     "run_id": "..."},
--    "helper":   {"source": "backfill_cell_history",  "run_id": "..."}}
-- Re-apply note: an environment that ran STEP 2 before this column
-- existed must re-run STEP 2 (IF NOT EXISTS makes it a no-op for the
-- first two columns) and then STEP 4, and STEP 0 must list all three.
ALTER TABLE billing_audit.attribution_snapshot
    ADD COLUMN IF NOT EXISTS backfill_source TEXT;
ALTER TABLE billing_audit.attribution_snapshot
    ADD COLUMN IF NOT EXISTS backfill_run_id TEXT;
ALTER TABLE billing_audit.attribution_snapshot
    ADD COLUMN IF NOT EXISTS backfill_provenance JSONB;

-- Named CHECK constraint, added only if it does not already exist so
-- re-running STEP 2 is safe. Restricts backfill_source to NULL (a row
-- never touched by any backfill) or one of five values. Four of them
-- ('live', 'backfill_artifacts', 'backfill_hash_history', 'operator')
-- are the SAME vocabulary pipeline_memory.row_event.source /
-- pipeline_memory.group_state.source already accept
-- (pipeline_memory/schema.sql:166-168, 204-206). The fifth,
-- 'backfill_cell_history', is specific to this table: a machine
-- inference sourced from Smartsheet cell history, distinct from
-- 'operator' (human-entered). D-12-A and the 2026-09-01 19:55
-- decision: this vocabulary deliberately has no cross-week ("last
-- known before the week") rung -- a row with no in-week evidence stays
-- a sentinel; it is never inherited from an adjacent week.
--
-- Re-apply note: if STEP 2 was already run against the OLD four-value
-- list ('live', 'backfill_artifacts', 'backfill_hash_history',
-- 'operator') before 'backfill_cell_history' was added, the DO block
-- below is a no-op (the constraint already exists) and will NOT
-- widen it. Drop and re-add it manually with the commented snippet
-- below -- NOT executed by default:
--
-- ALTER TABLE billing_audit.attribution_snapshot
--     DROP CONSTRAINT IF EXISTS attribution_snapshot_backfill_source_check;
-- ALTER TABLE billing_audit.attribution_snapshot
--     ADD CONSTRAINT attribution_snapshot_backfill_source_check
--     CHECK (
--         backfill_source IS NULL
--         OR backfill_source IN (
--             'live', 'backfill_artifacts', 'backfill_hash_history',
--             'backfill_cell_history', 'operator'
--         )
--     );
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint
        WHERE conname = 'attribution_snapshot_backfill_source_check'
    ) THEN
        ALTER TABLE billing_audit.attribution_snapshot
            ADD CONSTRAINT attribution_snapshot_backfill_source_check
            CHECK (
                backfill_source IS NULL
                OR backfill_source IN (
                    'live', 'backfill_artifacts', 'backfill_hash_history',
                    'backfill_cell_history', 'operator'
                )
            );
    END IF;
END;
$$;

-- STEP 2 VERIFY (Opus integration review, MEDIUM-2) -- mandatory.
-- The DO block above is a no-op when the constraint already exists and
-- will NOT widen an older, narrower definition; a stale definition makes
-- every apply that carries a newer provenance tag abort server-side.
-- Read the returned definition: it must accept every provenance tag the
-- two CLIs emit (the five listed in the DO block). If it does not, run
-- the commented drop/re-add snippet above, then re-run this SELECT.
SELECT conname, pg_catalog.pg_get_constraintdef(oid) AS live_definition
FROM pg_catalog.pg_constraint
WHERE conname = 'attribution_snapshot_backfill_source_check';


-- ── STEP 3 -- SENTINEL PREDICATE ─────────────────────────────
-- SQL twin of billing_audit/writer.py:96-115 (_SENTINEL_CLAIMERS /
-- is_sentinel_claimer). Update BOTH sides in the same PR if either
-- changes -- tests/test_own03_backfill_sql_contract.py asserts every
-- member of the Python frozenset appears in this SQL body.
--
-- The Python twin strips ALL whitespace (str.strip(), not just plain
-- spaces) before its blank / '#' / vocabulary checks, then collapses
-- any remaining internal whitespace run to a single space. `stripped`
-- mirrors that with a full-whitespace-set btrim (E' \t\r\n\f\v', not
-- the 1-arg btrim(text) default of space-only) so both sides agree
-- byte-for-byte on tab/newline-padded values -- every place below
-- that treats a value as blank reads from `stripped.v`, never the raw
-- `p_value`.
-- >>>>>>>> STEP 3 SELECTION STARTS HERE -- select down to the "STEP 3 SELECTION ENDS HERE" marker >>>>>>>>
CREATE OR REPLACE FUNCTION billing_audit.is_sentinel_value(p_value TEXT)
RETURNS BOOLEAN
LANGUAGE sql
IMMUTABLE
SET search_path = ''
AS $$
    WITH stripped AS (
        SELECT pg_catalog.btrim(p_value, E' \t\r\n\f\v') AS v
    )
    SELECT
        p_value IS NULL
        OR stripped.v = ''
        OR stripped.v LIKE '#%'
        OR pg_catalog.lower(
               pg_catalog.regexp_replace(
                   pg_catalog.btrim(
                       pg_catalog.replace(stripped.v, '_', ' ')
                   ),
                   '\s+', ' ', 'g'
               )
           ) IN (
               'unknown foreman',
               'unknown',
               'unknown helper',
               'unknown vac crew',
               'no match'
           )
    FROM stripped;
$$;
-- <<<<<<<< STEP 3 SELECTION ENDS HERE (include the `$$;` line above) <<<<<<<<


-- ── STEP 4 -- THE RPC ─────────────────────────────────────────
-- HOW TO RUN (seen live 2026-09-03, 42601 "unterminated dollar-quoted
-- string at or near AS $$"): the Supabase SQL editor's run-statement-
-- under-cursor splits inside a dollar-quoted body. Select the WHOLE
-- block from the DROP FUNCTION line through the closing `$$;` of the
-- CREATE FUNCTION and run that selection (or paste only that block
-- into a fresh query tab and run all). Same for STEP 3.
-- The DROP-first form is mandatory: see the lookup_attribution
-- incident note at billing_audit/schema.sql:246-256 -- Postgres
-- CREATE OR REPLACE FUNCTION cannot change a function's RETURNS TABLE
-- column set, so a bare CREATE OR REPLACE over a differently-shaped
-- prior version silently never deploys.
-- >>>>>>>> STEP 4 SELECTION STARTS HERE -- select from this line down to the
-- "STEP 4 SELECTION ENDS HERE" marker and run the selection as ONE statement. >>>>>>>>
DROP FUNCTION IF EXISTS billing_audit.backfill_attribution(jsonb);

CREATE FUNCTION billing_audit.backfill_attribution(
    p_rows jsonb
)
RETURNS TABLE (
    wr                TEXT,
    week_ending       DATE,
    smartsheet_row_id BIGINT,
    role              TEXT,
    result            TEXT
)
LANGUAGE plpgsql
VOLATILE
SET search_path = ''
AS $$
#variable_conflict use_column
-- ============================================================
-- ADJUST HERE -- STEP 0 correction region. If STEP 0's output showed
-- write-side role column names OTHER than frozen_primary /
-- frozen_helper / frozen_vac_crew, replace those three identifiers
-- everywhere they appear below (the three per-role UPDATE statements'
-- SET / WHERE clauses and the final classification SELECT) with the
-- real names -- and change nothing else in this file.
-- ============================================================
DECLARE
    v_row RECORD;
BEGIN
    -- Validate every input row BEFORE touching the table. role, value
    -- and backfill_source are never coerced and never silently
    -- skipped -- an offending row raises immediately (aborting the
    -- whole call) so a malformed p_rows payload fails loudly instead
    -- of partially applying.
    FOR v_row IN
        SELECT * FROM pg_catalog.jsonb_to_recordset(p_rows) AS q(
            wr                TEXT,
            week_ending       DATE,
            smartsheet_row_id BIGINT,
            role              TEXT,
            value             TEXT,
            backfill_source   TEXT,
            backfill_run_id   TEXT
        )
    LOOP
        IF v_row.role NOT IN ('primary', 'helper', 'vac_crew') THEN
            RAISE EXCEPTION 'backfill_attribution: invalid role %', v_row.role;
        END IF;
        IF billing_audit.is_sentinel_value(v_row.value) THEN
            RAISE EXCEPTION
                'backfill_attribution: proposed value for role=% (wr=% week_ending=% smartsheet_row_id=%) is a sentinel value, refusing to write it',
                v_row.role, v_row.wr, v_row.week_ending, v_row.smartsheet_row_id;
        END IF;
        IF v_row.backfill_source IS NULL
           OR v_row.backfill_source NOT IN (
               'live', 'backfill_artifacts', 'backfill_hash_history',
               'backfill_cell_history', 'operator'
           )
        THEN
            RAISE EXCEPTION 'backfill_attribution: invalid backfill_source %', v_row.backfill_source;
        END IF;
    END LOOP;

    -- Three explicit, static per-role UPDATE statements -- never a
    -- dynamically built column name and never a dynamically-assembled
    -- statement string. Each is scoped to its own role via the payload
    -- filter, joined to attribution_snapshot on the full PK (wr,
    -- week_ending, smartsheet_row_id), and each carries
    -- billing_audit.is_sentinel_value(<role column>) in its WHERE so a
    -- real (non-sentinel) name is never overwritten -- enforced
    -- server-side regardless of what the Python caller does (T-12-10).
    -- Each RETURNING clause captures exactly the keys THIS statement
    -- touched, so the classification below reflects what the sentinel
    -- predicate actually gated at call time, not a value that merely
    -- happens to match afterwards.
    RETURN QUERY
    WITH upd_primary AS (
        UPDATE billing_audit.attribution_snapshot AS s
        SET frozen_primary   = q.value,
            backfill_source  = q.backfill_source,
            backfill_run_id  = q.backfill_run_id,
            backfill_provenance = COALESCE(s.backfill_provenance, '{}'::jsonb)
                || pg_catalog.jsonb_build_object('primary', pg_catalog.jsonb_build_object('source', q.backfill_source, 'run_id', q.backfill_run_id))
        FROM pg_catalog.jsonb_to_recordset(p_rows) AS q(
            wr TEXT, week_ending DATE, smartsheet_row_id BIGINT, role TEXT,
            value TEXT, backfill_source TEXT, backfill_run_id TEXT
        )
        WHERE q.role = 'primary'
          AND s.wr = q.wr
          AND s.week_ending = q.week_ending
          AND s.smartsheet_row_id = q.smartsheet_row_id
          AND billing_audit.is_sentinel_value(s.frozen_primary)
        RETURNING s.wr, s.week_ending, s.smartsheet_row_id, 'primary'::TEXT AS role
    ),
    upd_helper AS (
        UPDATE billing_audit.attribution_snapshot AS s
        SET frozen_helper    = q.value,
            backfill_source  = q.backfill_source,
            backfill_run_id  = q.backfill_run_id,
            backfill_provenance = COALESCE(s.backfill_provenance, '{}'::jsonb)
                || pg_catalog.jsonb_build_object('helper', pg_catalog.jsonb_build_object('source', q.backfill_source, 'run_id', q.backfill_run_id))
        FROM pg_catalog.jsonb_to_recordset(p_rows) AS q(
            wr TEXT, week_ending DATE, smartsheet_row_id BIGINT, role TEXT,
            value TEXT, backfill_source TEXT, backfill_run_id TEXT
        )
        WHERE q.role = 'helper'
          AND s.wr = q.wr
          AND s.week_ending = q.week_ending
          AND s.smartsheet_row_id = q.smartsheet_row_id
          AND billing_audit.is_sentinel_value(s.frozen_helper)
        RETURNING s.wr, s.week_ending, s.smartsheet_row_id, 'helper'::TEXT AS role
    ),
    upd_vac_crew AS (
        UPDATE billing_audit.attribution_snapshot AS s
        SET frozen_vac_crew  = q.value,
            backfill_source  = q.backfill_source,
            backfill_run_id  = q.backfill_run_id,
            backfill_provenance = COALESCE(s.backfill_provenance, '{}'::jsonb)
                || pg_catalog.jsonb_build_object('vac_crew', pg_catalog.jsonb_build_object('source', q.backfill_source, 'run_id', q.backfill_run_id))
        FROM pg_catalog.jsonb_to_recordset(p_rows) AS q(
            wr TEXT, week_ending DATE, smartsheet_row_id BIGINT, role TEXT,
            value TEXT, backfill_source TEXT, backfill_run_id TEXT
        )
        WHERE q.role = 'vac_crew'
          AND s.wr = q.wr
          AND s.week_ending = q.week_ending
          AND s.smartsheet_row_id = q.smartsheet_row_id
          AND billing_audit.is_sentinel_value(s.frozen_vac_crew)
        RETURNING s.wr, s.week_ending, s.smartsheet_row_id, 'vac_crew'::TEXT AS role
    ),
    updated_keys AS (
        -- UNION (not UNION ALL): one key per updated (row, role) even
        -- if the live table ever holds duplicate key rows, so the
        -- final result never fans out past p_rows (MEDIUM-1).
        SELECT * FROM upd_primary
        UNION
        SELECT * FROM upd_helper
        UNION
        SELECT * FROM upd_vac_crew
    ),
    existing_rows AS (
        SELECT DISTINCT s.wr, s.week_ending, s.smartsheet_row_id
        FROM billing_audit.attribution_snapshot AS s
        JOIN pg_catalog.jsonb_to_recordset(p_rows) AS q(
            wr TEXT, week_ending DATE, smartsheet_row_id BIGINT, role TEXT,
            value TEXT, backfill_source TEXT, backfill_run_id TEXT
        )
          ON s.wr = q.wr
         AND s.week_ending = q.week_ending
         AND s.smartsheet_row_id = q.smartsheet_row_id
    )
    -- Return one row per input row: 'updated' for rows an UPDATE
    -- touched, 'skipped_real_name' for payload rows whose PK exists
    -- but whose role column failed the sentinel predicate,
    -- 'skipped_no_row' for payload rows with no matching PK.
    SELECT
        q.wr,
        q.week_ending,
        q.smartsheet_row_id,
        q.role,
        CASE
            WHEN u.wr IS NOT NULL THEN 'updated'
            WHEN e.wr IS NOT NULL THEN 'skipped_real_name'
            ELSE 'skipped_no_row'
        END AS result
    FROM pg_catalog.jsonb_to_recordset(p_rows) AS q(
        wr TEXT, week_ending DATE, smartsheet_row_id BIGINT, role TEXT,
        value TEXT, backfill_source TEXT, backfill_run_id TEXT
    )
    LEFT JOIN updated_keys AS u
      ON u.wr = q.wr
     AND u.week_ending = q.week_ending
     AND u.smartsheet_row_id = q.smartsheet_row_id
     AND u.role = q.role
    LEFT JOIN existing_rows AS e
      ON e.wr = q.wr
     AND e.week_ending = q.week_ending
     AND e.smartsheet_row_id = q.smartsheet_row_id;
END;
$$;
-- <<<<<<<< STEP 4 SELECTION ENDS HERE (the line above, `$$;`, must be included) <<<<<<<<


-- ── STEP 5 -- GRANT ───────────────────────────────────────────
-- service_role only. This function can rewrite billing attribution,
-- so it must NEVER be granted to the anon or authenticated Supabase
-- roles -- those are reachable from the browser-facing portal-v2
-- client and would turn an attribution rewrite into a public write
-- surface (T-12-12).
-- Postgres grants EXECUTE on a new function to PUBLIC by default, so a
-- GRANT alone leaves anon / authenticated able to call the RPC (seen
-- live 2026-09-03). The REVOKE makes the documented service_role-only
-- contract true; re-run STEP 5 after every STEP 4 (DROP resets both).
REVOKE ALL ON FUNCTION billing_audit.backfill_attribution(jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION billing_audit.backfill_attribution(jsonb) TO service_role;

-- Required after STEP 4/5 so PostgREST picks up the new function
-- signature and grant immediately, matching the existing
-- lookup_attribution / lookup_attribution_bulk OPERATOR instructions
-- (billing_audit/schema.sql:246-248, 296-300).
NOTIFY pgrst, 'reload schema';
