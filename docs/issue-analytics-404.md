# Issue: Analytics Page 404 — `GET /api/analytics?days=0`

**Severity:** High — the entire analytics page is blank on production  
**Reported:** 2026-06-13  
**Environment:** Render (production) at `wealthsimple-mcp.onrender.com`

---

## Symptom

Every visit to `/analytics` triggers:

```
GET https://wealthsimple-mcp.onrender.com/api/analytics?days=0 404 (Not Found)
```

The page shows a spinner then an error banner. No metric cards, charts, or run history are displayed.

---

## Why `days=0`

The analytics page initialises with `const [days, setDays] = useState(0)` where `0` means "All time". On mount, `useEffect(() => { load(days); }, [days, load])` fires immediately with `fetch('/api/analytics?days=0')`. This is correct client-side behaviour — the `days=0` value is not the bug.

The route handles `days=0` correctly:
```typescript
const cutoff = days > 0 ? new Date(Date.now() - days * 86_400_000) : null;
const filtered = entries.filter(e => !cutoff || new Date(e.started_at) >= cutoff);
```
When `days === 0`, `cutoff === null`, and all ledger entries are returned.

---

## Root Cause Analysis

### Cause A — Catch block hides the actual error (confirmed code bug)

**File:** `frontend/src/app/api/analytics/route.ts:74`

```typescript
} catch {
  return NextResponse.json({ error: 'Ledger not found or unreadable' }, { status: 404 });
}
```

Any exception anywhere in the try block (file not found, JSON parse failure, TypeError, permission error) is caught and returns `404` with the same fixed string. The real error is **never logged**. This makes it impossible to diagnose the failure from Render logs.

**Fix applied:** Added `console.error` to log the actual error before returning.

---

### Cause B — `ledger.json` not committed to git (most likely deployment cause)

**File:** `.gitignore`

```
data/runs/
!data/runs/ledger.json
```

The `!data/runs/ledger.json` exception tells git not to ignore this file. However, a `.gitignore` negation only affects files that git _would otherwise ignore_ — it does not retroactively add untracked files to the index. If `ledger.json` was created locally but never explicitly `git add`-ed, it is **not tracked** and **not present on Render**.

**Local state:** The file exists at `data/runs/ledger.json` with 2 valid entries (runs on 2026-06-09 and 2026-06-13).

**Resolution:** `git ls-files data/runs/ledger.json` — if empty, the file is untracked and must be explicitly added.

---

### Cause C — Analytics API route not deployed (possible secondary cause)

`frontend/src/app/api/analytics/route.ts` was created in the previous development session. If that session ended without a `git commit && git push`, the route does not exist on Render. Next.js returns 404 for routes that don't exist — this is visually indistinguishable from the catch-block 404.

**Resolution:** Verify `git status` includes this file as committed, and `git log` shows it in the most recent commit that's been pushed.

---

## Data Ledger Contents (local)

```json
[
  {
    "run_id": "run-20260609T065814Z-9f6f3c",
    "status": "success",
    "started_at": "2026-06-09T06:58:14.843187+00:00",
    "reviews_ingested": 144,
    "themes_in_note": 3,
    "note_word_count": 227,
    "delivery": { "mode": "local" }
  },
  {
    "run_id": "run-20260613T125253Z-4cad4d",
    "status": "success",
    "started_at": "2026-06-13T12:52:53.548135+00:00",
    "reviews_ingested": 142,
    "themes_in_note": 3,
    "note_word_count": 125,
    "delivery": { "mode": "mcp", "doc_url": "...", "draft_id": "..." }
  }
]
```

Both entries are valid and would produce correct output when the route can read the file.

---

## Fixes Applied

| Fix | File | Change |
|---|---|---|
| Log real error in catch | `frontend/src/app/api/analytics/route.ts` | Added `console.error('[analytics] ...')` before returning 404 |
| Commit `ledger.json` | `data/runs/ledger.json` | `git add data/runs/ledger.json` if untracked |
| Ensure route is deployed | All new frontend files | Committed and pushed to `main` |

---

## Verification

After fix:
1. Visit `https://wealthsimple-mcp.onrender.com/analytics`
2. Network tab: `GET /api/analytics?days=0` should return 200 with JSON body containing `totalRuns: 2`
3. Page should display: 2 metric cards with values, run history table with 2 rows
