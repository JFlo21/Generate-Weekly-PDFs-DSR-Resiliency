import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Mail } from 'lucide-react';
import { ParticleBackground } from '../ui/ParticleBackground';
import { GlassCard } from '../ui/GlassCard';

export function ConfirmEmailPage() {
  const navigate = useNavigate();

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
          <motion.div
            animate={{ y: [0, -10, 0] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
            className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-brand-red shadow-lg mb-6 mx-auto"
          >
            <Mail size={32} className="text-white" />
          </motion.div>

          <h1 className="text-2xl font-bold text-white mb-2">Check Your Email</h1>
          <p className="text-white/60 text-sm mb-6">
            We sent a confirmation link to your email address. Click it to activate your account.
          </p>

          <ul className="text-left text-white/50 text-sm space-y-2 mb-8">
            <li>• Check your spam or junk folder</li>
            <li>• Make sure you entered the correct email address</li>
            <li>• The confirmation link expires in 24 hours</li>
          </ul>

          <button
            onClick={() => navigate('/login', { replace: true })}
            className="text-brand-red-light hover:underline text-sm font-medium"
          >
            ← Back to Sign In
          </button>
        </GlassCard>
      </motion.div>
    </div>
  );
}
