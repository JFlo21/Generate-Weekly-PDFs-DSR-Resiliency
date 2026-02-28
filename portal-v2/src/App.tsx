import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import { AuthContext, useAuthState } from './hooks/useAuth';
import { AuthGuard } from './components/auth/AuthGuard';
import { LoginPage } from './components/auth/LoginPage';
import { ConfirmEmailPage } from './components/auth/ConfirmEmailPage';
import { AuthCallback } from './components/auth/AuthCallback';
import { ForgotPasswordPage } from './components/auth/ForgotPasswordPage';
import { ResetPasswordPage } from './components/auth/ResetPasswordPage';
import { DashboardLayout } from './components/layout/DashboardLayout';
import { DashboardPage } from './components/dashboard/DashboardPage';
import { UsersPage } from './components/admin/UsersPage';
import { ActivityPage } from './components/admin/ActivityPage';
import { PageTransition } from './components/layout/PageTransition';
import { ToastContainer } from './components/ui/Toast';
import { useToast } from './hooks/useToast';

function AuthProvider({ children }: { children: React.ReactNode }) {
  const auth = useAuthState();
  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>;
}

export default function App() {
  const { toasts, removeToast } = useToast();

  return (
    <BrowserRouter>
      <AuthProvider>
        <AnimatePresence mode="wait">
          <Routes>
            <Route path="/login" element={<PageTransition><LoginPage /></PageTransition>} />
            <Route path="/auth/confirm-email" element={<PageTransition><ConfirmEmailPage /></PageTransition>} />
            <Route path="/auth/confirm" element={<PageTransition><AuthCallback /></PageTransition>} />
            <Route path="/auth/forgot-password" element={<PageTransition><ForgotPasswordPage /></PageTransition>} />
            <Route path="/auth/reset-password" element={<PageTransition><ResetPasswordPage /></PageTransition>} />

            <Route
              path="/dashboard"
              element={
                <AuthGuard>
                  <DashboardLayout />
                </AuthGuard>
              }
            >
              <Route
                index
                element={
                  <PageTransition>
                    <DashboardPage />
                  </PageTransition>
                }
              />
              <Route
                path="admin/users"
                element={
                  <PageTransition>
                    <UsersPage />
                  </PageTransition>
                }
              />
              <Route
                path="admin/activity"
                element={
                  <PageTransition>
                    <ActivityPage />
                  </PageTransition>
                }
              />
            </Route>

            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </AnimatePresence>

        <ToastContainer toasts={toasts} onRemove={removeToast} />
      </AuthProvider>
    </BrowserRouter>
  );
}
