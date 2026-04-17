import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

/**
 * If the Supabase env vars are missing we create a dummy client that points
 * at a placeholder URL so the rest of the app can still render (the auth
 * guard will redirect to /login and API calls will simply fail gracefully).
 * This avoids a top-level throw that kills the entire SPA in dev / preview
 * environments where Supabase isn't configured yet.
 */
export const supabase: SupabaseClient = createClient(
  supabaseUrl || 'https://placeholder.supabase.co',
  supabaseAnonKey || 'placeholder-anon-key'
);

export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey);
