import { Link } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import type { UserRole } from '../../lib/types';

interface RoleGuardProps {
  allow: UserRole[];
  children: React.ReactNode;
}

export function RoleGuard({ allow, children }: RoleGuardProps) {
  const { profile, loading } = useAuth();
  // AuthGuard above already handles the loading skeleton — return null here.
  if (loading) return null;
  if (!profile || !allow.includes(profile.role)) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-slate-500 text-sm">
        <p>You don&apos;t have permission to view this page.</p>
        <Link to="/dashboard" className="mt-2 text-brand-red hover:underline text-sm">
          Go to dashboard
        </Link>
      </div>
    );
  }
  return <>{children}</>;
}
