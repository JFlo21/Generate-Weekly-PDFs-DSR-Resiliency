import { useMemo } from 'react';
import { motion } from 'framer-motion';
import { BookOpen, ExternalLink, FileText, History, Rocket, AlertCircle } from 'lucide-react';

interface QuickLink {
  title: string;
  description: string;
  path: string;
  icon: React.ElementType;
}

const quickLinkDefs: QuickLink[] = [
  {
    title: 'Getting Started',
    description: 'Learn how to set up and use the Linetec Portal',
    path: '/docs/intro',
    icon: Rocket,
  },
  {
    title: 'Changelog',
    description: 'View recent updates, fixes, and new features',
    path: '/changelog',
    icon: History,
  },
  {
    title: 'Run Logs',
    description: 'Detailed logs from workflow runs and artifact generation',
    path: '/docs/run-logs',
    icon: FileText,
  },
  {
    title: 'Release Notes',
    description: 'Major version releases and migration guides',
    path: '/docs/releases',
    icon: AlertCircle,
  },
];

export function DocsPage() {
  // Read env var inside component to avoid module-level reference issues
  const docsUrl = useMemo(() => (import.meta.env.VITE_DOCS_URL ?? '').trim(), []);
  const quickLinks = useMemo(
    () =>
      quickLinkDefs.map((link) => ({
        ...link,
        href: docsUrl ? `${docsUrl}${link.path}` : '#',
      })),
    [docsUrl]
  );
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="p-6 lg:p-8 space-y-8 max-w-5xl mx-auto"
    >
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="flex flex-col gap-1.5"
      >
        <div className="flex items-center gap-2">
          <div className="w-1 h-6 rounded-full bg-gradient-to-b from-brand-red to-red-700" />
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Documentation & Updates
          </h1>
        </div>
        <p className="text-sm text-slate-500 ml-3">
          Access guides, changelogs, run logs, and release notes for the Linetec Portal.
        </p>
      </motion.div>

      {/* Quick Links Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {quickLinks.map((link, i) => {
          const Icon = link.icon;
          return (
            <motion.a
              key={link.title}
              href={link.href}
              target="_blank"
              rel="noopener noreferrer"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 + i * 0.05 }}
              className="group relative flex flex-col gap-3 p-5 bg-white border border-slate-200 rounded-2xl shadow-sm hover:shadow-md hover:border-brand-red/30 transition-all"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-slate-100 to-slate-50 border border-slate-200 group-hover:from-brand-red/10 group-hover:to-red-50 group-hover:border-brand-red/20 transition-colors">
                  <Icon size={18} className="text-slate-600 group-hover:text-brand-red transition-colors" />
                </div>
                <ExternalLink size={14} className="text-slate-300 group-hover:text-brand-red transition-colors" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-900 group-hover:text-brand-red transition-colors">
                  {link.title}
                </h3>
                <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">
                  {link.description}
                </p>
              </div>
            </motion.a>
          );
        })}
      </div>

      {/* Embedded Docs (iframe) */}
      {docsUrl ? (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="space-y-3"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-700">Full Documentation</h2>
            <a
              href={docsUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-brand-red transition-colors"
            >
              Open in new tab
              <ExternalLink size={12} />
            </a>
          </div>
          <div className="relative w-full h-[600px] rounded-2xl overflow-hidden border border-slate-200 shadow-sm bg-white">
            <iframe
              src={docsUrl}
              title="Linetec Documentation"
              className="absolute inset-0 w-full h-full"
              sandbox="allow-scripts allow-same-origin allow-popups allow-forms"
            />
          </div>
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="flex flex-col items-center justify-center py-16 px-6 bg-slate-50 border border-slate-200 rounded-2xl"
        >
          <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-amber-100 border border-amber-200 mb-4">
            <BookOpen size={24} className="text-amber-600" />
          </div>
          <h3 className="text-base font-semibold text-slate-900 text-center">
            Documentation Not Configured
          </h3>
          <p className="text-sm text-slate-500 text-center mt-1 max-w-sm">
            Set the <code className="px-1.5 py-0.5 bg-slate-100 rounded text-xs font-mono">VITE_DOCS_URL</code> environment variable to enable the embedded documentation viewer.
          </p>
        </motion.div>
      )}
    </motion.div>
  );
}
