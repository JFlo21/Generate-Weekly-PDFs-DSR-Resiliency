import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, Check, ShieldCheck, LogOut, Loader2 } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { ParticleBackground } from '../ui/ParticleBackground';
import { GlassCard } from '../ui/GlassCard';
import { cn } from '../../lib/utils';

// Approval journey — purely informational, reassures the user where they are.
const STEPS = [
  { id: 'created', label: 'Account created', state: 'done' as const },
  { id: 'review', label: 'Pending review', state: 'current' as const },
  { id: 'granted', label: 'Access granted', state: 'upcoming' as const },
];

export function PendingApprovalPage() {
  const { logout, user, profile, loading } = useAuth();
  const navigate = useNavigate();
  const [signingOut, setSigningOut] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Auth-state-aware redirect (mirrors AuthGuard). Without this, signing out
  // clears the session but leaves the user stranded on /pending — the original
  // bug. It also bounces an approved user to the dashboard and a logged-out
  // visitor back to /login.
  useEffect(() => {
    if (loading) return;
    if (!user) {
      navigate('/login', { replace: true });
      return;
    }
    if (profile && profile.role !== 'pending') {
      navigate('/dashboard', { replace: true });
    }
  }, [user, profile, loading, navigate]);

  async function handleSignOut() {
    setSigningOut(true);
    setError(null);
    try {
      await logout();
      // Navigate immediately; the redirect effect above is the backstop if the
      // session clears asynchronously via onAuthStateChange.
      navigate('/login', { replace: true });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Sign out failed. Please try again.',
      );
      setSigningOut(false);
    }
  }

  return (
    <div className="relative min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-red-950 flex items-center justify-center p-4 overflow-hidden">
      <ParticleBackground />

      {/* Floating gradient orbs — shared atmosphere with the login screen */}
      <motion.div
        animate={{ y: [0, -20, 0], x: [0, 10, 0] }}
        transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
        className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full bg-amber-500/10 blur-3xl pointer-events-none"
        aria-hidden="true"
      />
      <motion.div
        animate={{ y: [0, 20, 0], x: [0, -15, 0] }}
        transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut', delay: 2 }}
        className="absolute bottom-1/4 right-1/4 w-80 h-80 rounded-full bg-brand-red/10 blur-3xl pointer-events-none"
        aria-hidden="true"
      />

      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 200, damping: 20 }}
        className="relative z-10 w-full max-w-md"
      >
        <GlassCard className="p-8">
          {/* Brand mark */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="flex justify-center mb-6"
          >
            <div className="inline-flex items-center justify-center bg-white rounded-2xl px-4 py-2.5 shadow-lg">
              <img
                src="/linetec-services-logo.png"
                alt="Linetec Services"
                className="h-9 w-auto"
              />
            </div>
          </motion.div>

          {/* Animated "waiting" status centerpiece */}
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.15, type: 'spring', stiffness: 180, damping: 16 }}
            className="relative mx-auto w-24 h-24 mb-6"
            aria-hidden="true"
          >
            {[0, 1].map((i) => (
              <motion.span
                key={i}
                className="absolute inset-0 rounded-full border border-amber-400/40"
                animate={{ scale: [1, 1.65], opacity: [0.55, 0] }}
                transition={{
                  duration: 2.4,
                  repeat: Infinity,
                  delay: i * 1.2,
                  ease: 'easeOut',
                }}
              />
            ))}
            <motion.span
              className="absolute inset-0 rounded-full border-2 border-dashed border-amber-400/30"
              animate={{ rotate: 360 }}
              transition={{ duration: 14, repeat: Infinity, ease: 'linear' }}
            />
            <div className="absolute inset-2 rounded-full bg-amber-400/10 border border-amber-400/30 backdrop-blur-sm flex items-center justify-center">
              <Clock size={34} className="text-amber-300" />
            </div>
          </motion.div>

          {/* Headline + identity */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-center space-y-2"
          >
            <h1 className="text-xl font-bold text-white">Account pending approval</h1>
            <p className="text-white/60 text-sm">
              Your account is created and awaiting admin review. You'll get access
              the moment it's approved.
            </p>
            {user?.email && (
              <div className="inline-flex max-w-full items-center gap-1.5 rounded-full bg-white/5 border border-white/10 px-3 py-1 mt-1">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400 shrink-0" aria-hidden="true" />
                <span className="text-xs text-white/50 truncate">
                  Signed in as {user.email}
                </span>
              </div>
            )}
          </motion.div>

          {/* Approval stepper */}
          <motion.ol
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.28 }}
            className="flex items-start justify-between gap-2 my-8"
          >
            {STEPS.map((step, i) => (
              <li
                key={step.id}
                className="relative flex flex-1 flex-col items-center text-center"
                aria-current={step.state === 'current' ? 'step' : undefined}
              >
                {/* connector to next step */}
                {i < STEPS.length - 1 && (
                  <span
                    className={cn(
                      'absolute top-4 left-1/2 h-px w-full',
                      step.state === 'done' ? 'bg-emerald-400/40' : 'bg-white/10',
                    )}
                    aria-hidden="true"
                  />
                )}
                <span
                  className={cn(
                    'relative z-10 flex h-8 w-8 items-center justify-center rounded-full border',
                    step.state === 'done' &&
                      'bg-emerald-500/20 border-emerald-400/50 text-emerald-300',
                    step.state === 'current' &&
                      'bg-amber-400/20 border-amber-400/60 text-amber-300',
                    step.state === 'upcoming' &&
                      'bg-white/5 border-white/15 text-white/40',
                  )}
                >
                  {step.state === 'done' ? (
                    <Check size={15} aria-hidden="true" />
                  ) : step.state === 'current' ? (
                    <motion.span
                      animate={{ scale: [1, 1.25, 1] }}
                      transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
                      className="h-2 w-2 rounded-full bg-amber-300"
                    />
                  ) : (
                    <ShieldCheck size={15} aria-hidden="true" />
                  )}
                </span>
                <span
                  className={cn(
                    'mt-2 text-[11px] leading-tight',
                    step.state === 'upcoming' ? 'text-white/40' : 'text-white/70',
                  )}
                >
                  {step.label}
                </span>
              </li>
            ))}
          </motion.ol>

          {/* Sign-out failure feedback */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden mb-3"
              >
                <div className="px-3 py-2 rounded-lg bg-red-500/20 border border-red-500/30 text-red-300 text-sm">
                  {error}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Sign out — secondary style, NOT brand-red (UI-SPEC color contract) */}
          <motion.button
            type="button"
            onClick={handleSignOut}
            disabled={signingOut}
            whileHover={{ scale: signingOut ? 1 : 1.02 }}
            whileTap={{ scale: signingOut ? 1 : 0.98 }}
            className={cn(
              'w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold transition-all',
              'bg-white/10 hover:bg-white/20 text-white border border-white/10',
              'disabled:opacity-60 disabled:cursor-not-allowed',
            )}
          >
            {signingOut ? (
              <>
                <Loader2 size={15} className="animate-spin" aria-hidden="true" />
                Signing out…
              </>
            ) : (
              <>
                <LogOut size={15} aria-hidden="true" />
                Sign Out
              </>
            )}
          </motion.button>

          <p className="text-center text-xs text-white/40 mt-5">
            Need access sooner? Contact your Linetec admin.
          </p>
        </GlassCard>
      </motion.div>
    </div>
  );
}
