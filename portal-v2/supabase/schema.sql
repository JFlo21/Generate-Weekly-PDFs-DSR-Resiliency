-- ============================================================
-- Linetec Report Portal v2 — Supabase Schema
-- Run this entire file in the Supabase SQL Editor.
-- ============================================================

-- ────────────────────────────────────────────────────────────
-- 1. ENUM: user_role
-- ────────────────────────────────────────────────────────────
CREATE TYPE user_role AS ENUM ('admin', 'viewer', 'biller');

-- ────────────────────────────────────────────────────────────
-- 2. TABLE: profiles
--    One row per auth.users entry. Auto-created via trigger.
-- ────────────────────────────────────────────────────────────
CREATE TABLE profiles (
  id            UUID        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email         TEXT        NOT NULL,
  display_name  TEXT,
  role          user_role   NOT NULL DEFAULT 'viewer',
  is_active     BOOLEAN     NOT NULL DEFAULT true,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ────────────────────────────────────────────────────────────
-- 3. TABLE: activity_logs
-- ────────────────────────────────────────────────────────────
CREATE TABLE activity_logs (
  id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID        NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  action     TEXT        NOT NULL,
  resource   TEXT,
  metadata   JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ────────────────────────────────────────────────────────────
-- 4. TABLE: artifact_downloads
-- ────────────────────────────────────────────────────────────
CREATE TABLE artifact_downloads (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID        NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  artifact_name    TEXT        NOT NULL,
  artifact_url     TEXT        NOT NULL,
  file_size_bytes  BIGINT      NOT NULL DEFAULT 0,
  downloaded_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ────────────────────────────────────────────────────────────
-- 5. INDEXES
-- ────────────────────────────────────────────────────────────
CREATE INDEX idx_activity_logs_user_id    ON activity_logs(user_id);
CREATE INDEX idx_activity_logs_created_at ON activity_logs(created_at DESC);
CREATE INDEX idx_activity_logs_action     ON activity_logs(action);

CREATE INDEX idx_artifact_downloads_user_id      ON artifact_downloads(user_id);
CREATE INDEX idx_artifact_downloads_downloaded_at ON artifact_downloads(downloaded_at DESC);

-- ────────────────────────────────────────────────────────────
-- 6. TRIGGER: auto-update updated_at on profiles
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER profiles_updated_at
  BEFORE UPDATE ON profiles
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at();

-- ────────────────────────────────────────────────────────────
-- 7. TRIGGER: auto-create profile when a new user signs up
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO profiles (id, email, role)
  VALUES (NEW.id, NEW.email, 'viewer')
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION handle_new_user();

-- ────────────────────────────────────────────────────────────
-- 8. ROW LEVEL SECURITY (RLS)
-- ────────────────────────────────────────────────────────────
ALTER TABLE profiles          ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity_logs     ENABLE ROW LEVEL SECURITY;
ALTER TABLE artifact_downloads ENABLE ROW LEVEL SECURITY;

-- profiles: users see own row; admins see all
CREATE POLICY "profiles_select_own"
  ON profiles FOR SELECT
  USING (
    auth.uid() = id
    OR EXISTS (
      SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin'
    )
  );

CREATE POLICY "profiles_update_admin"
  ON profiles FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin'
    )
  );

-- activity_logs: own rows; admins see all
CREATE POLICY "activity_logs_select"
  ON activity_logs FOR SELECT
  USING (
    user_id = auth.uid()
    OR EXISTS (
      SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin'
    )
  );

CREATE POLICY "activity_logs_insert"
  ON activity_logs FOR INSERT
  WITH CHECK (auth.uid() IS NOT NULL);

-- artifact_downloads: own rows; admins see all
CREATE POLICY "artifact_downloads_select"
  ON artifact_downloads FOR SELECT
  USING (
    user_id = auth.uid()
    OR EXISTS (
      SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin'
    )
  );

CREATE POLICY "artifact_downloads_insert"
  ON artifact_downloads FOR INSERT
  WITH CHECK (auth.uid() = user_id);
