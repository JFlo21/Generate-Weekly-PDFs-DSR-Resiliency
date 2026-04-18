import { motion } from 'framer-motion';
import { CheckCircle, Package, Download, Activity, TrendingUp } from 'lucide-react';
import { AnimatedCounter } from '../ui/AnimatedCounter';
import type { WorkflowRun, Artifact } from '../../lib/types';

interface StatsGridProps {
  runs: WorkflowRun[];
  artifacts: Artifact[];
}

export function StatsGrid({ runs, artifacts }: StatsGridProps) {
  const successful = runs.filter((r) => r.conclusion === 'success').length;
  const totalArtifacts = artifacts.length;
  const successRate = runs.length > 0 ? Math.round((successful / runs.length) * 100) : 0;

  const stats = [
    {
      label: 'Total Runs',
      value: runs.length,
      icon: Activity,
      iconColor: 'text-blue-600',
      iconBg: 'bg-blue-100',
      ringColor: 'ring-blue-100',
      accent: 'from-blue-500/10 to-transparent',
      valueColor: 'text-slate-900',
      trend: null,
    },
    {
      label: 'Successful',
      value: successful,
      icon: CheckCircle,
      iconColor: 'text-emerald-600',
      iconBg: 'bg-emerald-100',
      ringColor: 'ring-emerald-100',
      accent: 'from-emerald-500/10 to-transparent',
      valueColor: 'text-slate-900',
      trend: runs.length > 0 ? `${successRate}% success` : null,
    },
    {
      label: 'Artifacts',
      value: totalArtifacts,
      icon: Package,
      iconColor: 'text-violet-600',
      iconBg: 'bg-violet-100',
      ringColor: 'ring-violet-100',
      accent: 'from-violet-500/10 to-transparent',
      valueColor: 'text-slate-900',
      trend: null,
    },
    {
      label: 'Downloads',
      value: 0,
      icon: Download,
      iconColor: 'text-brand-red',
      iconBg: 'bg-red-100',
      ringColor: 'ring-red-100',
      accent: 'from-red-500/10 to-transparent',
      valueColor: 'text-slate-900',
      trend: null,
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map((stat, i) => {
        const Icon = stat.icon;
        return (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              delay: i * 0.06,
              type: 'spring',
              stiffness: 220,
              damping: 22,
            }}
            whileHover={{ y: -3 }}
            className="relative bg-white rounded-2xl p-5 border border-slate-200/70 shadow-[0_1px_2px_rgba(0,0,0,0.04)] hover:shadow-[0_8px_24px_rgba(0,0,0,0.06)] transition-shadow overflow-hidden group"
          >
            {/* Subtle gradient accent in the corner */}
            <div
              className={`absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl ${stat.accent} rounded-full blur-2xl pointer-events-none opacity-60 group-hover:opacity-100 transition-opacity`}
              aria-hidden="true"
            />

            <div className="relative flex items-start justify-between mb-4">
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                {stat.label}
              </span>
              <div
                className={`w-9 h-9 rounded-xl ${stat.iconBg} ring-4 ${stat.ringColor} flex items-center justify-center`}
              >
                <Icon size={17} className={stat.iconColor} strokeWidth={2.2} />
              </div>
            </div>

            <div className="relative flex items-baseline gap-2">
              <p className={`text-3xl font-bold tracking-tight ${stat.valueColor}`}>
                <AnimatedCounter to={stat.value} />
              </p>
              {stat.trend && (
                <span className="inline-flex items-center gap-0.5 text-[11px] font-medium text-emerald-600">
                  <TrendingUp size={10} strokeWidth={2.5} />
                  {stat.trend}
                </span>
              )}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
