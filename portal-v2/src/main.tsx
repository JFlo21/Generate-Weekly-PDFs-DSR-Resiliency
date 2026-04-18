// Sentry must be the very first import so it can instrument subsequent modules
// Cache bust: 2026-04-18T06:00:00Z — force Vite to recompile all modules
import './lib/sentry';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import './styles/globals.css';

const root = document.getElementById('root');
if (!root) throw new Error('Root element not found');

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>
);
