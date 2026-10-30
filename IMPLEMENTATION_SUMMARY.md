# Timestamp-First Collection Implementation Summary

## Pull Request

**PR #5**: https://github.com/flareware-gh/fdproxy/pull/5  
**Status**: ✅ CI Green (tests, black, ruff passing)

## What Was Implemented

### Phase A — Schema Changes

**Migration file**: `supabase/migrations/002_timestamp_first_collection.sql`

**Key changes:**
- Dropped unique constraint on `(session_date, slot)`
- Renamed `slot` → `intended_slot` (nullable)
- Added `request_started_at`, `request_finished_at` (wall-clock API timing)
- Added `trigger_source`, `trigger_id`, `intended_at` (scheduler metadata)
- Backfilled `request_*` from existing `started_at`/`finished_at`
- Added indexes on `request_started_at` and `trigger_source`

### Phase B — Collector Changes

**Core changes:**
- Removed slot distance gate (never errors on timing)
- Slot becomes optional soft label (±30 min window, else `null`)
- Introduced `TriggerEnvelope` model (source, id, intended_at, intended_slot, symbols)
- Records `request_started_at` before first API call, `request_finished_at` after last
- Outside RTH logs warning but proceeds (manual tests work)
- Every invocation creates new row (no upsert on slot)
- Exit non-zero only on real errors (feed/DB failure)

**CLI additions:**
- `--trigger-source` flag (e.g., `github_actions`, `vercel_cron`, `manual`, `agent`)
- `--trigger-id` flag (e.g., GitHub run ID)
- `--intended-at` flag (ISO 8601 timestamp)
- Reads `FDPROXY_TRIGGER_SOURCE`, `FDPROXY_TRIGGER_ID`, `GITHUB_RUN_ID` from environment

**JSON output includes:**
```json
{
  "run_id": "uuid",
  "intended_slot": "t1530",
  "request_started_at": "2026-10-30T15:31:22.123456-04:00",
  "request_finished_at": "2026-10-30T15:32:18.654321-04:00",
  "trigger_source": "github_actions",
  "trigger_id": "1234567890",
  "intended_at": null
}
```

### Phase C — GitHub Actions

**Workflow changes** (`.github/workflows/collect.yml`):
- Passes `--trigger-source github_actions`
- Passes trigger ID via `$GITHUB_RUN_ID` environment variable
- Keeps existing dense cron grid (no schedule changes)
- Job fails only when `collect` itself errors (not on slot timing)

## Migration Instructions

### 1. Apply Supabase Migration

```bash
# Connect to your Supabase project
cd supabase
supabase db push

# Or apply manually in the SQL Editor:
# Copy/paste contents of migrations/002_timestamp_first_collection.sql
```

**⚠️ Breaking Change**: This migration renames `slot` → `intended_slot`. Any custom queries selecting `slot` will break. Update them first.

### 2. Test Manual Collection

After migration, test with a manual workflow run:

```bash
# Via GitHub CLI
gh workflow run collect.yml \
  --field slot=auto \
  --field symbols=SPY,QQQ

# Then check the run
gh run list --workflow=collect.yml --limit 1
gh run view <run-id> --log
```

Or use the GitHub UI:
1. Go to Actions → Collect 0DTE Data → Run workflow
2. Set slot: `auto`
3. Set symbols: (leave empty for all, or `SPY,QQQ` for test)
4. Run workflow

**Expected behavior:**
- Creates new `snapshot_runs` row with timestamps
- `trigger_source` = `github_actions`
- `trigger_id` = GitHub run ID
- `intended_slot` assigned based on wall clock (or `null` if >30 min from any slot)
- Exit code 0 unless there's a real error

### 3. Verify Results

Query Supabase to confirm:

```sql
-- Check recent runs with new fields
SELECT 
    id,
    session_date,
    intended_slot,
    request_started_at,
    request_finished_at,
    trigger_source,
    trigger_id,
    status
FROM snapshot_runs
ORDER BY request_started_at DESC
LIMIT 10;

-- Verify no more unique constraint conflicts
-- (This should succeed multiple times)
-- Just re-run the workflow and check for new rows
```

## Documentation

All documentation has been updated:

- ✅ `SCHEMA.md` — Updated with new columns and removed unique constraint note
- ✅ `PLAN.md` — Updated snapshot schedule section with timestamp-first approach
- ✅ `README.md` — Updated CLI usage examples
- ✅ `docs/timestamp-first-collection.md` — Complete design rationale and migration guide
- ✅ `docs/cli.md` — Complete CLI reference with examples

## Testing

- ✅ All pytest tests passing (13/13)
- ✅ Black formatting applied
- ✅ Ruff linting green
- ✅ CI passing on PR

## Manual Test Example

```bash
# From your local machine with .env configured:

# Test with auto slot assignment
fdproxy collect --slot auto --json

# Test with explicit intended slot
fdproxy collect --slot t1530 --trigger-source manual --json

# Test specific symbols
fdproxy collect --symbols SPY,QQQ --dry-run --json

# Test outside market hours (should warn but proceed)
fdproxy collect --slot auto --json
```

## Future Extensions

The code is structured for easy HTTP adapter addition (Vercel route):

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
        slot=None,
        symbols=None,
        strict=False,
        dry_run=False,
        trigger=trigger,
    )
    
    return {"ok": result.status in ["ok", "partial"], "result": result.dict()}
```

One core collect path (`run_collect`), thin adapters (CLI, HTTP).

## Key Benefits

1. **No lost snapshots**: GitHub Actions cron irregularity no longer causes failures
2. **Flexible testing**: Manual tests work at any time (with a warning)
3. **Future-proof**: Easy to add Vercel cron or other schedulers
4. **Accurate timing**: `request_started_at`/`request_finished_at` capture actual API window
5. **Debuggable**: `trigger_source`/`trigger_id` trace back to CI run or deployment
6. **Analysis-friendly**: Time cohorts assigned in analysis, not at collection time

## Files Changed

```
modified:   .github/workflows/collect.yml
modified:   PLAN.md
modified:   README.md
modified:   SCHEMA.md
new:        docs/cli.md
new:        docs/timestamp-first-collection.md
modified:   src/fdproxy/cli.py
modified:   src/fdproxy/collect_svc.py
modified:   src/fdproxy/db.py
modified:   src/fdproxy/models.py
modified:   src/fdproxy/timeutil.py
new:        supabase/migrations/002_timestamp_first_collection.sql
modified:   tests/test_timeutil.py
```

## Next Steps

1. ✅ **Done**: PR created and CI green
2. ⏳ **Owner**: Apply migration to Supabase
3. ⏳ **Owner**: Run manual test to verify behavior
4. ⏳ **Owner**: Merge PR when ready
5. ⏳ **Owner**: Monitor first automated collection runs

---

**Contact**: Agent-implemented, ready for human review and deployment.
