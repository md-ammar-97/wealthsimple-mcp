# Deployment — Wealthsimple App Review Pulse

Full deployment reference for all components. Ordered from already-live to pending.

---

## Component 1 — google-mcp-server (Cloud Run) ✅ LIVE

Handles Google Workspace delivery (Doc append + Gmail draft). Already deployed.

```
Service:  mcp-server-google
Region:   europe-west1
URL:      https://mcp-server-google-695514226672.europe-west1.run.app
GCP project: gen-lang-client-0491576843 (NextLeap)
Repo:     md-ammar-97/mcp-server-google
CD:       git push main → Cloud Build → Cloud Run (automatic)
```

**Secrets (Google Secret Manager):**

| Secret name | Contents |
|---|---|
| `google-mcp-credentials` | Service account key JSON |
| `google-mcp-token` | OAuth2 token JSON |
| `google-mcp-api-key` | API key (must match `MCP_API_KEY` in GitHub/Render) |

Full runbook: `../google-mcp-server/deployment_plan.md`

---

## Component 2 — Weekly pipeline (GitHub Actions) ✅ LIVE

Scrapes reviews, runs the full pipeline, and delivers via google-mcp-server. Already configured.

```
Repo:     md-ammar-97/wealthsimple-mcp
Workflow: .github/workflows/weekly_pulse.yml
Schedule: cron 0 8 * * 1  (Monday 08:00 UTC)
Manual:   Actions tab → Weekly Pulse → Run workflow
```

**Required GitHub secrets** (Settings → Secrets → Actions):

| Secret | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key (primary LLM: `llama-3.3-70b-versatile`) |
| `GEMINI_API_KEY` | Gemini API key (fallback LLM: `gemini-2.5-flash-lite`) |
| `MCP_API_KEY` | Must match `SERVER_API_KEY` on Cloud Run (google-mcp-server) |

No server to deploy — the pipeline runs ephemerally and exits when done.

**Debugging delivery failures:**
If delivery silently fails, the pipeline still exits 0. Starting with the next run,
`[DELIVERY ERROR]` lines appear directly in the GitHub Actions log. Also check the
`errors` array in the `run_summary.json` artifact (uploaded for 30 days per run).

Most likely cause if delivery fails: `MCP_API_KEY` secret value doesn't match
`SERVER_API_KEY` in Cloud Run. Fix: rotate to a shared fresh value in both places.

---

## Component 3 — Frontend + backend (Render) 🔲 TBD

### Why not Vercel

The Next.js frontend API routes spawn Python subprocesses:
```typescript
// frontend/src/app/api/run/route.ts
spawn('python', ['-m', 'pulse.cli', 'run', '--input', ...])
```
They also write CSV files to `../data/` and read from `../outputs/`. Vercel serverless
functions have a 10-second timeout, cannot run subprocesses, and have no persistent
filesystem between requests.

### Deployment to Render (full-stack)

**Step 1 — Create `render.yaml` at project root:**
```yaml
services:
  - type: web
    name: wealthsimple-pulse
    env: node
    buildCommand: |
      pip install torch --extra-index-url https://download.pytorch.org/whl/cpu
      pip install -r requirements.txt && pip install -e .
      cd frontend && npm ci && npm run build
    startCommand: cd frontend && npm start
    envVars:
      - key: GROQ_API_KEY
        sync: false
      - key: GEMINI_API_KEY
        sync: false
      - key: MCP_API_KEY
        sync: false
      - key: NODE_ENV
        value: production
```

**Step 2 — Connect to Render:**
1. Go to [render.com](https://render.com) → New → Web Service
2. Connect GitHub repo `md-ammar-97/wealthsimple-mcp`
3. Render detects `render.yaml` automatically

**Step 3 — Set environment variables in Render dashboard:**
- `GROQ_API_KEY` — your Groq key
- `GEMINI_API_KEY` — your Gemini key
- `MCP_API_KEY` — same value as GitHub secret (must match Cloud Run `SERVER_API_KEY`)

**Step 4 — Deploy:** Render auto-deploys on every push to `main`.

---

## Secrets reference (all components)

| Secret | GitHub Actions | Render env | Google Secret Manager |
|---|---|---|---|
| `GROQ_API_KEY` | ✓ | ✓ | |
| `GEMINI_API_KEY` | ✓ | ✓ | |
| `MCP_API_KEY` | ✓ | ✓ | |
| `SERVER_API_KEY` | | | `google-mcp-api-key` |
| OAuth credentials | | | `google-mcp-credentials` |
| OAuth token | | | `google-mcp-token` |

`MCP_API_KEY` and `SERVER_API_KEY` must always hold the same value.
If delivery breaks after a key rotation, update both secrets simultaneously.

---

## Future: Vercel + Render split (Phase 6)

This requires refactoring the frontend API routes to call a Render FastAPI backend over
HTTP instead of spawning subprocesses. Once done:
- **Vercel**: Next.js frontend (static + API proxy)
- **Render**: FastAPI backend wrapping `pulse.cli`

Not needed for the weekly-pipeline use case — the GitHub Actions run handles the pipeline
automatically; the frontend is only needed for manual triggering and result viewing.
