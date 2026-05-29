# Phase 04: Auth, RBAC, and Deployment — Pattern Map

**Mapped:** 2026-05-29
**Files analyzed:** 14 (5 new, 8 modified, 1 deleted)
**Analogs found:** 14 / 14

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `portal-v2/src/lib/types.ts` | model | transform | self (current stale version) | exact — surgical edit |
| `portal-v2/src/lib/supabase.ts` | config | request-response | self (current silent version) | exact — surgical edit |
| `portal-v2/src/hooks/useAuth.ts` | hook | request-response | self (current scaffold) | exact — additive extension |
| `portal-v2/src/components/auth/AuthGuard.tsx` | middleware | request-response | self (current bypass version) | exact — surgical edit |
| `portal-v2/src/components/auth/LoginPage.tsx` | component | request-response | self (current form) | exact — additive |
| `portal-v2/src/components/auth/ForgotPasswordPage.tsx` | component | request-response | `LoginPage.tsx` | role-match (same auth-page layout) |
| `portal-v2/src/components/auth/ResetPasswordPage.tsx` | component | request-response | `LoginPage.tsx` | role-match (same auth-page layout) |
| `portal-v2/src/components/auth/PendingApprovalPage.tsx` | component | request-response | `LoginPage.tsx` | role-match (same auth-page layout, no form) |
| `portal-v2/src/components/auth/RoleGuard.tsx` | middleware | request-response | `AuthGuard.tsx` | role-match (same guard pattern, inline 403) |
| `portal-v2/src/components/ui/ConfigError.tsx` | component | request-response | `GlassCard.tsx` + `LoginPage.tsx` bg | partial-match (same design primitives) |
| `portal-v2/src/components/admin/UsersPage.tsx` | component | CRUD | self (current stale version) | exact — surgical edit |
| `portal-v2/src/components/admin/ActivityPage.tsx` | component | — | — | DELETE (D-14) |
| `portal-v2/src/App.tsx` | config | request-response | self (current route table) | exact — additive routes |
| `portal-v2/.env.example` | config | — | self (current) | exact — add one var |
| `supabase/portal_schema.sql` | migration | CRUD | self (current deployed) | exact — additive DDL |

---

## Pattern Assignments

### `portal-v2/src/lib/types.ts` (model, transform)

**Analog:** self — `portal-v2/src/lib/types.ts` (current, stale)
**Operation:** Surgical edit — change `UserRole`, `Profile`, remove `ActivityLog`/`ArtifactDownload` if unreferenced.

**Current stale block to replace** (lines 1, 31–49):
```typescript
// LINE 1 — BEFORE:
export type UserRole = 'admin' | 'viewer' | 'biller';

// LINES 31-39 — BEFORE:
export interface Profile {
  id: string;
  email: string;
  display_name: string | null;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
```

**Replacement — copy exactly:**
```typescript
// LINE 1 — AFTER (D-02):
export type UserRole = 'admin' | 'billing' | 'pending';

// Profile — AFTER (D-01, D-02):
export interface Profile {
  id: string;
  email: string;       // populated by handle_new_user() trigger
  role: UserRole;      // 'admin' | 'billing' | 'pending'
  created_at: string;  // ISO timestamp
}
```

**Types to remove** (lines 41–58) — `ActivityLog`, `ArtifactDownload` — verify no other file imports them before deleting. `ToastType`/`Toast` (lines 60–66) must be kept.

---

### `portal-v2/src/lib/supabase.ts` (config, request-response)

**Analog:** self — `portal-v2/src/lib/supabase.ts` (current, lines 1–18)
**Operation:** Full rewrite — replace silent placeholder with fail-loud factory + storage-adapter export.

**Current pattern to replace** (lines 1–18 — entire file):
```typescript
// CURRENT (silent placeholder — DO NOT keep):
export const supabase: SupabaseClient = createClient(
  supabaseUrl || 'https://placeholder.supabase.co',
  supabaseAnonKey || 'placeholder-anon-key'
);
export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey);
```

**Replacement pattern — copy exactly:**
```typescript
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
// (persistent across restarts) based on "Remember me" checkbox.
export function setSessionStorage(useSession: boolean): void {
  supabase = createSupabaseClient(useSession ? sessionStorage : localStorage);
}
```

**Key pitfall:** `auth.storage` is captured at `createClient` time — cannot be changed after construction. The factory pattern is the only correct approach. (RESEARCH.md Pitfall 4)

---

### `portal-v2/src/hooks/useAuth.ts` (hook, request-response)

**Analog:** self — `portal-v2/src/hooks/useAuth.ts` (current, lines 1–99)
**Operation:** Additive extension — keep all existing state/logic, add new parameters and helpers.

**Existing imports block to keep** (lines 1–4 — extend, do not replace):
```typescript
import { useState, useEffect, createContext, useContext } from 'react';
import type { User, Session } from '@supabase/supabase-js';
import { supabase, isSupabaseConfigured } from '../lib/supabase';
import type { Profile } from '../lib/types';
```

**Add to imports:**
```typescript
import { setSessionStorage } from '../lib/supabase';
```

**Existing `AuthContextValue` interface to extend** (lines 6–14):
```typescript
// CURRENT:
interface AuthContextValue {
  user: User | null;
  session: Session | null;
  profile: Profile | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

// AFTER — add captchaToken + rememberMe to login/signup, add resetPassword,
// add role helpers:
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
  role: Profile['role'] | null;
  isAdmin: boolean;
  isBilling: boolean;
}
```

**Existing `fetchProfile` pattern to keep verbatim** (lines 24–40):
```typescript
async function fetchProfile(userId: string): Promise<void> {
  const { data, error } = await supabase
    .from('profiles')
    .select('*')         // After D-01: select('id, email, role, created_at') is safer
    .eq('id', userId)
    .maybeSingle();      // maybeSingle() = no 406 if row missing
  if (error) {
    console.warn('[v0] Profile fetch returned an error:', error.message);
    return;
  }
  if (data) setProfile(data as Profile);
}
```

**Existing `useEffect` / `onAuthStateChange` pattern to keep** (lines 42–73):
```typescript
useEffect(() => {
  if (!isSupabaseConfigured) {
    setLoading(false);
    return;
  }
  supabase.auth.getSession().then(({ data: { session: s } }) => {
    setSession(s);
    setUser(s?.user ?? null);
    if (s?.user) fetchProfile(s.user.id);
    setLoading(false);
  }).catch(() => { setLoading(false); });

  const { data: listener } = supabase.auth.onAuthStateChange((_event, s) => {
    setSession(s);
    setUser(s?.user ?? null);
    if (s?.user) { fetchProfile(s.user.id); } else { setProfile(null); }
  });
  return () => listener.subscription.unsubscribe();
}, []);
```

**New `login` function — replace lines 75–81:**
```typescript
async function login(
  email: string,
  password: string,
  captchaToken?: string,
  rememberMe = false
): Promise<void> {
  // Swap storage BEFORE calling signInWithPassword — storage is baked at
  // createClient time (RESEARCH.md Pitfall 4).
  setSessionStorage(!rememberMe);
  const { error } = await supabase.auth.signInWithPassword({
    email,
    password,
    options: captchaToken ? { captchaToken } : undefined,
  });
  if (error) throw error;
}
```

**New `signup` function — replace lines 83–86:**
```typescript
async function signup(
  email: string,
  password: string,
  captchaToken?: string
): Promise<void> {
  // Do NOT insert into profiles after signUp — the handle_new_user() trigger
  // does this atomically. Client-side insert is a race-condition trap.
  const { error } = await supabase.auth.signUp({
    email,
    password,
    options: captchaToken ? { captchaToken } : undefined,
  });
  if (error) throw error;
}
```

**New `resetPassword` function — add after `logout`:**
```typescript
async function resetPassword(
  email: string,
  captchaToken?: string
): Promise<void> {
  const { error } = await supabase.auth.resetPasswordForEmail(email, {
    redirectTo: `${window.location.origin}/auth/reset`,
    ...(captchaToken ? { options: { captchaToken } } : {}),
  });
  if (error) throw error;
}
```

**Role helpers — compute from profile, add to returned value:**
```typescript
const role = profile?.role ?? null;
const isAdmin = role === 'admin';
const isBilling = role === 'billing';

return {
  user, session, profile, loading,
  login, signup, logout, resetPassword,
  role, isAdmin, isBilling,
};
```

---

### `portal-v2/src/components/auth/AuthGuard.tsx` (middleware, request-response)

**Analog:** self — `portal-v2/src/components/auth/AuthGuard.tsx` (current, lines 1–44)
**Operation:** Surgical edit — remove USE_MOCK bypass (lines 5, 17, 20, 26, 41), add profile import, add pending-role routing.

**Current import block** (lines 1–5 — line 5 is removed):
```typescript
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { Skeleton } from '../ui/Skeleton';
// REMOVE: import { USE_MOCK } from '../../lib/mockData';
```

**Current `useAuth` destructure to update** (line 12):
```typescript
// BEFORE:
const { user, loading } = useAuth();

// AFTER — add profile:
const { user, profile, loading } = useAuth();
```

**Lines to remove entirely:** line 17 (`const isDemoMode = USE_MOCK;`) and all `isDemoMode` references (lines 20, 26, 41).

**New `useEffect` replacing lines 19–24:**
```typescript
useEffect(() => {
  if (loading) return;
  if (!user) {
    navigate('/login', { replace: true });
    return;
  }
  // Pending users must not reach the dashboard (D-07, D-15).
  if (profile?.role === 'pending') {
    navigate('/pending', { replace: true });
  }
}, [user, profile, loading, navigate]);
```

**New guard at bottom replacing lines 41–43:**
```typescript
// Block render while redirecting pending users (avoids flash of dashboard).
if (!user || profile?.role === 'pending') return null;
return <>{children}</>;
```

**Loading skeleton to keep verbatim** (lines 26–38 — the Skeleton layout):
```typescript
if (loading) {
  return (
    <div className="min-h-screen bg-slate-50 p-8 space-y-4">
      <Skeleton className="h-16 w-full" />
      <div className="flex gap-4">
        <Skeleton className="h-screen w-56" />
        <div className="flex-1 space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    </div>
  );
}
```

---

### `portal-v2/src/components/auth/LoginPage.tsx` (component, request-response)

**Analog:** self — `portal-v2/src/components/auth/LoginPage.tsx` (current, lines 1–207)
**Operation:** Additive — keep all existing JSX structure, add three capabilities.

**Existing full-screen gradient + GlassCard wrapper to keep** (lines 41–64):
```typescript
<div className="relative min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-red-950 flex items-center justify-center p-4 overflow-hidden">
  <ParticleBackground />
  {/* gradient orbs — keep both motion.div blocks */}
  <motion.div className="relative z-10 w-full max-w-md">
    <GlassCard className="p-8">
```

**Existing form field pattern to copy for new fields** (lines 82–138 — email + password pattern):
```typescript
// Icon-left input:
<div className="relative">
  <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
  <input
    type="email"
    className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-white/10 border border-white/20 text-white placeholder-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-brand-red/60 focus:border-transparent transition-all"
  />
</div>

// Show/hide password toggle (keep aria-label pattern):
<button
  type="button"
  aria-label={showPassword ? 'Hide password' : 'Show password'}
  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/70 transition-colors"
>
  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
</button>
```

**Existing error block pattern to keep** (lines 142–155 — AnimatePresence):
```typescript
<AnimatePresence>
  {error && (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      className="overflow-hidden"
    >
      <div className="px-3 py-2 rounded-lg bg-red-500/20 border border-red-500/30 text-red-300 text-sm">
        {error}
      </div>
    </motion.div>
  )}
</AnimatePresence>
```

**Existing submit button pattern to keep** (lines 163–187):
```typescript
<motion.button
  type="submit"
  disabled={loading}
  whileHover={{ scale: 1.02 }}
  whileTap={{ scale: 0.98 }}
  className={cn(
    'w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold transition-all',
    'bg-brand-red text-white shadow-lg shadow-brand-red/30',
    'hover:bg-brand-red-dark disabled:opacity-60 disabled:cursor-not-allowed'
  )}
>
  {loading ? (
    <motion.div
      animate={{ rotate: 360 }}
      transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }}
      className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full"
    />
  ) : ( <>{mode === 'signin' ? 'Sign In' : 'Create Account'}<ArrowRight size={15} /></> )}
</motion.button>
```

**New state variables to add:**
```typescript
const [captchaToken, setCaptchaToken] = useState<string | null>(null);
const [rememberMe, setRememberMe] = useState(false);
const captchaRef = useRef<HCaptcha>(null);
```

**New imports to add:**
```typescript
import HCaptcha from '@hcaptcha/react-hcaptcha';
import { useRef } from 'react';
```

**Updated `handleSubmit` — key changes:**
```typescript
async function handleSubmit(e: React.FormEvent) {
  e.preventDefault();
  setLoading(true);
  setError(null);
  try {
    if (mode === 'signin') {
      await login(email, password, captchaToken ?? undefined, rememberMe);
      // Post-signin: role-aware routing
      // (AuthGuard handles pending→/pending; navigate to /dashboard for active roles)
      navigate('/dashboard', { replace: true });
    } else {
      await signup(email, password, captchaToken ?? undefined);
      // Post-signup: ALWAYS go to /pending (D-15) — NOT /dashboard
      navigate('/pending', { replace: true });
    }
  } catch (err) {
    setError(err instanceof Error ? err.message : 'Authentication failed');
  } finally {
    setLoading(false);
    // Reset captcha after every attempt (success or error) — tokens are single-use
    captchaRef.current?.resetCaptcha();
    setCaptchaToken(null);
  }
}
```

**New elements to add inside `<form>` (after password field, before error block):**
```typescript
{/* Forgot password link — sign-in mode only */}
{mode === 'signin' && (
  <div className="flex justify-end -mt-2">
    <Link to="/auth/forgot" className="text-xs text-white/50 hover:text-white/80 transition-colors">
      Forgot password?
    </Link>
  </div>
)}

{/* Remember me checkbox */}
<label className="flex items-center gap-2 cursor-pointer">
  <input
    type="checkbox"
    checked={rememberMe}
    onChange={(e) => setRememberMe(e.target.checked)}
    className="rounded border-white/20 bg-white/10 text-brand-red focus:ring-brand-red/60"
  />
  <span className="text-sm text-white/70">Remember me</span>
</label>

{/* hCaptcha widget */}
<HCaptcha
  sitekey={import.meta.env.VITE_HCAPTCHA_SITEKEY}
  onVerify={(token) => setCaptchaToken(token)}
  onExpire={() => setCaptchaToken(null)}
  ref={captchaRef}
/>
```

**Submit button `disabled` condition — extend to require captcha:**
```typescript
disabled={loading || !captchaToken}
// also: className includes disabled:opacity-60 disabled:cursor-not-allowed (existing)
```

---

### `portal-v2/src/components/auth/ForgotPasswordPage.tsx` (component, request-response) — NEW

**Analog:** `portal-v2/src/components/auth/LoginPage.tsx`

**Imports pattern — copy from LoginPage, omit ParticleBackground, add Lock + CheckCircle:**
```typescript
import { useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Lock, CheckCircle } from 'lucide-react';
import HCaptcha from '@hcaptcha/react-hcaptcha';
import { useAuth } from '../../hooks/useAuth';
import { GlassCard } from '../ui/GlassCard';
```

**Full-screen background pattern — copy from LoginPage lines 41–43 (no ParticleBackground):**
```typescript
<div className="relative min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-red-950 flex items-center justify-center p-4">
  <motion.div
    initial={{ scale: 0.9, opacity: 0 }}
    animate={{ scale: 1, opacity: 1 }}
    transition={{ type: 'spring', stiffness: 200, damping: 20 }}
    className="relative z-10 w-full max-w-md"
  >
    <GlassCard className="p-8">
```

**Back link pattern (top of card):**
```typescript
<Link to="/login" className="text-sm text-white/50 hover:text-white/80 transition-colors inline-flex items-center gap-1 mb-6">
  ← Back to sign in
</Link>
```

**Success state pattern (replaces form after email sent):**
```typescript
{sent ? (
  <div className="text-center space-y-3">
    <CheckCircle size={40} className="text-emerald-400 mx-auto" />
    <h2 className="text-xl font-bold text-white">Check your inbox</h2>
    <p className="text-white/60 text-sm">
      A reset link has been sent to {email}. The link expires in 60 minutes.
    </p>
    <Link to="/login" className="text-sm text-white/50 hover:text-white/80 transition-colors">
      Back to sign in
    </Link>
  </div>
) : (
  // form
)}
```

**Email field + hCaptcha + submit button — copy the exact field pattern from LoginPage (lines 83–105, 163–187).** Use same `bg-white/10 border border-white/20` input class and same `bg-brand-red` button class.

**Error/loading pattern — copy AnimatePresence error block from LoginPage lines 142–155.**

**`handleSubmit` pattern:**
```typescript
async function handleSubmit(e: React.FormEvent) {
  e.preventDefault();
  setLoading(true);
  setError(null);
  try {
    await resetPassword(email, captchaToken ?? undefined);
    setSent(true); // Show success state in-place; do NOT navigate
  } catch (err) {
    setError('Could not send reset email. Please try again.');
  } finally {
    setLoading(false);
    captchaRef.current?.resetCaptcha();
    setCaptchaToken(null);
  }
}
```

---

### `portal-v2/src/components/auth/ResetPasswordPage.tsx` (component, request-response) — NEW

**Analog:** `portal-v2/src/components/auth/LoginPage.tsx` + `useAuth.ts` `onAuthStateChange` pattern.

**Imports pattern:**
```typescript
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Lock } from 'lucide-react';
import { supabase } from '../../lib/supabase';
import { useToast } from '../../hooks/useToast';
import { GlassCard } from '../ui/GlassCard';
import { ToastContainer } from '../ui/Toast';
```

**PASSWORD_RECOVERY event listener — copy from RESEARCH.md Pattern 3 + useAuth.ts `onAuthStateChange` pattern (lines 60–72):**
```typescript
// Wait for Supabase to parse the recovery fragment from the URL.
// The form must be disabled until readyToReset is true.
useEffect(() => {
  const { data: listener } = supabase.auth.onAuthStateChange((event) => {
    if (event === 'PASSWORD_RECOVERY') {
      setReadyToReset(true);
    }
  });
  return () => listener.subscription.unsubscribe();
}, []);
```

**Password match validation pattern:**
```typescript
// Inline, not toast — below confirm field
const passwordsMatch = password === confirmPassword || confirmPassword === '';
// Error display:
{!passwordsMatch && (
  <p className="text-red-300 text-xs mt-1">Passwords do not match.</p>
)}
// Button disabled when:
disabled={loading || !readyToReset || !passwordsMatch || password.length < 6}
```

**Submit handler:**
```typescript
async function handleSubmit(e: React.FormEvent) {
  e.preventDefault();
  if (password !== confirmPassword) return;
  setLoading(true);
  setError(null);
  try {
    const { error } = await supabase.auth.updateUser({ password });
    if (error) throw error;
    addToast('success', 'Password updated — please sign in.');
    navigate('/login', { replace: true });
  } catch (err) {
    setError(err instanceof Error ? err.message : 'Could not update password. Please try again.');
  } finally {
    setLoading(false);
  }
}
```

**Show/hide toggle — copy from LoginPage lines 130–138 (exact same aria-label pattern).**

---

### `portal-v2/src/components/auth/PendingApprovalPage.tsx` (component, request-response) — NEW

**Analog:** `portal-v2/src/components/auth/LoginPage.tsx` (layout only — no form).

**Imports pattern:**
```typescript
import { Clock } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { GlassCard } from '../ui/GlassCard';
```

**Full-screen layout — copy gradient wrapper from LoginPage lines 41–43 (no ParticleBackground, no motion orbs):**
```typescript
<div className="relative min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-red-950 flex items-center justify-center p-4">
  <div className="relative z-10 w-full max-w-md">
    <GlassCard className="p-8">
```

**Content pattern:**
```typescript
<div className="text-center space-y-4">
  <Clock size={40} className="text-amber-400 mx-auto" />
  <h1 className="text-xl font-bold text-white">Account pending approval</h1>
  <p className="text-white/60 text-sm">
    Your account has been created and is awaiting admin approval.
  </p>
  <p className="text-white/60 text-sm">
    Contact your Linetec admin to request access.
  </p>
  {/* Sign out button — secondary style, NOT brand-red (this is not a primary CTA) */}
  <button
    onClick={() => logout()}
    className="w-full py-2.5 rounded-xl text-sm font-semibold bg-white/10 hover:bg-white/20 text-white transition-all"
  >
    Sign Out
  </button>
</div>
```

---

### `portal-v2/src/components/auth/RoleGuard.tsx` (middleware, request-response) — NEW

**Analog:** `portal-v2/src/components/auth/AuthGuard.tsx` (same guard shape, different outcome — inline 403 instead of redirect).

**Imports pattern — copy from AuthGuard lines 1–4, swap Navigate for Link:**
```typescript
import { Link } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import type { UserRole } from '../../lib/types';
```

**Core pattern:**
```typescript
interface RoleGuardProps {
  allow: UserRole[];
  children: React.ReactNode;
}

export function RoleGuard({ allow, children }: RoleGuardProps) {
  const { profile, loading } = useAuth();
  // AuthGuard above already handles the loading skeleton — return null here.
  if (loading) return null;
  if (!profile || !allow.includes(profile.role)) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-slate-500 text-sm">
        <p>You don&apos;t have permission to view this page.</p>
        <Link to="/dashboard" className="mt-2 text-brand-red hover:underline text-sm">
          Go to dashboard
        </Link>
      </div>
    );
  }
  return <>{children}</>;
}
```

---

### `portal-v2/src/components/ui/ConfigError.tsx` (component, request-response) — NEW

**Analog:** `portal-v2/src/components/ui/GlassCard.tsx` + LoginPage background pattern.

**Imports pattern:**
```typescript
import { XCircle } from 'lucide-react';
import { GlassCard } from './GlassCard';
```

**Pattern — rendered in `main.tsx` before router; no interactive controls:**
```typescript
export function ConfigError() {
  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <GlassCard className="max-w-md w-full p-8 text-center space-y-4">
        <XCircle size={40} className="text-red-400 mx-auto" />
        <h1 className="text-xl font-bold text-white">Configuration error</h1>
        <p className="text-white/60 text-sm">
          Portal configuration is incomplete. Set{' '}
          <code className="text-white/80">VITE_SUPABASE_URL</code> and{' '}
          <code className="text-white/80">VITE_SUPABASE_ANON_KEY</code> in your environment.
        </p>
      </GlassCard>
    </div>
  );
}
```

**Usage in `main.tsx` — add before `<App />` render:**
```typescript
import { ConfigError } from './components/ui/ConfigError';
const isConfigured = Boolean(
  import.meta.env.VITE_SUPABASE_URL && import.meta.env.VITE_SUPABASE_ANON_KEY
);
root.render(isConfigured ? <App /> : <ConfigError />);
```

---

### `portal-v2/src/components/admin/UsersPage.tsx` (component, CRUD)

**Analog:** self — `portal-v2/src/components/admin/UsersPage.tsx` (current, lines 1–141)
**Operation:** Surgical edit — fix ROLES array, fix stale column refs, add pending highlight, add last-admin guard, fix error state, add empty state.

**Current `ROLES` array to replace** (line 11):
```typescript
// BEFORE:
const ROLES: UserRole[] = ['viewer', 'biller', 'admin'];

// AFTER (D-02):
const ROLES: UserRole[] = ['admin', 'billing', 'pending'];
```

**Add `useAuth` import + `currentUserId` derivation:**
```typescript
// Add to imports (line 1 block):
import { useAuth } from '../../hooks/useAuth';

// In component body:
const { user } = useAuth();
const currentUserId = user?.id;
```

**Last-admin guard — add after `setUsers` in component body:**
```typescript
const adminCount = users.filter((u) => u.role === 'admin').length;
```

**Updated `updateRole` function — replace lines 31–44:**
```typescript
async function updateRole(userId: string, role: UserRole) {
  // Last-admin guard (RBAC-04): prevent demoting the last admin.
  const targetUser = users.find((u) => u.id === userId);
  if (
    targetUser?.role === 'admin' &&
    role !== 'admin' &&
    adminCount <= 1
  ) {
    addToast('error', 'Cannot demote the last admin. Promote another user to admin first.');
    return;
  }
  const { error: err } = await supabase
    .from('profiles')
    .update({ role })
    .eq('id', userId);
  if (err) {
    addToast('error', 'Role update failed. Please try again.');
  } else {
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, role } : u)));
    addToast('success', `Role updated to ${role}.`);
  }
}
```

**Heading section — add pending count badge (after existing `<h1>` line 53):**
```typescript
// Keep existing heading structure (lines 52-56), add badge:
<div className="flex items-center gap-3">
  <h1 className="text-xl font-bold text-slate-900">Users</h1>
  {users.filter((u) => u.role === 'pending').length > 0 && (
    <Badge variant="warning">
      {users.filter((u) => u.role === 'pending').length} pending
    </Badge>
  )}
</div>
```

**Avatar initial — fix stale `display_name` ref** (line 98):
```typescript
// BEFORE:
{(user.display_name ?? user.email)[0]}
// AFTER:
{user.email[0].toUpperCase()}
```

**User cell — remove `display_name` display** (lines 100–104):
```typescript
// BEFORE: shows display_name ?? '—' on first line, email on second
// AFTER: show only email (D-02 — display_name not in deployed schema)
<div>
  <p className="text-sm font-medium text-slate-800">{user.email}</p>
</div>
```

**Row className — add pending amber tint** (line 93):
```typescript
// BEFORE:
className="border-b border-slate-50 hover:bg-slate-50/50 transition-colors"
// AFTER:
className={cn(
  'border-b border-slate-50 hover:bg-slate-50/50 transition-colors',
  user.role === 'pending' && 'bg-amber-50/40'
)}
```

**Role `<select>` — add last-admin disabled guard** (lines 109–114):
```typescript
<select
  value={user.role}
  onChange={(e) => updateRole(user.id, e.target.value as UserRole)}
  disabled={user.id === currentUserId && adminCount <= 1}
  aria-disabled={user.id === currentUserId && adminCount <= 1 ? 'true' : undefined}
  title={
    user.id === currentUserId && adminCount <= 1
      ? 'You are the last admin and cannot change your own role'
      : undefined
  }
  className={cn(
    'text-xs border border-slate-200 rounded-lg px-2 py-1 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-red/40',
    user.id === currentUserId && adminCount <= 1 && 'opacity-50 cursor-not-allowed'
  )}
>
  {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
</select>
```

**Status badge — replace `is_active` pattern** (lines 123–125):
```typescript
// BEFORE: Badge variant={user.is_active ? 'success' : 'default'}
// AFTER: role-based badge (UI-SPEC color contract)
const roleBadgeVariant: Record<UserRole, 'info' | 'success' | 'warning'> = {
  admin: 'info',
  billing: 'success',
  pending: 'warning',
};
<Badge variant={roleBadgeVariant[user.role]}>{user.role}</Badge>
```

**Error state — replace bare `<p>` (line 67):**
```typescript
// BEFORE: <p className="p-6 text-sm text-red-500">{error}</p>
// AFTER:
<div className="p-6">
  <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700 flex items-center justify-between">
    <span>Could not load users. Check your connection and try again.</span>
    <button
      onClick={() => { setError(null); setLoading(true); /* re-trigger useEffect */ }}
      className="text-xs text-red-600 hover:underline ml-4 shrink-0"
    >
      Retry
    </button>
  </div>
</div>
```

**Empty state — add before `</table>` close or as alternate branch:**
```typescript
{users.length === 0 && !loading && !error && (
  <p className="text-slate-400 text-sm text-center py-12">No users found.</p>
)}
```

**Add `cn` import (needed for conditional classes):**
```typescript
import { cn } from '../../lib/utils';
```

---

### `portal-v2/src/App.tsx` (config, request-response)

**Analog:** self — `portal-v2/src/App.tsx` (current, lines 1–74)
**Operation:** Additive routes + deletions.

**Imports to add** (after line 9):
```typescript
import { ForgotPasswordPage } from './components/auth/ForgotPasswordPage';
import { ResetPasswordPage } from './components/auth/ResetPasswordPage';
import { PendingApprovalPage } from './components/auth/PendingApprovalPage';
import { RoleGuard } from './components/auth/RoleGuard';
// REMOVE: import { ActivityPage } from './components/admin/ActivityPage';
```

**New routes to add** (after the `/login` route, line 29):
```typescript
<Route path="/auth/forgot" element={<PageTransition><ForgotPasswordPage /></PageTransition>} />
<Route path="/auth/reset" element={<PageTransition><ResetPasswordPage /></PageTransition>} />
<Route path="/pending" element={<PageTransition><PendingApprovalPage /></PageTransition>} />
```

**Admin users route — wrap in RoleGuard** (lines 47–55):
```typescript
// BEFORE: bare <UsersPage /> inside PageTransition
// AFTER:
<Route
  path="admin/users"
  element={
    <RoleGuard allow={['admin']}>
      <PageTransition><UsersPage /></PageTransition>
    </RoleGuard>
  }
/>
```

**Activity route to remove** (lines 55–62):
```typescript
// DELETE entirely:
<Route
  path="admin/activity"
  element={
    <PageTransition>
      <ActivityPage />
    </PageTransition>
  }
/>
```

**Existing catch-all to keep verbatim** (line 65):
```typescript
<Route path="*" element={<Navigate to="/dashboard" replace />} />
```

---

### `portal-v2/.env.example` (config)

**Analog:** self — `portal-v2/.env.example` (current, lines 1–30)
**Operation:** Add one var after the Supabase block.

**Add after line 4 (after `VITE_SUPABASE_ANON_KEY`):**
```bash
VITE_HCAPTCHA_SITEKEY=your-hcaptcha-sitekey
# Dev/test: use hCaptcha test sitekey 10000000-ffff-ffff-ffff-000000000001
# (pairs with secret 0x0000000000000000000000000000000000000000 in Supabase dashboard)
```

**Stale Express vars to flag (NOT remove — Phase 07 cleanup):**
```bash
# VITE_API_BASE_URL — stale; Express removal in Phase 07
# GITHUB_TOKEN, SESSION_SECRET — Express backend only; Phase 07
```

---

### `supabase/portal_schema.sql` (migration, CRUD)

**Analog:** self — `supabase/portal_schema.sql` (current, lines 1–104)
**Operation:** Append idempotent DDL blocks at the end.

**Current profiles table shape to extend** (lines 54–58):
```sql
-- CURRENT (deployed):
CREATE TABLE IF NOT EXISTS public.profiles (
    id   uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    role text NOT NULL DEFAULT 'pending'
              CHECK (role IN ('admin','billing','pending'))
);
```

**DDL to append — copy exactly (D-01 + D-04):**
```sql
-- ============================================================================
-- Phase 04 D-01: Extend profiles with email + created_at
-- ============================================================================
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS email      text,
  ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

-- Backfill email from auth.users for any pre-existing rows (e.g. first-admin seed).
-- Safe to re-run: WHERE p.email IS NULL is idempotent.
UPDATE public.profiles p
SET email = u.email
FROM auth.users u
WHERE p.id = u.id AND p.email IS NULL;

-- Make email NOT NULL after backfill.
-- IF NOT EXISTS equivalent: only errors if column is already NOT NULL (safe to re-run on clean DB).
ALTER TABLE public.profiles
  ALTER COLUMN email SET NOT NULL;

-- ============================================================================
-- Phase 04 D-04: handle_new_user trigger
-- SECURITY DEFINER required: supabase_auth_admin lacks cross-schema permissions.
-- ON CONFLICT DO NOTHING: idempotent if trigger fires more than once.
-- ============================================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.profiles (id, email, role, created_at)
  VALUES (NEW.id, NEW.email, 'pending', now())
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ============================================================================
-- Phase 04 RBAC-04 (optional DB defense-in-depth): last-admin demotion guard
-- ============================================================================
CREATE OR REPLACE FUNCTION public.prevent_last_admin_demotion()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF OLD.role = 'admin' AND NEW.role != 'admin' THEN
    IF (SELECT COUNT(*) FROM public.profiles WHERE role = 'admin') <= 1 THEN
      RAISE EXCEPTION 'Cannot demote the last admin';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS check_last_admin ON public.profiles;
CREATE TRIGGER check_last_admin
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.prevent_last_admin_demotion();
```

---

## Shared Patterns

### GlassCard — all new auth pages
**Source:** `portal-v2/src/components/ui/GlassCard.tsx` (lines 9–19)
**Apply to:** ForgotPasswordPage, ResetPasswordPage, PendingApprovalPage, ConfigError
```typescript
// Full component — copy the class string, do NOT override backdrop-blur-xl or border-white/20
<GlassCard className="p-8">   {/* auth cards: always p-8 */}
// Classes baked in: backdrop-blur-xl bg-white/10 border border-white/20 rounded-2xl shadow-xl
```

### Badge role-to-variant mapping — UsersPage + any future role display
**Source:** `portal-v2/src/components/ui/Badge.tsx` (lines 11–17)
**Apply to:** UsersPage status column, UsersPage pending count badge
```typescript
// Available variants (do NOT add new ones in Phase 04):
// success: bg-emerald-100 text-emerald-700  → billing
// warning: bg-amber-100  text-amber-700    → pending
// info:    bg-blue-100   text-blue-700     → admin
// error:   bg-red-100    text-red-700      → (not used for roles)
// default: bg-slate-100  text-slate-600    → (not used for roles)
```

### Toast feedback — UsersPage + ResetPasswordPage
**Source:** `portal-v2/src/hooks/useToast.ts` (inferred from UsersPage lines 8, 17, 37–43)
**Apply to:** UsersPage role update, ResetPasswordPage post-success
```typescript
const { toasts, addToast, removeToast } = useToast();
// API: addToast(type: 'success' | 'error' | 'info', message: string)
// Always render: <ToastContainer toasts={toasts} onRemove={removeToast} />
```

### AnimatePresence error block — all form pages
**Source:** `portal-v2/src/components/auth/LoginPage.tsx` (lines 142–155)
**Apply to:** ForgotPasswordPage, ResetPasswordPage (and LoginPage already has it)
```typescript
<AnimatePresence>
  {error && (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      className="overflow-hidden"
    >
      <div className="px-3 py-2 rounded-lg bg-red-500/20 border border-red-500/30 text-red-300 text-sm">
        {error}
      </div>
    </motion.div>
  )}
</AnimatePresence>
```

### Loading spinner in button — all form submit buttons
**Source:** `portal-v2/src/components/auth/LoginPage.tsx` (lines 174–180)
**Apply to:** ForgotPasswordPage, ResetPasswordPage
```typescript
{loading ? (
  <motion.div
    animate={{ rotate: 360 }}
    transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }}
    className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full"
  />
) : <>{buttonLabel}<ArrowRight size={15} /></>}
```

### `supabase.auth.onAuthStateChange` subscription pattern
**Source:** `portal-v2/src/hooks/useAuth.ts` (lines 60–72)
**Apply to:** ResetPasswordPage (PASSWORD_RECOVERY event)
```typescript
// Always clean up on unmount — copy this exact pattern:
const { data: listener } = supabase.auth.onAuthStateChange((event, session) => {
  // handle event
});
return () => listener.subscription.unsubscribe();
```

### Page-motion wrapper for admin surfaces
**Source:** `portal-v2/src/components/admin/UsersPage.tsx` (lines 47–50)
**Apply to:** All admin page wrappers
```typescript
<motion.div
  initial={{ opacity: 0, y: 8 }}
  animate={{ opacity: 1, y: 0 }}
  className="p-6 max-w-5xl mx-auto space-y-6"
>
```

---

## No Analog Found

All Phase 04 files have close analogs in the codebase. No files require falling back to RESEARCH.md patterns exclusively.

| File | Reason |
|------|--------|
| `portal-v2/src/components/auth/ResetPasswordPage.tsx` | The `PASSWORD_RECOVERY` event listener is a new supabase-js pattern not previously used in the codebase; use RESEARCH.md Pattern 3 for the `onAuthStateChange` event name and `updateUser` call shape. All layout/UI patterns are copied from LoginPage. |

---

## Critical Anti-Patterns (Planner Must Enforce)

| Anti-Pattern | File | Action |
|---|---|---|
| `USE_MOCK` / `isDemoMode` bypass | `AuthGuard.tsx` lines 5, 17, 20, 26, 41 | Remove all references unconditionally |
| `placeholder.supabase.co` silent client | `supabase.ts` lines 13–16 | Replace with factory + ConfigError surface |
| `navigate('/dashboard')` after signup | `LoginPage.tsx` line 32 | Change to `navigate('/pending')` |
| `user.display_name` access | `UsersPage.tsx` lines 98, 102 | Replace with `user.email[0].toUpperCase()` and `user.email` |
| `ROLES = ['viewer', 'biller', 'admin']` | `UsersPage.tsx` line 11 | Replace with `['admin', 'billing', 'pending']` |
| Client-side `INSERT INTO profiles` after signUp | `useAuth.ts` (would be new code) | Never add — trigger handles it atomically |
| Recursive RLS on profiles | `supabase/portal_schema.sql` (if adding new policy) | Always use `public.current_user_role()` helper, never `EXISTS (SELECT FROM profiles)` |
| `service_role` key in portal-v2 or Vercel | anywhere | Absolute prohibition |

---

## Metadata

**Analog search scope:** `portal-v2/src/` (all subdirectories), `supabase/portal_schema.sql`
**Files scanned:** 12 source files read directly
**Confirmed live bugs (verified by line number):**
- `AuthGuard.tsx` line 17: `isDemoMode = USE_MOCK` — auth bypass active
- `LoginPage.tsx` line 32: `navigate('/dashboard')` after signup — skips pending gate
- `UsersPage.tsx` line 98: `user.display_name` — column absent from deployed schema
- `UsersPage.tsx` line 11: `['viewer', 'biller', 'admin']` — stale roles
- `supabase.ts` lines 13–15: silent placeholder client
**Pattern extraction date:** 2026-05-29
