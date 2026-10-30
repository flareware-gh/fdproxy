# FDProxy

**Research infrastructure for late-day 0DTE ETF options.**

FDProxy investigates whether buying same-day-expiry (0DTE) out-of-the-money calls/puts on select ETFs in the afternoon can produce asymmetric payoffs (≥5×) often enough to justify a systematic approach — without purchasing historical OPRA datasets.

## Universe (v1)

Six highly liquid ETFs across sectors:

- **SPY** — S&P 500
- **QQQ** — Nasdaq-100
- **SMH** — Semiconductors
- **XLF** — Financials
- **XLE** — Energy
- **HYG** — High-yield corporate bonds

All options and underlying quotes collected for feasibility studies and live convexity mapping.

## Market Data Source

**Yahoo Finance via `yfinance` is the only market-data provider in v1.**

Delayed chains are acceptable for research purposes. Every stored row is tagged with `feed_name=yahoo` and `delay_seconds`.

## Documentation

- **[PLAN.md](PLAN.md)** — Full project plan: goals, research architecture, phases, snapshot schedule, and data honesty principles
- **[SCHEMA.md](SCHEMA.md)** — Supabase database schema for instruments, snapshots, labels, and contract outcomes
- **[docs/timestamp-first-collection.md](docs/timestamp-first-collection.md)** — Timestamp-first collection design: problem, solution, migration guide

## Installation

```bash
# Clone the repository
git clone https://github.com/flareware-gh/fdproxy.git
cd fdproxy

# Install in development mode
pip install -e .

# Copy environment template and configure
cp .env.example .env
# Edit .env with your Supabase credentials
```

## CLI Usage

The CLI provides agent-friendly commands with `--json` output support.

### Doctor - Validate Environment

Check Python version, dependencies, Supabase connectivity, and Yahoo Finance access:

```bash
# Human-readable output
fdproxy doctor

# JSON output for agents
fdproxy doctor --json
```

### Collect - Gather Market Data

Collect underlying quotes and 0DTE option chains. The collector uses **timestamp-first** logic: it always saves data (except holidays) regardless of wall-clock distance from named slots. Slot names are soft labels assigned when near a planned time (±30 min).

```bash
# Collect with auto slot assignment (label with nearest slot if within ±30 min, else null)
fdproxy collect --slot auto

# Collect with an intended slot label
fdproxy collect --slot t1530

# Collect specific symbols only
fdproxy collect --symbols SPY,QQQ

# Dry run (no database writes)
fdproxy collect --dry-run

# JSON output for agents
fdproxy collect --json

# Strict mode (fail if any symbol errors)
fdproxy collect --strict

# Specify trigger metadata (typically from CI/scheduler)
fdproxy collect --trigger-source github_actions --trigger-id $GITHUB_RUN_ID
```

### Status - View Collection Health

```bash
fdproxy status
fdproxy status --days 3 --json
```

### Simulate - Analyze Option Paths

```bash
fdproxy simulate --from 2026-10-27 --to 2026-11-27
fdproxy simulate --from 2026-10-27 --to 2026-11-27 --entry-slot t1530 --json
```

### Study - Run Research Analyses

```bash
fdproxy study feasibility
fdproxy study convexity
```

All commands support:
- `--json` for machine-readable output
- `--env-file` to specify custom .env path
- `-v` / `--verbose` for detailed logging

## Project Status

**Phase 0 — Bootstrap (In Progress)**  
- ✅ Documentation complete (PLAN.md, SCHEMA.md)
- ✅ CLI scaffolded with Typer
- ✅ `fdproxy doctor` working (environment validation)
- ✅ `fdproxy collect` implemented (Yahoo Finance + delta buckets)
- ✅ Supabase migration ready (`supabase/migrations/001_init.sql`)
- ✅ GitHub Actions workflows (CI + automated collection)
- ✅ Unit tests with pytest

Next steps:
1. Apply Supabase migration to live project
2. Test collection with real market data
3. Begin Phase 1 feasibility studies

## License

Internal research project.
