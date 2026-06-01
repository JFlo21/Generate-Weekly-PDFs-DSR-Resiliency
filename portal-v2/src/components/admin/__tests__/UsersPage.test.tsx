import { describe, it, expect } from 'vitest';
import { canDemote } from '../UsersPage';

/**
 * Unit-tests for the last-admin guard logic (RBAC-04).
 *
 * canDemote is exported from UsersPage and encapsulates the exact condition
 * used in updateRole so we can test it in isolation without mounting the full
 * component (which requires Supabase and routing contexts).
 *
 * canDemote(targetCurrentRole, newRole, adminCount) → true = demotion allowed
 */
describe('canDemote — last-admin guard (RBAC-04)', () => {
  it('blocks demoting the last admin to billing', () => {
    expect(canDemote('admin', 'billing', 1)).toBe(false);
  });

  it('blocks demoting the last admin to pending', () => {
    expect(canDemote('admin', 'pending', 1)).toBe(false);
  });

  it('allows demoting when there are 2 admins', () => {
    expect(canDemote('admin', 'billing', 2)).toBe(true);
  });

  it('allows demoting when there are 3 admins', () => {
    expect(canDemote('admin', 'pending', 3)).toBe(true);
  });

  it('allows changing a billing user to any role (not an admin demotion)', () => {
    expect(canDemote('billing', 'pending', 1)).toBe(true);
    expect(canDemote('billing', 'admin', 1)).toBe(true);
  });

  it('allows changing a pending user to any role', () => {
    expect(canDemote('pending', 'admin', 0)).toBe(true);
    expect(canDemote('pending', 'billing', 1)).toBe(true);
  });

  it('allows keeping the last admin as admin (same role)', () => {
    // newRole === 'admin', so the guard never fires
    expect(canDemote('admin', 'admin', 1)).toBe(true);
  });
});
