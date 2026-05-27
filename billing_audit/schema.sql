-- ============================================================
-- Canonical DDL for the ``billing_audit`` Supabase schema.
--
-- This file is documentation-grade SQL. It is NOT auto-applied by
-- the Python pipeline — apply it manually in the Supabase SQL
-- Editor (Project Settings → SQL Editor) the first time you wire
-- the ``billing_audit`` integration to a new project, and again
-- whenever this file is updated to add a column.
--
-- After running, also confirm in:
--   Supabase → Project Settings → API → Data API Settings →
--     "Exposed schemas"
-- that ``billing_audit`` is in the exposed list, then click
-- "Reload schema cache". Without this step PostgREST returns
-- HTTP 406 PGRST106 on every call (see CLAUDE.md Living Ledger
-- entry [2026-04-24 10:50] for the operator runbook).
--
-- The Python writer/reader contract is enforced in
-- ``billing_audit/writer.py`` (``emit_run_fingerprint``,
-- ``freeze_row``, ``any_flag_enabled``). If you add or rename
-- columns here, you MUST update those call sites in the same
-- PR — the deployed schema and the Python code share an
-- implicit contract that this file documents.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS billing_audit;

-- ── feature_flag ────────────────────────────────────────────
-- Read-only-ish boolean kill switches. Each row gates a single
-- billing_audit feature for the running pipeline (e.g.
-- ``emit_assignment_fingerprint``).
CREATE TABLE IF NOT EXISTS billing_audit.feature_flag (
    flag_key   TEXT NOT NULL PRIMARY KEY,
    enabled    BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed the flags the pipeline currently reads. Both flags are
-- defined in ``billing_audit/writer.py`` (``_FLAG_WRITE`` and
-- ``_FLAG_FINGERPRINT``). Seed both as FALSE so a fresh deploy
-- is safe-by-default — operators enable the feature explicitly
-- via an UPDATE against this table. ON CONFLICT DO NOTHING
-- preserves operator edits on re-run.
INSERT INTO billing_audit.feature_flag (flag_key, enabled)
VALUES
    ('write_attribution_snapshot', FALSE),
    ('emit_assignment_fingerprint', FALSE)
ON CONFLICT (flag_key) DO NOTHING;

-- ── pipeline_run ────────────────────────────────────────────
-- One row per (work request, week-ending, run_id) that
-- ``emit_run_fingerprint`` has written. Read back by
-- ``pipeline_run_select`` to detect mid-week assignment changes
-- (drift between the prior run's ``assignment_fp`` and the
-- current run's). The PK matches ``on_conflict`` in the writer.
--
-- IMPORTANT: every column referenced in
-- ``billing_audit/writer.py`` ``emit_run_fingerprint`` MUST
-- appear here. The original deploy on 2026-04-23 shipped the
-- writer code without this DDL, which is what caused the
-- HTTP 400 spam in the 2026-04-24 weekly run (see CLAUDE.md
-- Living Ledger entry [2026-04-25] for the postmortem).
CREATE TABLE IF NOT EXISTS billing_audit.pipeline_run (
    wr               TEXT        NOT NULL,
    week_ending      DATE        NOT NULL,
    run_id           TEXT        NOT NULL,
    content_hash     TEXT,
    assignment_fp    TEXT,
    completed_count  INTEGER     NOT NULL DEFAULT 0,
    total_count      INTEGER     NOT NULL DEFAULT 0,
    release          TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (wr, week_ending, run_id)
);

-- Idempotent column-add guard for environments that have an
-- older partial pipeline_run table from a pre-2026-04-25 deploy.
-- Safe to re-run; ``ADD COLUMN IF NOT EXISTS`` is a no-op when
-- the column is already present.
--
-- This MUST run BEFORE the CREATE INDEX below, because the index
-- references ``created_at``. On a partial-deploy environment
-- where the table exists without ``created_at``, running
-- ``CREATE INDEX ... (created_at DESC)`` first would fail,
-- Supabase SQL Editor halts on the first error, and this
-- ALTER TABLE never runs — leaving the schema stuck. Order:
-- CREATE TABLE (no-op if exists) → ALTER TABLE (backfill
-- columns) → CREATE INDEX (now safe).
ALTER TABLE billing_audit.pipeline_run
    ADD COLUMN IF NOT EXISTS content_hash    TEXT,
    ADD COLUMN IF NOT EXISTS assignment_fp   TEXT,
    ADD COLUMN IF NOT EXISTS completed_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS total_count     INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS release         TEXT,
    ADD COLUMN IF NOT EXISTS created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- ── Phase 1 SUB-07: variant attribution (D-18) ──────────────
-- Records which variant produced each pipeline_run row:
-- 'primary' | 'helper' | 'vac_crew' | 'aep_billable' |
-- 'reduced_sub' | 'aep_billable_helper' | 'reduced_sub_helper'.
-- TEXT (not enum / not CHECK constraint) for forward
-- compatibility — new variants can be introduced by the writer
-- without a second schema migration. NULL on existing
-- pre-2026-05-14 rows; readers / aggregators MUST tolerate NULL.
--
-- Writer surface (per Blocker 1 Path B / Phase 1 plan 05):
-- this column is populated ONLY by ``emit_run_fingerprint``'s
-- upsert into pipeline_run. The ``freeze_attribution`` RPC's
-- parameter contract (documented at the RPC contract block
-- below) is UNCHANGED — no parameter for variant is added to
-- the RPC, because ``freeze_attribution`` writes to a
-- different table (``attribution_snapshot``) and recording
-- variant there would require a coordinated Supabase
-- Dashboard function update that serves no audit-query need
-- that ``pipeline_run.variant`` doesn't already serve.
--
-- Position: AFTER the column-add block above and BEFORE the
-- CREATE INDEX below (same ordering rule as documented in the
-- 2026-04-25 commentary at L77-88 — every ALTER TABLE must
-- precede the CREATE INDEX so partial-deploy environments
-- upgrade in one apply).
ALTER TABLE billing_audit.pipeline_run
    ADD COLUMN IF NOT EXISTS variant TEXT;

CREATE INDEX IF NOT EXISTS idx_pipeline_run_wr_week_created_at
    ON billing_audit.pipeline_run (wr, week_ending, created_at DESC);

-- ── group_content_hash (Sub-project E) ──────────────────────
-- Durable per-group change-detection hash store. Keyed on the same
-- 4-tuple as the engine's history_key (f"{wr}|{week}|{variant}|{identifier}").
-- ``identifier`` defaults to '' for bare primary / legacy-shape groups,
-- matching the engine's '{wr}|{week}|{variant}|' json key.
--
-- This durable store replaces (when SUPABASE_HASH_STORE_AUTHORITATIVE)
-- the role of (a) the ephemeral local hash_history.json and (b) the
-- 16-char hash token embedded in the attachment filename. Once a row
-- exists here, generated filenames no longer need to carry the hash.
--
-- OPERATOR: this DDL must be applied to the Supabase project and the
-- PostgREST schema cache reloaded (NOTIFY pgrst, 'reload schema';)
-- before the store can be read/written. Until then the lookup surfaces
-- as 'fetch_failure' (creds are configured but the table/schema cache
-- isn't ready — a PGRST/SQLSTATE error; PGRST106 also trips the run-
-- global kill), and the pipeline falls back to hash_history.json and
-- behaves exactly as before (fail-safe to regenerate).
CREATE TABLE IF NOT EXISTS billing_audit.group_content_hash (
    wr            TEXT        NOT NULL,
    week_ending   DATE        NOT NULL,
    variant       TEXT        NOT NULL,
    identifier    TEXT        NOT NULL DEFAULT '',
    content_hash  TEXT        NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (wr, week_ending, variant, identifier)
);

-- Backfill-safe column adds (mirrors the pipeline_run convention) so a
-- partial-deploy environment can be brought current without DROP. The
-- canonical CREATE TABLE above is authoritative for a fresh deploy
-- (content_hash NOT NULL). The backfill ALTER intentionally adds
-- content_hash as NULLABLE: it has no sensible default, and Postgres
-- rejects ``ADD COLUMN ... NOT NULL`` without a default on a table that
-- already has rows. This matches the pipeline_run pattern above, where
-- content_hash is likewise added nullable while count columns (which DO
-- have a sensible default) are added NOT NULL DEFAULT. updated_at carries
-- NOT NULL DEFAULT NOW() because NOW() is a valid backfill default.
ALTER TABLE billing_audit.group_content_hash
    ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE billing_audit.group_content_hash
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- ── freeze_attribution (RPC) ────────────────────────────────
-- The ``freeze_attribution`` Postgres function is NOT defined
-- here — its body is deployed and maintained directly in the
-- Supabase project, because it includes business-logic
-- attribution rules that are owned by the data team rather
-- than the pipeline. The pipeline's contract with it is:
--
--   PARAMETERS (all named, p_<name>):
--     p_wr               TEXT
--     p_week_ending      DATE
--     p_smartsheet_row_id BIGINT
--     p_primary          TEXT  (resolved foreman, may be NULL)
--     p_helper           TEXT  (helper foreman, NULL on primary rows)
--     p_helper_dept      TEXT
--     p_vac_crew         TEXT
--     p_pole             TEXT
--     p_cu               TEXT
--     p_work_type        TEXT
--     p_release          TEXT
--     p_run_id           TEXT
--
--   RETURNS: a row (or scalar) with ``source_run_id`` matching
--     ``p_run_id`` if THIS call wrote the snapshot, or a prior
--     run_id if a prior call already wrote it (first-write-wins).
--
-- The exact body lives in Supabase. Do NOT rename or change
-- the parameter names without the corresponding update in
-- ``billing_audit/writer.py:freeze_row``.

-- ── attribution_snapshot (READ surface) ─────────────────────
-- ``billing_audit.attribution_snapshot`` is the per-row personnel
-- snapshot table populated by ``freeze_attribution``. The Python
-- reader (``billing_audit.writer.lookup_attribution``) reads from
-- it via the ``lookup_attribution`` RPC defined below. PRIMARY
-- KEY shape: (wr, week_ending, smartsheet_row_id). Columns the
-- reader depends on: ``helper TEXT``, ``helper_dept TEXT``,
-- ``source_run_id TEXT``. Owned by the data team; pipeline must
-- tolerate column additions but the three names above are load-
-- bearing for Phase 1.1 Bug C claim-history attribution.
--
-- The table DDL itself is NOT defined here — it is deployed
-- and maintained directly in the Supabase project alongside
-- the ``freeze_attribution`` function body, because the
-- column set is owned by the data team (attribution rules,
-- partition keys, retention policy). The Python contract is
-- the three column names above plus the (wr, week_ending,
-- smartsheet_row_id) PK shape; everything else on this table
-- is opaque to the pipeline.

-- ── lookup_attribution (RPC) ────────────────────────────────
-- Read surface for Phase 1.1 Bug C AND the universal claim-
-- attribution effort (Foundation A, 2026-05-20). Returns ALL frozen
-- roles for ONE row so a single call serves any variant.
--
--   PARAMETERS (all named, p_<name>):
--     p_wr                TEXT
--     p_week_ending       DATE
--     p_smartsheet_row_id BIGINT
--
--   RETURNS: one row with
--     primary_foreman TEXT, helper TEXT, helper_dept TEXT,
--     vac_crew TEXT, source_run_id TEXT
--   or zero rows when no snapshot exists for the tuple.
--
-- Each role value is normalized: Smartsheet error tokens (anything
-- starting with '#', e.g. '#NO MATCH') and blank/whitespace-only
-- values are returned as NULL so the Python reader treats them as
-- "no claimer in this role".
--
-- The Python contract is enforced in billing_audit/writer.py
-- (_lookup_attribution_all / resolve_claimer). Do NOT rename the
-- returned column names without updating those call sites.
--
-- OPERATOR: apply this DROP + CREATE in the Supabase SQL Editor, then
-- run `NOTIFY pgrst, 'reload schema';` (or Project Settings → API →
-- Reload schema cache).
--
-- The DROP is REQUIRED: an earlier helper-only version of this function
-- returned (helper, helper_dept, source_run_id). Postgres CREATE OR
-- REPLACE FUNCTION cannot change a function's return columns, so a bare
-- CREATE OR REPLACE over the helper-only version fails with "cannot
-- change return type of existing function" — which is why the multi-role
-- contract silently never deployed (incident 2026-05-27). DROP FUNCTION
-- IF EXISTS first, then create the 5-column version below.
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
    source_run_id   TEXT
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        CASE WHEN s.frozen_primary     LIKE '#%' OR btrim(s.frozen_primary)     = '' THEN NULL ELSE s.frozen_primary     END AS primary_foreman,
        CASE WHEN s.frozen_helper      LIKE '#%' OR btrim(s.frozen_helper)      = '' THEN NULL ELSE s.frozen_helper      END AS helper,
        CASE WHEN s.frozen_helper_dept LIKE '#%' OR btrim(s.frozen_helper_dept) = '' THEN NULL ELSE s.frozen_helper_dept END AS helper_dept,
        CASE WHEN s.frozen_vac_crew    LIKE '#%' OR btrim(s.frozen_vac_crew)    = '' THEN NULL ELSE s.frozen_vac_crew    END AS vac_crew,
        s.source_run_id
    FROM billing_audit.attribution_snapshot AS s
    WHERE s.wr                = p_wr
      AND s.week_ending       = p_week_ending
      AND s.smartsheet_row_id = p_smartsheet_row_id
    LIMIT 1;
$$;

GRANT EXECUTE ON FUNCTION billing_audit.lookup_attribution(TEXT, DATE, BIGINT) TO service_role;

-- ── lookup_attribution_bulk (RPC) — Phase 2 (2026-05-26) ─────────────
-- Bulk generalization of lookup_attribution: accepts the run's
-- (wr, week_ending) set as a jsonb array and returns ALL matching
-- attribution_snapshot rows in one round-trip, applying the SAME
-- per-role #NO MATCH / blank -> NULL normalization (one source of
-- truth, D-01). Replaces ~137k per-row lookup_attribution RPCs/run.
--
-- OPERATOR: apply this CREATE OR REPLACE in the Supabase SQL Editor,
-- then run `NOTIFY pgrst, 'reload schema';` (or Project Settings ->
-- API -> Reload schema cache). Required before the bulk-prefetch fix
-- resolves real claimers at runtime (D-01 operator coordination,
-- mirrors the existing lookup_attribution deployment).
CREATE OR REPLACE FUNCTION billing_audit.lookup_attribution_bulk(
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
    source_run_id     TEXT
)
LANGUAGE sql
STABLE
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
        s.source_run_id
    FROM jsonb_to_recordset(p_wr_weeks) AS q(wr TEXT, week_ending DATE)
    JOIN billing_audit.attribution_snapshot AS s
      ON s.wr = q.wr AND s.week_ending = q.week_ending;
$$;

GRANT EXECUTE ON FUNCTION billing_audit.lookup_attribution_bulk(jsonb) TO service_role;
