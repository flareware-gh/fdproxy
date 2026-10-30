# Timestamp-First Collection with 5-Minute Request Labels

## Problem

The original design used `(session_date, slot)` as a unique key with named slots (`m0935`, `t1530`, `close`) and required the wall clock to be within ±10 minutes of a named slot. This caused issues:

1. **Lost snapshots**: GitHub Actions cron wakes late/irregularly, causing the ±10 min gate to reject runs
2. **Failed CI jobs**: When the slot gate raised an error, the entire workflow failed
3. **FK conflicts**: The unique constraint prevented re-running a slot (e.g., after a transient failure)
4. **Rigid scheduling**: Manual tests and alternative schedulers (Vercel cron) couldn't run outside the tight windows
5. **Label ambiguity**: Named slots were a poor fit for irregular scheduling and didn't capture actual collection time

## Solution: Timestamps Are Ground Truth + 5-Minute Request Labels

The new design treats **timestamps as ground truth** and uses **deterministic 5-minute bucket labels**:

- Fire on an interval (GitHub Actions cron grid remains the same)
- Always save data (except weekends/holidays)
- Keep duplicates and near-duplicates (no unique constraint on label)
- Compute `request_label` from `request_started_at` (floored to 5-minute buckets in ET)
- Labels are pure functions of timestamp: `rqHHmmtoHHmm` (e.g., `rq1030to1034`, `rq1505to1509`)
- Analysis filters by label or timestamp windows as needed

## Schema Changes

### Migration 002 (Timestamp-First Collection)
- **Removed**: Unique constraint on `(session_date, slot)`
- **Renamed**: `slot` → `intended_slot` (nullable soft label)
- **Added**: `request_started_at`, `request_finished_at`, `trigger_source`, `trigger_id`, `intended_at`
- **Backfilled**: `request_started_at` ← `started_at`, `request_finished_at` ← `finished_at`

### Migration 003 (5-Minute Request Labels)
- **Renamed**: `intended_slot` → `request_label` (nullable)
- **Backfilled**: `request_label` computed from `request_started_at` (or `started_at`) using 5-minute ET buckets
- **Indexed**: `(session_date, request_label)` for efficient querying
- **Removed**: Named slot assignment logic (`m0935`, `t1530`, `close`)
- **Removed**: `find_nearest_slot` usage in collection path (kept for potential simulate usage)

## Behavior Changes

### Label Assignment (Before - Migration 002)
```python
# Old: slot required, must be within ±10 minutes
if slot == "auto":
    resolved_slot = find_nearest_slot(now)
    if resolved_slot is None:
        raise ValueError("No slot within ±10 minutes")
```

### Label Assignment (Migration 002)
```python
# Timestamp-first: intended_slot is optional soft label
if slot is None or slot == "auto":
    intended_slot = find_nearest_slot(now, window_minutes=30)
else:
    intended_slot = slot
```

### Label Assignment (After - Migration 003)
```python
# 5-minute request labels: computed from request_started_at
request_started_at = now_et()  # Before first API call
request_label = request_label_from_dt(request_started_at)
# Example: 2026-10-30 10:32:17 ET → 'rq1030to1034'
```

### RTH Check (Before)
```python
# Old: Outside RTH was an error (except for holiday check)
# Prevented manual testing outside market hours
```

### RTH Check (After)
```python
# New: Outside RTH logs a warning but proceeds
if not is_rth(now):
    logger.warning(
        "Collection outside regular trading hours. "
        "Proceeding for manual/test purposes."
    )
```

### Database Write (Before)
```python
# Old: UPSERT on (session_date, slot) - could only run once per slot
client.table("snapshot_runs").upsert(data, on_conflict="session_date,slot").execute()
```

### Database Write (After)
```python
# New: INSERT always - creates new row every time with request_label
data = {
    "session_date": session_date.isoformat(),
    "request_label": request_label,  # Computed from request_started_at
    ...
}
client.table("snapshot_runs").insert(data).execute()
```

## Request Label Format

The `request_label` is a pure function of `request_started_at`:

```python
def request_label_from_dt(dt: datetime) -> str:
    """
    Generate 5-minute request label from datetime.
    
    Examples:
        2026-10-30 10:30:17 ET → 'rq1030to1034'
        2026-10-30 15:09:47 ET → 'rq1505to1509'
        2026-10-30 14:39:45 ET → 'rq1435to1439'
        2026-10-30 16:10:51 ET → 'rq1610to1614'
    """
    dt_et = dt.astimezone(ET)  # Convert to America/New_York
    floored_minute = (dt_et.minute // 5) * 5
    start_time = dt_et.replace(minute=floored_minute, second=0, microsecond=0)
    end_time = start_time + timedelta(minutes=4)  # Half-open [start, start+5min)
    return f"rq{start_time:%H%M}to{end_time:%H%M}"
```

## Trigger Envelope

The `TriggerEnvelope` model captures metadata about what triggered the collection:

```python
class TriggerEnvelope(BaseModel):
    trigger_source: str | None = None      # 'github_actions', 'vercel_cron', 'manual'
    trigger_id: str | None = None          # GitHub run ID, etc.
    intended_at: datetime | None = None    # Scheduler's aimed time
    symbols: list[str] | None = None       # Symbol override
```

### CLI Flags
```bash
fdproxy collect \
  --trigger-source github_actions \
  --trigger-id $GITHUB_RUN_ID \
  --intended-at 2026-10-30T15:30:00-04:00

# Note: --slot flag is deprecated and ignored
```

### Environment Variables
The CLI also reads from environment variables (lower precedence):
- `FDPROXY_TRIGGER_SOURCE`
- `FDPROXY_TRIGGER_ID`
- `GITHUB_RUN_ID` (GitHub Actions standard variable)

## Future: HTTP Adapter (Vercel Route)

The collector is structured for easy adaptation to HTTP triggers:

```python
# Future: app/api/collect/route.py
from fdproxy.collect_svc import run_collect
from fdproxy.models import TriggerEnvelope

def POST(request):
    trigger = TriggerEnvelope(
        trigger_source="vercel_cron",
        trigger_id=os.getenv("VERCEL_DEPLOYMENT_ID"),
        intended_at=datetime.fromisoformat(request.json["intended_at"]),
    )
    
    result = run_collect(
        slot=None,  # auto
        symbols=None,
        strict=False,
        dry_run=False,
        trigger=trigger,
    )
    
    return {"ok": result.status in ["ok", "partial"], "result": result.dict()}
```

One core collect path (`run_collect`), thin adapters (CLI, HTTP).

## Migration Guide

### For Users

1. **Apply the migration**: Run `supabase/migrations/002_timestamp_first_collection.sql` on your Supabase project
2. **Update code**: If you have custom queries selecting `slot`, change them to `intended_slot`
3. **Test**: Run `fdproxy collect --slot auto --dry-run` to verify behavior
4. **Observe**: CI will no longer fail due to slot timing; check that runs are being recorded with proper timestamps

### For Developers

1. **No more slot gates**: Don't check wall-clock distance in application logic
2. **Always create new rows**: No more upserts on `(session_date, slot)`
3. **Record timestamps**: Set `request_started_at` before first API call, `request_finished_at` after last
4. **Pass trigger metadata**: Build `TriggerEnvelope` from CLI flags or HTTP request
5. **Warn on RTH**: Log warnings for outside-RTH runs but don't fail

## Analysis Implications

### Before (Named Slots)
```sql
-- Old: Query by known slot
SELECT * FROM snapshot_runs 
WHERE session_date = '2026-10-27' AND slot = 't1530';
```

### After (5-Minute Request Labels)
```sql
-- Query by request_label (5-minute bucket)
SELECT * FROM snapshot_runs 
WHERE session_date = '2026-10-27'
  AND request_label = 'rq1530to1534'
ORDER BY request_started_at;

-- Query multiple 5-minute windows around a time
SELECT * FROM snapshot_runs 
WHERE session_date = '2026-10-27'
  AND request_label IN ('rq1525to1529', 'rq1530to1534', 'rq1535to1539')
ORDER BY request_started_at;

-- Query by timestamp window (more flexible)
SELECT * FROM snapshot_runs 
WHERE session_date = '2026-10-27'
  AND request_started_at BETWEEN '2026-10-27 15:25:00-04' AND '2026-10-27 15:35:00-04'
ORDER BY request_started_at;

-- Index on (session_date, request_label) makes label queries efficient
CREATE INDEX idx_snapshot_runs_session_date_request_label 
ON snapshot_runs(session_date, request_label);
```

## Benefits

1. **No lost snapshots**: Irregular scheduler timing doesn't cause failures
2. **Flexible testing**: Manual tests work at any time (with a warning)
3. **Future-proof**: Easy to add Vercel cron or other schedulers
4. **Accurate timing**: `request_started_at` / `request_finished_at` capture actual feed API window
5. **Debuggable**: `trigger_source` / `trigger_id` trace back to the CI run or deployment
6. **Deterministic labels**: `request_label` is a pure function of timestamp (no nearest-slot ambiguity)
7. **Efficient querying**: Index on `(session_date, request_label)` supports fast label-based lookups
8. **Analysis-friendly**: Labels provide consistent 5-minute buckets for grouping and comparison

## Trade-offs

1. **More rows**: Duplicates/near-duplicates are kept (filtered in analysis)
2. **Backward incompatibility**: 
   - Migration 002: Queries selecting `slot` need updating to `intended_slot`
   - Migration 003: Queries selecting `intended_slot` need updating to `request_label`
3. **Label granularity**: 5-minute buckets are finer than old named slots (but more consistent)
