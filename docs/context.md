# Context - Wealthsimple App Review Insights Analyser

## Project Purpose

Review Pulse automates product-review analysis for Wealthsimple Canada and provides a self-serve browser workflow for other apps. It converts public or operator-supplied reviews into a concise, PII-safe pulse note with ranked themes, verified quotes, and practical action ideas.

The production system has two entry paths:

1. A scheduled GitHub Actions run fetches Google Play reviews and performs configured Google Docs and Gmail delivery.
2. The `/upload` page accepts a CSV and uploader email, runs the pipeline without configured delivery, then sends the finished report once to the uploader.

---

## Current System Role

For every run, the pipeline:

1. Validates and normalizes review rows.
2. Filters reviews to the configured date window.
3. Redacts PII before any LLM call.
4. Classifies reviews into the eight canonical product themes.
5. Ranks themes and selects up to three for the note.
6. Selects real quotes and verifies them against redacted source text.
7. Generates practical action ideas when the LLM returns valid suggestions.
8. Produces a pulse note of at most 250 words and a plain-text email artifact.
9. Records run status, metrics, diagnostics, output paths, and delivery results.

Theme classification is required. If no ranked themes are produced, the run fails. Action generation is optional at runtime: a valid report can still be produced with the Action Ideas section omitted.

---

## Inputs

### Scheduled source

| Source | Method | Status |
|---|---|---|
| Google Play | `google-play-scraper`, package `com.wealthsimple` | Active production source |
| Apple App Store | iTunes customer-review RSS | Removed because the feed returned no usable results |

`pulse fetch` writes:

- `data/input/reviews_raw.csv`: fetched rows before normalization
- `data/output/reviews_clean.csv`: normalized English reviews used as pipeline input

The production date window is `review_window_weeks: 260`, chosen to include the available Google Play dataset. The setting is configurable.

### Browser CSV source

The `/upload` page saves the submitted file to `data/input/reviews.csv`.

Required columns:

| Column | Rule |
|---|---|
| `platform` | App Store/iOS/Apple or Google Play/Android aliases |
| `rating` | Numeric value that resolves to an integer from 1 through 5 |
| `text` | Non-empty review text |
| `date` | Accepted date or timestamp |

`title` is optional. Additional columns are ignored unless the pipeline explicitly uses them.

Accepted date forms include:

- `YYYY-MM-DD`
- ISO timestamps, including `Z` or an offset
- `YYYY/MM/DD`
- `DD/MM/YYYY`
- `MM/DD/YYYY`

Hyphenated `DD-MM-YYYY` is not currently accepted.

Rows rejected during validation are counted by reason, including `invalid_platform` and `unparseable_date`. If no valid rows remain, the run stops before classification and returns the rejection breakdown.

---

## Processing Flow

```text
Google Play fetch or browser CSV upload
  -> schema and row validation
  -> date-window filtering and deduplication
  -> PII redaction
  -> data/output/reviews_redacted.csv
  -> LLM theme classification
  -> theme ranking
  -> verified quote selection
  -> optional action generation
  -> outputs/weekly_note.md
  -> outputs/email_draft.txt
  -> outputs/run_summary.json
  -> configured or uploader-specific delivery
```

Production uses direct LLM classification with `use_clustering: false`. Embedding and KMeans clustering remain available for larger hosts but are disabled on Render because the free instance has 512 MB RAM.

The primary model is Groq `llama-3.3-70b-versatile`; Gemini `gemini-2.5-flash-lite` is the fallback.

---

## Delivery Behavior

### Scheduled GitHub Actions

Every Monday at 08:00 UTC, `.github/workflows/weekly_pulse.yml`:

1. Runs `pulse fetch`.
2. Runs the full pipeline without `--skip-delivery`.
3. Appends the pulse note to the configured Google Doc.
4. Calls `POST /send_email` for the configured recipient because `gmail_mcp.email_mode` is `send`.
5. Commits `data/runs/ledger.json` with `[skip ci]`.
6. Uploads output artifacts for 30 days.

### Browser upload

The Next.js API runs:

```text
python3 -m pulse.cli run
  --input <absolute data/input/reviews.csv>
  --output-dir <absolute outputs>
  --run-id <uuid>
  --skip-delivery
```

After Python exits, the route waits for `run_summary.json` to report `success`. It then calls `POST /send_email` once for the uploader. This avoids sending the same upload report both to the configured weekly recipient and to the uploader.

`outputs/email_draft.txt` is an audit artifact. It does not mean the message was only saved to Gmail Drafts. Actual delivery is determined by the endpoint used and the `email_mode` setting.

---

## Persistent State

The system uses JSON state:

- `outputs/run_summary.json`: latest run details for the frontend
- `data/runs/<run_id>.json`: per-run summary
- `data/runs/ledger.json`: delivery idempotency and analytics history

Email delivery keys include the mode, such as `wealthsimple-2026-W24-email-send`, so a prior draft does not suppress a later send.

Render storage is ephemeral. Scheduled GitHub Actions commits `ledger.json` to the repository so analytics history survives redeploys.

---

## Hard Constraints

| Rule | Current behavior |
|---|---|
| Public or operator-supplied data only | No login-gated scraping |
| No PII in LLM prompts or reports | Raw title/text are redacted first |
| No invented quotes | Selected quotes are verified against source text |
| Grounded themes | Theme labels come from the canonical enum |
| Maximum five themes | Up to three are shown in the note |
| Note length | At most 250 words |
| Delivery is observable | IDs and errors are recorded in the run summary |

---

## Current Status

- [x] Scheduled Google Play ingestion
- [x] Browser CSV upload for App Store and Google Play data
- [x] Clear validation diagnostics when rows are rejected
- [x] PII redaction before LLM use
- [x] Ranked themes and verified quotes
- [x] Optional action ideas
- [x] Pulse note under 250 words
- [x] Google Docs append
- [x] Gmail draft and send support
- [x] Upload report sent to the uploader
- [x] Persistent analytics ledger
- [x] Render deployment and Monday GitHub Actions schedule

---

## Known Limitations

- Google Play is the only automated store source; App Store data must be uploaded by CSV.
- Ambiguous slash dates are interpreted using the parser's supported order; ISO dates are preferred.
- `DD-MM-YYYY` is rejected unless date parsing is extended.
- LLM quality depends on the clarity and volume of review text.
- Render's free plan cannot safely load the embedding model, so clustering is disabled in production.
- Browser email failure is non-fatal: the generated report remains available even if delivery fails.
