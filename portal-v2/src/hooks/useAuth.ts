import { useState, useEffect, createContext, useContext } from 'react';
import type { User, Session } from '@supabase/supabase-js';
import { supabase, isSupabaseConfigured, setSessionStorage } from '../lib/supabase';
import type { Profile, UserRole } from '../lib/types';

interface AuthContextValue {
  user: User | null;
  session: Session | null;
  profile: Profile | null;
  loading: boolean;
  login: (email: string, password: string, captchaToken?: string, rememberMe?: boolean) => Promise<void>;
  signup: (email: string, password: string, captchaToken?: string) => Promise<void>;
  logout: () => Promise<void>;
  resetPassword: (email: string, captchaToken?: string) => Promise<void>;
  // Role helpers (D-16)
  role: UserRole | null;
  isAdmin: boolean;
  isBilling: boolean;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuthState(): AuthContextValue {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);

  async function fetchProfile(userId: string): Promise<void> {
    // Use maybeSingle() so that a missing profile row returns `data: null`
    // instead of a 406 error. This is the correct behavior when a brand-new
    // Supabase user hasn't had their profile row created yet.
    const { data, error } = await supabase
      .from('profiles')
      .select('id, email, role, created_at')
      .eq('id', userId)
      .maybeSingle();
    if (error) {
      // Don't spam the console on every auth state change — only log once
      // per session to aid debugging without flooding logs.
      console.warn('[v0] Profile fetch returned an error:', error.message);
      return;
    }
    if (data) setProfile(data as Profile);
  }

  useEffect(() => {
    if (!isSupabaseConfigured) {
      // Supabase env vars are missing — stop the loading spinner so the
      // auth guard redirects to login instead of spinning indefinitely.
      setLoading(false);
      return;
    }

    supabase.auth.getSession().then(({ data: { session: s } }) => {
      setSession(s);
      setUser(s?.user ?? null);
      if (s?.user) fetchProfile(s.user.id);
      setLoading(false);
    }).catch(() => {
      // Network/config error — stop spinning.
      setLoading(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange(
      (_event, s) => {
        setSession(s);
        setUser(s?.user ?? null);
        if (s?.user) {
          fetchProfile(s.user.id);
        } else {
          setProfile(null);
        }
      }
    );

    return () => listener.subscription.unsubscribe();
  }, []);

  async function login(
    email: string,
    password: string,
    captchaToken?: string,
    rememberMe = false,
  ): Promise<void> {
    // Storage is captured at createClient time — swap BEFORE signInWithPassword
    // (RESEARCH.md Pitfall 4). Unchecked "Remember me" → sessionStorage (tab-only).
    setSessionStorage(!rememberMe);
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
      options: captchaToken ? { captchaToken } : undefined,
    });
    if (error) throw error;
  }

  async function signup(
    email: string,
    password: string,
    captchaToken?: string,
  ): Promise<void> {
    // Do NOT insert into profiles here — handle_new_user() trigger does it
    // atomically (client-side insert is a race-condition trap).
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: captchaToken ? { captchaToken } : undefined,
    });
    if (error) throw error;
  }

  async function logout(): Promise<void> {
    await supabase.auth.signOut();
  }

  async function resetPassword(
    email: string,
    captchaToken?: string,
  ): Promise<void> {
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/auth/reset`,
      ...(captchaToken ? { captchaToken } : {}),
    });
    if (error) throw error;
  }

  const role = profile?.role ?? null;
  const isAdmin = role === 'admin';
  const isBilling = role === 'billing';

  return {
    user, session, profile, loading,
    login, signup, logout, resetPassword,
    role, isAdmin, isBilling,
  };
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
