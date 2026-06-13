# Data Model — Wealthsimple App Review Insights Analyser

## Overview

The pipeline operates on three categories of data:

| Category | Description |
|---|---|
| **Ingested data** | Raw public review CSV dropped by the operator |
| **Intermediate data** | In-memory dataframes and structured objects produced between pipeline steps |
| **Output artifacts** | Files written to disk: cleaned CSV, weekly note, email draft |

No database. No persistent state. Every field definition below is the contract that code must honour across pipeline steps.

---

## 1. Input Review CSV

**Path:** `data/input/reviews.csv`
**Encoding:** UTF-8
**Delimiter:** comma (`,`)
**Header row:** required

### 1.1 Required Columns

| Column | Type | Nullable | Constraints | Notes |
|---|---|---|---|---|
| `platform` | `string` | No | Must be `"App Store"` or `"Google Play"` | Case-insensitive on ingest; normalised to title case |
| `rating` | `integer` | No | 1 – 5 inclusive | Fractional values rounded to nearest integer |
| `title` | `string` | Yes | Max 500 characters | Empty string treated as null |
| `text` | `string` | No | Min 5 characters after strip | Rows with empty `text` are dropped |
| `date` | `string` | No | ISO 8601 (`YYYY-MM-DD`) preferred; falls back to `DD/MM/YYYY` | Parsed to `datetime` on ingest |

### 1.2 Optional Columns

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `app_version` | `string` | Yes | e.g. `"24.11.0"` — passed through; not used in LLM steps |
| `country` | `string` | Yes | ISO 3166-1 alpha-2 country code — passed through |
| `helpful_votes` | `integer` | Yes | Used as a secondary ranking signal for quote selection |

### 1.3 Ignored Columns
Any column not listed above is silently ignored. This allows raw exports from third-party aggregators to be dropped in without preprocessing.

### 1.4 Sample Input Row

```csv
platform,rating,title,text,date,app_version,country,helpful_votes
App Store,2,Keeps logging me out,"Every time I open the app I have to log back in. Very annoying.",2026-03-15,24.10.1,CA,3
Google Play,5,Love it,"Super easy to use, portfolio view is clean.",2026-02-28,,CA,
```

---

## 2. Validation Rules (Ingest Step)

Applied by `pulse/ingestion/ingest.py` before any further processing.

| Rule | Action on failure |
|---|---|
| Missing required column | Hard exit — log missing column names |
| `platform` not in allowed values | Row dropped; logged |
| `rating` outside 1–5 | Row dropped; logged |
| `text` empty or < 5 chars after strip | Row dropped; logged |
| `date` unparseable | Row dropped; logged |
| `date` outside configured review window | Row excluded (not an error) |
| Duplicate row (same `platform` + `date` + `text`) | Second occurrence dropped |

**Minimum viable dataset:** at least 5 rows must survive validation. If fewer remain, pipeline logs a warning and continues with a low-data flag set in the run summary.

---

## 3. Intermediate Data Models

### 3.1 Validated Review Record

Produced by `pulse/ingestion/ingest.py`. One record per review that passed validation.

```python
{
    "review_id":    int,        # sequential integer assigned at ingest (0-based)
    "platform":     str,        # "App Store" | "Google Play"
    "rating":       int,        # 1–5
    "title":        str | None, # None if missing
    "text":         str,        # non-empty, stripped
    "date":         datetime,   # tz-naive UTC
    "app_version":  str | None,
    "country":      str | None,
    "helpful_votes": int | None
}
```

### 3.2 Redacted Review Record

Produced by `pulse/privacy/redact.py`. Extends the validated record; `title` and `text` are PII-scrubbed.

```python
{
    # all fields from 3.1, plus:
    "title_redacted": str | None,    # PII-stripped version of title
    "text_redacted":  str,           # PII-stripped version of text
    "pii_found":      bool           # True if any PII pattern was matched
}
```

**Fields sent to LLM:** only `title_redacted` and `text_redacted`. The raw `title` and `text` are never included in any prompt.

### 3.3 Themed Review Record

Produced by `pulse/analysis/cluster.py` (Mode B, default) or `pulse/analysis/classify.py` (Mode A). Extends the redacted record.

```python
{
    # all fields from 3.2, plus:
    "theme":               str,    # canonical theme label (= cluster_theme in Mode B)
    "confidence":          float,  # 0.0–1.0 (= cluster_confidence in Mode B)

    # Mode B only (use_clustering: true) — absent when use_clustering: false:
    "cluster_id":          int,    # KMeans cluster index (0-based)
    "cluster_theme":       str,    # canonical theme label assigned to this cluster by LLM
    "cluster_confidence":  float   # cosine similarity of review embedding to cluster centroid
}
```

### 3.4 Theme Summary Record

Produced by `pulse/analysis/classify.py` (aggregation step). One record per active theme.

```python
{
    "theme":         str,    # theme label
    "review_count":  int,    # number of reviews assigned to this theme
    "avg_rating":    float,  # mean rating of reviews in this theme
    "rank":          int     # 1 = highest volume; used to select top 3
}
```

### 3.5 Selected Quote Record

Produced by `pulse/analysis/quote_select.py`. One record per top-3 theme.

```python
{
    "theme":        str,   # theme label
    "quote":        str,   # verbatim substring from text_redacted
    "review_id":    int,   # review_id of the source review
    "verified":     bool   # True = substring match confirmed in source data
}
```

### 3.6 Action Idea Record

Produced by `pulse/analysis/action_gen.py`. One record per generated action idea.

```python
{
    "action":        str,   # plain-English action idea (one sentence)
    "linked_theme":  str    # theme label this action is tied to
}
```

### 3.7 Pulse Note Record

Produced by `pulse/render/pulse_note.py`. Single object representing the assembled note.

```python
{
    "product_name":   str,            # "Wealthsimple Canada"
    "period_start":   datetime,       # earliest review date in window
    "period_end":     datetime,       # latest review date in window
    "review_count":   int,            # total reviews processed
    "themes":         list[str],      # top 3 theme labels, ranked
    "quotes":         list[str],      # 3 verbatim quote strings
    "actions":        list[str],      # 3 action idea strings
    "note_text":      str,            # final ≤250-word note body
    "word_count":     int,            # confirmed word count of note_text
    "generated_at":   datetime        # UTC timestamp of this run
}
```

---

## 4. Theme Enum

All eight predefined theme labels. The LLM must return exactly one of these strings per **cluster** (Mode B) or per **review** (Mode A). String matching is case-sensitive.

| Label | Short code | Category |
|---|---|---|
| `"Account access & login"` | `AAL` | Account |
| `"Onboarding & verification"` | `OBV` | Account |
| `"Transfers, deposits & withdrawals"` | `TDW` | Transactions |
| `"Trading, investing & crypto"` | `TIC` | Transactions |
| `"App performance, bugs & reliability"` | `APR` | Technical |
| `"Customer support & issue resolution"` | `CSR` | Support |
| `"Fees, pricing & product communication"` | `FPC` | Business |
| `"Tax, statements & documents"` | `TSD` | Compliance |

---

## 5. LLM JSON Contracts

Each LLM step sends a structured prompt and expects a strictly typed JSON response. The pipeline validates the response shape before use.

> **Mode B note:** When `use_clustering: true` (the default), theme classification is handled by `pulse/analysis/cluster.py` via a plain-text call (`call_llm_text()`) — one call per cluster, returning a single theme label string. The JSON contract in §5.1 applies only to Mode A (`classify_reviews()` in `classify.py`).

### 5.1 Theme Classification Response (Mode A only)

**Called by:** `pulse/analysis/classify.py`
**One API call per batch of up to 50 reviews.**

```json
[
  {
    "review_index": 0,
    "theme": "App performance, bugs & reliability",
    "confidence": 0.91
  },
  {
    "review_index": 1,
    "theme": "Account access & login",
    "confidence": 0.85
  }
]
```

**Validation rules:**
- `review_index` must match an index in the submitted batch
- `theme` must be one of the eight label strings exactly
- `confidence` must be a float between 0.0 and 1.0
- Every submitted review index must appear in the response

### 5.2 Quote Selection Response

**Called by:** `pulse/analysis/quote_select.py`
**One API call per top-3 theme.**

```json
{
  "quote": "Every time I open the app I have to log back in. Very annoying.",
  "review_index": 0
}
```

**Validation rules:**
- `quote` must be a non-empty string
- `quote` must exist as a verbatim substring in the `text_redacted` of the identified review
- `review_index` must refer to a review in the submitted candidate list
- If validation fails, pipeline falls back to the highest `helpful_votes` review in the theme

### 5.3 Action Idea Response

**Called by:** `pulse/analysis/action_gen.py`
**Single API call.**

```json
[
  {
    "action": "Investigate persistent session expiry affecting users on iOS — check token refresh timing and background app state handling.",
    "linked_theme": "Account access & login"
  },
  {
    "action": "Add a visible transfer status tracker so users can see where their deposit is in the processing queue.",
    "linked_theme": "Transfers, deposits & withdrawals"
  },
  {
    "action": "Surface a contextual in-app support entry point on high-friction screens such as the transfer confirmation page.",
    "linked_theme": "Customer support & issue resolution"
  }
]
```

**Validation rules:**
- Array must contain exactly 3 elements
- `action` must be a non-empty string, max 200 characters
- `linked_theme` must be one of the eight label strings exactly
- Each `linked_theme` must correspond to one of the top 3 themes selected for this run

---

## 6. PII Redaction Map

Applied to `title` and `text` fields before any LLM call or output write.

| PII Type | Detection Pattern | Replacement |
|---|---|---|
| Email address | `[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}` | `[email]` |
| Canadian phone number | `(\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}` | `[phone]` |
| Account / transaction ID | `\b[A-Z]{2,4}[\-]?\d{6,12}\b` | `[id]` |
| Name trigger phrase | `(my name is|I'm|I am)\s+[A-Z][a-z]+([\s][A-Z][a-z]+)?` | trigger phrase retained; name replaced with `[name]` |
| Numeric ID strings | `\b\d{7,}\b` | `[number]` |

**Post-redaction check:** the cleaned `text_redacted` is scanned once more with all patterns. If any match remains, the row is flagged `pii_found = True` and logged for manual review.

---

## 7. Output File Schemas

### 7.1 Clean Reviews CSV

**Path:** `data/output/reviews_clean.csv`
**Written by:** `pulse/privacy/redact.py`

| Column | Type | Notes |
|---|---|---|
| `review_id` | integer | Assigned at ingest |
| `platform` | string | Normalised |
| `rating` | integer | 1–5 |
| `title_redacted` | string \| empty | PII-stripped |
| `text_redacted` | string | PII-stripped |
| `date` | string | `YYYY-MM-DD` |
| `app_version` | string \| empty | Optional; passed through |
| `country` | string \| empty | Optional; passed through |
| `helpful_votes` | integer \| empty | Optional; passed through |
| `pii_found` | boolean | `True` if redaction was applied |

**Raw `title` and `text` columns are never written to this file.**

### 7.2 Weekly Pulse Note

**Path:** `outputs/weekly_note.md`
**Written by:** `pulse/render/pulse_note.py`
**Encoding:** UTF-8

```markdown
# Wealthsimple Canada — Weekly Review Pulse
**Period:** {YYYY-MM-DD} to {YYYY-MM-DD} | **Reviews analysed:** {n}

## Top Themes
1. **{theme_1}** — {one-line explanation}
2. **{theme_2}** — {one-line explanation}
3. **{theme_3}** — {one-line explanation}

## Real User Quotes
- "{quote_1}"
- "{quote_2}"
- "{quote_3}"

## Action Ideas
1. {action_1}
2. {action_2}
3. {action_3}

---
*Generated: {YYYY-MM-DD HH:MM UTC} | Word count: {n}*
```

**Word count** is computed on the body only (excluding the metadata footer line). Must be ≤ 250.

### 7.3 Email Draft

**Path:** `outputs/email_draft.txt`
**Written by:** `pulse/render/email_draft.py`
**Encoding:** UTF-8, plain text

```
To: {email_recipient from config.yaml}
Subject: Weekly Review Pulse — Wealthsimple Canada

Hi Team,

Here is this week's review pulse for Wealthsimple Canada.

---

{note_text — full body of weekly_note.md}

---

Thanks,
{sender_name from config.yaml}
```

---

## 8. Run Metadata Record

Produced at the end of each run. Written to `outputs/run_summary.json` for observability. Not a deliverable artifact; used for debugging and re-run auditing.

```json
{
  "run_id":              "run-20260607T100000Z-c4e82a",
  "input_hash":          "sha256:a3f9b1c2d4e5f6",
  "period_key":          "wealthsimple-2026-W23",
  "delivery_key":        "wealthsimple-2026-W23-email",
  "product":             "Wealthsimple Canada",
  "input_csv":           "data/input/reviews.csv",
  "review_window_weeks": 10,
  "window_start":        "2026-03-25",
  "window_end":          "2026-06-07",
  "reviews_ingested":    142,
  "reviews_after_dedup": 139,
  "reviews_after_window_filter": 127,
  "rows_dropped_validation": 3,
  "rows_with_pii":       4,
  "rows_excluded_post_redaction": 1,
  "themes_found":        5,
  "themes_in_note":      3,
  "selected_themes":     ["App performance, bugs & reliability", "Account access & login", "Customer support & issue resolution"],
  "note_word_count":     218,
  "note_truncated":      false,
  "model":               "llama-3.3-70b-versatile",
  "llm_calls":           7,
  "output_paths": {
    "clean_csv":    "data/output/reviews_clean.csv",
    "weekly_note":  "outputs/weekly_note.md",
    "email_draft":  "outputs/email_draft.txt"
  },
  "delivery": {
    "mode":       "local",
    "doc_url":    null,
    "draft_id":   null,
    "message_id": null
  },
  "started_at":          "2026-06-07T10:00:00Z",
  "completed_at":        "2026-06-07T10:03:42Z",
  "low_data_warning":    false,
  "status":              "success",
  "errors":              []
}
```

---

## 9. Data Lifecycle Summary

```
STAGE                   DATA OBJECT                      FILE ON DISK
─────────────────────────────────────────────────────────────────────
Raw CSV input           —                                data/input/reviews.csv
↓ ingest
Validated records       list[ValidatedReview]            —
↓ redact
Redacted records        list[RedactedReview]             data/output/reviews_clean.csv
↓ classify
Themed records          list[ThemedReview]               —
↓ aggregate
Theme summaries         list[ThemeSummary]               —
↓ top-3 select
Top themes              list[str] (3 labels)             —
↓ quote extract
Quote records           list[QuoteRecord] (3)            —
↓ action generate
Action records          list[ActionRecord] (3)           —
↓ note assemble + polish
Pulse note              PulseNote                        outputs/weekly_note.md
↓ email wrap
Email draft             str                              outputs/email_draft.txt
↓ run summary
Run metadata            RunSummary                       outputs/run_summary.json
```

---

## 10. Field-Level Sensitivity Classification

| Field | Sensitivity | Included in LLM prompt | Included in outputs |
|---|---|---|---|
| `platform` | Public | Yes (as metadata) | Yes |
| `rating` | Public | Yes (as metadata) | Aggregated only |
| `title` (raw) | May contain PII | **No** | **No** |
| `text` (raw) | May contain PII | **No** | **No** |
| `title_redacted` | Sanitised | Yes | Yes (clean CSV only) |
| `text_redacted` | Sanitised | Yes | Yes (clean CSV only) |
| `date` | Public | As date range only | Date range in note |
| `app_version` | Public | No | Clean CSV only |
| `country` | Public | No | Clean CSV only |
| `helpful_votes` | Public | No | Not in outputs |
| `review_id` | Internal | No | Clean CSV only |
| `pii_found` | Internal flag | No | Clean CSV only |
