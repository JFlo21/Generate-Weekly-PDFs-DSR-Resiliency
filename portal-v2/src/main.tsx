// Sentry must be the very first import so it can instrument subsequent modules
import './lib/sentry';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import { ConfigError } from './components/ui/ConfigError';
import './styles/globals.css';

const root = document.getElementById('root');
if (!root) throw new Error('Root element not found');

const isConfigured = Boolean(
  import.meta.env.VITE_SUPABASE_URL && import.meta.env.VITE_SUPABASE_ANON_KEY
);

createRoot(root).render(
  <StrictMode>
    {isConfigured ? <App /> : <ConfigError />}
  </StrictMode>
);
