-- FDProxy 5-minute request label migration
-- Replace named slot labeling with timestamp-based 5-minute buckets

-- Rename column: intended_slot → request_label
ALTER TABLE snapshot_runs RENAME COLUMN intended_slot TO request_label;

-- Backfill request_label for existing rows using 5-minute ET buckets
-- Formula: floor(minute / 5) * 5, format as rqHHmmtoHHmm
UPDATE snapshot_runs
SET request_label = 
    'rq' || 
    TO_CHAR(
        (COALESCE(request_started_at, started_at) AT TIME ZONE 'America/New_York'),
        'HH24'
    ) || 
    LPAD(
        ((EXTRACT(MINUTE FROM (COALESCE(request_started_at, started_at) AT TIME ZONE 'America/New_York'))::integer / 5) * 5)::text,
        2,
        '0'
    ) ||
    'to' ||
    TO_CHAR(
        (COALESCE(request_started_at, started_at) AT TIME ZONE 'America/New_York') + INTERVAL '4 minutes',
        'HH24'
    ) || 
    LPAD(
        ((EXTRACT(MINUTE FROM ((COALESCE(request_started_at, started_at) AT TIME ZONE 'America/New_York') + INTERVAL '4 minutes'))::integer / 5) * 5)::text,
        2,
        '0'
    )
WHERE request_label IS NULL 
  AND (request_started_at IS NOT NULL OR started_at IS NOT NULL);

-- Create index on (session_date, request_label) for efficient querying
-- No UNIQUE constraint - duplicates allowed for timestamp-first collection
CREATE INDEX IF NOT EXISTS idx_snapshot_runs_session_date_request_label 
ON snapshot_runs(session_date, request_label);

-- Note: request_label remains nullable (TEXT, NULL)
-- Rows without timestamps will have NULL labels (edge case for incomplete runs)
