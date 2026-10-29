-- pipeline_memory/upsert_audit_findings_grant_migration.sql
-- STATUS: NOT APPLIED. Owner approval required before any live apply.
-- Do not run from CI, a script, or an MCP/SQL tool without Juan's explicit
-- go-ahead on the exact FORWARD SQL below.
--
-- PR #435 (Copilot security finding): pipeline_memory.upsert_audit_findings
-- had no explicit EXECUTE contract, so it relied on Postgres' default
-- EXECUTE-to-PUBLIC grant for new functions -- reachable by anon /
-- authenticated through PostgREST (RLS still blocks the row writes).
-- This migration REVOKEs PUBLIC and GRANTs service_role, mirroring the
-- acknowledge_finding REVOKE and the upsert_rows_bulk GRANT.
--
-- Scope: privileges only. No function body, table, column, index, policy
-- or data change. The pipeline calls this RPC as service_role, which the
-- GRANT keeps. AUDIT_MEMORY_ENABLED is off in production, so no run calls
-- the RPC today either way.
--
-- FORWARD == the REVOKE/GRANT pair after the upsert_audit_findings block in
-- pipeline_memory/schema.sql (pinned by
-- tests/test_audit_findings_sql_contract.py). Apply outside a scheduled-run
-- window, REVOKE before GRANT, in one transaction.
--
-- Read-back after FORWARD (read-only):
--   SELECT has_function_privilege('service_role',
--            'pipeline_memory.upsert_audit_findings(text,jsonb,jsonb)',
--            'EXECUTE');                                           -- true
--   SELECT has_function_privilege('anon',
--            'pipeline_memory.upsert_audit_findings(text,jsonb,jsonb)',
--            'EXECUTE');                                           -- false
--   SELECT has_function_privilege('authenticated',
--            'pipeline_memory.upsert_audit_findings(text,jsonb,jsonb)',
--            'EXECUTE');                                           -- false

-- ── FORWARD ───────────────────────────────────────────────────────────
BEGIN;

REVOKE ALL ON FUNCTION pipeline_memory.upsert_audit_findings(TEXT, JSONB, JSONB)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION pipeline_memory.upsert_audit_findings(TEXT, JSONB, JSONB)
    TO service_role;

COMMIT;

-- ── ROLLBACK (commented; restores the prior PUBLIC default) ───────────
-- Run only on owner instruction. The explicit service_role GRANT is left in
-- place: it is a no-op once PUBLIC holds EXECUTE again.
--
--   BEGIN;
--   GRANT EXECUTE ON FUNCTION pipeline_memory.upsert_audit_findings(TEXT, JSONB, JSONB) TO PUBLIC;
--   COMMIT;
