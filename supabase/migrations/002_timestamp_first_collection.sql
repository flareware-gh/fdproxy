-- FDProxy timestamp-first collection schema changes
-- Phase A: Remove slot uniqueness constraint, add timestamp and trigger tracking

-- Drop the unique constraint on (session_date, slot)
-- This allows multiple runs per slot, treating timestamps as ground truth
ALTER TABLE snapshot_runs DROP CONSTRAINT IF EXISTS snapshot_runs_session_date_slot_key;

-- Make slot nullable (soft label, not a gate)
-- Rename to intended_slot to clarify it's a soft assignment, not a requirement
ALTER TABLE snapshot_runs RENAME COLUMN slot TO intended_slot;
ALTER TABLE snapshot_runs ALTER COLUMN intended_slot DROP NOT NULL;

-- Add new timestamp columns for request tracking
-- request_started_at: wall-clock time immediately before first Yahoo API request
-- request_finished_at: wall-clock time after last Yahoo API response
ALTER TABLE snapshot_runs ADD COLUMN request_started_at TIMESTAMPTZ;
ALTER TABLE snapshot_runs ADD COLUMN request_finished_at TIMESTAMPTZ;

-- Add trigger source tracking
-- trigger_source: 'github_actions', 'vercel_cron', 'manual', 'agent', etc.
-- trigger_id: e.g., GitHub run ID, Vercel deployment ID
ALTER TABLE snapshot_runs ADD COLUMN trigger_source TEXT;
ALTER TABLE snapshot_runs ADD COLUMN trigger_id TEXT;

-- Add intended_at for scheduler's aimed time
-- This is when the scheduler wanted to run, vs when it actually started
ALTER TABLE snapshot_runs ADD COLUMN intended_at TIMESTAMPTZ;

-- Backfill request_* from existing started_at/finished_at where sensible
-- Existing rows have started_at/finished_at which approximate request timing
UPDATE snapshot_runs 
SET 
    request_started_at = started_at,
    request_finished_at = finished_at
WHERE request_started_at IS NULL 
  AND started_at IS NOT NULL;

-- Add index on request_started_at for time-based queries
CREATE INDEX idx_snapshot_runs_request_started_at ON snapshot_runs(request_started_at);

-- Add index on trigger_source for filtering by source
CREATE INDEX idx_snapshot_runs_trigger_source ON snapshot_runs(trigger_source);

-- Note: RLS policies remain unchanged (service role writer)

-- Backward compatibility notes:
-- 1. Column renamed: slot → intended_slot (nullable). Old queries selecting "slot" will fail after migration.
--    Update application code to use "intended_slot" before applying this migration.
-- 2. Unique constraint removed: Multiple runs can now exist for the same (session_date, intended_slot).
--    Application no longer upserts; db.create_snapshot_run() now uses INSERT instead of UPSERT.
-- 3. New columns (request_started_at, request_finished_at, trigger_source, trigger_id, intended_at)
--    are nullable and backfilled where possible. Old rows will have NULL for trigger_* fields.
