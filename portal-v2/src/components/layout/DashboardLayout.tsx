import { Outlet } from 'react-router-dom';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';
import { useRuns } from '../../hooks/useRuns';
import type { WorkflowRun } from '../../lib/types';

export interface DashboardOutletContext {
  runs: WorkflowRun[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

export function DashboardLayout() {
  const { runs, loading, error, countdown, refresh, isConnected } = useRuns();

  const ctx: DashboardOutletContext = { runs, loading, error, refresh };

  return (
    <div className="flex flex-col h-screen bg-slate-50">
      <Navbar countdown={countdown} isConnected={isConnected} onRefresh={refresh} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <Outlet context={ctx} />
        </main>
      </div>
    </div>
  );
}
