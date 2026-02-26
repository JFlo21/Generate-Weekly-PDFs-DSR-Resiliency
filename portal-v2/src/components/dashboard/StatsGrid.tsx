import { motion } from 'framer-motion';
import { CheckCircle, Package, Download, Activity } from 'lucide-react';
import { AnimatedCounter } from '../ui/AnimatedCounter';
import type { WorkflowRun, Artifact } from '../../lib/types';

interface StatsGridProps {
  runs: WorkflowRun[];
  artifacts: Artifact[];
}

export function StatsGrid({ runs, artifacts }: StatsGridProps) {
  const successful = runs.filter((r) => r.conclusion === 'success').length;
  const totalArtifacts = artifacts.length;

  const stats = [
    {
      label: 'Total Runs',
      value: runs.length,
      icon: Activity,
      color: 'text-blue-600',
      bg: 'bg-blue-50',
    },
    {
      label: 'Successful',
      value: successful,
      icon: CheckCircle,
      color: 'text-emerald-600',
      bg: 'bg-emerald-50',
    },
    {
      label: 'Artifacts',
      value: totalArtifacts,
      icon: Package,
      color: 'text-violet-600',
      bg: 'bg-violet-50',
    },
    {
      label: 'Downloads',
      value: 0,
      icon: Download,
      color: 'text-brand-red',
      bg: 'bg-red-50',
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map((stat, i) => {
        const Icon = stat.icon;
        return (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05, type: 'spring', stiffness: 200, damping: 20 }}
            whileHover={{ y: -2, boxShadow: '0 8px 30px rgba(0,0,0,0.08)' }}
            className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm cursor-default"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">
                {stat.label}
              </span>
              <div className={`w-8 h-8 rounded-xl ${stat.bg} flex items-center justify-center`}>
                <Icon size={16} className={stat.color} />
              </div>
            </div>
            <p className={`text-2xl font-bold ${stat.color}`}>
              <AnimatedCounter to={stat.value} />
            </p>
          </motion.div>
        );
      })}
    </div>
  );
}
