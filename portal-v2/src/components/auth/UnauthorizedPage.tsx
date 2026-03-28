import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ShieldAlert } from 'lucide-react';

export function UnauthorizedPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-8">
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 200, damping: 20 }}
        className="bg-white rounded-2xl border border-slate-200 shadow-sm p-10 max-w-md w-full text-center space-y-6"
      >
        <div className="flex justify-center">
          <div className="p-4 rounded-full bg-red-50">
            <ShieldAlert size={36} className="text-brand-red" />
          </div>
        </div>
        <div>
          <h1 className="text-xl font-bold text-slate-900">Access Denied</h1>
          <p className="text-sm text-slate-500 mt-2">
            You don't have permission to view this page. Contact an administrator
            to request access.
          </p>
        </div>
        <button
          onClick={() => navigate('/dashboard', { replace: true })}
          className="inline-flex items-center justify-center px-5 py-2.5 rounded-xl bg-brand-red text-white text-sm font-medium hover:bg-brand-red/90 transition-colors"
        >
          Go to Dashboard
        </button>
      </motion.div>
    </div>
  );
}
