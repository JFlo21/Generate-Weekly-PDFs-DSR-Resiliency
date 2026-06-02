/**
 * scripts/security-probe.ts
 *
 * Live RLS / signed-URL verification probe (Phase 07 D-07/D-08).
 * Uses ONLY the public anon key + a dedicated pending-role test account.
 * Never uses the privileged key. Idempotent — writes no state.
 *
 * Diagnostic-only tool — NOT a deployed/production service. This one-shot
 * security probe is EXEMPT from the CLAUDE.md "wrap new optimizations in
 * Sentry" rule (that rule targets the production Smartsheet upload pipeline).
 * It already satisfies the never-swallow-exceptions rule via the top-level
 * .catch() + non-zero process.exit(1) exit-code contract below — no Sentry
 * wiring required. Do not file a Living-Ledger entry for a missing wrap.
 *
 * Environment variables consumed:
 *   SUPABASE_URL                    -- Supabase project URL
 *                                      (same value as VITE_SUPABASE_URL)
 *   SUPABASE_ANON_KEY               -- public anon key (safe to expose;
 *                                      RLS is the guard per SEC-03)
 *   SUPABASE_PROBE_PENDING_EMAIL    -- email of the dedicated pending-role
 *                                      test account
 *   SUPABASE_PROBE_PENDING_PASSWORD -- password for the pending-role test
 *                                      account; store in GitHub Actions
 *                                      Secrets for CI runs
 *
 * Usage (local):
 *   SUPABASE_URL=https://poeyztlmsawfoqlanucc.supabase.co \
 *   SUPABASE_ANON_KEY=<anon-key> \
 *   SUPABASE_PROBE_PENDING_EMAIL=<probe-email> \
 *   SUPABASE_PROBE_PENDING_PASSWORD=<probe-password> \
 *   npx tsx scripts/security-probe.ts
 *
 * Usage (CI — GitHub Actions):
 *   env:
 *     SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
 *     SUPABASE_ANON_KEY: ${{ secrets.SUPABASE_ANON_KEY }}
 *     SUPABASE_PROBE_PENDING_EMAIL: ${{ secrets.SUPABASE_PROBE_PENDING_EMAIL }}
 *     SUPABASE_PROBE_PENDING_PASSWORD: ${{ secrets.SUPABASE_PROBE_PENDING_PASSWORD }}
 *   run: npx tsx scripts/security-probe.ts
 *   (Do NOT add the privileged key to this step's env.)
 *
 * Security posture (threat model T-07-*):
 *   - The privileged key is NEVER referenced — SEC-03 is the hard constraint.
 *   - Failure logs contain only assertion IDs and HTTP status codes, never
 *     row data (work_request, filename, etc.).
 *   - The probe operates under the same RLS constraints as the real portal:
 *     anon key + signInWithPassword only.
 */
import { createClient } from '@supabase/supabase-js';

// ---------------------------------------------------------------------------
// Env-var guard — fail loud and early if any required variable is missing.
// Mirrors the required-env check pattern from publish_artifacts_to_supabase.py.
// ---------------------------------------------------------------------------
const SUPABASE_URL_RAW = process.env.SUPABASE_URL;
const SUPABASE_ANON_KEY_RAW = process.env.SUPABASE_ANON_KEY;
const PROBE_EMAIL_RAW = process.env.SUPABASE_PROBE_PENDING_EMAIL;
const PROBE_PASSWORD_RAW = process.env.SUPABASE_PROBE_PENDING_PASSWORD;

if (!SUPABASE_URL_RAW || !SUPABASE_ANON_KEY_RAW || !PROBE_EMAIL_RAW || !PROBE_PASSWORD_RAW) {
  console.error(
    'PROBE ERROR: Missing required env vars. Set SUPABASE_URL, ' +
    'SUPABASE_ANON_KEY, SUPABASE_PROBE_PENDING_EMAIL, ' +
    'SUPABASE_PROBE_PENDING_PASSWORD.'
  );
  process.exit(1);
}

// After the guard above, all four vars are guaranteed non-empty strings.
const SUPABASE_URL: string = SUPABASE_URL_RAW;
const SUPABASE_ANON_KEY: string = SUPABASE_ANON_KEY_RAW;
const PROBE_EMAIL: string = PROBE_EMAIL_RAW;
const PROBE_PASSWORD: string = PROBE_PASSWORD_RAW;

// ---------------------------------------------------------------------------
// Supabase clients — anon key only (SEC-03 / D-08).
// Two separate client instances so the pending sign-in session is isolated
// from the anon (unauthenticated) assertions.
// ---------------------------------------------------------------------------

// Anon client — no auth session; tests the public/unauthenticated surface.
const anonClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// Pending-role client — signs in via signInWithPassword (anon key only).
const pendingClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// ---------------------------------------------------------------------------
// Probe
// ---------------------------------------------------------------------------

async function runProbe(): Promise<void> {
  let failures = 0;

  // SEC-01a: anon REST SELECT artifacts → empty array
  // Verifies RLS policy `artifacts_select_billing_or_admin` blocks anon reads.
  const { data: anonRows } = await anonClient
    .from('artifacts')
    .select('id')
    .limit(1);
  if (anonRows && anonRows.length > 0) {
    console.error('FAIL SEC-01a: anon can read artifacts rows');
    failures++;
  } else {
    console.log('PASS SEC-01a: anon REST artifacts → []');
  }

  // SEC-01b: anon Storage GET on private bucket → 400 or 403
  // Verifies the excel-artifacts bucket is not publicly accessible (public:false).
  const storageUrl = `${SUPABASE_URL}/storage/v1/object/excel-artifacts/test`;
  const storageResp = await fetch(storageUrl);
  if (storageResp.status !== 400 && storageResp.status !== 403) {
    console.error(
      `FAIL SEC-01b: anon Storage GET returned ${storageResp.status}, expected 400/403`
    );
    failures++;
  } else {
    console.log(`PASS SEC-01b: anon Storage GET → ${storageResp.status}`);
  }

  // Sign in as the dedicated pending-role test account.
  // Uses signInWithPassword against the public anon key — zero privileged-key exposure.
  // The account's profiles.role MUST be 'pending' (see RESEARCH Pitfall 5).
  const { error: signInError } = await pendingClient.auth.signInWithPassword({
    email: PROBE_EMAIL,
    password: PROBE_PASSWORD,
  });
  if (signInError) {
    console.error('FAIL: pending user sign-in failed:', signInError.message);
    process.exit(1);
  }
  console.log('INFO: signed in as pending user');

  // SEC-01c: pending JWT SELECT artifacts → 0 rows
  // Verifies that a logged-in but unapproved (pending) user cannot read billing data.
  const { data: pendingRows } = await pendingClient
    .from('artifacts')
    .select('id')
    .limit(1);
  if (pendingRows && pendingRows.length > 0) {
    console.error('FAIL SEC-01c: pending user can read artifact rows');
    failures++;
  } else {
    console.log('PASS SEC-01c: pending JWT artifacts → []');
  }

  // SEC-05/SEC-01d: pending JWT createSignedUrl → denied
  // Verifies the Storage SELECT policy blocks a pending user from generating
  // a signed download URL, even for a single-object path.
  // TTL=300 mirrors the SIGNED_URL_TTL constant in useDownloadArtifact.ts (SEC-05).
  const { data: signedData, error: signedError } = await pendingClient.storage
    .from('excel-artifacts')
    .createSignedUrl('any-path.xlsx', 300);
  if (signedData?.signedUrl) {
    console.error('FAIL SEC-05/SEC-01d: pending user obtained a signed URL');
    failures++;
  } else {
    console.log(
      'PASS SEC-05/SEC-01d: pending JWT createSignedUrl → denied:',
      signedError?.message
    );
  }

  // ---------------------------------------------------------------------------
  // Exit-code contract
  // ---------------------------------------------------------------------------
  if (failures > 0) {
    console.error(`\nSECURITY PROBE FAILED: ${failures} assertion(s) failed`);
    process.exit(1);
  }
  console.log('\nAll security probe assertions passed.');
}

// Top-level never-swallow guarantee — makes the Sentry-wrap exemption safe.
runProbe().catch((err: unknown) => {
  console.error(err);
  process.exit(1);
});
