import { XCircle } from 'lucide-react';
import { GlassCard } from './GlassCard';

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
