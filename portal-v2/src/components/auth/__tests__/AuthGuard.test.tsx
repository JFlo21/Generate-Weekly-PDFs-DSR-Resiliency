import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AuthGuard } from '../AuthGuard';

const navigate = vi.fn();
vi.mock('react-router-dom', () => ({ useNavigate: () => navigate }));
const authState = { user: null as unknown, profile: null as unknown, loading: false };
vi.mock('../../../hooks/useAuth', () => ({ useAuth: () => authState }));

beforeEach(() => { navigate.mockClear(); });

describe('AuthGuard (AUTH-06)', () => {
  it('redirects unauthenticated users to /login', () => {
    Object.assign(authState, { user: null, profile: null, loading: false });
    render(<AuthGuard><div>secret</div></AuthGuard>);
    expect(navigate).toHaveBeenCalledWith('/login', { replace: true });
    expect(screen.queryByText('secret')).toBeNull();
  });
  it('redirects pending users to /pending and hides children', () => {
    Object.assign(authState, { user: { id: 'u1' }, profile: { role: 'pending' }, loading: false });
    render(<AuthGuard><div>secret</div></AuthGuard>);
    expect(navigate).toHaveBeenCalledWith('/pending', { replace: true });
    expect(screen.queryByText('secret')).toBeNull();
  });
  it('renders children for billing/admin users', () => {
    Object.assign(authState, { user: { id: 'u1' }, profile: { role: 'billing' }, loading: false });
    render(<AuthGuard><div>secret</div></AuthGuard>);
    expect(screen.getByText('secret')).toBeTruthy();
  });
});
