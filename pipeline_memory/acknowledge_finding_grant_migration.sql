-- pipeline_memory/acknowledge_finding_grant_migration.sql
-- STATUS: NOT APPLIED. Do not run from CI, a script, or an MCP/SQL tool
-- without Juan's explicit go-ahead on the exact FORWARD SQL below.
--
-- PR #435 (Greptile P1): pipeline_memory.acknowledge_finding REVOKEs the
-- PUBLIC default EXECUTE but never GRANTs service_role, so only the owner
-- (postgres) can call it. Live read-back 2026-10-29: proacl =
-- {postgres=X/postgres}, service_role=false. The SQL editor (postgres)
-- still works; the service-role procedure gets permission denied.
--
-- Scope: privileges only. No function body, table, column, index, policy
-- or data change. anon / authenticated stay without EXECUTE.
--
-- FORWARD == the REVOKE/GRANT pair after the acknowledge_finding block in
-- pipeline_memory/schema.sql (pinned by
-- tests/test_audit_findings_sql_contract.py). REVOKE before GRANT, in one
-- transaction.
--
-- Read-back after FORWARD (read-only):
--   SELECT has_function_privilege('service_role',
--            'pipeline_memory.acknowledge_finding(text,text,text,text)',
--            'EXECUTE');                                           -- true
--   SELECT has_function_privilege('anon',
--            'pipeline_memory.acknowledge_finding(text,text,text,text)',
--            'EXECUTE');                                           -- false
--   SELECT has_function_privilege('authenticated',
--            'pipeline_memory.acknowledge_finding(text,text,text,text)',
--            'EXECUTE');                                           -- false

-- ── FORWARD ───────────────────────────────────────────────────────────
BEGIN;

REVOKE ALL ON FUNCTION pipeline_memory.acknowledge_finding(TEXT, TEXT, TEXT, TEXT)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION pipeline_memory.acknowledge_finding(TEXT, TEXT, TEXT, TEXT)
    TO service_role;

COMMIT;

-- ── ROLLBACK (commented; restores owner-only EXECUTE) ─────────────────
-- Run only on owner instruction.
--
--   BEGIN;
--   REVOKE EXECUTE ON FUNCTION pipeline_memory.acknowledge_finding(TEXT, TEXT, TEXT, TEXT) FROM service_role;
--   COMMIT;
