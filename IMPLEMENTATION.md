# FDProxy — CLI implementation plan (detailed)

Companion to `PLAN.md`. This is how we build each CLI command. **Not code yet** — implementation blueprint for review / next coding pass.

## 0. Stack choices

| Layer | Choice | Why |
|-------|--------|-----|
| Primary language | **Python 3.11+** | `yfinance`, pandas, studies, agents all call one binary |
| CLI framework | **Typer** (+ rich optional) | Subcommands, `--help`, exit codes |
| Packaging | `pyproject.toml` + `fdproxy` console script | `pip install -e .` then `fdproxy …` |
| HTTP / DB | `httpx` + `supabase-py` (or PostgREST via service role) | Matches connected Supabase |
| Config | env: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, optional `FDPROXY_*` | No secrets in git |
| Tests | `pytest` + recorded Yahoo fixtures | Offline CI for parse/bucket logic |
| Node/TS | **Deferred** | Only if we later want a web dashboard (`web/`); CLI stays Python |

Optional later: thin `bin/fdproxy` shell wrapper; HTML status page is Phase 4+, not blocking collect.

## 1. Package layout

```
fdproxy/
  pyproject.toml
  README.md
  PLAN.md
  SCHEMA.md
  IMPLEMENTATION.md          # this file
  supabase/migrations/001_init.sql
  src/fdproxy/
    __init__.py
    __main__.py              # python -m fdproxy
    cli.py                   # Typer app: collect, status, simulate, study, doctor
    config.py                # env load, universe, slots, delta buckets
    timeutil.py              # ET session date, slot schedule, holiday skip
    feeds/
      base.py                # Protocol: fetch_underlying, fetch_chain
      yahoo.py               # yfinance implementation (only feed)
    greeks.py                # BS delta/IV when Yahoo omits delta
    buckets.py               # map chain → delta_bucket picks 0.025…0.30
    db.py                    # Supabase upserts / queries
    models.py                # pydantic/dataclasses for rows + JSON envelopes
    collect_svc.py           # orchestration for one slot
    simulate_svc.py          # path / multiple logic
    study/
      feasibility.py
      convexity.py
  tests/
    fixtures/yahoo_spy_chain.json
    test_buckets.py
    test_slots.py
    test_collect_dry_run.py
  .github/workflows/
    collect.yml
    ci.yml
  .env.example
```

## 2. Shared conventions (every command)

### 2.1 Flags (global)

| Flag | Default | Meaning |
|------|---------|---------|
| `--json` | off | Machine-readable stdout (single JSON object); humans get concise text |
| `--env-file` | `.env` | Optional dotenv path |
| `--dry-run` | off | Fetch + compute, **no** Supabase writes |
| `-v` / `--verbose` | off | Logs to stderr (never pollute `--json` stdout) |

### 2.2 Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success (including `skipped_holiday`) |
| 1 | Operational failure (feed down, partial required symbols failed when `--strict`) |
| 2 | Bad args / config |
| 3 | Supabase error |

### 2.3 JSON envelope

```json
{
  "ok": true,
  "command": "collect",
  "collector_version": "0.1.0",
  "data": { },
  "errors": []
}
```

Agents parse `ok` + `errors`; ignore human text mode.

### 2.4 Universe & buckets (config constants)

```text
SYMBOLS = SPY QQQ SMH XLF XLE HYG
DELTA_BUCKETS = 0.025 0.05 0.10 0.20 0.30
FEED = yahoo
SLOTS = m0935 m1030 m1200 m1400 m1445 t1500 t1515 t1530 t1545 t1550 t1555 close
```

## 3. `fdproxy doctor`

**Purpose:** Validate environment before any collect.

**Steps**
1. Check Python version, `yfinance` import.
2. Check `SUPABASE_URL` + service role present (don’t print secrets).
3. `SELECT 1` / list tables via Supabase; report missing migrations.
4. One Yahoo smoke: `Ticker("SPY").fast_info` or last price + whether today appears in `options`.
5. Print ET “now”, next slot, whether RTH.

**Output:** checklist; `--json` with `checks: [{name, ok, detail}]`.

**Done when:** green doctor on a configured machine without writing data.

---

## 4. `fdproxy collect`

**Purpose:** One snapshot run for one slot (or auto-picked nearest slot).

### 4.1 CLI

```bash
fdproxy collect [--slot SLOT|auto] [--symbols SPY,QQQ] [--strict]
                [--json] [--dry-run]
```

- `--slot auto`: choose planned slot closest to now ET among today’s schedule (or error if outside collection window).
- Default symbols = full universe.
- `--strict`: exit 1 if any symbol’s options fetch fails (default: mark `partial`, continue).

### 4.2 Algorithm

1. Resolve `session_date` (ET), `slot`, `scheduled_at`.
2. If weekend / NYSE holiday → insert `snapshot_runs` status `skipped_holiday`, exit 0.
3. Insert/upsert `snapshot_runs` as `started` → fetch loop:
   - For each symbol:
     - `YahooFeed.underlying(symbol)`
     - `YahooFeed.chain_0dte(symbol)` — expiry == session_date; if no 0DTE, store underlying only + note in `meta`.
     - Compute mid; vendor delta if present else `greeks.delta_from_mid(...)`.
     - `buckets.assign(...)` → set `delta_bucket` / `is_bucket_pick` for nearest abs-delta per right.
   - Upsert `underlying_snapshots`, `option_snapshots` (idempotent unique keys).
4. Finalize run `ok` / `partial` / `failed`; print summary counts.

### 4.3 Yahoo feed details (`feeds/yahoo.py`)

| Method | Behavior |
|--------|----------|
| `underlying` | last/bid/ask if available; day O/H/L; volume; `quoted_at=now UTC`; `delay_seconds` default **900** (document as assumption unless Yahoo exposes delay) |
| `chain_0dte` | `Ticker.options` → pick expiry matching ET session date; `option_chain`; normalize columns to our schema; keep full near strip (filter absurd strikes optionally \|Δ\| < 0.5 or ±5%) |

**Resilience:** per-symbol try/except; rate-limit sleep (e.g. 0.2–0.5s) between symbols; retries 2× on transient HTTP.

### 4.4 Greeks (`greeks.py`)

- Inputs: S, K, T (year fraction to 16:00 ET), r≈0, q≈0, mid price.
- Solve IV from mid (bisection); delta from BS.
- If mid ≤ 0 or T≈0: delta ≈ 1/0/−1 by intrinsic; mark `delta_source=intrinsic`.
- Store `delta_source`: `yahoo` \| `bs` \| `intrinsic`.

### 4.5 Bucket assignment (`buckets.py`)

For each right C/P independently: among OTM contracts (calls K>S, puts K<S), pick strike minimizing `|abs(delta) - bucket|` for each target bucket; ties → closer to ATM or tighter spread. Set `is_bucket_pick=true` on those rows; others keep `delta_bucket=null` or filled for analysis but `is_bucket_pick=false`.

### 4.6 DB writes (`db.py`)

- Use service role; upsert on unique constraints from `SCHEMA.md`.
- Batch option inserts (chunks of 500).
- Never log full key.

### 4.7 Done when

- Dry-run prints counts without DB.
- Live run creates one `snapshot_runs` + underlyings + options for SPY on a session with 0DTE.
- Re-run same slot upserts, no duplicate PKs.

---

## 5. `fdproxy status`

**Purpose:** Health view for agents / humans.

```bash
fdproxy status [--days 5] [--json]
```

**Queries**
- Last N `snapshot_runs` (date, slot, status, feed, error).
- Missing slots today vs schedule.
- Row counts: options/underlyings last 24h.
- Optional: fraction of symbols with 0DTE present.

**Done when:** matches Supabase UI for a known run.

---

## 6. `fdproxy simulate`

**Purpose:** From stored snapshots, build option mid paths and multiples (mid-to-mid and ask→bid) for bucket picks — feeds Model C/D research.

```bash
fdproxy simulate --from YYYY-MM-DD --to YYYY-MM-DD
                 [--entry-slot t1530] [--symbols ...]
                 [--write-outcomes] [--json]
```

### 6.1 Algorithm

1. Load option rows for entry slot + later slots same day (including `close`).
2. Key by `(symbol, expiry, right, strike)`.
3. For each `is_bucket_pick` at entry:
   - `entry_mid`, `entry_ask`
   - Over later quotes: `max_mid`, `end_mid`
   - `max_multiple_mid = max_mid / entry_mid` (guard entry_mid > 0)
   - `multiple_ask_to_bid = max_bid_later / entry_ask` (conservative; null if missing)
   - Flags `hit_3x`, `hit_5x`, `hit_10x` on mid multiple
4. Print summary histograms by symbol × delta_bucket; optionally upsert `contract_outcomes`.

### 6.2 Done when

- On fixture multi-slot day, multiples match hand calculation.
- Separates mid vs ask→bid clearly in JSON.

---

## 7. `fdproxy study feasibility`

**Purpose:** Phase 1 offline study (free bars — Yahoo history), not live options.

```bash
fdproxy study feasibility [--symbols ...] [--start ...] [--end ...]
                          [--out studies/feasibility/]
                          [--json]
```

**Work**
1. Download intraday or 1m/5m if Yahoo allows; else document fallback (e.g. daily only → weaker study).
2. Compute last-30m / 15m / 60m returns vs thresholds in PLAN.
3. Condition on event calendar CSV (static file we maintain).
4. Write Parquet/CSV + `summary.json` + short `REPORT.md` stub.

**Honesty:** if only daily bars available, say so and produce a limited report rather than fake intraday.

---

## 8. `fdproxy study convexity`

**Purpose:** Phase 2 toy map from feasibility \(F(r)\) + BS/intrinsic toy options at delta buckets.

```bash
fdproxy study convexity --feasibility studies/feasibility/summary.json
                        [--out studies/convexity/] [--json]
```

Outputs heatmaps/tables: P(multiple ≥ 3/5/10) under empirical moves; spread stress.

---

## 9. GitHub Actions

### `collect.yml`

- Per-slot cron expressions covering each slot (UTC converted from ET; note DST — these are EDT times, will need updating for EST).
- **Implemented design:** separate cron entries for each slot → `fdproxy collect --slot auto --json` at each target time; auto finds nearest slot within ±10 minutes.
- Secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.
- Setup: checkout, Python, `pip install -e .`, run collect, upload logs on failure.

### `ci.yml`

- pytest on PR; no live Yahoo required (fixtures).

---

## 10. Supabase migration order

1. Apply `001_init.sql` matching `SCHEMA.md` (tables + uniques + indexes).
2. Seed `instruments` six rows.
3. RLS: deny anon write; service role used by CLI only.
4. Verify with `fdproxy doctor`.

---

## 11. Build sequence (coding order)

| Step | Deliverable | Est. |
|------|-------------|------|
| A | `pyproject`, config, timeutil, empty Typer CLI | small |
| B | Migration + `db.py` + doctor | small |
| C | Yahoo feed + greeks + buckets + unit tests | medium |
| D | `collect` dry-run then live | medium |
| E | Actions auto-collect | small |
| F | `status` | small |
| G | `simulate` + outcomes table | medium |
| H | `study feasibility` / `convexity` | medium |

Do **not** block A–E on studies; start gathering as soon as collect works.

## 12. Agent usage examples (target UX)

```bash
fdproxy doctor --json
fdproxy collect --slot t1530 --json
fdproxy collect --slot auto --json
fdproxy status --days 3 --json
fdproxy simulate --from 2026-10-27 --to 2026-11-27 --entry-slot t1530 --write-outcomes --json
```

## 13. Open risks (implementation)

1. Yahoo may omit true 0DTE or return empty chains for SMH/XLF/XLE/HYG — handle as `partial`.
2. Yahoo delta column quality — always recompute BS delta for bucket picks.
3. Actions minute skew — `--slot auto` + unique `(session_date, slot)`.
4. Rate limits — backoff; consider serializing symbols.

## 14. After this plan is approved

Implement steps A→E first (collect live), then F–H. Same review style: PR for scaffolding, then PRs per command group.
