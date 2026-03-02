import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { supabase } from '../../lib/supabase';
import { ParticleBackground } from '../ui/ParticleBackground';
import { GlassCard } from '../ui/GlassCard';

type Status = 'loading' | 'success' | 'error';

export function AuthCallback() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<Status>('loading');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    async function handleCallback() {
      try {
        const { error } = await supabase.auth.getSession();
        if (error) throw error;

        // Supabase puts `type` in the URL fragment for implicit flow; fall back
        // to the query string for PKCE / older link formats
        const hashParams = new URLSearchParams(window.location.hash.slice(1));
        const type = hashParams.get('type') ?? new URLSearchParams(window.location.search).get('type');

        if (type === 'recovery') {
          navigate('/auth/reset-password', { replace: true });
          return;
        }

        setStatus('success');
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : 'Verification failed');
        setStatus('error');
      }
    }

    handleCallback();
  }, [navigate]);

  // Redirect to dashboard after showing success — cleaned up on unmount
  useEffect(() => {
    if (status !== 'success') return;
    const timer = setTimeout(() => navigate('/dashboard', { replace: true }), 2000);
    return () => clearTimeout(timer);
  }, [status, navigate]);

  return (
    <div className="relative min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-red-950 flex items-center justify-center p-4 overflow-hidden">
      <ParticleBackground />

      <motion.div
        animate={{ y: [0, -20, 0], x: [0, 10, 0] }}
        transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
        className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full bg-brand-red/10 blur-3xl pointer-events-none"
        aria-hidden="true"
      />
      <motion.div
        animate={{ y: [0, 20, 0], x: [0, -15, 0] }}
        transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut', delay: 2 }}
        className="absolute bottom-1/4 right-1/4 w-80 h-80 rounded-full bg-red-800/10 blur-3xl pointer-events-none"
        aria-hidden="true"
      />

      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 200, damping: 20 }}
        className="relative z-10 w-full max-w-md"
      >
        <GlassCard className="p-8 text-center">
          {status === 'loading' && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-col items-center gap-4"
            >
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
              >
                <Loader2 size={48} className="text-brand-red" />
              </motion.div>
              <p className="text-white/70 text-sm">Verifying your account…</p>
            </motion.div>
          )}

          {status === 'success' && (
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ type: 'spring', stiffness: 200, damping: 20 }}
              className="flex flex-col items-center gap-4"
            >
              <CheckCircle2 size={56} className="text-green-400" />
              <h2 className="text-2xl font-bold text-white">Verified!</h2>
              <p className="text-white/60 text-sm">Redirecting to dashboard…</p>
            </motion.div>
          )}

          {status === 'error' && (
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ type: 'spring', stiffness: 200, damping: 20 }}
              className="flex flex-col items-center gap-4"
            >
              <XCircle size={56} className="text-red-400" />
              <h2 className="text-2xl font-bold text-white">Something went wrong</h2>
              <p className="text-white/60 text-sm">{errorMsg}</p>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => navigate('/login', { replace: true })}
                className="mt-2 px-6 py-2.5 rounded-xl bg-brand-red text-white text-sm font-semibold shadow-lg shadow-brand-red/30 hover:bg-brand-red-dark transition-all"
              >
                Back to Login
              </motion.button>
            </motion.div>
          )}
        </GlassCard>
      </motion.div>
    </div>
  );
}
