import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { Skeleton } from '../ui/Skeleton';

interface AuthGuardProps {
  children: React.ReactNode;
}

export function AuthGuard({ children }: AuthGuardProps) {
  const { user, profile, loading } = useAuth();
  const navigate = useNavigate();

  // Authorization is not resolved until we know the session AND, for a
  // logged-in user, their profile (role). useAuth resolves the session
  // (loading=false) and the profile in two separate async steps, so there is a
  // window where `user` is set but `profile` is still null. Treat that as still
  // resolving — otherwise a pending user transiently renders the dashboard
  // shell before the /pending redirect fires (SEC-04 HIGH-03). A logged-in user
  // always has a profiles row (handle_new_user trigger), so `user && !profile`
  // means "fetch in flight", not "no profile".
  const resolving = loading || (Boolean(user) && !profile);

  useEffect(() => {
    if (resolving) return;
    if (!user) {
      navigate('/login', { replace: true });
      return;
    }
    // Pending users must not reach the dashboard (D-07, D-15).
    if (profile?.role === 'pending') {
      navigate('/pending', { replace: true });
    }
  }, [user, profile, resolving, navigate]);

  if (resolving) {
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

  // Block render while redirecting pending users (avoids flash of dashboard).
  if (!user || profile?.role === 'pending') return null;
  return <>{children}</>;
}
