import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import { AuthContext, useAuthState } from './hooks/useAuth';
import { AuthGuard } from './components/auth/AuthGuard';
import { LoginPage } from './components/auth/LoginPage';
import { DashboardLayout } from './components/layout/DashboardLayout';
import { DashboardPage } from './components/dashboard/DashboardPage';
import { UsersPage } from './components/admin/UsersPage';
import { ForgotPasswordPage } from './components/auth/ForgotPasswordPage';
import { ResetPasswordPage } from './components/auth/ResetPasswordPage';
import { PendingApprovalPage } from './components/auth/PendingApprovalPage';
import { RoleGuard } from './components/auth/RoleGuard';
import { PageTransition } from './components/layout/PageTransition';
import { ToastContainer } from './components/ui/Toast';
import { ErrorBoundary } from './components/ui/ErrorBoundary';
import { useToast } from './hooks/useToast';

function AuthProvider({ children }: { children: React.ReactNode }) {
  const auth = useAuthState();
  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>;
}

export default function App() {
  const { toasts, removeToast } = useToast();

  return (
    <BrowserRouter>
      <ErrorBoundary>
      <AuthProvider>
        <AnimatePresence mode="wait">
          <Routes>
            <Route path="/login" element={<PageTransition><LoginPage /></PageTransition>} />
            <Route path="/auth/forgot" element={<PageTransition><ForgotPasswordPage /></PageTransition>} />
            <Route path="/auth/reset" element={<PageTransition><ResetPasswordPage /></PageTransition>} />
            <Route path="/pending" element={<PageTransition><PendingApprovalPage /></PageTransition>} />

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
                  <RoleGuard allow={['admin']}>
                    <PageTransition>
                      <UsersPage />
                    </PageTransition>
                  </RoleGuard>
                }
              />
            </Route>

            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </AnimatePresence>

        <ToastContainer toasts={toasts} onRemove={removeToast} />
      </AuthProvider>
      </ErrorBoundary>
    </BrowserRouter>
  );
}
