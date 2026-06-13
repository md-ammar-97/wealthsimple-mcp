# Context — Wealthsimple App Review Insights Analyser

## Project Purpose

This system automates the weekly analysis of public Wealthsimple Canada app reviews from the Apple App Store and Google Play Store. It converts raw, noisy review data into a concise, stakeholder-ready product insight note — eliminating the need for teams to manually read review exports every week.

---

## System Role

The system acts as a **weekly review intelligence pipeline**. Given a CSV of recent public app reviews, it must:

1. Clean and redact any PII from the review text
2. Classify reviews into up to five product themes
3. Select three real, verbatim user quotes
4. Generate three practical action ideas
5. Produce a one-page weekly pulse note (≤ 250 words)
6. Draft a stakeholder email containing the weekly note

---

## Primary Users

| Persona | Need |
|---|---|
| Product & Growth | Identify recurring pain points; inform roadmap |
| Support | Spot complaint patterns; prepare responses |
| Leadership | Weekly sentiment health check; no manual reading |

---

## Input

### Data Acquisition (automated — no manual export required)

| Source | Method | Auth |
|---|---|---|
| Apple App Store | iTunes customer-reviews RSS (`itunes.apple.com/ca/rss/customerreviews/…`) | None — public feed |
| Google Play Store | `google-play-scraper` Python library (public scraper) | None — public data |

- **App Store ID:** `1360669270` (Wealthsimple Canada)
- **Play Store package:** `com.wealthsimple`
- **Window:** Last 10 weeks per run (configurable 8–12)
- **Columns kept:** `platform`, `rating`, `title`, `text`, `date`, `app_version`, `country`, `helpful_votes`
- **Columns dropped at source:** `reviewId`, `userName`, `userImage`, `reviewCreatedVersion`, `at`, `replyContent`, `repliedAt`

### Data Files

| File | Contents |
|---|---|
| `data/input/reviews_raw.csv` | All fetched reviews, both platforms — no filtering applied |
| `data/output/reviews_clean.csv` | Normalized reviews after applying quality filters (see below) |

### Normalization Filters (applied before pipeline analysis)

| Filter | Rule |
|---|---|
| Short text | Drop reviews where text has fewer than **8 words** |
| Emoji | Drop reviews whose title or text contains any emoji character |
| Language | Drop reviews not detected as **English** (`langdetect`) |

- **PII policy:** All usernames, emails, phone numbers, account IDs, and financial identifiers are stripped during the redaction step before any LLM call

---

## Processing Pipeline

```
Fetch (iTunes RSS + google-play-scraper)
   → Save reviews_raw.csv  (all fetched, unfiltered)
   → Normalize (drop short, emoji, non-English)
   → Save reviews_clean.csv  (quality-filtered)
   → PII Redaction
   → Theme Classification (LLM, max 5 themes)
   → Top 3 Theme Selection
   → Quote Extraction (3 verbatim quotes, no invention)
   → Action Idea Generation (3 practical ideas)
   → Weekly Pulse Note (≤ 250 words)
   → Email Draft
```

---

## Theme Legend

| # | Theme | Covers |
|---|---|---|
| 1 | Account access & login | Sign-in failures, lockouts, 2FA issues |
| 2 | Onboarding & verification | KYC, identity checks, account setup |
| 3 | Transfers, deposits & withdrawals | Fund movement delays, failures, limits |
| 4 | Trading, investing & crypto | Order execution, portfolio UX, crypto flows |
| 5 | App performance, bugs & reliability | Crashes, freezes, slow loads, UI errors |
| 6 | Customer support & issue resolution | Wait times, response quality, ticket handling |
| 7 | Fees, pricing & product communication | Fee transparency, unexpected charges, messaging |
| 8 | Tax, statements & documents | T-slips, RRSP, document access, filing |

> The weekly note presents only the **top three themes** by review volume or severity.

---

## Output Specification

### Weekly Pulse Note
- **Length:** 250 words or less
- **Sections:** Product name, review period, top 3 themes, 3 real quotes, 3 action ideas
- **Format:** Markdown, PDF, or Doc
- **Tone:** Scannable, stakeholder-friendly, factual

### Email Draft
- **Subject:** `Weekly Review Pulse — Wealthsimple Canada`
- **Body:** Brief intro + embedded weekly note
- **Recipient:** Internal team alias or stakeholder group
- **Format:** Plain text or screenshot

### Reviews CSV
- Stored per run; sample or redacted data acceptable for sharing
- Must include: `platform`, `rating`, `title`, `text`, `date`

---

## Hard Constraints

| Rule | Detail |
|---|---|
| No login scraping | Public exports only |
| No PII | Strip before any output |
| No invented quotes | All quotes must be verbatim from input CSV |
| No hallucinated themes | Themes must be grounded in actual review content |
| Max 5 themes | Weekly note shows top 3 only |
| Word limit | Note must be ≤ 250 words |
| No BI dashboard | Output is a weekly insight pulse, not analytics |

---

## Out of Scope

- Real-time or continuous monitoring
- Social media, support tickets, or login-gated data
- Account-level or transaction-level analytics
- Manual review tagging workflows
- Full product analytics dashboards

---

## Re-Run Behavior

The workflow is designed to be re-run each week:

1. Export a fresh review CSV covering the new 8–12 week window
2. Drop it into the input directory (replacing the prior CSV)
3. Run the pipeline
4. New weekly note and email draft are generated automatically

No state is carried between runs. Each run is fully self-contained.

---

## Success Checklist

- [ ] Processes a review CSV from App Store and Google Play
- [ ] Generates a clean weekly note under 250 words
- [ ] Identifies ≤ 5 themes; presents top 3 in the note
- [ ] Includes 3 real review quotes with no PII
- [ ] Provides 3 actionable, product-oriented ideas
- [ ] Produces a stakeholder-ready email draft
- [ ] Can be re-run for future weeks with minimal manual effort
- [ ] Demo completable in 3 minutes or less

---

## Key Assumptions & Limitations

- Reviews are sourced externally (e.g., manually exported or via a public review aggregator) — the system does not scrape directly
- Review volume per window may vary; the pipeline handles sparse or rich datasets
- Theme classification quality depends on review text clarity and LLM prompt quality
- Quotes are selected by the LLM but must exist verbatim in the input CSV — the system does not generate synthetic quotes
- The 250-word limit applies to the pulse note body only, not the email wrapper
