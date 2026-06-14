# Issues Log — Wealthsimple Pulse

Consolidated tracker for all production bugs and fixes. Each issue includes root cause, fix applied, and current status.

---

## ISSUE-001 — Analytics page 404 on every visit

**Status:** FIXED (2026-06-13)  
**Symptom:** `GET /api/analytics?days=0 404 (Not Found)` on every visit to the analytics page.

### Root Causes

**A — `ledger.json` not tracked in git (PRIMARY)**  
`.gitignore` contained `data/runs/` (directory rule) with `!data/runs/ledger.json` (negation). Git directory ignores block file-level negations — the file was never `git add`-ed, so Render never received it. The analytics route read from a file that didn't exist on the server.

**B — Catch block hid the real error**  
`analytics/route.ts` catch block returned 404 with a fixed string regardless of what threw. Render logs contained no indication of the real failure.

### Fix Applied
- `git add -f data/runs/ledger.json` to force-track despite directory ignore rule
- Added `console.error` in catch block before returning 404 so future errors are visible in Render logs

**Files:** `frontend/src/app/api/analytics/route.ts`, `data/runs/ledger.json`

---

## ISSUE-002 — CSV upload shows 503 loop ("Results timed out")

**Status:** FIXED (2026-06-14)
**Symptom:** After uploading a CSV, pipeline appears to complete but `GET /api/results` returns 503 on every retry (5 original retries, 12 after fix). Ends with "Results timed out" error.

### Root Cause Analysis

**A — `run_summary.json` not overwritten (FIXED by ISSUE-007)**
Node.js pre-writes `run_summary.json` with `status: 'running'` before spawning Python. When Python exited code 0, `child.on('close')` immediately pushed `{ completed: true }` without verifying the file was updated, so the browser read the stale placeholder. The later diagnostic exposed the missing `python -m pulse.cli` entry point documented in ISSUE-007.

**Fix:** Server-side verification loop — poll `run_summary.json` for up to 10 seconds after Python exits code 0 before pushing `{ completed: true }` to the SSE queue.

**B — Error events not pushed to SSE queue (FIXED 2026-06-13)**  
`child.on('error')` and `child.on('close', code !== 0)` wrote to `global.pipelineRun` but never pushed to `global.pipelineQueue`. The SSE route drains only the queue. Errors were silently lost; browser saw "Connection lost" after 12-minute SSE timeout.

**Fix:** Both error paths now push to `pipelineQueue` with `completed: true`.

**C — Retry window only 5 seconds total (FIXED 2026-06-13)**  
`fetchResults()` retried 5 times × 0+500+1000+1500+2000ms = 5s total. Any delay between Python writing the file and Node reading it caused all retries to fail.

**Fix:** Increased to 12 attempts with exponential backoff, capped at 5s per attempt (~40s total).

**D — `fetchResults()` called from React render body (FIXED 2026-06-13)**  
Side effect called during render — React 19 concurrent mode may call render multiple times, causing duplicate `fetchResults()` invocations.

**Fix:** Moved into `useEffect` watching `pipelineStatus.completed` and `pipelineStatus.error`.

**E — `review_count` field mismatch (FIXED 2026-06-13)**  
`results/route.ts` read `summary.review_count` but Python's orchestrator writes `reviews_ingested`. Review count always showed 0 even on successful runs.

**Fix:** `reviewCount: summary.reviews_ingested ?? summary.review_count ?? 0`

**Files:** `frontend/src/app/api/run/route.ts`, `frontend/src/app/api/results/route.ts`, `frontend/src/app/upload/page.tsx`

---

## ISSUE-003 — Steps all completing at once (no real-time animation)

**Status:** FIXED (2026-06-13)  
**Symptom:** Pipeline step indicators all flipped from idle → done simultaneously when the pipeline finished, instead of animating one by one.

### Root Cause
Python uses full stdout buffering when stdout is a pipe (not a TTY). All step log events accumulated in Python's buffer and were flushed as a single burst when Python exited.

### Fix Applied
Added `PYTHONUNBUFFERED: '1'` to the spawn environment in `run/route.ts`:
```typescript
env: { ...process.env, PYTHONUNBUFFERED: '1' }
```

**Files:** `frontend/src/app/api/run/route.ts`

---

## ISSUE-004 — Stale SSE completion events from previous runs

**Status:** FIXED (2026-06-13)  
**Symptom:** On a new run, the SSE route could immediately drain a leftover `{ completed: true }` event from a previous run, causing the browser to show results from the old run.

### Root Cause
`pipeline/status/route.ts` drained `global.pipelineQueue` without checking `runId`. Stale events from prior runs remained in the queue if their SSE subscriber disconnected before draining.

### Fix Applied
- SSE GET handler now reads `runId` from URL query param
- Queue drain loop skips events where `run.runId !== runId`
- `stageToStepUpdate` returns `{ completed: true, error: ... }` for error completions (not just `{ completed: true }`)

**Files:** `frontend/src/app/api/pipeline/status/route.ts`

---

## ISSUE-005 — Error field lost in SSE completion event

**Status:** FIXED (2026-06-13)  
**Symptom:** When Python exited with an error, the browser received `{ completed: true }` (no error field), so `usePipelineStatus` set `completed: true` without `error`. The `useEffect` in upload page called `fetchResults()` instead of showing the real error.

### Root Cause
`stageToStepUpdate` returned `JSON.stringify({ completed: true })` for all completions, including error completions. The `usePipelineStatus` `onmessage` handler didn't forward the `error` field from the SSE event.

### Fix Applied
- `stageToStepUpdate` returns `{ completed: true, error: run.error }` when `run.stage === 'error'`
- `usePipelineStatus` onmessage sets `error: data.error ?? prev.error` on completion

**Files:** `frontend/src/app/api/pipeline/status/route.ts`, `frontend/src/hooks/usePipelineStatus.ts`

---

## ISSUE-006 — Persistent 503: server verifies file before signalling browser

**Status:** FIXED (2026-06-14; root cause documented in ISSUE-007)
**Symptom:** Even after fixes B–E (ISSUE-002), the 503 loop persists. All 12 retries fail. `run_summary.json` still says `status: 'running'` when `fetchResults()` reads it.

### Root Cause
The server-side verification correctly proved that Python exited 0 without updating the summary. ISSUE-007 identified the underlying cause: `python3 -m pulse.cli` imported the module but did not invoke the Click entry point.

**Confirmed non-causes:**
- `use_clustering: false` is already set — no PyTorch/OOM risk
- Orchestrator delivery guard (lines 100-103) does not skip `write_run_summary`
- The 12-retry fix is confirmed deployed (browser logs show 12 × 503)

### Fix Applied (this session)
Server-side polling loop in `run/route.ts` close handler: after Python exits code 0, read `run_summary.json` every second for up to 10 seconds. Only push `{ completed: true }` (success) when file shows `status: 'success'`. If still `'running'` after 10s, push a diagnostic error event so the browser shows a real error message instead of a 503 timeout.

Added diagnostics:
- `debug/route.ts` now returns `runSummaryContent` (parsed JSON) and `pipelineRunState`
- `results/route.ts` logs `global.pipelineRun` to Render logs when returning 503

**Files:** `frontend/src/app/api/run/route.ts`, `frontend/src/app/api/debug/route.ts`, `frontend/src/app/api/results/route.ts`

---

## ISSUE-007 — "Pipeline exited 0 but summary status is 'running' after 10s"

**Status:** FIXED AND DEPLOYED (2026-06-14)
**Symptom:** The diagnostic message added in ISSUE-006 surfaces in the browser: "Pipeline exited 0 but summary status is 'running' after 10s". The live `/api/debug` endpoint confirms the Node placeholder remains unchanged after the child process exits.

### Root Cause
Render launches:
```bash
python3 -m pulse.cli run ...
```

`pulse/cli.py` defined the Click `main()` group but did not contain:
```python
if __name__ == "__main__":
    main()
```

Running the module therefore imported the CLI definitions, performed no pipeline work, and exited successfully with code 0. Since `run_pipeline()` never ran, Python never replaced the Node-written `{status: "running"}` placeholder.

### Fix Applied
- Added the missing module entrypoint to `pulse/cli.py`
- Added a regression test that runs `python -m pulse.cli --help`
- Passed Node's `runId` to Python via `--run-id` so placeholder, SSE, logs, and final summary share one ID
- Retained the earlier absolute input/output path fix

**Files:** `pulse/cli.py`, `frontend/src/app/api/run/route.ts`, `tests/unit/test_cli.py`

---

## Open Investigation Items

No active production bug from this issue set remains open. Future LLM failures should be diagnosed from the structured stage logs and `run_summary.json`.

---

## ISSUE-008 - Empty ranked themes after CSV upload

**Status:** FIXED (2026-06-14)
**Symptom:** The upload page reported: `ranked_themes is empty - theme classification must have failed upstream.`

### Root Cause
The live run summary showed that ingestion rejected all 49 uploaded rows:

- `reviews_ingested: 0`
- `reviews_after_dedup: 0`
- `rows_dropped_validation: 49`

Theme classification therefore received no reviews. The previous pipeline behavior continued through
redaction, classification, and ranking before raising a misleading downstream error.

The importer also accepted only the exact platform names `App Store` and `Google Play`, and only bare
`YYYY-MM-DD` or `DD/MM/YYYY` dates. Common export values such as `iOS`, `Android`, `Play Store`, ISO
timestamps, and US-style slash dates were rejected.

### Fix Applied
- Accept common App Store and Google Play platform aliases
- Accept ISO timestamps, `MM/DD/YYYY`, and `YYYY/MM/DD` dates
- Record validation rejection counts and date-window exclusions in the run summary
- Stop after ingestion when zero valid reviews remain and report the exact rejection breakdown
- Make the optional `title` column optional in browser-side CSV validation

**Files:** `pulse/ingestion/validators.py`, `pulse/ingestion/ingest.py`,
`pulse/orchestrator.py`, `frontend/src/app/upload/page.tsx`,
`frontend/src/components/UploadZone/UploadZone.tsx`, `tests/unit/test_ingest.py`

---

## ISSUE-009 - Successful report creates a Gmail draft but sends no email

**Status:** FIXED (2026-06-14)
**Symptom:** Pipeline and report generation succeeded, and Gmail contained the report in Drafts, but
the recipient never received a message.

### Root Cause
The configured `email_mode` was `draft`, the delivery client always called
`POST /create_email_draft`, and google-mcp-server did not expose a send endpoint.
`APPROVAL_MODE=auto` approved draft creation only; it did not send the draft.

### Fix Applied
- Added `POST /send_email` backed by Gmail `users.messages.send`
- Made the pipeline honor `gmail_mcp.email_mode`
- Set production delivery to `email_mode: send`
- Added mode-specific delivery keys so a prior draft does not suppress a send
- Changed CSV uploads to send to the uploader and skip the pipeline's configured delivery,
  preventing duplicate messages

**Files:** `pulse/delivery/gmail_mcp.py`, `pulse/orchestrator.py`, `pulse/cli.py`,
`pulse/ledger/run_ledger.py`, `config/delivery.yaml`,
`frontend/src/app/api/run/route.ts`, `tests/unit/test_mcp_delivery.py`,
`tests/unit/test_ledger.py`, `tests/unit/test_cli.py`
