# Deployment — Review Pulse

Full deployment reference for all components.

---

## Component 1 — google-mcp-server (Cloud Run) ✅ LIVE

Handles Google Workspace delivery (Doc append + Gmail draft/send). Already deployed.

```
Service:     mcp-server-google
Region:      europe-west1
URL:         https://mcp-server-google-695514226672.europe-west1.run.app
GCP project: gen-lang-client-0491576843 (NextLeap)
Repo:        md-ammar-97/mcp-server-google
CD:          git push main → Cloud Build → Cloud Run (automatic)
```

**Required Cloud Run environment variables:**

| Variable | Value |
|---|---|
| `SERVER_API_KEY` | Must match `MCP_API_KEY` in GitHub and Render |
| `APPROVAL_MODE` | `auto` — skips terminal operator approval gate for automated runs |

**Secrets (Google Secret Manager):**

| Secret name | Contents |
|---|---|
| `google-mcp-credentials` | OAuth 2.0 client credentials JSON |
| `google-mcp-token` | OAuth2 token JSON |
| `google-mcp-api-key` | API key (must match `MCP_API_KEY` in GitHub/Render) |

**Endpoints used by the pipeline:**

| Endpoint | Body | Purpose |
|---|---|---|
| `POST /append_to_doc` | `{ doc_id, content }` | Append weekly note section to Google Doc |
| `POST /create_email_draft` | `{ to, subject, body }` | Create a Gmail draft |
| `POST /send_email` | `{ to, subject, body }` | Send a Gmail message |

Full runbook: `../google-mcp-server/deployment_plan.md`

---

## Component 2 — Weekly pipeline (GitHub Actions) ✅ LIVE

Scrapes reviews, runs the full pipeline, delivers via google-mcp-server, and commits the updated ledger back to the repo.

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

**What each run does:**
1. `pulse fetch` — scrapes fresh Google Play reviews
2. `pulse run` — 8-step pipeline with `APPROVAL_MODE: auto` (skips terminal gate)
3. `git commit data/runs/ledger.json && git push` with `[skip ci]` tag — persists analytics history

**Debugging delivery failures:**
If delivery silently fails, the pipeline still exits 0. `[DELIVERY ERROR]` lines appear in the GitHub Actions log. Check the `errors` array in the `run_summary.json` artifact (uploaded for 30 days per run).

Most likely cause: `MCP_API_KEY` secret value doesn't match `SERVER_API_KEY` in Cloud Run. Fix: rotate to a matching fresh value in both places simultaneously.

---

## Component 3 — Frontend + backend (Render) ✅ LIVE

```
Service:  wealthsimple-mcp
URL:      https://wealthsimple-mcp.onrender.com
Plan:     Free (512 MB RAM)
CD:       git push main → auto-deploy
```

### Why not Vercel

The Next.js API routes spawn Python subprocesses:
```typescript
// frontend/src/app/api/run/route.ts
spawn('python3', ['-m', 'pulse.cli', 'run', '--input', ...])
```
They also write CSV files to `../data/` and read from `../outputs/`. Vercel serverless functions have a 10-second timeout, cannot run subprocesses, and have no persistent filesystem between requests.

### Render environment variables

Set these in the Render dashboard (Settings → Environment):

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key |
| `GEMINI_API_KEY` | Gemini API key |
| `MCP_API_KEY` | Must match `SERVER_API_KEY` on Cloud Run |
| `MCP_SERVER_URL` | Optional — defaults to the Cloud Run URL if unset |
| `NODE_ENV` | `production` |

### RAM constraint

The Render free plan has 512 MB RAM. The BAAI/bge-small-en-v1.5 embedding model used by the clustering step requires ~400–600 MB, which causes an OOM kill (SIGKILL) with no Python exception. This is why `use_clustering: false` is set in `config/pipeline.yaml` — the pipeline uses direct LLM classification instead of embeddings.

If you upgrade to a paid Render instance (1 GB+), you can re-enable clustering by setting `use_clustering: true` in `config/pipeline.yaml`.

### Frontend pages

| Route | Description |
|---|---|
| `/` | Homepage with pipeline overview and two entry cards |
| `/upload` | Upload any app's CSV → email + app name → 8-step SSE progress → inline results + email sent |
| `/analytics` | Wealthsimple historical analytics: Recharts charts + run history table from `ledger.json` |

### Browser upload execution

The `/api/run` route launches:

```text
python3 -m pulse.cli run
  --input <absolute data/input/reviews.csv>
  --output-dir <absolute outputs>
  --run-id <uuid>
  --skip-delivery
```

`--skip-delivery` prevents the pipeline from also sending to the configured weekly recipient or appending the shared Google Doc. After `run_summary.json` reaches `success`, the route calls `POST /send_email` once using the uploader's submitted address.

The route waits up to 10 seconds after process exit for `run_summary.json` to leave `running`. An exit code of 0 is not treated as success unless the summary also reports `success`.

### CSV validation

Required headers are `platform`, `rating`, `text`, and `date`; `title` is optional. Accepted platform aliases cover App Store/iOS/Apple and Google Play/Android. Accepted dates include ISO dates/timestamps, `YYYY/MM/DD`, `DD/MM/YYYY`, and `MM/DD/YYYY`.

Validation failures are recorded in `validation_drop_reasons`. If no valid reviews remain, the API returns the pipeline diagnostic instead of continuing to theme classification.

### Re-deploy

Auto-deploys on every push to `main`. To manually re-deploy: Render dashboard → Manual Deploy.

---

## Secrets reference (all components)

| Secret | GitHub Actions | Render env | GCP Secret Manager |
|---|---|---|---|
| `GROQ_API_KEY` | ✓ | ✓ | |
| `GEMINI_API_KEY` | ✓ | ✓ | |
| `MCP_API_KEY` | ✓ | ✓ | |
| `SERVER_API_KEY` | | | `google-mcp-api-key` |
| `APPROVAL_MODE` | (in workflow yaml) | | (in Cloud Run env) |
| OAuth credentials | | | `google-mcp-credentials` |
| OAuth token | | | `google-mcp-token` |

**`MCP_API_KEY` and `SERVER_API_KEY` must always hold the same value.**
If delivery breaks after a key rotation, update both secrets simultaneously.

---

## Analytics data persistence

`data/runs/ledger.json` accumulates a summary of every successful pipeline run. It is:
- Committed to the repo by GitHub Actions after each weekly run (`[skip ci]`)
- Read by the `/api/analytics` API route to power the `/analytics` page
- Gitignored by default **except** via the `.gitignore` exception `!data/runs/ledger.json`

This means the analytics page has persistent historical data even across Render redeploys (which wipe ephemeral disk state).

---

## Troubleshooting

### Pipeline stuck at "running" in browser
The SSE stream polls `global.pipelineQueue` every 500ms. The run route now verifies the final summary state before signalling completion. If the browser still shows a stuck progress bar:
- Check Render logs for `[pipeline close]` or `[pipeline spawn error]`
- The queue-based event drain means multi-line Python stdout chunks are split and each line parsed independently — this is the fixed version
- Inspect `outputs/run_summary.json`; `status: error` should include the upstream validation or analysis failure

### Results not found
If the pipeline is OOM-killed (exit code 137 = SIGKILL), Python's exception handler cannot update the summary. A placeholder is written before spawning, and the run route now reports that the summary remained `running` instead of presenting a false success.

### MCP email not sent (CSV upload flow)
The `/api/run` route calls `POST /send_email` on the MCP server after `pulse run --skip-delivery` exits with code 0. Failure is non-fatal. Check:
1. `MCP_API_KEY` is set in Render env
2. `APPROVAL_MODE=auto` is set on the Cloud Run service
3. Render logs for `[pipeline close] code: 0`
4. Cloud Run is serving a revision that exposes `POST /send_email`

`APPROVAL_MODE=auto` approves the endpoint action. Calling `/create_email_draft` still creates only a draft; successful delivery requires `/send_email`.
