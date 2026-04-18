import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  LayoutDashboard,
  Users,
  Activity,
  ChevronLeft,
  ChevronRight,
  Package,
  Sparkles,
  BookOpen,
  ExternalLink,
} from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { cn } from '../../lib/utils';

// Docusaurus URL — configured via env var so the Docusaurus deployment can
// move without a code change. When unset, the docs nav entries are hidden
// entirely rather than producing a dead link.
const DOCS_URL = (import.meta.env.VITE_DOCS_URL ?? '').trim();

interface NavItem {
  /** Internal react-router path. Mutually exclusive with `href`. */
  to?: string;
  /** External URL — opens in a new tab with an external-link icon. */
  href?: string;
  icon: React.ElementType;
  label: string;
  adminOnly?: boolean;
  badge?: string;
}

const navItems: NavItem[] = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  ...(DOCS_URL
    ? [
        {
          href: DOCS_URL,
          icon: BookOpen,
          label: 'Docs & Updates',
          badge: 'New',
        } satisfies NavItem,
      ]
    : []),
  { to: '/dashboard/admin/users', icon: Users, label: 'Admin Users', adminOnly: true },
  { to: '/dashboard/admin/activity', icon: Activity, label: 'Activity', adminOnly: true },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const { profile } = useAuth();
  const isAdmin = profile?.role === 'admin';
  const visibleItems = navItems.filter((item) => !item.adminOnly || isAdmin);

  return (
    <motion.aside
      animate={{ width: collapsed ? 72 : 232 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      className="relative flex flex-col h-full bg-white border-r border-slate-200 shrink-0"
    >
      {/* Section label */}
      <div className="px-4 pt-5 pb-3">
        <motion.p
          animate={{ opacity: collapsed ? 0 : 1 }}
          transition={{ duration: 0.15 }}
          className="text-[10px] font-semibold uppercase tracking-wider text-slate-400"
        >
          Navigation
        </motion.p>
      </div>

      {/* Nav items */}
      <nav className="flex-1 flex flex-col gap-1 px-3">
        {visibleItems.map((item, i) => {
          const Icon = item.icon;
          const key = item.to ?? item.href ?? item.label;

          // External link (Docusaurus docs site) — opens in a new tab with
          // an icon hint, styled to match the non-active NavLink state so
          // the sidebar stays visually cohesive.
          if (item.href) {
            return (
              <motion.div
                key={key}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
              >
                <a
                  href={item.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={`${item.label} (opens in a new tab)`}
                  className="relative flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all whitespace-nowrap group text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                >
                  <Icon
                    size={18}
                    className="shrink-0 transition-transform group-hover:scale-110"
                  />
                  <motion.span
                    animate={{
                      opacity: collapsed ? 0 : 1,
                      width: collapsed ? 0 : 'auto',
                    }}
                    transition={{ duration: 0.15 }}
                    className="overflow-hidden flex-1"
                  >
                    {item.label}
                  </motion.span>
                  {!collapsed && item.badge && (
                    <span className="text-[9px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-brand-red/10 text-brand-red border border-brand-red/20">
                      {item.badge}
                    </span>
                  )}
                  {!collapsed && !item.badge && (
                    <ExternalLink
                      size={12}
                      className="shrink-0 text-slate-400 group-hover:text-slate-600 transition-colors"
                    />
                  )}
                </a>
              </motion.div>
            );
          }

          // Internal route — react-router NavLink with active-state styling.
          return (
            <motion.div
              key={key}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.04 }}
            >
              <NavLink
                to={item.to!}
                end={item.to === '/dashboard'}
                className={({ isActive }) =>
                  cn(
                    'relative flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all whitespace-nowrap group',
                    isActive
                      ? 'bg-gradient-to-r from-brand-red to-red-700 text-white shadow-md shadow-brand-red/20'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <motion.span
                        layoutId="sidebar-active-dot"
                        className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-white rounded-r-full"
                        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                      />
                    )}
                    <Icon
                      size={18}
                      className={cn(
                        'shrink-0 transition-transform',
                        !isActive && 'group-hover:scale-110'
                      )}
                    />
                    <motion.span
                      animate={{
                        opacity: collapsed ? 0 : 1,
                        width: collapsed ? 0 : 'auto',
                      }}
                      transition={{ duration: 0.15 }}
                      className="overflow-hidden"
                    >
                      {item.label}
                    </motion.span>
                  </>
                )}
              </NavLink>
            </motion.div>
          );
        })}
      </nav>

      {/* Bottom promo card — fills empty space gracefully */}
      {!collapsed && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="m-3 p-4 rounded-2xl bg-gradient-to-br from-slate-900 via-slate-800 to-red-950 text-white overflow-hidden relative"
        >
          <div className="absolute -right-4 -top-4 w-20 h-20 rounded-full bg-brand-red/20 blur-2xl pointer-events-none" />
          <div className="relative">
            <div className="flex items-center gap-1.5 mb-2">
              <Sparkles size={12} className="text-amber-300" />
              <span className="text-[10px] font-semibold uppercase tracking-wider text-amber-300">
                Pro tip
              </span>
            </div>
            <p className="text-xs font-medium leading-relaxed text-white/90">
              Press{' '}
              <kbd className="inline-flex items-center justify-center px-1.5 py-0.5 rounded bg-white/15 border border-white/20 text-[10px] font-mono">
                ⌘K
              </kbd>{' '}
              to search runs &amp; artifacts instantly.
            </p>
          </div>
        </motion.div>
      )}

      {/* Collapsed icon-only footer */}
      {collapsed && (
        <div className="flex justify-center pb-4">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-slate-900 to-red-950 flex items-center justify-center">
            <Package size={16} className="text-white" />
          </div>
        </div>
      )}

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="absolute top-5 -right-3 z-10 flex items-center justify-center w-6 h-6 rounded-full bg-white border border-slate-200 shadow-sm text-slate-500 hover:text-slate-900 hover:border-slate-300 transition-colors"
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
      </button>
    </motion.aside>
  );
}
