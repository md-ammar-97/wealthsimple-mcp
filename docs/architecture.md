# Architecture - Wealthsimple App Review Insights Analyser

## 1. Overview

Review Pulse is a Python analysis pipeline with a Next.js frontend and a separate Google Workspace delivery service.

It supports two production workflows:

1. **Scheduled Wealthsimple run:** GitHub Actions fetches Google Play reviews, runs the pipeline, appends the note to Google Docs, sends Gmail, and commits the analytics ledger.
2. **Self-serve CSV run:** Render accepts a CSV and email address, runs the pipeline with configured delivery disabled, displays the report, and sends it once to the uploader.

```text
Google Play ---------------------> pulse fetch
                                        |
Browser CSV -> data/input/reviews.csv   |
                 |                      |
                 +-------> pulse run <--+
                              |
          validate -> redact -> classify -> rank
                              |
                quotes -> actions -> note -> email artifact
                              |
                 outputs/run_summary.json
                    /                     \
       scheduled configured delivery      browser uploader delivery
          /append_to_doc + /send_email          /send_email
                    \                     /
                 google-mcp-server on Cloud Run
```

---

## 2. Repositories and Runtime Components

| Component | Repository/path | Runtime |
|---|---|---|
| Python pipeline | `md-ammar-97/wealthsimple-mcp`, `pulse/` | GitHub Actions and Render |
| Next.js frontend/API | `md-ammar-97/wealthsimple-mcp`, `frontend/` | Render |
| Google delivery API | `md-ammar-97/mcp-server-google` | Google Cloud Run |
| Scheduled workflow | `.github/workflows/weekly_pulse.yml` | GitHub Actions |

### Deployment topology

| Service | URL or schedule | Deployment |
|---|---|---|
| Review Pulse app | `https://wealthsimple-mcp.onrender.com` | Push to `main` triggers Render |
| Google MCP server | `https://mcp-server-google-695514226672.europe-west1.run.app` | Push to `main` triggers Cloud Build and Cloud Run |
| Weekly pipeline | Monday 08:00 UTC | GitHub Actions |

---

## 3. Data Acquisition

### 3.1 Automated Google Play source

`pulse fetch` uses `google-play-scraper` for package `com.wealthsimple`.

```text
data/input/reviews_raw.csv
  -> normalization
data/output/reviews_clean.csv
```

Normalization removes very short reviews, emoji-bearing reviews, and non-English reviews. Source fields that may contain usernames or platform identifiers are not written to the canonical files.

Apple iTunes RSS is not an active source because it returned no usable review data. App Store reviews remain supported through CSV upload.

### 3.2 Browser CSV source

`POST /api/upload` writes the uploaded file to:

```text
data/input/reviews.csv
```

It also stores the uploader email and app name in process memory for the subsequent run and delivery request.

---

## 4. CSV Contract and Ingestion

Required headers:

- `platform`
- `rating`
- `text`
- `date`

Optional header:

- `title`

Optional metadata includes `app_version`, `country`, and `helpful_votes`.

### Platform normalization

Accepted aliases normalize to either `App Store` or `Google Play`. Supported examples include:

- App Store, appstore, Apple, Apple App Store, iOS, iPhone, iPad
- Google Play, Google Play Store, Play Store, googleplay, Android

Case is ignored. Hyphens and underscores are normalized to spaces.

### Date parsing

Accepted forms:

- `YYYY-MM-DD`
- ISO timestamps, including `Z` and timezone offsets
- `YYYY/MM/DD`
- `DD/MM/YYYY`
- `MM/DD/YYYY`

`DD-MM-YYYY` is not currently accepted.

### Ingestion behavior

`pulse/ingestion/ingest.py`:

1. Reads UTF-8, then falls back to Latin-1.
2. Validates required columns.
3. Validates platform, rating, text, and date per row.
4. Applies `review_window_weeks`.
5. Deduplicates on platform, date, and text.
6. Assigns sequential `review_id` values.
7. Returns both records and validation metadata.

Validation metadata includes:

- `rows_dropped_validation`
- `validation_drop_reasons`
- `rows_outside_window`
- `reviews_ingested`
- `reviews_after_dedup`
- `low_data_warning`

If no valid reviews remain, the run stops before LLM classification and reports rejection counts. This prevents the downstream `ranked_themes is empty` error from hiding an ingestion problem.

---

## 5. Privacy Boundary

`pulse/privacy/redact.py` redacts email addresses, phone numbers, account-like identifiers, names in supported trigger phrases, and long numeric identifiers.

Only redacted title and text fields are sent to LLM providers. Raw `title` and `text` are not written to the pipeline audit CSV.

The redacted output is:

```text
data/output/reviews_redacted.csv
```

This is distinct from `data/output/reviews_clean.csv`, which is the normalized output of `pulse fetch`.

---

## 6. Analysis Pipeline

### 6.1 Classification

Production configuration:

```yaml
provider: groq
model: llama-3.3-70b-versatile
fallback_provider: gemini
fallback_model: gemini-2.5-flash-lite
use_clustering: false
```

With `use_clustering: false`, `pulse/analysis/classify.py` classifies reviews in LLM batches. It validates indices, canonical theme labels, and confidence values, then retries missing results once.

Optional clustering remains implemented in `embed.py` and `cluster.py`. It is disabled in production because the BGE embedding model can exceed Render's 512 MB memory limit.

### 6.2 Canonical themes

Every classified review maps to one of eight labels:

1. Account access & login
2. Onboarding & verification
3. Transfers, deposits & withdrawals
4. Trading, investing & crypto
5. App performance, bugs & reliability
6. Customer support & issue resolution
7. Fees, pricing & product communication
8. Tax, statements & documents

Theme ranking sorts by review volume descending, average rating ascending, then label. The configured maximum is five themes; up to three are selected for the note.

An empty ranked-theme list is fatal because no grounded report can be generated.

### 6.3 Quotes

Quote selection returns redacted source text and verifies it against the submitted review records. The pipeline never accepts an invented quote.

### 6.4 Actions

Action generation requests up to three ideas linked to selected themes. It normalizes common response-field variants and trims long ideas.

If the LLM returns no valid actions after retries, the run remains valid and the note omits the Action Ideas section.

---

## 7. Rendering and Artifacts

Artifacts are assembled in memory and written only after the analysis stages succeed:

| Artifact | Path | Purpose |
|---|---|---|
| Redacted review CSV | `data/output/reviews_redacted.csv` | PII-safe audit input |
| Pulse note | `outputs/weekly_note.md` | Stakeholder report, maximum 250 words |
| Email audit copy | `outputs/email_draft.txt` | Plain-text message body |
| Latest run summary | `outputs/run_summary.json` | Frontend status and diagnostics |
| Per-run summary | `data/runs/<run_id>.json` | `pulse status` lookup |
| Ledger | `data/runs/ledger.json` | Analytics and delivery idempotency |

The name `email_draft.txt` describes the local artifact, not the Gmail delivery mode.

---

## 8. Run State and Idempotency

A run summary begins with identifiers and configuration:

- `run_id`
- `input_hash`
- `period_key`
- `delivery_key`
- `product`
- `input_csv`
- `review_window_weeks`
- `model`
- `started_at`

It is then updated with ingestion metrics, themes, quotes, actions, output paths, status, errors, and delivery IDs.

Delivery keys are mode-specific:

```text
wealthsimple-<ISO year>-W<week>-email-draft
wealthsimple-<ISO year>-W<week>-email-send
```

This prevents a previous draft from suppressing a later send. `--force` bypasses delivery guards.

The JSON ledger is committed by the scheduled workflow because Render's local filesystem is ephemeral.

---

## 9. Delivery Architecture

### 9.1 Google MCP endpoints

The Cloud Run service exposes:

| Endpoint | Result |
|---|---|
| `POST /append_to_doc` | Appends formatted Markdown content to a Google Doc |
| `POST /create_email_draft` | Creates a styled Gmail draft |
| `POST /send_email` | Sends a styled Gmail message |

Mutating requests use `X-Api-Key` when `SERVER_API_KEY` is configured. The pipeline reads its matching client value from `MCP_API_KEY`.

`APPROVAL_MODE=auto` approves the requested action in headless production. It does not turn draft creation into sending; the endpoint controls that behavior.

### 9.2 Scheduled delivery

`config/delivery.yaml` currently enables Docs and Gmail with:

```yaml
delivery_mode: mcp

docs_mcp:
  enabled: true
  doc_id: "..."

gmail_mcp:
  enabled: true
  email_mode: send
```

The scheduled workflow runs `pulse run` normally. The orchestrator appends the note and calls the Gmail endpoint selected by `email_mode`.

Delivery failures are non-fatal. Local artifacts remain available, errors are added to `run_summary.json`, and CI prints `[DELIVERY ERROR]` lines.

### 9.3 Browser upload delivery

The Next.js route spawns:

```text
python3 -m pulse.cli run
  --input <absolute data/input/reviews.csv>
  --output-dir <absolute outputs>
  --run-id <uuid>
  --skip-delivery
```

The route writes a placeholder summary before spawning, drains structured stdout into an SSE queue, and waits up to 10 seconds after process exit for the summary to leave `running`.

Only `status: success` is treated as completion. It then calls `/send_email` for the uploader. Email failure is logged but does not invalidate an already generated report.

---

## 10. Frontend Architecture

| Route | Role |
|---|---|
| `/` | Product overview |
| `/upload` | CSV submission, live progress, inline report |
| `/analytics` | Ledger-backed historical metrics |
| `/run` | Legacy upload flow |
| `/results` | Legacy result view |

API routes use module-global process state for the active upload metadata, pipeline queue, and run status. This is suitable for the current single Render service but is not a multi-instance queue architecture.

Structured Python log lines are split by newline and queued. `/api/pipeline/status` drains the queue every 500 ms over Server-Sent Events.

---

## 11. Configuration and Secrets

### Pipeline configuration

Important production values in `config/pipeline.yaml`:

```yaml
review_window_weeks: 260
min_reviews: 5
max_themes: 5
note_themes: 3
max_note_words: 250
use_clustering: false
```

### Required secrets

| Variable | Used by |
|---|---|
| `GROQ_API_KEY` | Primary LLM |
| `GEMINI_API_KEY` | Fallback LLM |
| `MCP_API_KEY` | Pipeline and frontend calls to Google MCP |
| `SERVER_API_KEY` | Google MCP server validation |
| Google OAuth credential/token JSON | Cloud Run Gmail and Docs authorization |

Secrets are stored in GitHub Actions secrets, Render environment variables, or Google Secret Manager. They are not committed.

---

## 12. Failure Semantics

| Condition | Result |
|---|---|
| Missing required CSV header | Ingestion exits with named columns |
| Invalid individual rows | Dropped and counted by reason |
| All rows invalid or outside window | Run fails before classification with diagnostics |
| No classified/ranked themes | Run fails |
| No valid actions | Run succeeds without Action Ideas |
| Delivery endpoint fails | Run remains successful; error recorded |
| Python exits 0 but summary stays `running` | Browser reports an inconsistent final state |
| Process exits non-zero | Browser reports pipeline failure |
| Render OOM/SIGKILL | Placeholder summary may remain `running`; route reports this rather than false success |

---

## 13. Verification

Current verification commands:

```bash
python -m pytest tests/unit -q

cd frontend
npm run build
```

The Python unit suite currently contains 135 tests. The separate Google MCP repository contains 6 tests.

---

## 14. Known Constraints

- Automated ingestion is Google Play only.
- Slash-based dates can be ambiguous; ISO format is recommended.
- `DD-MM-YYYY` is unsupported.
- Render's free instance requires direct LLM classification.
- Browser queue and metadata state are process-local.
- The legacy `/api/results/csv` route serves `data/output/reviews_clean.csv`; it is not the browser upload's redacted audit download.
- Render disk is ephemeral; durable analytics history depends on the committed ledger.
- Gmail and Docs delivery depend on a valid OAuth refresh token and matching API keys.
