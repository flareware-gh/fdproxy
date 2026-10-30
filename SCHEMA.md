# FDProxy — Supabase schema (draft)

Project: `FDProxy` / `lwfpttiwijynwbjekaxo`  
Business timezone: `America/New_York`. Store `timestamptz` in UTC.

**Note:** The column `right` is a Postgres reserved keyword and is quoted as `"right"` in SQL DDL. PostgREST and client libraries reference it as `right` (unquoted) in JSON payloads.

## Tables

### `instruments`
| Column | Type | Notes |
|--------|------|--------|
| symbol | text PK | SPY, QQQ, SMH, XLF, XLE, HYG |
| name | text | |
| collect_options | boolean | true |
| collect_underlying | boolean | true |
| active | boolean | |
| notes | text | |

### `snapshot_runs`
| Column | Type | Notes |
|--------|------|--------|
| id | uuid PK | |
| session_date | date | ET calendar date |
| request_label | text (nullable) | 5-min bucket label (`rq1030to1034`, `rq1505to1509`); derived from `request_started_at` |
| scheduled_at | timestamptz | when the scheduler planned to run |
| started_at | timestamptz | collector start time |
| finished_at | timestamptz | collector finish time |
| request_started_at | timestamptz | wall-clock immediately before first feed API request |
| request_finished_at | timestamptz | wall-clock after last feed API response |
| trigger_source | text | `github_actions`, `vercel_cron`, `manual`, `agent` |
| trigger_id | text | e.g., GitHub run ID, Vercel deployment ID |
| intended_at | timestamptz (nullable) | scheduler's aimed time (vs actual start) |
| status | text | `ok` \| `partial` \| `failed` \| `skipped_holiday` |
| collector_version | text | |
| feed_name | text | e.g. `yahoo` |
| error | text | |
| meta | jsonb | |

**No unique constraint** (timestamps are ground truth; duplicates/near-duplicates allowed). `request_label` is computed from `request_started_at` floored to 5-minute buckets in ET timezone. Index on `(session_date, request_label)` for efficient querying.

### `underlying_snapshots`
| Column | Type | Notes |
|--------|------|--------|
| id | bigserial PK | |
| run_id | uuid FK | |
| symbol | text | |
| quoted_at | timestamptz | |
| last | numeric | |
| bid | numeric | |
| ask | numeric | |
| mid | numeric | |
| volume | numeric | |
| day_open | numeric | |
| day_high | numeric | |
| day_low | numeric | |
| delay_seconds | int | |
| raw | jsonb | |

Unique: `(run_id, symbol)`.

### `option_snapshots`
Full strip (or near strip) each run; delta buckets are derived or tagged.

| Column | Type | Notes |
|--------|------|--------|
| id | bigserial PK | |
| run_id | uuid FK | |
| symbol | text | |
| expiry | date | 0DTE ⇒ session_date |
| dte | int | |
| right | text | `C` \| `P` (SQL: `"right"` quoted) |
| strike | numeric | |
| bid | numeric | |
| ask | numeric | |
| mid | numeric | |
| last | numeric | |
| volume | numeric | |
| open_interest | numeric | |
| delta | numeric | vendor or computed |
| gamma | numeric | optional |
| iv | numeric | optional |
| delta_bucket | numeric | nearest of 0.025,0.05,0.10,0.20,0.30 or null if not selected |
| is_bucket_pick | boolean | true if chosen as bucket representative |
| quoted_at | timestamptz | |
| delay_seconds | int | |
| raw | jsonb | |

Unique: `(run_id, symbol, expiry, "right", strike)`.

### `session_labels`
| Column | Type | Notes |
|--------|------|--------|
| session_date | date | |
| symbol | text | |
| r_from_slot_bp | jsonb | e.g. `{"t1530": 42.1, ...}` close vs slot |
| rv_metrics | jsonb | |
| is_event_day | boolean | |
| event_tags | text[] | |
| meta | jsonb | |

Unique: `(session_date, symbol)`.

### `contract_outcomes` (Phase 3/4)
Path stats for bucket picks (and optionally all strikes).

| Column | Type | Notes |
|--------|------|--------|
| session_date | date | |
| symbol | text | |
| right | text | `C` \| `P` (SQL: `"right"` quoted) |
| strike | numeric | |
| entry_slot | text NOT NULL | e.g. `t1530` (required for PK) |
| entry_mid | numeric | |
| entry_ask | numeric | |
| max_mid | numeric | through close |
| end_mid | numeric | |
| max_multiple_mid | numeric | max_mid / entry_mid |
| multiple_ask_to_bid | numeric | conservative |
| hit_3x | boolean | |
| hit_5x | boolean | |
| hit_10x | boolean | |
| delta_bucket | numeric | |
| meta | jsonb | |

## RLS (v1)
Service-role writer for collector; no public anon writes.

## Volume
Denser grid (~12 slots) × 6 symbols × ~50–150 option rows ≈ on the order of **5k–15k option rows/day** — still fine for months on free-tier Postgres.
