import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Lock, Eye, EyeOff, ArrowRight } from 'lucide-react';
import { supabase } from '../../lib/supabase';
import { useToast } from '../../hooks/useToast';
import { GlassCard } from '../ui/GlassCard';
import { ToastContainer } from '../ui/Toast';

export function ResetPasswordPage() {
  const navigate = useNavigate();
  const { toasts, addToast, removeToast } = useToast();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Gate the submit button until the PASSWORD_RECOVERY event fires.
  // The page mounts before Supabase parses the recovery fragment — if we
  // allow submit before readyToReset, updateUser throws "Auth session missing".
  // (RESEARCH.md Pitfall 3 / T-04-16 mitigation)
  const [readyToReset, setReadyToReset] = useState(false);

  useEffect(() => {
    const { data: listener } = supabase.auth.onAuthStateChange((event) => {
      if (event === 'PASSWORD_RECOVERY') setReadyToReset(true);
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  // Inline match validation — only show error when confirm field has content
  const passwordsMatch = password === confirmPassword || confirmPassword === '';

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirmPassword) return;
    setLoading(true);
    setError(null);
    try {
      const { error: updateError } = await supabase.auth.updateUser({ password });
      if (updateError) throw updateError;
      addToast('success', 'Password updated — please sign in.');
      navigate('/login', { replace: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not update password. Please try again.';
      // Expired/invalid token — surface link to request a new reset
      if (message.toLowerCase().includes('expired') || message.toLowerCase().includes('invalid') || message.toLowerCase().includes('session')) {
        setError('This reset link has expired. Request a new one.');
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-red-950 flex items-center justify-center p-4">
      <ToastContainer toasts={toasts} onRemove={removeToast} />

      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 200, damping: 20 }}
        className="relative z-10 w-full max-w-md"
      >
        <GlassCard className="p-8">
          {/* Header */}
          <div className="mb-6">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-brand-red shadow-lg mb-4">
              <Lock size={20} className="text-white" />
            </div>
            <h1 className="text-xl font-bold text-white">Set new password</h1>
            <p className="text-white/60 text-sm mt-1">
              {readyToReset
                ? 'Enter your new password below.'
                : 'Verifying your reset link…'}
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* New password */}
            <div>
              <label className="block text-sm font-medium text-white/80 mb-1.5">
                New password
              </label>
              <div className="relative">
                <Lock
                  size={16}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40"
                />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                  placeholder="••••••••"
                  className="w-full pl-9 pr-10 py-2.5 rounded-xl bg-white/10 border border-white/20 text-white placeholder-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-brand-red/60 focus:border-transparent transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/70 transition-colors"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Confirm new password */}
            <div>
              <label className="block text-sm font-medium text-white/80 mb-1.5">
                Confirm new password
              </label>
              <div className="relative">
                <Lock
                  size={16}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40"
                />
                <input
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  minLength={6}
                  placeholder="••••••••"
                  className="w-full pl-9 pr-10 py-2.5 rounded-xl bg-white/10 border border-white/20 text-white placeholder-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-brand-red/60 focus:border-transparent transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/70 transition-colors"
                  aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
                >
                  {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {/* Inline match error — only when confirm has content */}
              {!passwordsMatch && (
                <p className="text-red-300 text-xs mt-1">Passwords do not match.</p>
              )}
            </div>

            {/* Error */}
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
                    {error.includes('expired') && (
                      <>
                        {' '}
                        <Link
                          to="/auth/forgot"
                          className="underline hover:text-red-200 transition-colors"
                        >
                          Request a new one.
                        </Link>
                      </>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Submit */}
            <motion.button
              type="submit"
              disabled={loading || !readyToReset || !passwordsMatch || password.length < 6}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold transition-all bg-brand-red text-white shadow-lg shadow-brand-red/30 hover:bg-brand-red-dark disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading ? (
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }}
                  className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full"
                />
              ) : (
                <>
                  Set New Password
                  <ArrowRight size={15} />
                </>
              )}
            </motion.button>
          </form>
        </GlassCard>
      </motion.div>
    </div>
  );
}
