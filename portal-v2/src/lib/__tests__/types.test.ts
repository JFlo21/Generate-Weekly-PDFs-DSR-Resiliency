import { describe, it, expect } from 'vitest';
import type { Profile, UserRole, BillingArtifact } from '../types';

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

describe('BillingArtifact type contract (public.artifacts row shape)', () => {
  it('has exactly the 9 required keys matching public.artifacts columns', () => {
    const sample: BillingArtifact = {
      id: 'a1b2c3d4-0000-0000-0000-000000000000',
      work_request: '90001',
      week_ending: '2026-05-17',
      week_ending_fmt: '051726',
      variant: '',
      filename: 'WR_90001_WeekEnding_051726.xlsx',
      storage_path: '2026-05-17/WR_90001_WeekEnding_051726.xlsx',
      size_bytes: 12345,
      created_at: '2026-05-17T12:00:00Z',
    };
    expect(Object.keys(sample).sort()).toEqual(
      ['created_at', 'filename', 'id', 'size_bytes', 'storage_path',
       'variant', 'week_ending', 'week_ending_fmt', 'work_request']
    );
  });
});
