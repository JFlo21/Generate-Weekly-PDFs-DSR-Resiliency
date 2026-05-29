import { describe, it, expect } from 'vitest';
import type { Profile, UserRole } from '../types';

describe('types contract (D-01/D-02)', () => {
  it('Profile has exactly id, email, role, created_at', () => {
    const p: Profile = {
      id: 'u1',
      email: 'a@linetec.com',
      role: 'billing',
      created_at: '2026-05-29T00:00:00Z',
    };
    expect(Object.keys(p).sort()).toEqual(
      ['created_at', 'email', 'id', 'role']
    );
  });
  it('UserRole admits only admin | billing | pending', () => {
    const roles: UserRole[] = ['admin', 'billing', 'pending'];
    expect(roles).toHaveLength(3);
    // @ts-expect-error 'viewer' is no longer a valid role
    const bad: UserRole = 'viewer';
    expect(bad).toBe('viewer'); // runtime value irrelevant; line must fail typecheck
  });
});
