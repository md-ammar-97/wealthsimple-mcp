# Issue: CSV Upload Results 503 Loop — "Results timed out"

**Severity:** Critical — CSV upload analysis never returns results  
**Reported:** 2026-06-13  
**Environment:** Render (production) at `wealthsimple-mcp.onrender.com`

---

## Symptom

After uploading a CSV and watching the pipeline run:

```
GET /api/results 503 (Service Unavailable)  × 5
```

Then the page shows: **"Results timed out. The pipeline may still be running."**

---

## Flow Trace

Understanding the exact sequence is necessary to locate the bug:

```
User submits form
  → POST /api/upload        (saves CSV + stores global.csvMeta)
  → POST /api/run           (writes placeholder run_summary.json {status:'running'})
                             (spawns python3 -m pulse.cli run --input data/input/reviews.csv)
  → GET /api/pipeline/status (SSE; drains global.pipelineQueue every 500ms)

Python runs orchestrator:
  steps 1–8 → each emits step_start / step_done to stdout
  step 9 (delivery) → up to 30s
  write_run_summary(run_data, config, path)   ← writes {status:'success'} to run_summary.json
  Python exits with code 0

Node.js child.on('close', code === 0):
  → pushes { completed: true } to global.pipelineQueue
  → SSE drains queue, sends data: {"completed":true} to browser
  → browser: pipelineStatus.completed = true
  → fetchResults() called

fetchResults():
  attempt 0 (0ms delay)  → GET /api/results → 503
  attempt 1 (500ms)       → GET /api/results → 503
  attempt 2 (1000ms)      → GET /api/results → 503
  attempt 3 (1500ms)      → GET /api/results → 503
  attempt 4 (2000ms)      → GET /api/results → 503
  → setError('Results timed out...')  → stage = 'error'
```

`/api/results` returns 503 only when `summary.status === 'running'`. That status is the **Node.js placeholder** value. For 503 to persist through all 5 retries, Python must not have overwritten this file with `status: 'success'`.

---

## Root Cause Analysis

### Cause A — Python fails on Render before writing `run_summary.json` (needs Render logs)

The most likely production cause. `write_run_summary` in `pulse/orchestrator.py` is called at **line 238**, which is the last step. If Python crashes before reaching line 238:

- In normal Python exception flow, the `except` block at line 247 runs first, writing `run_summary.json` with `status: 'error'`, and then `raise` exits with code 1.
- Code 1 exit → Node.js `child.on('close')` sees non-zero code → does **not** push `{completed:true}` → browser never calls `fetchResults()`.

But the browser IS calling `fetchResults()` (we see the 503s). So Python exited with **code 0**. Possible explanations requiring Render logs to confirm:
- Python completed all steps successfully but `write_run_summary` failed silently (filesystem permission or path issue on Render)
- A stale `{completed:true}` from a prior run was still in `global.pipelineQueue` when the new SSE connected (new run resets the queue on `POST /api/run`, so this would only happen if SSE connected before the POST was processed)

**Action:** Check Render logs for `[pipeline close] code:` and `[pipeline stderr]`. If code is not 0, the scenario above is different.

---

### Cause B — Error events NOT in SSE queue (confirmed code bug)

**File:** `frontend/src/app/api/run/route.ts:111-138`

When Python exits with non-zero code:

```typescript
child.on('error', (err: Error) => {
  // Sets global.pipelineRun but NEVER pushes to global.pipelineQueue
  global.pipelineRun = { runId, stage: 'error', event: 'error', error: err.message, completed: false };
});

child.on('close', async (code) => {
  if (code === 0) {
    global.pipelineQueue.push({ completed: true, ... });  // ✓ queue gets event
  } else {
    global.pipelineRun = { ..., completed: false };         // ✗ NOT in queue
  }
});
```

The SSE route at `/api/pipeline/status` drains `global.pipelineQueue` — it does **not** read `global.pipelineRun`. Pipeline errors are never delivered to the browser via SSE.

**Result when Python fails:**
- Queue stays empty; SSE stream drains nothing for 12 minutes then times out
- Browser `EventSource` fires `onerror`
- `usePipelineStatus` sets `pipelineStatus.error = 'Connection lost. The pipeline may have failed.'`
- Upload page shows the generic connection-lost message
- The actual Python error (from stderr) is only in Render logs

**Fix:** Push the error state to `global.pipelineQueue` so the SSE delivers it to the browser.

---

### Cause C — `PYTHONUNBUFFERED` not set in spawn environment

**File:** `frontend/src/app/api/run/route.ts:81`

```typescript
const child = spawn(PYTHON_BIN, [...], {
  cwd: PROJECT_ROOT,
  env: { ...process.env },   // PYTHONUNBUFFERED not set
});
```

When Python's stdout is a pipe (not a TTY), Python defaults to **full buffering**. All step log lines (`step_start`, `step_done`, etc.) are accumulated in Python's internal buffer and flushed only when:
- The buffer fills (~8 KB)
- Python exits normally

**Result:** The progress bar does not animate step by step. All 8 steps appear done simultaneously when Python finishes. If Python crashes mid-run, the buffered step events may be lost.

**Fix:** Add `PYTHONUNBUFFERED: '1'` to the spawn env:
```typescript
env: { ...process.env, PYTHONUNBUFFERED: '1' },
```

---

### Cause D — `fetchResults()` retry window too short (confirmed, 5 seconds total)

**File:** `frontend/src/app/upload/page.tsx:51-78`

```typescript
for (let attempt = 0; attempt < 5; attempt++) {
  await new Promise(r => setTimeout(r, attempt * 500));
  // delays: 0, 500, 1000, 1500, 2000 ms = 5 seconds total
```

After `completed:true` arrives, the client polls for only **5 seconds**. Even on successful runs, if Python writes `run_summary.json` and then Node.js's close event takes longer than expected to process (network/process scheduling jitter), all retries can expire. Should be extended to ~30 seconds with exponential backoff.

---

### Cause E — `review_count` field name mismatch (confirmed data bug)

**File:** `frontend/src/app/api/results/route.ts:33`

```typescript
reviewCount: summary.review_count ?? 0,   // reads 'review_count'
```

Python's orchestrator writes `reviews_ingested` in `run_data`:
```python
run_data.update({ "reviews_ingested": ingest_meta.get("reviews_ingested", len(reviews)) })
```

The `run_summary.json` field is `reviews_ingested`, not `review_count`. Even on successful runs, the upload results page always shows **0 reviews analysed**.

**Fix:** Change to `summary.reviews_ingested ?? summary.review_count ?? 0`.

---

### Cause F — Side effect during React render (anti-pattern)

**File:** `frontend/src/app/upload/page.tsx:82-91`

```typescript
// In render body — NOT inside useEffect:
const prevCompleted = useRef(false);
if (stage === 'running' && pipelineStatus.completed && !prevCompleted.current) {
  prevCompleted.current = true;
  fetchResults();   // ← side effect during render
}
```

`fetchResults()` is called from the render function body. React 19 concurrent mode can invoke render multiple times (e.g., during transitions or strict mode). Side effects must be in `useEffect`.

**Fix:** Wrap in `useEffect([pipelineStatus.completed, pipelineStatus.error, stage])`.

---

### Cause G — `run_summary.json` written AFTER delivery (architectural timing issue)

**File:** `pulse/orchestrator.py:212-239`

The orchestrator structure is:

```python
# All 8 steps complete
write_artifact(note, ...)
write_artifact(email, ...)

# Step 10 — DELIVERY (up to 30s before run_summary.json is written)
try: append_doc_section(...)   # 15s timeout
except: ...
try: create_gmail_draft(...)   # 15s timeout
except: ...

# ONLY NOW:
write_run_summary(run_data, ...)   # run_summary.json written here
append_ledger(run_data, ...)
```

Delivery can take up to 30 seconds before `run_summary.json` is written. During that time:
- SSE step events for all 8 steps have been sent (steps complete before delivery)
- `completed:true` has NOT been sent yet (Python hasn't exited)
- If the user closes the browser tab during delivery, the SSE connection drops but Python keeps running
- When Python finally exits, `completed:true` is pushed — but no SSE client is connected to drain it

This is not a direct cause of the 503 issue (Node.js pushes `completed:true` AFTER Python exits, which is AFTER `write_run_summary`). But it's a UX concern: the browser may appear stuck at "100% complete visually but no completion signal" for up to 30 seconds while delivery runs.

---

## Fixes Applied

| Fix | File | Change |
|---|---|---|
| Push error to SSE queue | `frontend/src/app/api/run/route.ts` | `close` and `error` handlers push to `pipelineQueue` |
| Set PYTHONUNBUFFERED | `frontend/src/app/api/run/route.ts` | `env: { ...process.env, PYTHONUNBUFFERED: '1' }` |
| Increase retry window | `frontend/src/app/upload/page.tsx` | 10 retries, exponential backoff up to 30s |
| Fix review_count field | `frontend/src/app/api/results/route.ts` | `summary.reviews_ingested ?? ...` |
| Move side effect to useEffect | `frontend/src/app/upload/page.tsx` | `useEffect` watching `pipelineStatus.completed` |
| Filter SSE queue by runId | `frontend/src/app/api/pipeline/status/route.ts` | Skip queue items where `runId` doesn't match |

---

## Outstanding — Needs Render Logs

Check Render dashboard (Logs tab) after the next upload attempt:

| Log line to look for | Meaning |
|---|---|
| `[pipeline close] code: 0` | Python exited cleanly; run_summary.json should be written |
| `[pipeline close] code: 1` | Python raised an exception; check stderr for traceback |
| `[pipeline close] code: 137` | OOM kill (SIGKILL); RAM exceeded 512 MB |
| `[pipeline stderr] ...` | Python error text; check for import errors or file not found |
| `[pipeline spawn error] ...` | Node.js could not even start Python |

---

## Verification

After fixes are deployed:
1. Upload a CSV at `/upload`, enter email, click Run Pipeline
2. Progress bar should animate step by step in real time (PYTHONUNBUFFERED fix)
3. After ~1–2 minutes, results section appears: themes, quotes, actions, pulse note
4. Review count in success banner should show the actual count (not 0)
5. Render logs should show `[pipeline close] code: 0` with no stderr errors
