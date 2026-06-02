import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderHook } from '@testing-library/react';
import { ToastProvider, useToastContext } from '../ToastContext';

// ------------------------------------------------------------------
// Test 1: addToast renders the message in the output
// ------------------------------------------------------------------
describe('ToastProvider', () => {
  it('renders a toast message when addToast is called', async () => {
    function Consumer() {
      const { addToast } = useToastContext();
      return (
        <button onClick={() => addToast('info', 'hello world')}>
          add toast
        </button>
      );
    }

    render(
      <ToastProvider>
        <Consumer />
      </ToastProvider>
    );

    await userEvent.click(screen.getByRole('button', { name: 'add toast' }));
    expect(screen.getByText('hello world')).toBeInTheDocument();
  });

  // ------------------------------------------------------------------
  // Test 2: removeToast removes the toast from the context toasts array
  // ------------------------------------------------------------------
  it('removes a toast when removeToast is called', async () => {
    // This consumer reflects the toasts array directly so we can assert
    // on it independently of the framer-motion exit animation in ToastContainer.
    function ConsumerWithCapture() {
      const { addToast, removeToast, toasts } = useToastContext();
      return (
        <>
          <button onClick={() => addToast('error', 'to be removed')}>
            add
          </button>
          <span data-testid="toast-count">{toasts.length}</span>
          {toasts.map((t) => (
            <button
              key={t.id}
              onClick={() => removeToast(t.id)}
              aria-label={`remove-${t.id}`}
            >
              remove
            </button>
          ))}
        </>
      );
    }

    render(
      <ToastProvider>
        <ConsumerWithCapture />
      </ToastProvider>
    );

    // Initially zero toasts
    expect(screen.getByTestId('toast-count').textContent).toBe('0');

    await userEvent.click(screen.getByRole('button', { name: 'add' }));
    // One toast added — consumer reflects it
    expect(screen.getByTestId('toast-count').textContent).toBe('1');

    // Click the inline remove button rendered by the consumer
    const removeBtn = screen.getByRole('button', { name: /^remove-/ });
    await userEvent.click(removeBtn);
    // toasts array back to zero — removeToast worked
    expect(screen.getByTestId('toast-count').textContent).toBe('0');
  });

  // ------------------------------------------------------------------
  // Test 3: exactly ONE ToastContainer region in the provider (C-01)
  // ------------------------------------------------------------------
  it('renders exactly one ToastContainer (C-01 single-stack guarantee)', () => {
    render(
      <ToastProvider>
        <div>child content</div>
      </ToastProvider>
    );

    // ToastContainer renders a fixed div at bottom-right z-50 per Toast.tsx
    const containers = document.querySelectorAll('.fixed.bottom-6.right-6.z-50');
    expect(containers).toHaveLength(1);
  });

  // ------------------------------------------------------------------
  // Test 4: useToastContext() outside provider throws
  // ------------------------------------------------------------------
  it('throws when useToastContext is called outside ToastProvider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => {
      renderHook(() => useToastContext());
    }).toThrow('useToastContext must be used within ToastProvider');

    spy.mockRestore();
  });
});
