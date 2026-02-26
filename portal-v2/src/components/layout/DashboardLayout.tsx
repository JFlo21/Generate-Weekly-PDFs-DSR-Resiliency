import { Outlet } from 'react-router-dom';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';
import { useRuns } from '../../hooks/useRuns';

export function DashboardLayout() {
  const { countdown, refresh, isConnected } = useRuns();

  return (
    <div className="flex flex-col h-screen bg-slate-50">
      <Navbar countdown={countdown} isConnected={isConnected} onRefresh={refresh} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
