import { motion } from 'framer-motion';
import { ArtifactTable } from '../artifacts/ArtifactTable';

/**
 * DashboardPage — thin shell rendering ArtifactTable at /dashboard.
 * D-01: ArtifactTable is the /dashboard landing view.
 * D-02: Legacy runs/explorer files are preserved in the tree (Phase 07 removes them)
 *       but are no longer imported or rendered here.
 */
export function DashboardPage() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="p-6 lg:p-8 space-y-6 max-w-6xl mx-auto"
    >
      <div className="flex items-center gap-2">
        <div className="w-1 h-6 rounded-full bg-gradient-to-b from-brand-red to-red-700" />
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Artifacts
        </h1>
      </div>
      <ArtifactTable />
    </motion.div>
  );
}
