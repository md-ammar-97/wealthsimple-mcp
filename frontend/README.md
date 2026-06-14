# Review Pulse — Frontend

Next.js 15 frontend for the Review Pulse app store intelligence pipeline. Deployed to Render alongside the Python backend.

**Live:** [wealthsimple-mcp.onrender.com](https://wealthsimple-mcp.onrender.com)

---

## Pages

| Route | Description |
|---|---|
| `/` | Homepage — marketing hero, pipeline strip, feature cards |
| `/upload` | Analyse any app — email + app name + CSV → 8-step live progress → inline results |
| `/analytics` | Wealthsimple historical analytics — Recharts charts + run history table |
| `/run` | Legacy upload + pipeline tracker |
| `/results` | Legacy results view |

---

## Tech stack

- **Framework:** Next.js 15 (App Router, Turbopack)
- **Language:** TypeScript / React 19
- **Design system:** Atlassian Design System tokens (custom CSS, no `@atlaskit` packages)
- **Charts:** Recharts 3
- **Animations:** Framer Motion 11
- **Fonts:** Inter Variable (body), DM Serif Display (legacy results)
- **Icons:** Material Symbols Outlined (Google Fonts)
- **Deployment:** Render (Node.js, runs alongside Python backend)

---

## Local development

```bash
cd frontend
npm install
npm run dev       # http://localhost:3000 (Turbopack)
```

The API routes call `python3 -m pulse.cli` so the Python environment must be active in the same repo root:

```bash
# In repo root (before starting Next.js):
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -r requirements.txt
pip install -e .
```

Required env vars (set in `.env.local` or shell):

```
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AIza...
MCP_API_KEY=...
```

---

## Key API routes

| Route | Method | Purpose |
|---|---|---|
| `/api/upload` | `POST` | Accept CSV + `email` + `appName`; save to `data/input/reviews.csv`; store meta in `global.csvMeta` |
| `/api/run` | `POST` | Spawn `pulse run`; initialise `global.pipelineQueue`; return `{ runId }` immediately; send MCP email after exit code 0 |
| `/api/pipeline/status` | `GET` (SSE) | Drain `global.pipelineQueue` at 500ms intervals; emit step state events |
| `/api/results` | `GET` | Read `outputs/run_summary.json` + artifact files; return `RunResult` JSON |
| `/api/analytics` | `GET` | Read `data/runs/ledger.json`; support `?days=` filter; return chart data + run history |
| `/api/debug` | `GET` | Diagnostic endpoint — Python version, pulse install, filesystem state |

---

## Design system

Tokens are in `src/styles/tokens.css`. Key values:

| Token | Value |
|---|---|
| `--color-primary` | `#0052CC` (Atlassian blue-500) |
| `--nav-bg` | `#0747A6` (Atlassian blue-600) |
| `--color-bg-page` | `#F4F5F7` (Atlassian N10) |
| `--shadow-card` | Atlassian elevation level 1 |
| `--radius-md` | `4px` |

Global CSS primitives in `src/styles/global.css`: `.btn`, `.btn-primary`, `.btn-default`, `.btn-lg`, `.atlas-card`, `.atlas-input`, `.atlas-label`, `.badge`, `.badge-blue/green/red/...`, `.section-msg-info/success/warning/error`.

---

## SSE progress tracking

The pipeline emits JSON log lines to stdout per step. The run route:
1. Splits each stdout chunk by `\n` and parses each line independently (fixes multi-line buffer bug)
2. Pushes valid events into `global.pipelineQueue[]`

The SSE route (`/api/pipeline/status`) drains the queue every 500ms and emits step state events to the client. This queue-based approach prevents event loss when the Python process flushes multiple log lines in the same TCP packet.

---

## Build

```bash
npm run build    # production build (Turbopack)
npm start        # start production server
```

The Render build command is defined in `render.yaml` at the repo root and runs `npm ci && npm run build` after installing Python dependencies.
