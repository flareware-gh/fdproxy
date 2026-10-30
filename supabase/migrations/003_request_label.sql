-- FDProxy 5-minute request label migration
-- Replace named slot labeling with timestamp-based 5-minute buckets

-- Rename column: intended_slot → request_label
ALTER TABLE snapshot_runs RENAME COLUMN intended_slot TO request_label;

-- Backfill request_label for existing rows using 5-minute ET buckets
-- Formula: floor to 5-min bucket start, then add 4 minutes for end
-- Overwrites old named slots (m1030, t1530, close) with new format (rqHHmmtoHHmm)
UPDATE snapshot_runs
SET request_label = sub.label
FROM (
  SELECT id,
    'rq' || to_char(bucket_start, 'HH24MI') || 'to' || to_char(bucket_start + interval '4 minutes', 'HH24MI') AS label
  FROM (
    SELECT id,
      date_trunc('hour', ts) + make_interval(mins => (EXTRACT(MINUTE FROM ts)::int / 5) * 5) AS bucket_start
    FROM (
      SELECT id,
        (COALESCE(request_started_at, started_at) AT TIME ZONE 'America/New_York') AS ts
      FROM snapshot_runs
      WHERE COALESCE(request_started_at, started_at) IS NOT NULL
    ) s
  ) b
) sub
WHERE snapshot_runs.id = sub.id;

-- Create index on (session_date, request_label) for efficient querying
-- No UNIQUE constraint - duplicates allowed for timestamp-first collection
CREATE INDEX IF NOT EXISTS idx_snapshot_runs_session_date_request_label 
ON snapshot_runs(session_date, request_label);

-- Note: request_label remains nullable (TEXT, NULL)
-- Rows without timestamps will have NULL labels (edge case for incomplete runs)
