import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey);

// Factory — creates the client with the given Web Storage backend.
// Called once at startup (localStorage default) and again on sign-in
// when "Remember me" state is known.
function createSupabaseClient(storage: Storage = localStorage): SupabaseClient {
  if (!isSupabaseConfigured) {
    throw new Error(
      'VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY must be set'
    );
  }
  return createClient(supabaseUrl!, supabaseAnonKey!, {
    auth: {
      storage,
      persistSession: true,
      autoRefreshToken: true,
    },
  });
}

// Shared singleton — default persistent (localStorage).
// ConfigError surface intercepts when isSupabaseConfigured is false
// (main.tsx renders ConfigError before this module's methods are called).
export let supabase: SupabaseClient = isSupabaseConfigured
  ? createSupabaseClient(localStorage)
  : (null as unknown as SupabaseClient);

// Called by LoginPage at form submit, before signInWithPassword.
// Swaps the singleton to use sessionStorage (tab-only) or localStorage
// (persistent across restarts) based on the "Remember me" checkbox.
export function setSessionStorage(useSession: boolean): void {
  supabase = createSupabaseClient(useSession ? sessionStorage : localStorage);
}
