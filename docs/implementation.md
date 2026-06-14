# Implementation Status - Wealthsimple App Review Insights Analyser

## Document Purpose

This document records the implemented system rather than the original delivery plan. For contracts and operational detail, also see:

- [Context](context.md)
- [Architecture](architecture.md)
- [Data model](data_model.md)
- [Edge cases](edge_cases.md)
- [Deployment](../DEPLOYMENT.md)
- [Issue history](issues.md)

---

## Current Status

| Area | Status | Notes |
|---|---|---|
| Google Play acquisition | Complete | Scheduled source for Wealthsimple |
| CSV ingestion | Complete | App Store and Google Play aliases supported |
| PII redaction | Complete | Runs before all LLM calls |
| Theme analysis | Complete | Direct LLM path active in production |
| Note and email rendering | Complete | Atomic artifact write after analysis |
| Google Docs delivery | Complete | Cloud Run MCP endpoint |
| Gmail draft/send delivery | Complete | Production mode is `send` |
| Browser upload | Complete | Live SSE progress and inline report |
| Analytics | Complete | Reads committed JSON ledger |
| GitHub Actions | Complete | Monday 08:00 UTC |
| Render deployment | Complete | Next.js and Python in one service |

---

## 1. Data Acquisition

### Implemented files

| File | Role |
|---|---|
| `pulse/ingestion/fetch_reviews.py` | Fetch public Google Play reviews |
| `pulse/ingestion/normalize.py` | Drop short, emoji-bearing, and non-English reviews |
| `data/input/reviews_raw.csv` | Raw fetched review fields after source-level PII column removal |
| `data/output/reviews_clean.csv` | Normalized input for `pulse run` |

`pulse fetch` supports:

```text
pulse fetch [--weeks N] [--raw-output PATH] [--clean-output PATH]
```

Google Play package `com.wealthsimple` is the only automated store source. The Apple iTunes RSS implementation was removed after the feed returned no usable results.

Production uses `review_window_weeks: 260` because the available fetched dataset is older than a narrow weekly window. The fetch command gathers reviews; ingestion applies the configured date cutoff.

---

## 2. Ingestion and Validation

### Implemented files

| File | Role |
|---|---|
| `pulse/ingestion/validators.py` | Required headers, platform aliases, rating/text/date parsing |
| `pulse/ingestion/ingest.py` | Read, validate, date-filter, deduplicate, and report diagnostics |

Required headers are:

```text
platform, rating, text, date
```

`title` is optional.

Accepted platforms normalize common App Store/iOS/Apple and Google Play/Android aliases. Accepted dates are ISO dates/timestamps, `YYYY/MM/DD`, `DD/MM/YYYY`, and `MM/DD/YYYY`.

The ingestion result includes:

- `reviews_ingested`
- `reviews_after_dedup`
- `rows_dropped_validation`
- `validation_drop_reasons`
- `rows_outside_window`
- `low_data_warning`

When no valid reviews remain, ingestion produces a specific failure such as:

```text
No valid reviews remained after ingestion
(validation rejections: invalid_platform=25, unparseable_date=24).
```

This validation boundary prevents invalid input from surfacing later as an unexplained empty-theme error.

---

## 3. Privacy

### Implemented files

| File | Role |
|---|---|
| `pulse/privacy/patterns.py` | Compiled PII patterns |
| `pulse/privacy/redact.py` | Redact title/text and write the PII-safe CSV |

The redacted audit file is:

```text
data/output/reviews_redacted.csv
```

It is intentionally separate from `reviews_clean.csv`, the normalized output from `pulse fetch`.

Only redacted text is included in LLM prompts or user-facing artifacts.

---

## 4. Analysis

### Implemented files

| File | Role |
|---|---|
| `pulse/analysis/classify.py` | Batched direct LLM classification |
| `pulse/analysis/embed.py` | Optional review embeddings |
| `pulse/analysis/cluster.py` | Optional KMeans clustering and cluster labeling |
| `pulse/analysis/quote_select.py` | Select and verify source quotes |
| `pulse/analysis/action_gen.py` | Generate and normalize action ideas |

Production configuration:

```yaml
provider: groq
model: llama-3.3-70b-versatile
fallback_provider: gemini
fallback_model: gemini-2.5-flash-lite
use_clustering: false
```

The direct classification path validates canonical theme names, fixes confidence values, detects missing review indices, and retries missing results once.

`rank_themes()` must return at least one grounded theme. If it returns an empty list, note generation stops with:

```text
ranked_themes is empty - theme classification must have failed upstream.
```

Action generation is deliberately softer. If the LLM returns no valid actions after retries, the pipeline still writes the report and omits the Action Ideas section.

---

## 5. Rendering and Run State

### Implemented files

| File | Role |
|---|---|
| `pulse/render/pulse_note.py` | Build and enforce the 250-word report |
| `pulse/render/email_draft.py` | Build the plain-text email audit copy |
| `pulse/delivery/local.py` | Write artifacts |
| `pulse/ledger/run_ledger.py` | IDs, summaries, ledger, delivery guard |
| `pulse/orchestrator.py` | End-to-end step coordination |

Successful full runs write:

```text
data/output/reviews_redacted.csv
outputs/weekly_note.md
outputs/email_draft.txt
outputs/run_summary.json
data/runs/<run_id>.json
data/runs/ledger.json
```

The note and email artifacts are assembled in memory and written only after analysis succeeds. A failed upstream stage does not replace prior successful note/email files with partial output.

`run_summary.json` contains validation diagnostics, themes, quotes, actions, output paths, status, errors, and delivery IDs.

---

## 6. CLI

Implemented commands:

```bash
pulse fetch --weeks 1

pulse run \
  --input data/output/reviews_clean.csv \
  --output-dir outputs

pulse run \
  --input data/input/reviews.csv \
  --run-id <uuid> \
  --output-dir outputs \
  --skip-delivery

pulse dry-run --input data/output/reviews_clean.csv

pulse status --run-id <run_id>
```

Important `pulse run` flags:

| Flag | Behavior |
|---|---|
| `--input` | Select input CSV |
| `--run-id` | Use a caller-generated identifier |
| `--output-dir` | Select note/email/summary directory |
| `--skip-delivery` | Generate local artifacts without configured Docs/Gmail delivery |
| `--force` | Bypass delivery idempotency guards |

`pulse/cli.py` includes a module entry point, so both the installed `pulse` command and `python -m pulse.cli` work.

---

## 7. Frontend

### Implemented routes

| Route | Purpose |
|---|---|
| `/` | Product overview |
| `/upload` | Submit CSV/email/app name, view progress and results |
| `/analytics` | Ledger-backed charts and run history |
| `/run` | Legacy upload flow |
| `/results` | Legacy results view |

### Browser run sequence

1. `/api/upload` saves `data/input/reviews.csv` and stores upload metadata.
2. `/api/run` writes a placeholder `run_summary.json` with `status: running`.
3. It spawns `python3 -m pulse.cli run` with absolute paths, a UUID, and `--skip-delivery`.
4. Python JSON log lines are split and queued.
5. `/api/pipeline/status` drains the queue over SSE every 500 ms.
6. On process exit, `/api/run` waits for the run summary to become `success` or `error`.
7. A successful report is sent once to the uploader through `POST /send_email`.

The 10-second post-exit summary check fixed the earlier false-completion state:

```text
Pipeline exited 0 but summary status is 'running' after 10s
```

That message now indicates a real inconsistency or abrupt process termination rather than allowing stale output to be presented as a new success.

---

## 8. Google Workspace Delivery

### Pipeline client

| File | Behavior |
|---|---|
| `pulse/delivery/docs_mcp.py` | Calls `POST /append_to_doc` |
| `pulse/delivery/gmail_mcp.py` | Calls draft or send endpoint based on `email_mode` |

Production delivery configuration:

```yaml
docs_mcp:
  enabled: true

gmail_mcp:
  enabled: true
  email_mode: send
```

`deliver_gmail_email()` records:

- `email_mode`
- `message_id` and optional `thread_id` for sends
- `draft_id` for drafts

Delivery keys include the mode, for example:

```text
wealthsimple-2026-W24-email-send
```

The local `email_draft.txt` file is always an audit copy. The actual Gmail behavior is controlled by `email_mode` and the endpoint.

### Separate Google MCP service

The Cloud Run service supports:

```text
POST /append_to_doc
POST /create_email_draft
POST /send_email
```

`APPROVAL_MODE=auto` approves the requested endpoint action. It does not automatically send a message created through the draft endpoint.

---

## 9. Scheduled Automation

`.github/workflows/weekly_pulse.yml`:

1. Runs every Monday at 08:00 UTC or manually.
2. Installs Python 3.11 and dependencies.
3. Runs `pulse fetch`.
4. Runs `pulse run` with configured MCP delivery.
5. Commits `data/runs/ledger.json` using `[skip ci]`.
6. Uploads `outputs/` artifacts for 30 days.

The workflow does not use `--skip-delivery`, so it sends the configured stakeholder email and appends the shared Google Doc.

Missing action ideas do not fail the workflow. Delivery errors are non-fatal but appear as `[DELIVERY ERROR]` in logs and in the summary `errors` array.

---

## 10. Testing and Verification

### Python

```bash
python -m pytest tests/unit -q
```

Current result: **135 unit tests passed**.

Coverage includes ingestion diagnostics, date/platform aliases, PII redaction, LLM response handling, empty action behavior, note generation, ledger keys, and Gmail draft/send delivery.

### Frontend

```bash
cd frontend
npm run build
```

Current result: production build passes.

### Google MCP repository

```bash
python -m pytest tests -q
```

Current result: **6 tests passed**.

---

## 11. Remaining Constraints

- Automated store acquisition is Google Play only.
- `DD-MM-YYYY` is not accepted by the current date parser.
- Render free-tier memory requires `use_clustering: false`.
- Browser queue and upload metadata are process-local and assume one service instance.
- Render disk is ephemeral; committed `ledger.json` provides durable analytics history.
- Browser email delivery failure is non-fatal after report generation.
