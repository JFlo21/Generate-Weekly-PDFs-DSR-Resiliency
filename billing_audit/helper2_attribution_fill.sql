-- ============================================================
-- billing_audit/helper2_attribution_fill.sql
--
-- OWNER-APPLIED. Nothing in this repo executes any statement in this
-- file at runtime -- no Python script, pipeline module, or CI job
-- ever runs this SQL. Apply only after the Phase 14 Plan 11 Task 3
-- decision checkpoint authorizes it (.planning/phases/14-foreman-
-- helper-2/14-DECISIONS.md, O-14-C), by the owner or by a session
-- under the owner's explicit delegation, in a run-free window
-- confirmed by `gh run list` immediately before applying (the window
-- lesson recorded in D-14-07-APPLIED: check right before applying,
-- not minutes before).
--
-- Phase 14 (Foreman Helper #2), requirement HLP-06, closing O-14-C.
-- The deployed ``freeze_attribution`` (migration 20260908165511,
-- D-14-07-APPLIED / D-14-07-VERIFIED) is per-ROW first-write-wins:
-- ``ON CONFLICT (wr, week_ending, smartsheet_row_id) DO NOTHING``.
-- A row frozen BEFORE it carried a Helper #2 keeps ``frozen_helper2``
-- NULL forever, because the pipeline never re-sends an already-frozen
-- row (until Phase 14 plan 14-11 Task 1's admission gate, which is
-- inert against the deployed function until this file applies -- a
-- re-sent row hits DO NOTHING today and is counted already-frozen,
-- exactly as before). This file gives Helper #2 -- and ONLY Helper
-- #2 -- first-write-wins PER ROLE: the function fills the two
-- Helper #2 columns on conflict when they are still empty, without
-- touching any other column of the row.
--
-- WHAT THIS FILE DOES NOT DO: it does not change what
-- freeze_attribution does to frozen_primary, frozen_helper,
-- frozen_helper_dept, or frozen_vac_crew -- those keep today's
-- per-ROW first-write-wins (ON CONFLICT DO NOTHING is unaffected for
-- them; the DO UPDATE below only ever assigns Helper #2 columns and
-- the provenance map). It does not touch
-- billing_audit.backfill_attribution, billing_audit.lookup_attribution,
-- or billing_audit.lookup_attribution_bulk. It does not set
-- backfill_source or backfill_run_id (those mean "the most recent
-- BACKFILL write"; a live fill from the pipeline is not a backfill) --
-- only the per-role backfill_provenance JSONB map gains a 'helper2'
-- entry with source 'live', mirroring the Phase 12 / OWN-03 per-role
-- provenance shape (billing_audit/own03_backfill_attribution.sql).
--
-- SAFETY: CREATE OR REPLACE on the IDENTICAL 14-parameter signature
-- (position, name, and type unchanged) -- never DROP. Grants and the
-- PostgREST schema cache survive a CREATE OR REPLACE untouched; the
-- NOTIFY at the end is a courtesy so PostgREST re-reads the function
-- body promptly, not a requirement for correctness.
--
-- PER-ROLE WRITE GUARANTEE: the ON CONFLICT DO UPDATE's SET list
-- names ONLY frozen_helper2, frozen_helper2_dept, and
-- backfill_provenance. It is gated in both directions:
--   - the CURRENT frozen_helper2 must be a sentinel (NULL, blank,
--     '#...', or a named unknown) for the update to fire at all
--     (is_sentinel_value(s.frozen_helper2));
--   - the INCOMING Helper #2 must be a real, non-sentinel value
--     (NOT is_sentinel_value(EXCLUDED.frozen_helper2)) -- a 12-
--     argument call (the currently deployed writer, or any future
--     call whose Helper #2 resolves to NULL) leaves
--     EXCLUDED.frozen_helper2 NULL, is_sentinel_value(NULL) is TRUE,
--     NOT TRUE is FALSE, so the WHERE is false and the UPDATE
--     touches nothing -- proving the deployed writer is unaffected
--     by this apply until the code merges.
--
-- Run STEP 1 through STEP 3 in order, top to bottom. STEP 1 is the
-- rollback capture AND a self-check gate: if the live body it reads
-- back differs from the body embedded in STEP 2, in anything OTHER
-- than the ON CONFLICT clause, STOP -- this file must be re-derived
-- from the live body, never applied over an unknown one. The body
-- embedded in STEP 2 below was derived from the verbatim pre-14-09
-- body (parked in the vault raw folder named in D-14-07-APPLIED) plus
-- the exact splice D-14-07-APPLIED records (frozen_helper2,
-- frozen_helper2_dept added to the INSERT list, positioned after
-- frozen_vac_crew and before source_release/source_run_id; the two
-- new parameters appended LAST with DEFAULT NULL, same reason as
-- 14-09: Postgres rejects a non-defaulted parameter after a defaulted
-- one, and PostgREST binds by name so position never affects the
-- writer). STEP 1's live re-check is what makes it safe to apply a
-- derived body instead of re-deriving it from a fresh
-- pg_get_functiondef at write time.
-- ============================================================


-- ── STEP 1 -- ROLLBACK CAPTURE (read-only) + SELF-CHECK GATE ──
-- Save both result sets below before continuing. This is the
-- rollback reference for O-14-C-APPLIED (re-apply this captured body
-- via CREATE OR REPLACE, same signature, no window needed, no data
-- destroyed -- a fill only ever wrote into columns that were null or
-- sentinel).
SELECT pg_catalog.pg_get_functiondef(p.oid) AS pre_apply_definition
FROM pg_catalog.pg_proc AS p
JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
WHERE n.nspname = 'billing_audit'
  AND p.proname = 'freeze_attribution';

SELECT grantee, privilege_type
FROM information_schema.role_routine_grants
WHERE routine_schema = 'billing_audit'
  AND routine_name = 'freeze_attribution'
ORDER BY grantee;

-- SELF-CHECK: compare the definition above against STEP 2's embedded
-- body below. If they differ in anything OTHER than the ON CONFLICT
-- clause (parameter list, RETURNS, LANGUAGE, search_path, the
-- DECLARE/BEGIN body up to the ON CONFLICT line, or the IF/SELECT
-- fallback and RETURN), STOP. Do not run STEP 2 over an unknown body.


-- ── STEP 2 -- PER-ROLE HELPER #2 FILL ────────────────────────
-- Deployed 14-parameter signature and order (D-14-07-APPLIED):
-- p_wr, p_week_ending, p_smartsheet_row_id, p_pole, p_cu,
-- p_work_type, p_primary, p_helper, p_helper_dept, p_vac_crew,
-- p_release, p_run_id, p_helper2, p_helper2_dept -- unchanged, same
-- names, same positions, same types. RETURNS, LANGUAGE, and
-- SET search_path TO '' unchanged. The INSERT gains the alias AS s
-- (so the WHERE clause below can reference the pre-conflict row via
-- s.* alongside the proposed row via EXCLUDED.*); the INSERT column
-- list, VALUES list, and everything before ON CONFLICT are otherwise
-- byte-identical to the deployed body. The ONLY semantic change is
-- the ON CONFLICT clause: DO NOTHING becomes a gated DO UPDATE that
-- writes ONLY the two Helper #2 columns and the provenance map.
CREATE OR REPLACE FUNCTION billing_audit.freeze_attribution(
    p_wr                TEXT,
    p_week_ending       DATE,
    p_smartsheet_row_id BIGINT,
    p_pole              TEXT,
    p_cu                TEXT,
    p_work_type         TEXT,
    p_primary           TEXT,
    p_helper            TEXT,
    p_helper_dept       TEXT,
    p_vac_crew          TEXT,
    p_release           TEXT,
    p_run_id            TEXT,
    p_helper2           TEXT DEFAULT NULL,
    p_helper2_dept      TEXT DEFAULT NULL
)
RETURNS billing_audit.attribution_snapshot
LANGUAGE plpgsql
SET search_path TO ''
AS $function$
DECLARE
  v_result billing_audit.attribution_snapshot;
BEGIN
  INSERT INTO billing_audit.attribution_snapshot AS s (
    wr, week_ending, smartsheet_row_id,
    pole, cu, work_type,
    frozen_primary, frozen_helper, frozen_helper_dept, frozen_vac_crew,
    frozen_helper2, frozen_helper2_dept,
    source_release, source_run_id
  ) VALUES (
    p_wr, p_week_ending, p_smartsheet_row_id,
    p_pole, p_cu, p_work_type,
    p_primary, p_helper, p_helper_dept, p_vac_crew,
    p_helper2, p_helper2_dept,
    p_release, p_run_id
  )
  ON CONFLICT (wr, week_ending, smartsheet_row_id) DO UPDATE
  SET frozen_helper2      = EXCLUDED.frozen_helper2,
      frozen_helper2_dept = EXCLUDED.frozen_helper2_dept,
      backfill_provenance = COALESCE(s.backfill_provenance, '{}'::pg_catalog.jsonb)
          || pg_catalog.jsonb_build_object('helper2',
                 pg_catalog.jsonb_build_object('source', 'live', 'run_id', EXCLUDED.source_run_id))
  WHERE billing_audit.is_sentinel_value(s.frozen_helper2)
    AND NOT billing_audit.is_sentinel_value(EXCLUDED.frozen_helper2)
  RETURNING * INTO v_result;

  IF v_result.wr IS NULL THEN
    SELECT * INTO v_result
    FROM billing_audit.attribution_snapshot
    WHERE wr                = p_wr
      AND week_ending       = p_week_ending
      AND smartsheet_row_id = p_smartsheet_row_id;
  END IF;

  RETURN v_result;
END;
$function$;

NOTIFY pgrst, 'reload schema';


-- ── STEP 3 -- READ-BACK SHAPE CHECK, THEN SYNTHETIC-ROW PROOF ──
-- 3a (read-only): confirm the DO UPDATE clause landed.
SELECT pg_catalog.pg_get_functiondef(p.oid) AS post_apply_definition
FROM pg_catalog.pg_proc AS p
JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
WHERE n.nspname = 'billing_audit'
  AND p.proname = 'freeze_attribution';
-- Expect the output to contain:
--   ON CONFLICT (wr, week_ending, smartsheet_row_id) DO UPDATE
-- If it still reads DO NOTHING, STOP -- the apply did not land.

-- 3b -- synthetic-row procedure. Same synthetic key 14-09's Task 3
-- used (ZZ-HELPER2-VERIFY, 2000-01-01, D-14-07-VERIFIED check 3), row
-- ids 1 and 2. All rows deleted at the end of this step, count 0
-- confirmed, regardless of outcome -- this key cannot exist in
-- Smartsheet.

-- Call 1 -- row 1, 12-argument named call (Helper #2 absent): the
-- fresh-insert path, unaffected by this file's change.
SELECT * FROM billing_audit.freeze_attribution(
    p_wr => 'ZZ-HELPER2-VERIFY', p_week_ending => '2000-01-01'::date,
    p_smartsheet_row_id => 1,
    p_pole => 'POLE-1', p_cu => 'CU-1', p_work_type => 'Install',
    p_primary => 'Verify Primary', p_helper => 'Verify Helper',
    p_helper_dept => 'DEPT-1', p_vac_crew => NULL,
    p_release => 'verify', p_run_id => 'verify-run-1'
);

-- Call 2 -- row 1, 14-argument call, a valid Helper #2, and
-- DIFFERENT primary/helper/vac_crew values than Call 1. Expect:
-- frozen_helper2 / frozen_helper2_dept filled;
-- backfill_provenance.helper2 = {"source": "live", "run_id":
-- "verify-run-2"}; every other column byte-identical to Call 1's
-- result, INCLUDING frozen_at and source_run_id (the different
-- primary/helper/vac_crew/release/run_id sent on this call must NOT
-- appear anywhere in the returned row).
SELECT * FROM billing_audit.freeze_attribution(
    p_wr => 'ZZ-HELPER2-VERIFY', p_week_ending => '2000-01-01'::date,
    p_smartsheet_row_id => 1,
    p_pole => 'POLE-DIFFERENT', p_cu => 'CU-DIFFERENT',
    p_work_type => 'Different Type', p_primary => 'Different Primary',
    p_helper => 'Different Helper', p_helper_dept => 'DEPT-DIFFERENT',
    p_vac_crew => 'Different Vac Crew', p_release => 'verify-2',
    p_run_id => 'verify-run-2',
    p_helper2 => 'Verify Helper2', p_helper2_dept => 'DEPT-H2'
);

-- Call 3 -- row 1, 14-argument call, a DIFFERENT Helper #2 than
-- Call 2. Expect: unchanged from Call 2's result -- first-write-wins
-- PER ROLE refuses the second Helper #2 claim (is_sentinel_value on
-- the now-real frozen_helper2 is FALSE, so the WHERE is false).
SELECT * FROM billing_audit.freeze_attribution(
    p_wr => 'ZZ-HELPER2-VERIFY', p_week_ending => '2000-01-01'::date,
    p_smartsheet_row_id => 1,
    p_pole => 'POLE-1', p_cu => 'CU-1', p_work_type => 'Install',
    p_primary => 'Verify Primary', p_helper => 'Verify Helper',
    p_helper_dept => 'DEPT-1', p_vac_crew => NULL,
    p_release => 'verify', p_run_id => 'verify-run-3',
    p_helper2 => 'A Second Different Helper2',
    p_helper2_dept => 'DEPT-H2-OTHER'
);

-- Call 4 -- row 2, 14-argument call, a FRESH row (never frozen
-- before). Expect: a normal insert carrying Helper #2 and NO
-- backfill_provenance entry -- the insert path is untouched by this
-- file, so it never writes provenance.
SELECT * FROM billing_audit.freeze_attribution(
    p_wr => 'ZZ-HELPER2-VERIFY', p_week_ending => '2000-01-01'::date,
    p_smartsheet_row_id => 2,
    p_pole => 'POLE-2', p_cu => 'CU-2', p_work_type => 'Install',
    p_primary => 'Row Two Primary', p_helper => 'Row Two Helper',
    p_helper_dept => 'DEPT-2', p_vac_crew => NULL,
    p_release => 'verify', p_run_id => 'verify-run-4',
    p_helper2 => 'Row Two Helper2', p_helper2_dept => 'DEPT-2-H2'
);

-- 3c -- cleanup. Delete both synthetic rows; confirm the count is 0
-- afterward (the synthetic key cannot exist in Smartsheet, so this
-- DELETE can never touch a real billing row).
DELETE FROM billing_audit.attribution_snapshot
WHERE wr = 'ZZ-HELPER2-VERIFY' AND week_ending = '2000-01-01'::date;

SELECT count(*) AS remaining_synthetic_rows
FROM billing_audit.attribution_snapshot
WHERE wr = 'ZZ-HELPER2-VERIFY';
-- Expect 0.

-- Task 3 (.planning/phases/14-foreman-helper-2/14-DECISIONS.md)
-- records the five synthetic-row observations from Calls 1-4 and the
-- STEP 3c cleanup confirmation as O-14-C-VERIFIED: fill happened,
-- other columns byte-identical, provenance present, second fill
-- refused, fresh insert carries no provenance.
