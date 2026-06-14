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

**Status:** PARTIALLY FIXED; persistent 503 fix in progress (this session)  
**Symptom:** After uploading a CSV, pipeline appears to complete but `GET /api/results` returns 503 on every retry (5 original retries, 12 after fix). Ends with "Results timed out" error.

### Root Cause Analysis

**A — `run_summary.json` not overwritten (CURRENT OPEN ISSUE)**  
Node.js pre-writes `run_summary.json` with `status: 'running'` before spawning Python. When Python exits code 0, `child.on('close')` immediately pushes `{ completed: true }` to the SSE queue WITHOUT verifying the file was updated. The browser calls `fetchResults()` and reads the stale placeholder. Root environmental cause on Render is unknown without logs; may be filesystem sync, path difference, or a Python crash that exits 0 early.

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

**Status:** IN PROGRESS (this session)  
**Symptom:** Even after fixes B–E (ISSUE-002), the 503 loop persists. All 12 retries fail. `run_summary.json` still says `status: 'running'` when `fetchResults()` reads it.

### Root Cause
Unknown without Render logs. The `child.on('close', code === 0)` handler pushes `{ completed: true }` immediately after Python exits, without confirming the file was written. On Render, the file may not be readable immediately after Python's exit (filesystem sync, path difference, or a Python crash that exits 0 early without calling `write_run_summary`).

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

**Status:** IN PROGRESS (2026-06-13)  
**Symptom:** The diagnostic message added in ISSUE-006 now surfaces in the browser: "Pipeline exited 0 but summary status is 'running' after 10s". Python exits code 0 via normal completion (confirmed: no `sys.exit(0)` in codebase; validation failures use `sys.exit(1)`). This means `run_pipeline()` returns normally and `write_run_summary()` at orchestrator.py line 238 IS called — but the file lands at the wrong path.

### Root Cause
The spawn call passes **relative paths**:
```typescript
spawn(PYTHON_BIN, ['-m', 'pulse.cli', 'run', '--input', 'data/input/reviews.csv'], {
  cwd: PROJECT_ROOT, ...
})
```
Python resolves `outputs/run_summary.json` relative to its actual runtime CWD. If Render does not fully honor the `cwd` spawn option, Python writes to a different directory than `${PROJECT_ROOT}/outputs/`. Node's verification loop polls the wrong path and sees only the stale 'running' placeholder.

**Confirmed non-causes:** No `sys.exit(0)` anywhere; delivery guard does not skip `write_run_summary`; `use_clustering: false`.

### Fix Applied
Pass absolute paths so Python's runtime CWD is irrelevant:
```typescript
const INPUT_CSV = path.join(PROJECT_ROOT, 'data', 'input', 'reviews.csv');
const child = spawn(PYTHON_BIN, [
  '-m', 'pulse.cli', 'run',
  '--input', INPUT_CSV,
  '--output-dir', OUTPUTS_DIR,
], { cwd: PROJECT_ROOT, env: { ...process.env, PYTHONUNBUFFERED: '1' } });
console.log('[pipeline spawn]', PYTHON_BIN, '--input', INPUT_CSV, '--output-dir', OUTPUTS_DIR, 'cwd:', PROJECT_ROOT);
```
Also: non-JSON stdout (previously silently dropped) now logged via `console.log('[pipeline stdout]', line)`.

**Files:** `frontend/src/app/api/run/route.ts`

---

## Open Investigation Items

| Item | Where to look |
|---|---|
| Confirm ISSUE-007 fix resolved the path problem | Render logs: `[pipeline spawn]` shows absolute paths; no "unexpected summary status" after next deploy |
| Whether GROQ_API_KEY is set and Groq calls succeed | Render logs: Python stderr during step 3 (classify) |
