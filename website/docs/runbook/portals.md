---
id: portals
title: Portals
sidebar_position: 4
---

# Portals

The repo ships two operator UIs. Both are optional for the core pipeline.

## `portal/` (Express)

Node.js + Express server that exposes operator views over the generator's
output. Key paths:

- `server.js` — entry point.
- `routes/` — HTTP routes.
- `services/` — Smartsheet, generator, and filesystem adapters.
- `middleware/` — auth and logging.
- `public/` — static assets.
- `tests/` — `vitest` suite (`vitest.config.mjs`).

Run locally:

```bash
cd portal
cp .env.example .env
npm install
node server.js
```

## `portal-v2/` (Vite + React)

In-progress rewrite. Uses Vite, Tailwind, Supabase, and deploys to Vercel
(`vercel.json`). Key paths:

- `src/` — React source.
- `supabase/` — migrations and edge function scaffolding.
- `vite.config.ts`, `tailwind.config.ts`, `tsconfig*.json` — standard
  frontend config.

Run locally:

```bash
cd portal-v2
cp .env.example .env
npm install
npm run dev
```

## When to touch which

- **Bug in an existing operator view** → `portal/`.
- **New UI feature** → `portal-v2/`.
- **Neither** is in the hot path of the scheduled report generation.
