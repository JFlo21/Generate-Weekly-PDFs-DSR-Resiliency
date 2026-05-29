-- ============================================================================
-- portal_schema.sql -- Supabase data layer for the v1.1 Artifact Portal
-- ============================================================================
-- APPLY MANUALLY in the Supabase SQL Editor of the EXISTING project (the one
-- that also hosts billing_audit). This project applies SQL by hand -- there is
-- NO `supabase db push` / CLI migration. Idempotent -- safe to re-run.
--
-- `public` is exposed by PostgREST BY DEFAULT; do NOT remove it (or
-- billing_audit) from Project Settings -> API -> Exposed schemas. No
-- schema-cache reload is needed for `public` (contrast the billing_audit
-- rollout, which hit PGRST106 when its schema was not exposed).
--
-- Python writer contract: scripts/publish_artifacts_to_supabase.py upserts the
-- 9 snake_case columns below and dedupes on sha256 (on_conflict="sha256").
--
-- RLS uses a SECURITY DEFINER helper (current_user_role) instead of an inline
-- subquery on public.profiles, because a policy ON public.profiles that itself
-- SELECTs from public.profiles triggers "infinite recursion detected in policy
-- for relation profiles". The helper bypasses RLS, breaking the recursion.
-- Anti-patterns deliberately avoided: no USING (true); no CHECK on artifacts.variant.
-- ============================================================================

-- 1) Artifact metadata table (DATA-02; 9-column writer contract + id/created_at)
CREATE TABLE IF NOT EXISTS public.artifacts (
    id              uuid        NOT NULL DEFAULT gen_random_uuid(),
    work_request    text        NOT NULL,
    week_ending     date        NOT NULL,
    week_ending_fmt text        NOT NULL,
    variant         text        NOT NULL,
    filename        text        NOT NULL,
    storage_path    text        NOT NULL,
    size_bytes      bigint      NOT NULL DEFAULT 0,
    sha256          text        NOT NULL,
    run_id          text        NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (sha256)
);

-- Backfill-safe column guards (MUST precede CREATE INDEX -- the SQL Editor
-- halts on the first error, so add-column-if-not-exists runs before indexing).
ALTER TABLE public.artifacts ADD COLUMN IF NOT EXISTS week_ending_fmt text;
ALTER TABLE public.artifacts ADD COLUMN IF NOT EXISTS variant         text;
ALTER TABLE public.artifacts ADD COLUMN IF NOT EXISTS storage_path    text;
ALTER TABLE public.artifacts ADD COLUMN IF NOT EXISTS size_bytes      bigint DEFAULT 0;
ALTER TABLE public.artifacts ADD COLUMN IF NOT EXISTS sha256          text;
ALTER TABLE public.artifacts ADD COLUMN IF NOT EXISTS run_id          text;
ALTER TABLE public.artifacts ADD COLUMN IF NOT EXISTS created_at      timestamptz DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_artifacts_work_request ON public.artifacts (work_request, week_ending DESC);
CREATE INDEX IF NOT EXISTS idx_artifacts_week_ending  ON public.artifacts (week_ending DESC);

-- 2) Profiles (role) table (D-11; operator-controlled enum -- CHECK is correct here)
CREATE TABLE IF NOT EXISTS public.profiles (
    id   uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    role text NOT NULL DEFAULT 'pending'
              CHECK (role IN ('admin','billing','pending'))
);

-- 3) Recursion-safe role lookup (SECURITY DEFINER bypasses RLS).
CREATE OR REPLACE FUNCTION public.current_user_role()
RETURNS text
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT role FROM public.profiles WHERE id = auth.uid()
$$;

-- 4) Row-Level Security -- enable + role-aware policies (never USING (true)).
ALTER TABLE public.profiles  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.artifacts ENABLE ROW LEVEL SECURITY;

-- profiles: a user reads their own row; admins read/manage all rows.
DROP POLICY IF EXISTS profiles_self_read ON public.profiles;
CREATE POLICY profiles_self_read ON public.profiles
    FOR SELECT TO authenticated
    USING (auth.uid() = id);

DROP POLICY IF EXISTS profiles_admin_all ON public.profiles;
CREATE POLICY profiles_admin_all ON public.profiles
    FOR ALL TO authenticated
    USING (public.current_user_role() = 'admin')
    WITH CHECK (public.current_user_role() = 'admin');

-- artifacts: only admin/billing may read; pending + anonymous get nothing.
-- No INSERT/UPDATE policy -- the portal is read-only and the service_role
-- publish step bypasses RLS, so no write policy is needed.
DROP POLICY IF EXISTS artifacts_select_billing_or_admin ON public.artifacts;
CREATE POLICY artifacts_select_billing_or_admin ON public.artifacts
    FOR SELECT TO authenticated
    USING (public.current_user_role() IN ('admin','billing'));

-- 5) Storage SELECT policy -- REQUIRED for createSignedUrl on the private
-- excel-artifacts bucket (the single most commonly-missed policy here).
DROP POLICY IF EXISTS storage_artifacts_role_select ON storage.objects;
CREATE POLICY storage_artifacts_role_select ON storage.objects
    FOR SELECT TO authenticated
    USING (
        bucket_id = 'excel-artifacts'
        AND public.current_user_role() IN ('admin','billing')
    );
