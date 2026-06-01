import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RoleGuard } from '../RoleGuard';

const authState = { profile: null as unknown, loading: false };
vi.mock('../../../hooks/useAuth', () => ({ useAuth: () => authState }));
vi.mock('react-router-dom', () => ({ Link: ({ children }: { children: React.ReactNode }) => <a>{children}</a> }));

describe('RoleGuard (RBAC-05)', () => {
  it('blocks a billing user from an admin-only surface', () => {
    Object.assign(authState, { profile: { role: 'billing' }, loading: false });
    render(<RoleGuard allow={['admin']}><div>admin-only</div></RoleGuard>);
    expect(screen.queryByText('admin-only')).toBeNull();
    expect(screen.getByText(/permission to view this page/i)).toBeTruthy();
  });
  it('allows an admin user', () => {
    Object.assign(authState, { profile: { role: 'admin' }, loading: false });
    render(<RoleGuard allow={['admin']}><div>admin-only</div></RoleGuard>);
    expect(screen.getByText('admin-only')).toBeTruthy();
  });
  it('renders null while loading', () => {
    Object.assign(authState, { profile: null, loading: true });
    const { container } = render(<RoleGuard allow={['admin']}><div>admin-only</div></RoleGuard>);
    expect(container.textContent).toBe('');
  });
});
