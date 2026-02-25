# AGENTS.md

## Cursor Cloud specific instructions

### Codebase Overview

This repo contains two products:

1. **Python Excel Generator** (root) — CLI tool that pulls data from Smartsheet API and generates weekly Excel billing reports.
2. **Node.js Report Portal** (`portal/`) — Express web app for viewing/downloading those reports.

### Running Tests

- **Python tests:** `PYTHONPATH=/workspace pytest tests/ -v` (the `PYTHONPATH` is required because `tests/test_performance_optimizations.py` imports root-level modules like `generate_weekly_pdfs`).
- **Portal tests:** `npx vitest run` from `portal/`.

### Running the Portal (dev mode)

```
cd portal && node --watch server.js
```

The portal runs on port 3000. Dev credentials: `admin` / `admin123` (password hash is generated via `node -e "console.log(require('bcryptjs').hashSync('admin123', 12))"`).

Set `POLLING_ENABLED=false` in `portal/.env` when no `GITHUB_TOKEN` is configured, otherwise the poller logs errors on every interval.

### Running the Python Generator

```
SKIP_UPLOAD=true python3 generate_weekly_pdfs.py
```

Without a valid `SMARTSHEET_API_TOKEN`, the script initializes correctly but fails at sheet validation (expected). For full end-to-end runs, a real token is required.

### Key Gotchas

- No lint configuration (ESLint/flake8/ruff) is committed to this repo. There are no `lint` npm scripts or Python linting configs.
- `pip install` puts binaries in `~/.local/bin`; ensure this is on `PATH`.
- The portal `.env` needs `ADMIN_PASSWORD_HASH` set to a bcrypt hash (not the plaintext password).
- The portal serves React/ReactDOM/htm from `node_modules` as vendor static files — no build step is needed.
- The Python generator processes 55+ Smartsheet sheets and 80K+ rows. A full run with a real `SMARTSHEET_API_TOKEN` takes 40+ minutes. For quick dev iteration, focus on unit tests (`pytest tests/`) rather than full generator runs.
- When running the generator, stdout is heavily buffered when piped. Use `python3 -u generate_weekly_pdfs.py` for unbuffered output if you need to monitor progress live.
