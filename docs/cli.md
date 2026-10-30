# FDProxy CLI Reference

Agent-friendly CLI with `--json` output support for all commands.

## Global Options

Available on all commands:

```bash
--env-file PATH    # Path to .env file (default: .env)
-v, --verbose      # Verbose output
```

## Commands

### `fdproxy doctor`

Validate environment and connectivity.

**Usage:**
```bash
fdproxy doctor [--json]
```

**Checks:**
- Python version
- Package dependencies
- Supabase connectivity (ping)
- Yahoo Finance access

**Exit codes:**
- `0`: All checks passed
- `1`: One or more checks failed

**Example output (JSON):**
```json
{
  "ok": true,
  "command": "doctor",
  "collector_version": "0.1.0",
  "data": {
    "checks": [
      {"name": "python_version", "ok": true, "detail": "3.11.5"},
      {"name": "supabase", "ok": true, "detail": "Connected"},
      {"name": "yahoo_finance", "ok": true, "detail": "Accessible"}
    ]
  }
}
```

---

### `fdproxy collect`

Collect underlying quotes and 0DTE option chains.

**Timestamp-first logic:** Always saves data (except holidays) regardless of wall-clock distance from named slots. Slot names are soft labels assigned when near a planned time (±30 min).

**Usage:**
```bash
fdproxy collect [OPTIONS]
```

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--slot` | str | `None` | Slot name (`m0935`, `t1530`, etc.) or `auto` (soft label) |
| `--symbols` | str | `None` | Comma-separated symbols (default: all) |
| `--strict` | bool | `False` | Exit 1 if any symbol fails |
| `--dry-run` | bool | `False` | Fetch and compute without DB writes |
| `--json` | bool | `False` | JSON output |
| `--trigger-source` | str | `None` | Trigger source (`github_actions`, `vercel_cron`, `manual`, `agent`) |
| `--trigger-id` | str | `None` | Trigger ID (e.g., GitHub run ID) |
| `--intended-at` | str | `None` | Intended time (ISO 8601 timestamp) |

**Environment variables:**
- `FDPROXY_TRIGGER_SOURCE`: Default trigger source
- `FDPROXY_TRIGGER_ID`: Default trigger ID
- `GITHUB_RUN_ID`: Auto-detected in GitHub Actions

**Exit codes:**
- `0`: Collection succeeded (`ok`, `partial`, or `skipped_holiday`)
- `1`: Collection failed (feed or DB error)

**Examples:**

```bash
# Auto slot assignment (nearest within ±30 min, or null)
fdproxy collect --slot auto

# Explicit intended slot label
fdproxy collect --slot t1530

# Specific symbols
fdproxy collect --symbols SPY,QQQ

# Dry run (no DB writes)
fdproxy collect --dry-run --json

# Strict mode (fail on any symbol error)
fdproxy collect --slot t1530 --strict

# From GitHub Actions (with trigger metadata)
fdproxy collect \
  --slot auto \
  --trigger-source github_actions \
  --trigger-id $GITHUB_RUN_ID \
  --json

# Manual collection with intended time
fdproxy collect \
  --slot t1530 \
  --trigger-source manual \
  --intended-at 2026-10-30T15:30:00-04:00
```

**Example output (JSON):**
```json
{
  "ok": true,
  "command": "collect",
  "collector_version": "0.1.0",
  "data": {
    "session_date": "2026-10-30",
    "intended_slot": "t1530",
    "status": "ok",
    "symbols_attempted": ["SPY", "QQQ", "SMH", "XLF", "XLE", "HYG"],
    "symbols_success": ["SPY", "QQQ", "SMH", "XLF", "XLE", "HYG"],
    "underlying_count": 6,
    "option_count": 342,
    "bucket_picks_count": 60,
    "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "request_started_at": "2026-10-30T15:31:22.123456-04:00",
    "request_finished_at": "2026-10-30T15:32:18.654321-04:00",
    "trigger_source": "github_actions",
    "trigger_id": "1234567890",
    "intended_at": null
  }
}
```

**Behavior:**

1. **Slot assignment:**
   - `--slot auto` or omitted: Assign nearest planned slot if within ±30 min, else `null`
   - `--slot <name>`: Use `<name>` as `intended_slot` (soft label, never an error)

2. **Holiday/weekend:**
   - Creates run with `status: "skipped_holiday"`, exits 0

3. **Outside RTH:**
   - Logs warning but proceeds (manual tests must work)

4. **Symbol failures:**
   - Normal mode: Log failure, continue, set `status: "partial"`, exit 0
   - Strict mode: Stop immediately, set `status: "failed"`, exit 1

5. **Timestamps:**
   - `request_started_at`: Recorded immediately before first Yahoo API request
   - `request_finished_at`: Recorded after last Yahoo API response

6. **Database:**
   - Always creates new `snapshot_runs` row (no upsert)
   - `run_id` is UUID, returned in output

---

### `fdproxy status`

Show collection status and health (not yet implemented).

**Usage:**
```bash
fdproxy status [--days N] [--json]
```

**Options:**
- `--days`: Number of days to query (default: 5)

---

### `fdproxy simulate`

Simulate option paths from stored snapshots (not yet implemented).

**Usage:**
```bash
fdproxy simulate --from DATE --to DATE [OPTIONS]
```

**Options:**
- `--from`: Start date (YYYY-MM-DD)
- `--to`: End date (YYYY-MM-DD)
- `--entry-slot`: Entry slot (default: `t1530`)
- `--symbols`: Comma-separated symbols
- `--write-outcomes`: Write to `contract_outcomes` table
- `--json`: JSON output

---

### `fdproxy study`

Run offline research studies (not yet implemented).

**Usage:**
```bash
fdproxy study ANALYSIS [--json]
```

**Arguments:**
- `ANALYSIS`: Analysis type (`feasibility`, `convexity`)

---

## JSON Output Format

All commands support `--json` flag for machine-readable output.

**Envelope structure:**
```json
{
  "ok": true,
  "command": "collect",
  "collector_version": "0.1.0",
  "data": { ... },
  "errors": []
}
```

**Fields:**
- `ok` (bool): Overall success
- `command` (str): Command name
- `collector_version` (str): FDProxy version
- `data` (dict): Command-specific result data
- `errors` (list[str]): Error messages (if any)

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Failure (command-specific) |

**Note:** `collect` returns 0 for `ok`, `partial`, and `skipped_holiday` statuses. Only real errors (feed/DB failures) return 1.

---

## Environment Variables

### Required

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

### Optional

```bash
FDPROXY_TRIGGER_SOURCE=manual
FDPROXY_TRIGGER_ID=custom-id
GITHUB_RUN_ID=1234567890  # Auto-detected in GitHub Actions
```

---

## Agent Integration

The CLI is designed for agent-friendly automation:

1. **Idempotent operations**: Safe to retry (no upserts, always creates new runs)
2. **JSON output**: Parse with `jq` or JSON libraries
3. **Clear exit codes**: 0 = success, 1 = failure
4. **Metadata tracking**: `trigger_source`, `trigger_id` for traceability
5. **Timestamps**: `request_started_at`, `request_finished_at` for accurate timing

**Example agent workflow:**

```bash
#!/bin/bash
set -e

# Run collection
OUTPUT=$(fdproxy collect --slot auto --trigger-source agent --json)

# Parse result
RUN_ID=$(echo "$OUTPUT" | jq -r '.data.run_id')
STATUS=$(echo "$OUTPUT" | jq -r '.data.status')

echo "Collection completed: run_id=$RUN_ID, status=$STATUS"

# Query results
# ... (use run_id to fetch data from Supabase)
```

---

## Troubleshooting

### "No slot within ±30 minutes"

**Before (old behavior):** This was an error that stopped collection.

**After (new behavior):** Collection proceeds with `intended_slot: null`. This is normal and expected when running outside the planned schedule.

### "Collection outside regular trading hours"

This is a warning, not an error. Collection proceeds for manual testing purposes. Yahoo Finance data may be delayed or stale outside RTH.

### "Some checks failed" (doctor)

Run `fdproxy doctor` (without `--json`) to see detailed check results. Common issues:
- Supabase credentials not set or invalid
- Network connectivity issues
- Python dependencies missing

### "Symbol XYZ failed"

In normal mode (default), failures are logged but don't stop collection. Check the logs for details. In `--strict` mode, the first failure stops immediately with exit code 1.
