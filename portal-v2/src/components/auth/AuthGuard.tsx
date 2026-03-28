import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { Skeleton } from '../ui/Skeleton';
import type { UserRole, Profile } from '../../lib/types';

interface AuthGuardProps {
  children: React.ReactNode;
  /** When provided, the authenticated user must have this role (or 'admin'). */
  requiredRole?: UserRole;
}

/** Role hierarchy: admin > biller > viewer */
const ROLE_RANK: Record<UserRole, number> = {
  admin: 3,
  biller: 2,
  viewer: 1,
};

function hasRequiredRole(profile: Profile | null, requiredRole: UserRole | undefined): boolean {
  if (!requiredRole || !profile) return true;
  return (ROLE_RANK[profile.role] ?? 0) >= (ROLE_RANK[requiredRole] ?? 0);
}

export function AuthGuard({ children, requiredRole }: AuthGuardProps) {
  const { user, profile, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      navigate('/login', { replace: true });
      return;
    }
    if (!hasRequiredRole(profile, requiredRole)) {
      navigate('/unauthorized', { replace: true });
    }
  }, [user, profile, loading, navigate, requiredRole]);

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

  if (!user) return null;

  if (!hasRequiredRole(profile, requiredRole)) return null;

  return <>{children}</>;
}
