# Timestamp-First Collection Design

## Problem

The original design used `(session_date, slot)` as a unique key and required the wall clock to be within ±10 minutes of a named slot. This caused issues:

1. **Lost snapshots**: GitHub Actions cron wakes late/irregularly, causing the ±10 min gate to reject runs
2. **Failed CI jobs**: When the slot gate raised an error, the entire workflow failed
3. **FK conflicts**: The unique constraint prevented re-running a slot (e.g., after a transient failure)
4. **Rigid scheduling**: Manual tests and alternative schedulers (Vercel cron) couldn't run outside the tight windows

## Solution: Timestamps Are Ground Truth

The new design treats **timestamps as ground truth**:

- Fire on an interval (GitHub Actions cron grid remains the same)
- Always save data (except weekends/holidays)
- Keep duplicates and near-duplicates (no unique constraint on slot)
- Assign time cohorts later in analysis based on actual `request_started_at` / `request_finished_at`

## Schema Changes (Migration 002)

### Removed
- Unique constraint on `(session_date, slot)`

### Renamed
- `slot` → `intended_slot` (nullable): A soft label, not a requirement

### Added
- `request_started_at` (timestamptz): Wall-clock immediately before first feed API request
- `request_finished_at` (timestamptz): Wall-clock after last feed API response
- `trigger_source` (text): e.g., `github_actions`, `vercel_cron`, `manual`, `agent`
- `trigger_id` (text): e.g., GitHub run ID, Vercel deployment ID
- `intended_at` (timestamptz, nullable): Scheduler's aimed time (vs actual start)

### Backfilled
- Existing rows: `request_started_at` ← `started_at`, `request_finished_at` ← `finished_at`

## Behavior Changes

### Slot Assignment (Before)
```python
# Old: slot required, must be within ±10 minutes
if slot == "auto":
    resolved_slot = find_nearest_slot(now)
    if resolved_slot is None:
        raise ValueError("No slot within ±10 minutes")
```

### Slot Assignment (After)
```python
# New: intended_slot is optional soft label
if slot is None or slot == "auto":
    # Try to assign nearest slot within ±30 minutes
    intended_slot = find_nearest_slot(now, window_minutes=30)
    # If None, that's fine - we proceed anyway
else:
    # Use explicit slot as intended label
    intended_slot = slot
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
# New: INSERT always - creates new row every time
client.table("snapshot_runs").insert(data).execute()
```

## Trigger Envelope

A new `TriggerEnvelope` model captures metadata about what triggered the collection:

```python
class TriggerEnvelope(BaseModel):
    trigger_source: str | None = None      # 'github_actions', 'vercel_cron', 'manual'
    trigger_id: str | None = None          # GitHub run ID, etc.
    intended_at: datetime | None = None    # Scheduler's aimed time
    intended_slot: str | None = None       # Soft label override
    symbols: list[str] | None = None       # Symbol override
```

### CLI Flags
```bash
fdproxy collect \
  --slot auto \
  --trigger-source github_actions \
  --trigger-id $GITHUB_RUN_ID \
  --intended-at 2026-10-30T15:30:00-04:00
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

### Before
```sql
-- Old: Query by known slot
SELECT * FROM snapshot_runs 
WHERE session_date = '2026-10-27' AND slot = 't1530';
```

### After
```sql
-- New: Query by timestamp window, filter by source
SELECT * FROM snapshot_runs 
WHERE session_date = '2026-10-27'
  AND request_started_at BETWEEN '2026-10-27 15:25:00-04' AND '2026-10-27 15:35:00-04'
  AND trigger_source = 'github_actions'
ORDER BY request_started_at;

-- Or: Use intended_slot as a soft filter
SELECT * FROM snapshot_runs 
WHERE session_date = '2026-10-27'
  AND intended_slot = 't1530'
ORDER BY request_started_at;

-- Analysis: Assign runs to time cohorts
WITH cohorts AS (
  SELECT 
    *,
    CASE 
      WHEN EXTRACT(MINUTE FROM request_started_at) BETWEEN 25 AND 35 THEN 't1530'
      WHEN EXTRACT(MINUTE FROM request_started_at) BETWEEN 40 AND 50 THEN 't1545'
      -- ... more cohort logic
      ELSE 'uncategorized'
    END AS analysis_cohort
  FROM snapshot_runs
  WHERE session_date = '2026-10-27'
)
SELECT * FROM cohorts ORDER BY request_started_at;
```

## Benefits

1. **No lost snapshots**: Irregular scheduler timing doesn't cause failures
2. **Flexible testing**: Manual tests work at any time (with a warning)
3. **Future-proof**: Easy to add Vercel cron or other schedulers
4. **Accurate timing**: `request_started_at` / `request_finished_at` capture actual feed API window
5. **Debuggable**: `trigger_source` / `trigger_id` trace back to the CI run or deployment
6. **Analysis-friendly**: Time cohorts assigned in analysis, not at collection time

## Trade-offs

1. **More rows**: Duplicates/near-duplicates are kept (filtered in analysis)
2. **Backward incompatibility**: Queries selecting `slot` need updating to `intended_slot`
3. **Slightly more complex queries**: Analysis now filters by timestamp windows instead of exact slot matches
