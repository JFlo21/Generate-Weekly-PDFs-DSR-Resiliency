import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { Skeleton } from '../ui/Skeleton';
import { USE_MOCK } from '../../lib/mockData';

interface AuthGuardProps {
  children: React.ReactNode;
}

export function AuthGuard({ children }: AuthGuardProps) {
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  // In demo/mock mode (no backend configured), bypass auth entirely so the
  // dashboard is accessible for preview and testing.
  const isDemoMode = USE_MOCK;

  useEffect(() => {
    if (isDemoMode) return; // Skip redirect in demo mode
    if (!loading && !user) {
      navigate('/login', { replace: true });
    }
  }, [user, loading, navigate, isDemoMode]);

  if (!isDemoMode && loading) {
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

  if (!isDemoMode && !user) return null;

  return <>{children}</>;
}
