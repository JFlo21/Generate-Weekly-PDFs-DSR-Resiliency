import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { axe } from 'jest-axe';
import { PendingApprovalPage } from '../PendingApprovalPage';

// Mock router + auth the same way AuthGuard.test.tsx does, so we can assert
// on navigation without a real <BrowserRouter>.
const navigate = vi.fn();
vi.mock('react-router-dom', () => ({ useNavigate: () => navigate }));

const logout = vi.fn().mockResolvedValue(undefined);
const authState = {
  logout,
  user: null as unknown,
  profile: null as unknown,
  loading: false,
};
vi.mock('../../../hooks/useAuth', () => ({ useAuth: () => authState }));

// The canvas particle background is decorative and irrelevant to this behavior.
vi.mock('../../ui/ParticleBackground', () => ({ ParticleBackground: () => null }));

beforeEach(() => {
  navigate.mockClear();
  logout.mockClear();
  Object.assign(authState, {
    logout,
    user: { id: 'u1', email: 'hello@linetec.com' },
    profile: { role: 'pending' },
    loading: false,
  });
});

describe('PendingApprovalPage (sign-out bug fix)', () => {
  it('renders the pending-approval status for a pending user', () => {
    render(<PendingApprovalPage />);
    expect(screen.getByText(/account pending approval/i)).toBeTruthy();
  });

  it('signs out AND navigates to /login when Sign Out is clicked', async () => {
    render(<PendingApprovalPage />);
    fireEvent.click(screen.getByRole('button', { name: /sign out/i }));
    await waitFor(() => expect(logout).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(navigate).toHaveBeenCalledWith('/login', { replace: true }),
    );
  });

  it('redirects to /login when the session is already cleared (no user)', () => {
    Object.assign(authState, { user: null, profile: null, loading: false });
    render(<PendingApprovalPage />);
    expect(navigate).toHaveBeenCalledWith('/login', { replace: true });
  });

  it('redirects an already-approved user to /dashboard', () => {
    Object.assign(authState, {
      user: { id: 'u1', email: 'hello@linetec.com' },
      profile: { role: 'billing' },
      loading: false,
    });
    render(<PendingApprovalPage />);
    expect(navigate).toHaveBeenCalledWith('/dashboard', { replace: true });
  });

  it('has no detectable accessibility violations', async () => {
    const { container } = render(<PendingApprovalPage />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
