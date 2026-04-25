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

-- Seed the flags the pipeline currently reads. Insert defaults
-- only — re-running this block will not clobber operator edits.
INSERT INTO billing_audit.feature_flag (flag_key, enabled)
VALUES ('emit_assignment_fingerprint', FALSE)
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

CREATE INDEX IF NOT EXISTS idx_pipeline_run_wr_week_created_at
    ON billing_audit.pipeline_run (wr, week_ending, created_at DESC);

-- Idempotent column-add guard for environments that have an
-- older partial pipeline_run table from a pre-2026-04-25 deploy.
-- Safe to re-run; ``ADD COLUMN IF NOT EXISTS`` is a no-op when
-- the column is already present.
ALTER TABLE billing_audit.pipeline_run
    ADD COLUMN IF NOT EXISTS content_hash    TEXT,
    ADD COLUMN IF NOT EXISTS assignment_fp   TEXT,
    ADD COLUMN IF NOT EXISTS completed_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS total_count     INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS release         TEXT,
    ADD COLUMN IF NOT EXISTS created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW();

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
