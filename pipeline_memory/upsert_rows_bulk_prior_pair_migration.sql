-- pipeline_memory/upsert_rows_bulk_prior_pair_migration.sql
-- STATUS: NOT APPLIED (repo change only; nothing live has changed).
-- Phase 11 plan 11-14, G-11-37 minor mechanism C: upsert_rows_bulk also
-- returns the row's PRIOR (wr, week_ending) pair when its Work Request #
-- changed, so the OLD WR's group enters the D-04 candidate.
--
-- APPROVED by Juan 2026-10-29 (additive); live apply gated on the pre-apply
-- SQL review checkpoint (plan 11-14 Task 2): the exact FORWARD SQL below must
-- be shown to the owner and an explicit go-ahead received BEFORE
-- `apply_migration` runs. Target: Supabase project poeyztlmsawfoqlanucc.
--
-- Scope: ONE `CREATE OR REPLACE FUNCTION` on the UNCHANGED signature
-- (BIGINT, TEXT, JSONB) -> TABLE(wr TEXT, week_ending DATE). It keeps the
-- live `GRANT EXECUTE ... TO service_role` and the `SET search_path = ''`
-- pin. No table, column, index, constraint, policy or grant change; the
-- row_state / row_event writes and content_hash are untouched. The returned
-- set is a superset of today's (one extra branch), so scope can only widen.
-- No Excel regeneration or upload follows from applying it: the set feeds
-- only the shadow candidate and the (flag OFF) incremental path.
--
-- FORWARD == the upsert_rows_bulk block of pipeline_memory/schema.sql
-- (whitespace-normalised, pinned by
-- tests/test_upsert_rows_bulk_prior_pair_contract.py). ROLLBACK == the
-- verbatim pre-change body (tests/fixtures/incremental/upsert_rows_bulk_pre_g1137.sql).
-- Apply outside a scheduled-run window.
--
-- Read-back after FORWARD (read-only):
--   SELECT position('prior_wr' IN pg_get_functiondef(
--            'pipeline_memory.upsert_rows_bulk(bigint,text,jsonb)'
--            ::regprocedure)) > 0;                                 -- true
--   SELECT has_function_privilege('service_role',
--            'pipeline_memory.upsert_rows_bulk(bigint,text,jsonb)',
--            'EXECUTE');                                           -- true

-- ==== FORWARD ====
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
            q.helper2_observed, q.helper2_completed, q.helper2_dept, q.helper2_job,
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
            helper2_observed   TEXT,
            helper2_completed  BOOLEAN,
            helper2_dept       TEXT,
            helper2_job        TEXT,
            row_modified_at    TIMESTAMPTZ,
            content_hash       TEXT
        )
    ),
    prior AS (
        SELECT rs.row_id,
               rs.content_hash AS prior_hash,
               rs.week_ending  AS prior_week_ending
               , rs.wr AS prior_wr
        FROM pipeline_memory.row_state AS rs
        WHERE rs.sheet_id = p_sheet_id
          AND rs.row_id IN (SELECT i.row_id FROM incoming AS i)
    ),
    changed AS (
        SELECT
            i.*,
            p.prior_hash,
            p.prior_week_ending,
            p.prior_wr,
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
                'helper2_observed', c.helper2_observed,
                'helper2_completed', c.helper2_completed,
                'helper2_dept', c.helper2_dept,
                'helper2_job', c.helper2_job,
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
            -- Helper #2 (14-12) appended last, leading commas: the pre-commit
            -- working-tree tripwire (test_schema_changes_are_additive_only)
            -- stayed clean; tests/test_upsert_rows_bulk_helper2_contract.py
            -- is the CI guard that pins these lists to HASH_FIELDS.
            , helper2_observed, helper2_completed, helper2_dept, helper2_job
        )
        SELECT
            p_sheet_id, i.row_id, i.wr, i.week_ending, i.snapshot_date,
            i.cu, i.pole, i.work_type, i.quantity, i.units_total_price,
            i.units_completed, i.foreman_observed, i.helper_observed,
            i.helper_completed, i.helper_dept, i.helper_job,
            i.vac_crew_observed, i.vac_completed, i.row_modified_at,
            i.content_hash, p_run_id, p_run_id, p_run_id
            , i.helper2_observed, i.helper2_completed, i.helper2_dept, i.helper2_job
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
            helper2_observed = CASE WHEN pipeline_memory.row_state.content_hash
                                          IS DISTINCT FROM EXCLUDED.content_hash
                                     THEN EXCLUDED.helper2_observed
                                     ELSE pipeline_memory.row_state.helper2_observed END,
            helper2_completed = CASE WHEN pipeline_memory.row_state.content_hash
                                           IS DISTINCT FROM EXCLUDED.content_hash
                                      THEN EXCLUDED.helper2_completed
                                      ELSE pipeline_memory.row_state.helper2_completed END,
            helper2_dept = CASE WHEN pipeline_memory.row_state.content_hash
                                      IS DISTINCT FROM EXCLUDED.content_hash
                                 THEN EXCLUDED.helper2_dept
                                 ELSE pipeline_memory.row_state.helper2_dept END,
            helper2_job = CASE WHEN pipeline_memory.row_state.content_hash
                                     IS DISTINCT FROM EXCLUDED.content_hash
                                THEN EXCLUDED.helper2_job
                                ELSE pipeline_memory.row_state.helper2_job END,
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
    SELECT c.prior_wr, c.prior_week_ending
    FROM changed AS c
    WHERE c.prior_wr IS NOT NULL
      AND c.prior_week_ending IS NOT NULL
      AND c.prior_wr IS DISTINCT FROM c.wr
    UNION
    SELECT c.wr, c.prior_week_ending
    FROM changed AS c
    WHERE c.prior_week_ending IS NOT NULL
      AND c.prior_week_ending IS DISTINCT FROM c.week_ending;
END;
$$;

-- ==== ROLLBACK BEGIN (run this block to restore the pre-change function) ====
-- CREATE OR REPLACE FUNCTION pipeline_memory.upsert_rows_bulk(
--     p_sheet_id BIGINT,
--     p_run_id   TEXT,
--     p_rows     JSONB
-- )
-- RETURNS TABLE (wr TEXT, week_ending DATE)
-- LANGUAGE plpgsql
-- VOLATILE
-- SET search_path = ''
-- AS $$
-- BEGIN
--     RETURN QUERY
--     WITH incoming AS (
--         SELECT
--             q.row_id, q.wr, q.week_ending, q.snapshot_date, q.cu, q.pole,
--             q.work_type, q.quantity, q.units_total_price, q.units_completed,
--             q.foreman_observed, q.helper_observed, q.helper_completed,
--             q.helper_dept, q.helper_job, q.vac_crew_observed,
--             q.helper2_observed, q.helper2_completed, q.helper2_dept, q.helper2_job,
--             q.vac_completed, q.row_modified_at, q.content_hash
--         FROM jsonb_to_recordset(p_rows) AS q(
--             row_id             BIGINT,
--             wr                 TEXT,
--             week_ending        DATE,
--             snapshot_date      DATE,
--             cu                 TEXT,
--             pole               TEXT,
--             work_type          TEXT,
--             quantity           NUMERIC,
--             units_total_price  NUMERIC,
--             units_completed    BOOLEAN,
--             foreman_observed   TEXT,
--             helper_observed    TEXT,
--             helper_completed   BOOLEAN,
--             helper_dept        TEXT,
--             helper_job         TEXT,
--             vac_crew_observed  TEXT,
--             vac_completed      BOOLEAN,
--             helper2_observed   TEXT,
--             helper2_completed  BOOLEAN,
--             helper2_dept       TEXT,
--             helper2_job        TEXT,
--             row_modified_at    TIMESTAMPTZ,
--             content_hash       TEXT
--         )
--     ),
--     prior AS (
--         SELECT rs.row_id,
--                rs.content_hash AS prior_hash,
--                rs.week_ending  AS prior_week_ending
--         FROM pipeline_memory.row_state AS rs
--         WHERE rs.sheet_id = p_sheet_id
--           AND rs.row_id IN (SELECT i.row_id FROM incoming AS i)
--     ),
--     changed AS (
--         SELECT
--             i.*,
--             p.prior_hash,
--             p.prior_week_ending,
--             (p.row_id IS NULL) AS is_new
--         FROM incoming AS i
--         LEFT JOIN prior AS p ON p.row_id = i.row_id
--         WHERE p.prior_hash IS DISTINCT FROM i.content_hash
--     ),
--     ins_events AS (
--         INSERT INTO pipeline_memory.row_event (
--             sheet_id, row_id, run_id, change_kind, wr, week_ending,
--             after_image, source
--         )
--         SELECT
--             p_sheet_id,
--             c.row_id,
--             p_run_id,
--             CASE WHEN c.is_new THEN 'insert' ELSE 'update' END,
--             c.wr,
--             c.week_ending,
--             jsonb_build_object(
--                 'wr', c.wr,
--                 'week_ending', c.week_ending,
--                 'snapshot_date', c.snapshot_date,
--                 'cu', c.cu,
--                 'pole', c.pole,
--                 'work_type', c.work_type,
--                 'quantity', c.quantity,
--                 'units_total_price', c.units_total_price,
--                 'units_completed', c.units_completed,
--                 'foreman_observed', c.foreman_observed,
--                 'helper_observed', c.helper_observed,
--                 'helper_completed', c.helper_completed,
--                 'helper_dept', c.helper_dept,
--                 'helper_job', c.helper_job,
--                 'vac_crew_observed', c.vac_crew_observed,
--                 'vac_completed', c.vac_completed,
--                 'helper2_observed', c.helper2_observed,
--                 'helper2_completed', c.helper2_completed,
--                 'helper2_dept', c.helper2_dept,
--                 'helper2_job', c.helper2_job,
--                 'row_modified_at', c.row_modified_at,
--                 'content_hash', c.content_hash
--             ),
--             'live'
--         FROM changed AS c
--         RETURNING 1
--     ),
--     ins_state AS (
--         INSERT INTO pipeline_memory.row_state (
--             sheet_id, row_id, wr, week_ending, snapshot_date, cu, pole,
--             work_type, quantity, units_total_price, units_completed,
--             foreman_observed, helper_observed, helper_completed,
--             helper_dept, helper_job, vac_crew_observed, vac_completed,
--             row_modified_at, content_hash, first_seen_run, last_seen_run,
--             last_changed_run
--             -- Helper #2 (14-12) appended last, leading commas: the pre-commit
--             -- working-tree tripwire (test_schema_changes_are_additive_only)
--             -- stayed clean; tests/test_upsert_rows_bulk_helper2_contract.py
--             -- is the CI guard that pins these lists to HASH_FIELDS.
--             , helper2_observed, helper2_completed, helper2_dept, helper2_job
--         )
--         SELECT
--             p_sheet_id, i.row_id, i.wr, i.week_ending, i.snapshot_date,
--             i.cu, i.pole, i.work_type, i.quantity, i.units_total_price,
--             i.units_completed, i.foreman_observed, i.helper_observed,
--             i.helper_completed, i.helper_dept, i.helper_job,
--             i.vac_crew_observed, i.vac_completed, i.row_modified_at,
--             i.content_hash, p_run_id, p_run_id, p_run_id
--             , i.helper2_observed, i.helper2_completed, i.helper2_dept, i.helper2_job
--         FROM incoming AS i
--         ON CONFLICT (sheet_id, row_id) DO UPDATE SET
--             last_seen_run = p_run_id,
--             wr = CASE WHEN pipeline_memory.row_state.content_hash
--                            IS DISTINCT FROM EXCLUDED.content_hash
--                       THEN EXCLUDED.wr ELSE pipeline_memory.row_state.wr END,
--             week_ending = CASE WHEN pipeline_memory.row_state.content_hash
--                                     IS DISTINCT FROM EXCLUDED.content_hash
--                                THEN EXCLUDED.week_ending
--                                ELSE pipeline_memory.row_state.week_ending END,
--             snapshot_date = CASE WHEN pipeline_memory.row_state.content_hash
--                                        IS DISTINCT FROM EXCLUDED.content_hash
--                                   THEN EXCLUDED.snapshot_date
--                                   ELSE pipeline_memory.row_state.snapshot_date END,
--             cu = CASE WHEN pipeline_memory.row_state.content_hash
--                            IS DISTINCT FROM EXCLUDED.content_hash
--                       THEN EXCLUDED.cu ELSE pipeline_memory.row_state.cu END,
--             pole = CASE WHEN pipeline_memory.row_state.content_hash
--                              IS DISTINCT FROM EXCLUDED.content_hash
--                         THEN EXCLUDED.pole ELSE pipeline_memory.row_state.pole END,
--             work_type = CASE WHEN pipeline_memory.row_state.content_hash
--                                    IS DISTINCT FROM EXCLUDED.content_hash
--                               THEN EXCLUDED.work_type
--                               ELSE pipeline_memory.row_state.work_type END,
--             quantity = CASE WHEN pipeline_memory.row_state.content_hash
--                                   IS DISTINCT FROM EXCLUDED.content_hash
--                              THEN EXCLUDED.quantity
--                              ELSE pipeline_memory.row_state.quantity END,
--             units_total_price = CASE WHEN pipeline_memory.row_state.content_hash
--                                            IS DISTINCT FROM EXCLUDED.content_hash
--                                       THEN EXCLUDED.units_total_price
--                                       ELSE pipeline_memory.row_state.units_total_price END,
--             units_completed = CASE WHEN pipeline_memory.row_state.content_hash
--                                          IS DISTINCT FROM EXCLUDED.content_hash
--                                     THEN EXCLUDED.units_completed
--                                     ELSE pipeline_memory.row_state.units_completed END,
--             foreman_observed = CASE WHEN pipeline_memory.row_state.content_hash
--                                           IS DISTINCT FROM EXCLUDED.content_hash
--                                      THEN EXCLUDED.foreman_observed
--                                      ELSE pipeline_memory.row_state.foreman_observed END,
--             helper_observed = CASE WHEN pipeline_memory.row_state.content_hash
--                                          IS DISTINCT FROM EXCLUDED.content_hash
--                                     THEN EXCLUDED.helper_observed
--                                     ELSE pipeline_memory.row_state.helper_observed END,
--             helper_completed = CASE WHEN pipeline_memory.row_state.content_hash
--                                           IS DISTINCT FROM EXCLUDED.content_hash
--                                      THEN EXCLUDED.helper_completed
--                                      ELSE pipeline_memory.row_state.helper_completed END,
--             helper_dept = CASE WHEN pipeline_memory.row_state.content_hash
--                                      IS DISTINCT FROM EXCLUDED.content_hash
--                                 THEN EXCLUDED.helper_dept
--                                 ELSE pipeline_memory.row_state.helper_dept END,
--             helper_job = CASE WHEN pipeline_memory.row_state.content_hash
--                                     IS DISTINCT FROM EXCLUDED.content_hash
--                                THEN EXCLUDED.helper_job
--                                ELSE pipeline_memory.row_state.helper_job END,
--             vac_crew_observed = CASE WHEN pipeline_memory.row_state.content_hash
--                                            IS DISTINCT FROM EXCLUDED.content_hash
--                                       THEN EXCLUDED.vac_crew_observed
--                                       ELSE pipeline_memory.row_state.vac_crew_observed END,
--             vac_completed = CASE WHEN pipeline_memory.row_state.content_hash
--                                        IS DISTINCT FROM EXCLUDED.content_hash
--                                   THEN EXCLUDED.vac_completed
--                                   ELSE pipeline_memory.row_state.vac_completed END,
--             helper2_observed = CASE WHEN pipeline_memory.row_state.content_hash
--                                           IS DISTINCT FROM EXCLUDED.content_hash
--                                      THEN EXCLUDED.helper2_observed
--                                      ELSE pipeline_memory.row_state.helper2_observed END,
--             helper2_completed = CASE WHEN pipeline_memory.row_state.content_hash
--                                            IS DISTINCT FROM EXCLUDED.content_hash
--                                       THEN EXCLUDED.helper2_completed
--                                       ELSE pipeline_memory.row_state.helper2_completed END,
--             helper2_dept = CASE WHEN pipeline_memory.row_state.content_hash
--                                       IS DISTINCT FROM EXCLUDED.content_hash
--                                  THEN EXCLUDED.helper2_dept
--                                  ELSE pipeline_memory.row_state.helper2_dept END,
--             helper2_job = CASE WHEN pipeline_memory.row_state.content_hash
--                                      IS DISTINCT FROM EXCLUDED.content_hash
--                                 THEN EXCLUDED.helper2_job
--                                 ELSE pipeline_memory.row_state.helper2_job END,
--             row_modified_at = CASE WHEN pipeline_memory.row_state.content_hash
--                                          IS DISTINCT FROM EXCLUDED.content_hash
--                                     THEN EXCLUDED.row_modified_at
--                                     ELSE pipeline_memory.row_state.row_modified_at END,
--             content_hash = CASE WHEN pipeline_memory.row_state.content_hash
--                                       IS DISTINCT FROM EXCLUDED.content_hash
--                                  THEN EXCLUDED.content_hash
--                                  ELSE pipeline_memory.row_state.content_hash END,
--             last_changed_run = CASE WHEN pipeline_memory.row_state.content_hash
--                                           IS DISTINCT FROM EXCLUDED.content_hash
--                                      THEN p_run_id
--                                      ELSE pipeline_memory.row_state.last_changed_run END
--         RETURNING 1
--     )
--     SELECT c.wr, c.week_ending
--     FROM changed AS c
--     UNION
--     SELECT c.wr, c.prior_week_ending
--     FROM changed AS c
--     WHERE c.prior_week_ending IS NOT NULL
--       AND c.prior_week_ending IS DISTINCT FROM c.week_ending;
-- END;
-- $$;
-- ==== ROLLBACK END ====
