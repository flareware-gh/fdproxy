# FDProxy — 0DTE late-day options feasibility, CLI collection & live calibration

**Repo:** https://github.com/flareware-gh/fdproxy  
**Supabase:** project `FDProxy` (`lwfpttiwijynwbjekaxo`) — https://lwfpttiwijynwbjekaxo.supabase.co  
**Status:** planning draft (not implemented)

## 1. Goal

Investigate whether buying **same-day-expiry (0DTE) OTM calls/puts** on selected ETFs in the **afternoon into the close** can produce **asymmetric payoffs (≥5×)** often enough to motivate a systematic approach — **without purchasing historical OPRA datasets**.

We will:

1. Quantify how often underlyings move enough late-day for that convexity to be possible (**feasibility**).
2. Build a **toy convexity map** from move distributions → illustrative option multiples.
3. Ship an **agent-friendly CLI** that collects live snapshots into Supabase so any agent (or GitHub Actions) can gather data and later **simulate / observe** option price paths that reach 5×+.
4. Calibrate internal models from that live panel; if discovery supports it, also study **per-contract multi-bagger** outcomes (including ~10×) as a research label — useful when it works, not required for the project to succeed.

Live order placement is out of scope until data quality and models justify it.

## 2. Universe (locked)

| Symbol | Role |
|--------|------|
| **SPY** | Trade + features |
| **QQQ** | Trade + features |
| **SMH** | Trade + features |
| **XLF** | Trade + features |
| **XLE** | Trade + features |
| **HYG** | Trade + features |

Options **and** underlying for all six. No XLK, RSP, Mag-7, IWM, SPX, single-stock or leveraged ETFs in v1.

**Liquidity note:** SPY/QQQ 0DTE books are deep; SMH/XLF/XLE/HYG vary. Always store spread/depth proxies; gate any "5×" analysis on tradable width.

## 3. Non-goals (v1)

- Buying ThetaData / Databento / ORATS / full OPRA history.
- Dealer GEX as a single master signal.
- Automated live trading / order placement.
- Treating ChatGPT/WSB frequency tables as ground truth.

**Not a non-goal:** predicting or labeling "will / did this contract go ~10×?" — welcome as a **secondary** discovery target if the data supports it; primary training still prefers move/direction/EV because extreme multiples are rare.

## 4. Product shape: CLI-first (agent-usable)

Everything important is a **CLI** a human or any agent can run with clear flags, JSON stdout, and non-zero exit codes. Python and/or TypeScript/Node are fine; HTML/CSS for optional dashboards later.

### Proposed commands (`fdproxy` or `npx tsx` / `python -m fdproxy`)

| Command | Purpose |
|---------|---------|
| `fdproxy collect --slot <name\|auto>` | Pull underlyings + 0DTE strip for the universe; write Supabase; print summary JSON |
| `fdproxy collect --once --symbols SPY,QQQ` | Ad-hoc / agent-triggered collect |
| `fdproxy status` | Last runs, missing slots, row counts |
| `fdproxy study feasibility …` | Phase 1 offline study |
| `fdproxy study convexity …` | Phase 2 toy map |
| `fdproxy simulate --from … --to …` | Replay stored snapshots → mid paths, multiples, delta buckets |
| `fdproxy doctor` | Env, feed, Supabase connectivity |

**Agent contract**

- `--json` on every command for machine parsing.
- Idempotent upserts on `(session_date, slot, symbol, …)`.
- Documented in `README.md` + `docs/cli.md` so agents don't need chat context.
- GitHub Actions calls the same `collect` binary the agent would.

## 5. Research architecture

| Model | Question | Notes |
|-------|----------|--------|
| **A — Move** | \(P(\|R_{t\to\mathrm{close}}\| > x)\) for bp thresholds | Every session informs this |
| **B — Direction** | \(P(R > x \mid \|R\| > x)\) | Conditional sign |
| **C — Contract / EV** | Map \(F(r)\) → option payoff by **delta bucket**; spread-aware | Primary option layer |
| **D — Extreme multiple (optional)** | Did mid (or ask→bid) reach ≥5× / ≥10× before close? | Secondary label when sample allows |

**Strike / contract selection (locked):** target **absolute delta** buckets approximately **0.025, 0.05, 0.10, 0.20, 0.30** (calls and puts). Prefer nearest listed strike per bucket; store vendor delta when available, else compute from mid + simple BS. Also keep a wide raw strip (±~3% or full near-dated chain) so bucket mapping can be recomputed offline if IV/delta is revised.

## 6. Quote feed (v1)

**Yahoo Finance via `yfinance` only** for all collection (CLI + GitHub Actions). Delayed chains are acceptable for research; tag every row with `feed_name=yahoo` and `delay_seconds`. No other market-data vendors in v1.

## 7. Snapshot schedule (ET, RTH only)

**Timestamp-first collection:** Slots are soft labels for analysis cohorts, not gates. The collector fires on an interval, always saves (except holidays), and keeps duplicates/near-duplicates. Time cohorts are assigned later in analysis based on actual request timestamps.

Denser afternoon, plus earlier calibration chunks:

| Slot | Target (ET) | Cadence idea |
|------|-------------|--------------|
| `m0935` | 09:35 | Open context |
| `m1030` | 10:30 | Morning regime |
| `m1200` | 12:00 | Midday |
| `m1400` | 14:00 | Pre-power-hour |
| `m1445` | 14:45 | Approaching close hour |
| `t1500` | 15:00 | Close-hour start |
| `t1515` | 15:15 | |
| `t1530` | 15:30 | Primary decision window |
| `t1545` | 15:45 | |
| `t1550` | 15:50 | |
| `t1555` | 15:55 | |
| `close` | 16:00 | Last quote / settle proxy |

GitHub Actions: cron (or scheduled workflow) invoking `fdproxy collect` on an interval grid. Slot labels are assigned as nearest planned slot if within ±30 min, else null — never an error. Actions minute resolution is coarse (GitHub Actions cron wakes late/irregularly) — accept skew; record `scheduled_at`, `started_at`, `request_started_at`, `request_finished_at`, `intended_at`, `trigger_source`, `trigger_id`. Holidays/weekends → `skipped_holiday`.

## 8. Phases

### Phase 0 — Bootstrap
- `PLAN.md`, `SCHEMA.md`, `README.md`, `docs/cli.md`
- Supabase migrations
- Scaffold CLI (Python or TS — pick one primary for collect; studies can be Python)
- `.env.example`; secrets in Actions + local only

### Phase 1 — Feasibility (free bars)
Late-session return distributions for the six symbols; event/vol conditionals; honest limits of free bar data.

### Phase 2 — Toy convexity
Map empirical \(F(r)\) → multiples for delta buckets 0.025…0.30; stress spreads.

### Phase 3 — Live collector + simulate
CLI + Actions → Supabase; `simulate` joins slots into paths and flags ≥3×/≥5×/≥10× mid (and conservative ask→bid).

### Phase 4 — Calibration
Fit/refresh A/B; C EV by delta; optional D extreme-multiple rates; weekly health digest.

## 9. Data honesty

1. No invented quotes or frequencies.  
2. Mid-to-mid vs executable (ask→bid) always separated.  
3. Tag `source`, `delay_seconds`, `collector_version`.  
4. American ETF options: note early exercise / pin in Phase 4.  
5. External blog/ChatGPT tables are hypotheses only.

## 10. Suggested layout

```
fdproxy/
  PLAN.md
  SCHEMA.md
  README.md
  docs/cli.md
  supabase/migrations/
  src/                 # CLI + feeds + supabase client
  studies/             # feasibility, convexity
  web/                 # optional later HTML dashboard
  .github/workflows/collect.yml
  .env.example
```

## 11. Decisions (resolved in this revision)

| # | Decision |
|---|----------|
| 1 | Feed: **Yahoo Finance / `yfinance` only** |
| 2 | Strikes by **delta buckets 0.025 / 0.05 / 0.10 / 0.20 / 0.30** (+ raw strip for recompute) |
| 3 | **GitHub Actions** scheduling; denser last hour + earlier day chunks |
| 4 | Overall plan: **yes, with CLI-first + optional extreme-multiple label** (see §12) |

## 12. Reviewer note — is this okay? Recommended tweaks

**Generally yes.** Direction is sound for a no-history budget: measure physics → toy map → earn real option paths via CLI → calibrate.

**Changes I'm baking in (vs prior draft):**

1. Removed "no 10× primary label" as a non-goal; kept rarity as a modeling caution, not a ban.  
2. Made **CLI / agent ergonomics** a first-class deliverable, not an afterthought.  
3. **Delta buckets** instead of ±% only.  
4. **Earlier + denser** snapshot grid.  
5. Explicit **Yahoo-only feed** with delay tagging.

**Remaining risks to accept:**

- Yahoo delay/gaps → fine for research, weak for "would I have filled?"  
- SMH/XLF/XLE/HYG 0DTE may be missing or wide some days → store nulls, don't fake chains.  
- Actions timing skew → log scheduled vs actual.  
- Extreme multiples stay sparse for months → don't block Model A/B/C on Model D.

## 13. After approval

1. Push `PLAN.md` + `SCHEMA.md` + `README.md` to GitHub.  
2. Apply Supabase migration.  
3. Scaffold CLI `collect` / `status` / `doctor`.  
4. Wire Actions; start gathering on the next RTH session.  
5. Parallel: Phase 1 feasibility scripts.

---

*Draft for human review — not pushed.*
