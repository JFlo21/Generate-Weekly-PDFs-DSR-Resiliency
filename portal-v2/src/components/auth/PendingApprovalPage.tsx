import { Clock } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { GlassCard } from '../ui/GlassCard';

export function PendingApprovalPage() {
  const { logout } = useAuth();

  return (
    <div className="relative min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-red-950 flex items-center justify-center p-4">
      <div className="relative z-10 w-full max-w-md">
        <GlassCard className="p-8">
          <div className="text-center space-y-4">
            <Clock size={40} className="text-amber-400 mx-auto" />
            <h1 className="text-xl font-bold text-white">Account pending approval</h1>
            <p className="text-white/60 text-sm">
              Your account has been created and is awaiting admin approval.
            </p>
            <p className="text-white/60 text-sm">
              Contact your Linetec admin to request access.
            </p>
            {/* Sign out — secondary style, NOT brand-red (UI-SPEC color contract) */}
            <button
              onClick={() => logout()}
              className="w-full py-2.5 rounded-xl text-sm font-semibold bg-white/10 hover:bg-white/20 text-white transition-all"
            >
              Sign Out
            </button>
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
