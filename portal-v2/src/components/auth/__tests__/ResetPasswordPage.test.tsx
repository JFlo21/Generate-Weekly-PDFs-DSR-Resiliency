import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { ResetPasswordPage } from '../ResetPasswordPage';

// Hoisted spies so the supabase mock factory can reference them.
const { verifyOtp, onAuthStateChange, unsubscribe } = vi.hoisted(() => ({
  verifyOtp: vi.fn(),
  onAuthStateChange: vi.fn(),
  unsubscribe: vi.fn(),
}));

vi.mock('../../../lib/supabase', () => ({
  supabase: { auth: { verifyOtp, onAuthStateChange, updateUser: vi.fn() } },
}));

vi.mock('../../../hooks/useToast', () => ({
  useToast: () => ({ toasts: [], addToast: () => {}, removeToast: () => {} }),
}));

vi.mock('react-router-dom', async () => {
  const React = await import('react');
  return {
    useNavigate: () => () => {},
    Link: ({ to, children }: { to: string; children: React.ReactNode }) =>
      React.createElement('a', { href: to }, children),
  };
});

// Render framer-motion components as plain elements (strip animation-only
// props) so jsdom rendering is deterministic and free of matchMedia access.
vi.mock('framer-motion', async () => {
  const React = await import('react');
  const STRIP = new Set([
    'initial', 'animate', 'exit', 'transition', 'whileHover', 'whileTap',
    'whileFocus', 'whileInView', 'whileDrag', 'layout', 'layoutId',
    'variants', 'drag', 'dragConstraints', 'onAnimationComplete',
    'onAnimationStart',
  ]);
  const clean = (props: Record<string, unknown>) => {
    const out: Record<string, unknown> = {};
    for (const k of Object.keys(props)) if (!STRIP.has(k)) out[k] = props[k];
    return out;
  };
  const motion = new Proxy(
    {},
    {
      get: (_t, tag: string) => (props: Record<string, unknown>) => {
        const { children, ...rest } = props;
        return React.createElement(tag, clean(rest), children as React.ReactNode);
      },
    }
  );
  return {
    motion,
    AnimatePresence: ({ children }: { children: React.ReactNode }) => children,
  };
});

const RECOVERY_URL = '/auth/reset?token_hash=abc123&type=recovery';

beforeEach(() => {
  verifyOtp.mockReset();
  onAuthStateChange.mockReset();
  unsubscribe.mockReset();
  verifyOtp.mockResolvedValue({ error: null });
  onAuthStateChange.mockReturnValue({ data: { subscription: { unsubscribe } } });
  window.history.pushState({}, '', '/auth/reset');
});

describe('ResetPasswordPage — token_hash recovery flow (auth-C)', () => {
  it('verifies the OTP with token_hash + recovery type from the URL', async () => {
    window.history.pushState({}, '', RECOVERY_URL);
    render(<ResetPasswordPage />);
    await act(async () => {}); // flush the mount effect's microtasks
    expect(verifyOtp).toHaveBeenCalledWith({
      token_hash: 'abc123',
      type: 'recovery',
    });
  });

  it('enables the reset form once verifyOtp succeeds', async () => {
    verifyOtp.mockResolvedValue({ error: null });
    window.history.pushState({}, '', RECOVERY_URL);
    render(<ResetPasswordPage />);
    expect(
      await screen.findByText('Enter your new password below.')
    ).toBeTruthy();
  });

  it('surfaces the expired-link message when verifyOtp returns an error', async () => {
    verifyOtp.mockResolvedValue({ error: { message: 'Token has expired' } });
    window.history.pushState({}, '', RECOVERY_URL);
    render(<ResetPasswordPage />);
    expect(
      await screen.findByText(/This reset link has expired/)
    ).toBeTruthy();
  });

  it('does not call verifyOtp when no token_hash is present (implicit flow)', async () => {
    render(<ResetPasswordPage />);
    await act(async () => {});
    expect(verifyOtp).not.toHaveBeenCalled();
  });

  it('still honors the PASSWORD_RECOVERY event as a fallback', async () => {
    render(<ResetPasswordPage />);
    expect(onAuthStateChange).toHaveBeenCalled();
    const handler = onAuthStateChange.mock.calls[0][0] as (e: string) => void;
    await act(async () => {
      handler('PASSWORD_RECOVERY');
    });
    expect(screen.getByText('Enter your new password below.')).toBeTruthy();
  });
});
