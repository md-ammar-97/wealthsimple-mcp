# Wealthsimple App Review Pulse

Automated weekly pipeline that scrapes app store reviews, classifies themes with an LLM, generates a structured insight note, and delivers it to a Google Doc and Gmail draft — hands-free.

**Weekly output doc:** [Pulse Notes — Wealthsimple Canada](https://docs.google.com/document/d/1CGfHgYXRhyEy3Yss9Qxmu1onO_roWWyTyo4u8CyKt9M/edit)

---

## How it works

```
Google Play (only — Apple iTunes RSS deprecated)
        ↓  pulse fetch
  reviews_raw.csv → reviews_clean.csv
        ↓  pulse run
  Redact PII → Embed → Cluster → Rank themes
        ↓
  Select quotes → Generate actions → Write pulse note
        ↓
  ┌─────────────────────────────────┐
  │  google-mcp-server (Cloud Run)  │
  │  POST /append_to_doc            │ → Google Doc
  │  POST /create_email_draft       │ → Gmail draft
  └─────────────────────────────────┘
```

Every Monday at 8 AM UTC, GitHub Actions runs the full pipeline automatically.

---

## Delivery

| Channel | Destination |
|---|---|
| Google Doc | [Pulse Notes](https://docs.google.com/document/d/1CGfHgYXRhyEy3Yss9Qxmu1onO_roWWyTyo4u8CyKt9M/edit) — new section appended each week |
| Gmail draft | `mohdammar97@gmail.com` — ready to review and send |

Delivery is handled by [google-mcp-server](../google-mcp-server) running on Cloud Run at:
`https://mcp-server-google-695514226672.europe-west1.run.app`

---

## Local setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

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

To change the target Google Doc, update `docs_mcp.doc_id` in `config/delivery.yaml`.

---

## Deployment

| Component             | Platform       | Status  |
|-----------------------|----------------|---------|
| Delivery (MCP server) | Cloud Run      | Live    |
| Weekly pipeline       | GitHub Actions | Live    |
| Frontend + backend    | Render         | TBD     |

> **Note:** The Next.js frontend spawns Python subprocesses and reads local files — it cannot run on Vercel serverless. The full stack (Next.js + Python) deploys to Render as one service. See [DEPLOYMENT.md](DEPLOYMENT.md) for step-by-step instructions.

---

## Project structure

```
pulse/
  ingestion/     fetch + normalize reviews
  privacy/       PII redaction
  analysis/      embed, cluster, classify, rank, quote, action gen
  render/        pulse note + email draft templating
  delivery/      docs_mcp.py + gmail_mcp.py  ← calls google-mcp-server
  ledger/        run ID, idempotency guard, run summary
  utils/         logging
config/
  pipeline.yaml
  delivery.yaml
prompts/         LLM prompt templates
data/            gitignored — scraped and processed CSVs
outputs/         gitignored — generated notes and email drafts
```
