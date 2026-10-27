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

## CLI (to be built)

An agent-friendly command-line interface will provide:

- `fdproxy collect` — Pull underlyings + 0DTE strips and write to Supabase
- `fdproxy status` — Report last runs, missing slots, row counts
- `fdproxy simulate` — Replay stored snapshots → mid paths, multiples, delta buckets
- `fdproxy study` — Run feasibility and convexity analyses
- `fdproxy doctor` — Check environment, feed connectivity, Supabase health

All commands will support `--json` output for machine parsing. Implementation details will be documented in `docs/cli.md` once built.

## Project Status

**Phase 0 — Planning**  
Documentation complete. Next steps:
1. Apply Supabase migrations
2. Scaffold CLI (`collect` / `status` / `doctor`)
3. Wire GitHub Actions for automated collection
4. Begin Phase 1 feasibility studies

No collector, migrations, or GitHub Actions implemented yet.

## License

Internal research project.
