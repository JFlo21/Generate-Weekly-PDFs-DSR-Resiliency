-- pipeline_memory/helper2_columns_migration.sql
-- APPLIED 2026-09-09 02:21:29Z as Supabase migration 20260909022129_helper2_row_state_columns_marker_and_rpc
-- together with the schema.sql RPC block (D-14-13-DDL-APPLIED / D-14-13-VERIFIED in 14-DECISIONS.md).
-- Phase 14 Plan 12 (O-14-B closure): additive DDL for D-14-08-APPLIED
-- (row_state Helper #2 columns) and D-14-10-APPLIED (sheet_registry
-- mapping-schema marker). Both decisions were owner-approved on
-- 2026-09-06; the apply itself was owner-delegated on 2026-09-08.
--
-- OWNER-APPLIED. Nothing in this repo executes any statement in this
-- file. Apply in Supabase project poeyztlmsawfoqlanucc (SQL Editor or an
-- owner-delegated migration), THEN re-run the reapply-safe
-- pipeline_memory.upsert_rows_bulk block of pipeline_memory/schema.sql so
-- the RPC's column lists reference the new columns. The RPC body is
-- deliberately NOT duplicated here (one source of truth: schema.sql;
-- tests/test_upsert_rows_bulk_helper2_contract.py pins both files).
--
-- Additive and idempotent: ADD COLUMN IF NOT EXISTS, nullable, no index,
-- no constraint, no data migration, no default (so no table rewrite --
-- a brief ACCESS EXCLUSIVE metadata lock only). Code on either side of
-- the apply is safe: old code ignores the columns; new code degrades
-- when they are absent (pipeline_memory/writer.py fail-open contract,
-- pipeline_memory/reader.py mapping_schema degrade). Rollback = drop the
-- five columns; the pre-state (column lists, RPC definition, grants,
-- search_path pin) is parked in the owner's vault raw folder under
-- "2026-09-08 - pipeline_memory upsert_rows_bulk pre-state ...".
--
-- Sequencing (O-14-B record): apply this file and the RPC block in ONE
-- session, outside a scheduled-run window (check `gh run list
-- --workflow weekly-excel-generation.yml` at the moment of applying).

-- STEP 1: row_state Helper #2 business columns (HASH_FIELDS members
-- 17-20; same shapes as their Helper #1 counterparts).
ALTER TABLE pipeline_memory.row_state
    ADD COLUMN IF NOT EXISTS helper2_observed  TEXT;
ALTER TABLE pipeline_memory.row_state
    ADD COLUMN IF NOT EXISTS helper2_completed BOOLEAN;
ALTER TABLE pipeline_memory.row_state
    ADD COLUMN IF NOT EXISTS helper2_dept      TEXT;
ALTER TABLE pipeline_memory.row_state
    ADD COLUMN IF NOT EXISTS helper2_job       TEXT;

-- STEP 2: sheet_registry mapping-schema marker. NULL on every existing
-- row => each sheet takes exactly one full validation on the next run,
-- after which discovery writes MAPPING_SCHEMA_MARKER ('helper2-v1').
ALTER TABLE pipeline_memory.sheet_registry
    ADD COLUMN IF NOT EXISTS mapping_schema TEXT;

-- STEP 3 (not in this file): re-run the pipeline_memory.upsert_rows_bulk
-- CREATE OR REPLACE FUNCTION block from pipeline_memory/schema.sql.

-- Read-back (expected after STEP 1-3):
--   SELECT column_name FROM information_schema.columns
--    WHERE table_schema = 'pipeline_memory' AND table_name = 'row_state'
--      AND column_name LIKE 'helper2%';                      -- 4 rows
--   SELECT column_name FROM information_schema.columns
--    WHERE table_schema = 'pipeline_memory'
--      AND table_name = 'sheet_registry'
--      AND column_name = 'mapping_schema';                   -- 1 row
--   SELECT position('helper2_observed' IN pg_get_functiondef(
--            'pipeline_memory.upsert_rows_bulk(bigint,text,jsonb)'
--            ::regprocedure)) > 0;                           -- true
--   SELECT grantee, privilege_type
--     FROM information_schema.role_routine_grants
--    WHERE specific_schema = 'pipeline_memory'
--      AND routine_name = 'upsert_rows_bulk';  -- service_role EXECUTE kept
