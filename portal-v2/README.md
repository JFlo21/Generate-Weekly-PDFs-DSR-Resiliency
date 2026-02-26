# Linetec Report Portal v2

A modern revamp of the Linetec Report Portal built with **React 18 + TypeScript + Framer Motion + Tailwind CSS + Vite**, using **Supabase** for authentication and database, designed to deploy on **Vercel**.

> **Note:** The original `portal/` directory is kept intact for reference. This `portal-v2/` directory is the new frontend — it proxies all `/api/*` calls to the existing Express backend.

---

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [Prerequisites](#prerequisites)
3. [Supabase Setup](#supabase-setup)
4. [Local Development](#local-development)
5. [Vercel Deployment](#vercel-deployment)
6. [How Auth Works](#how-auth-works)
7. [How Activity Logging Works](#how-activity-logging-works)
8. [How Role Assignment Works](#how-role-assignment-works)
9. [Project Structure](#project-structure)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend framework | React 18 + TypeScript |
| Build tool | Vite 5 |
| Animations | Framer Motion |
| Styling | Tailwind CSS |
| Auth + Database | Supabase (`@supabase/supabase-js`) |
| Routing | React Router DOM v6 |
| Icons | Lucide React |
| Class utilities | clsx + tailwind-merge |

---

## Prerequisites

- **Node.js 18+** and **npm**
- A [Supabase](https://supabase.com) account (free tier works)
- A [Vercel](https://vercel.com) account (for deployment)
- A **GitHub Personal Access Token** (for the Express backend)

---

## Supabase Setup

### 1. Create a Supabase project

1. Go to [supabase.com](https://supabase.com) and click **New project**.
2. Choose a name (e.g. `linetec-portal`), set a database password, and select a region.
3. Wait for the project to initialize (~1 minute).

### 2. Run the schema

1. In the Supabase dashboard, navigate to **SQL Editor**.
2. Open `portal-v2/supabase/schema.sql` from this repo.
3. Paste the entire contents and click **Run**.
4. This creates:
   - `user_role` enum (`admin`, `viewer`, `biller`)
   - `profiles` table (linked to `auth.users` via trigger)
   - `activity_logs` table
   - `artifact_downloads` table
   - Indexes, RLS policies, and triggers

### 3. Copy your project credentials

In the Supabase dashboard → **Settings → API**:
- Copy **Project URL** → `VITE_SUPABASE_URL`
- Copy **anon / public** key → `VITE_SUPABASE_ANON_KEY`

### 4. Enable email/password auth

1. Go to **Authentication → Providers**.
2. Make sure **Email** is enabled.
3. Optionally disable "Confirm email" during development.

### 5. Make yourself an admin

After signing up through the portal, run this in the SQL Editor:

```sql
UPDATE profiles SET role = 'admin' WHERE email = 'your@email.com';
```

---

## Local Development

```bash
# 1. Install portal-v2 dependencies
cd portal-v2
npm install

# 2. Copy and fill in environment variables
cp .env.example .env.local
# Edit .env.local — set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY

# 3. Start the Express backend (in a separate terminal)
cd ../portal
npm install
npm start          # Runs on http://localhost:3000

# 4. Start the Vite dev server
cd ../portal-v2
npm run dev        # Runs on http://localhost:5173

# 5. Open http://localhost:5173
```

Vite automatically proxies `/api`, `/auth`, `/csrf-token`, and `/health` to `http://localhost:3000`, so the Express backend handles all data fetching while the frontend runs on port 5173.

---

## Vercel Deployment

### Option A — Frontend on Vercel + Express backend elsewhere (Recommended)

This is the simplest approach. Deploy the Vite frontend on Vercel and host the Express backend separately on [Railway](https://railway.app), [Render](https://render.com), or a VPS.

**Why separate?** The Express backend uses SSE (`/api/events`), in-memory polling state, and long-lived connections that don't work with Vercel's serverless model.

**Steps:**

1. Push your branch to GitHub.
2. Go to [vercel.com](https://vercel.com) → **Add New Project** → import this repo.
3. Set **Root Directory** to `portal-v2`.
4. Set **Build Command** to `npm run build`.
5. Set **Output Directory** to `dist`.
6. Add environment variables:
   - `VITE_SUPABASE_URL` — your Supabase project URL
   - `VITE_SUPABASE_ANON_KEY` — your Supabase anon key
   - `VITE_API_BASE_URL` — the URL of your deployed Express backend (e.g. `https://your-backend.railway.app`)
7. Deploy the Express backend (`portal/`) to Railway or Render separately.
8. Click **Deploy**.

### Option B — Full stack on Vercel (Advanced)

This requires converting the Express routes into Vercel serverless functions under `portal-v2/api/`:

1. Create `portal-v2/api/runs.ts`, `portal-v2/api/latest.ts`, etc. as individual Vercel functions.
2. **Important:** The `/api/events` SSE endpoint **cannot run on Vercel serverless** — you must replace it with [Supabase Realtime](https://supabase.com/docs/guides/realtime) subscriptions instead.
3. High-level migration steps:
   - Move GitHub API calls from `portal/routes/api.js` into serverless functions
   - Replace the `EventSource` SSE listener in `useRuns.ts` with a Supabase Realtime channel
   - Store run data in a Supabase table (updated by a scheduled serverless function) instead of in-memory

Option A is recommended for most use cases.

---

## How Auth Works

```
User visits portal → AuthGuard checks Supabase session
  └─ No session → redirect to /login
  └─ Has session → render dashboard

User signs up on /login
  → Supabase creates a row in auth.users
  → handle_new_user() trigger fires
  → Creates a row in profiles with role = 'viewer'

User signs in
  → Supabase auth.signInWithPassword()
  → Session stored in localStorage (Supabase default)
  → Profile fetched from profiles table
  → User lands on /dashboard
```

---

## How Activity Logging Works

Every significant user action (download, login, navigation) should insert a row into `activity_logs`:

```typescript
import { supabase } from '../lib/supabase';

await supabase.from('activity_logs').insert({
  user_id: user.id,
  action: 'downloaded_artifact',
  resource: artifact.name,
  metadata: { size: artifact.size_in_bytes },
});
```

Admins can view the full feed at `/dashboard/admin/activity`. The page subscribes to real-time Supabase changes so new entries appear instantly.

---

## How Role Assignment Works

1. Admin navigates to **Dashboard → Admin Users** (`/dashboard/admin/users`).
2. The page loads all `profiles` rows (RLS allows admins to see all).
3. Each row has a **Role** dropdown (`viewer`, `biller`, `admin`).
4. Changing the dropdown calls `supabase.from('profiles').update({ role })`.
5. The change takes effect immediately — the user's next page load will reflect their new role.

You can also change roles directly via SQL:

```sql
UPDATE profiles SET role = 'admin' WHERE email = 'colleague@linetec.com';
```

---

## Project Structure

```
portal-v2/
├── index.html
├── package.json
├── tsconfig.json / tsconfig.app.json / tsconfig.node.json
├── vite.config.ts
├── tailwind.config.ts
├── postcss.config.js
├── .env.example
├── README.md
│
├── src/
│   ├── main.tsx               # React mount
│   ├── App.tsx                # Root router + AuthProvider + AnimatePresence
│   ├── lib/
│   │   ├── supabase.ts        # Supabase client
│   │   ├── api.ts             # Typed fetch helpers for Express backend
│   │   ├── types.ts           # TypeScript interfaces
│   │   └── utils.ts           # formatDate, formatSize, timeAgo, cn()
│   ├── hooks/
│   │   ├── useAuth.ts         # Supabase auth state + login/signup/logout
│   │   ├── useRuns.ts         # Polling + SSE for workflow runs
│   │   ├── useArtifacts.ts    # Fetch artifacts for a selected run
│   │   └── useToast.ts        # Toast state management
│   ├── components/
│   │   ├── layout/            # Navbar, Sidebar, DashboardLayout, PageTransition
│   │   ├── auth/              # LoginPage, AuthGuard
│   │   ├── dashboard/         # DashboardPage, StatsGrid, SearchBar, RunCard, RunList, ArtifactPanel, ExcelViewer
│   │   ├── admin/             # UsersPage, ActivityPage
│   │   └── ui/                # AnimatedCounter, GlassCard, ParticleBackground, Skeleton, Badge, Toast
│   └── styles/
│       └── globals.css
│
└── supabase/
    └── schema.sql             # Full database schema
```
