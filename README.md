# Review Pulse — App Store Intelligence

Automated weekly pipeline that scrapes Google Play reviews for Wealthsimple Canada, classifies themes with an LLM, generates a structured insight note, and delivers it to a Google Doc and Gmail draft — hands-free. Also exposes a self-serve CSV upload flow for analysing any app.

**Live app:** [wealthsimple-mcp.onrender.com](https://wealthsimple-mcp.onrender.com)
**Weekly output doc:** [Pulse Notes — Wealthsimple Canada](https://docs.google.com/document/d/1CGfHgYXRhyEy3Yss9Qxmu1onO_roWWyTyo4u8CyKt9M/edit)

---

## How it works

```
Google Play  (google-play-scraper, Monday 08:00 UTC via GitHub Actions)
        ↓  pulse fetch
  reviews_raw.csv → reviews_clean.csv
        ↓  pulse run
  Ingest → Redact PII → Classify → Rank themes
        ↓
  Select quotes → Generate actions → Write pulse note
        ↓
  ┌─────────────────────────────────┐
  │  google-mcp-server (Cloud Run)  │
  │  POST /append_to_doc            │ → Google Doc
  │  POST /create_email_draft       │ → Gmail draft
  └─────────────────────────────────┘
        ↓
  data/runs/ledger.json  ← committed back to repo by Actions
        ↓
  /analytics page  ← reads ledger for charts + history
```

Every Monday at 8 AM UTC, GitHub Actions runs the full pipeline automatically and commits the updated `ledger.json` so the analytics page always has persistent history across Render redeploys.

---

## Frontend pages

| Route | Description |
|---|---|
| `/` | Marketing homepage — pipeline overview, two entry points |
| `/upload` | Upload any app's CSV → 8-step progress → inline results → email sent |
| `/analytics` | Wealthsimple-specific historical charts and run history (from `ledger.json`) |
| `/run` | Legacy CSV upload + pipeline tracker (still functional) |
| `/results` | Legacy results view |

---

## Delivery

| Channel | Destination |
|---|---|
| Google Doc | [Pulse Notes](https://docs.google.com/document/d/1CGfHgYXRhyEy3Yss9Qxmu1onO_roWWyTyo4u8CyKt9M/edit) — new section appended each week |
| Gmail draft | `mohdammar97@gmail.com` — ready to review and send |
| CSV upload email | User's submitted email address — report sent after pipeline completes |

Delivery is handled by [google-mcp-server](https://mcp-server-google-695514226672.europe-west1.run.app) running on Cloud Run.

---

## Local setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# CPU-only PyTorch (avoids large CUDA download)
pip install torch --extra-index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
pip install -e .

cp .env.example .env          # fill in your API keys
```

### Environment variables

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq LLM API key (primary model: `llama-3.3-70b-versatile`) |
| `GEMINI_API_KEY` | Gemini API key (fallback model: `gemini-2.5-flash-lite`) |
| `MCP_API_KEY` | API key for the google-mcp-server — must match `SERVER_API_KEY` on Cloud Run |
| `MCP_SERVER_URL` | Optional override for the MCP server URL (defaults to the Cloud Run URL) |

---

## CLI

```bash
# Fetch latest reviews (last 1 week)
pulse fetch --weeks 1

# Run full pipeline (ingest → classify → note → deliver)
pulse run --input data/output/reviews_clean.csv

# Dry run — ingest + redact only, no LLM calls, no delivery
pulse dry-run --input data/output/reviews_clean.csv

# Check status of a past run
pulse status --run-id <run_id>
```

---

## GitHub Actions

The workflow at [`.github/workflows/weekly_pulse.yml`](.github/workflows/weekly_pulse.yml) runs every Monday at 8 AM UTC.

**What it does:**
1. `pulse fetch` — scrapes fresh Google Play reviews
2. `pulse run` — full 8-step pipeline with MCP delivery
3. Commits `data/runs/ledger.json` back to the repo so the `/analytics` page has persistent history

**Required GitHub secrets** (Settings → Secrets → Actions):

| Secret | Value |
|---|---|
| `GROQ_API_KEY` | Your Groq API key |
| `GEMINI_API_KEY` | Your Gemini API key |
| `MCP_API_KEY` | API key for google-mcp-server (same as `SERVER_API_KEY` in Secret Manager) |

You can also trigger it manually from the **Actions** tab → **Weekly Pulse** → **Run workflow**.

Run artifacts (the generated note and email draft) are uploaded and kept for 30 days.

---

## Config

| File | Purpose |
|---|---|
| `config/pipeline.yaml` | Product, LLM model, review window, clustering settings |
| `config/delivery.yaml` | MCP server URL, Google Doc ID, email recipient, enable/disable delivery |

**Important:** `use_clustering` is set to `false` in `config/pipeline.yaml` for the Render deployment. The BAAI/bge-small-en-v1.5 embedding model requires ~400–600 MB RAM which exceeds the Render free plan's 512 MB limit. Clustering is available locally where RAM is not constrained.

---

## Deployment

| Component | Platform | Status |
|---|---|---|
| Delivery (MCP server) | Cloud Run (`europe-west1`) | ✅ Live |
| Weekly pipeline | GitHub Actions | ✅ Live |
| Frontend + backend | Render (Node.js + Python) | ✅ Live |

**Live URL:** `https://wealthsimple-mcp.onrender.com`

> The Next.js frontend spawns Python subprocesses and reads local files — it cannot run on Vercel serverless. The full stack (Next.js + Python) deploys to Render as one service. See [DEPLOYMENT.md](DEPLOYMENT.md) for details.

---

## Project structure

```
pulse/
  ingestion/     fetch + normalize reviews (Google Play only)
  privacy/       PII redaction
  analysis/      classify, rank, quote select, action gen
                 (embed + cluster disabled on Render — use_clustering: false)
  render/        pulse note + email draft templating
  delivery/      docs_mcp.py + gmail_mcp.py  ← calls google-mcp-server
  ledger/        run ID, idempotency guard, run summary, ledger.json
  utils/         logging, LLM wrapper, word count

config/
  pipeline.yaml  (use_clustering: false for Render; true for local)
  delivery.yaml  (MCP enabled; email_recipient configured)

frontend/
  src/app/
    page.tsx           Homepage
    upload/            CSV upload + results (all-in-one, email sent on completion)
    analytics/         Wealthsimple historical analytics (Recharts)
    api/
      upload/          Accept CSV + email + appName
      run/             Spawn pipeline; queue events; send MCP email after completion
      pipeline/status/ SSE stream draining event queue
      results/         Read run_summary.json + artifacts
      analytics/       Read data/runs/ledger.json for charts
  src/components/
    AtlasNav/          Sticky dark-blue navigation bar
    PipelineTracker/   8-step progress indicator (SSE-driven)
    ...
  src/styles/
    tokens.css         Atlassian Design System token palette
    global.css         Base styles, .btn-*, .atlas-*, .badge-* primitives

data/
  runs/
    ledger.json        Committed to repo by GitHub Actions after each weekly run
```
