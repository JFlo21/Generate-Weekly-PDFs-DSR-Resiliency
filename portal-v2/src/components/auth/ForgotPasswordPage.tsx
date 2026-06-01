import { useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Lock, CheckCircle, ArrowRight } from 'lucide-react';
import HCaptcha from '@hcaptcha/react-hcaptcha';
import { useAuth } from '../../hooks/useAuth';
import { GlassCard } from '../ui/GlassCard';

export function ForgotPasswordPage() {
  const { resetPassword } = useAuth();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const captchaRef = useRef<HCaptcha>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await resetPassword(email, captchaToken ?? undefined);
      setSent(true); // Show success state in-place — do NOT navigate
    } catch {
      // SECURITY (UI-SPEC): only show generic error on real transport failure.
      // Never reveal whether the email exists (T-04-15 mitigation).
      setError('Could not send reset email. Please try again.');
    } finally {
      setLoading(false);
      captchaRef.current?.resetCaptcha();
      setCaptchaToken(null);
    }
  }

  return (
    <div className="relative min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-red-950 flex items-center justify-center p-4">
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 200, damping: 20 }}
        className="relative z-10 w-full max-w-md"
      >
        <GlassCard className="p-8">
          {sent ? (
            /* Success state — in-place, no navigation */
            <div className="text-center space-y-3">
              <CheckCircle size={40} className="text-emerald-400 mx-auto" />
              <h2 className="text-xl font-bold text-white">Check your inbox</h2>
              <p className="text-white/60 text-sm">
                A reset link has been sent to {email}. The link expires in 60 minutes.
              </p>
              <Link
                to="/login"
                className="text-sm text-white/50 hover:text-white/80 transition-colors inline-block"
              >
                Back to sign in
              </Link>
            </div>
          ) : (
            <>
              {/* Back link */}
              <Link
                to="/login"
                className="text-sm text-white/50 hover:text-white/80 transition-colors inline-flex items-center gap-1 mb-6"
              >
                ← Back to sign in
              </Link>

              {/* Header */}
              <div className="mb-6">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-brand-red shadow-lg mb-4">
                  <Lock size={20} className="text-white" />
                </div>
                <h1 className="text-xl font-bold text-white">Reset your password</h1>
                <p className="text-white/60 text-sm mt-1">
                  Enter your email and we'll send you a reset link.
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Email */}
                <div>
                  <label className="block text-sm font-medium text-white/80 mb-1.5">
                    Email
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    placeholder="you@linetec.com"
                    className="w-full px-4 py-2.5 rounded-xl bg-white/10 border border-white/20 text-white placeholder-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-brand-red/60 focus:border-transparent transition-all"
                  />
                </div>

                {/* hCaptcha widget */}
                <HCaptcha
                  sitekey={import.meta.env.VITE_HCAPTCHA_SITEKEY}
                  onVerify={(token) => setCaptchaToken(token)}
                  onExpire={() => setCaptchaToken(null)}
                  ref={captchaRef}
                />

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
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Submit */}
                <motion.button
                  type="submit"
                  disabled={loading || !captchaToken}
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
                      Send Reset Email
                      <ArrowRight size={15} />
                    </>
                  )}
                </motion.button>
              </form>
            </>
          )}
        </GlassCard>
      </motion.div>
    </div>
  );
}
