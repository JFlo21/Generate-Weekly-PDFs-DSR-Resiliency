import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import { SpeedInsights } from '@vercel/speed-insights/react';
import { AuthContext, useAuthState } from './hooks/useAuth';
import { AuthGuard } from './components/auth/AuthGuard';
import { LoginPage } from './components/auth/LoginPage';
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
        <SpeedInsights />
      </AuthProvider>
    </BrowserRouter>
  );
}
