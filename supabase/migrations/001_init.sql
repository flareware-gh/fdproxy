-- FDProxy initial schema
-- Matches SCHEMA.md

-- Instruments table
CREATE TABLE instruments (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    collect_options BOOLEAN DEFAULT TRUE,
    collect_underlying BOOLEAN DEFAULT TRUE,
    active BOOLEAN DEFAULT TRUE,
    notes TEXT
);

-- Snapshot runs table
CREATE TABLE snapshot_runs (
    id UUID PRIMARY KEY,
    session_date DATE NOT NULL,
    slot TEXT NOT NULL,
    scheduled_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    collector_version TEXT,
    feed_name TEXT,
    error TEXT,
    meta JSONB,
    UNIQUE (session_date, slot)
);

-- Underlying snapshots table
CREATE TABLE underlying_snapshots (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES snapshot_runs(id),
    symbol TEXT NOT NULL,
    quoted_at TIMESTAMPTZ NOT NULL,
    last NUMERIC,
    bid NUMERIC,
    ask NUMERIC,
    mid NUMERIC,
    volume NUMERIC,
    day_open NUMERIC,
    day_high NUMERIC,
    day_low NUMERIC,
    delay_seconds INTEGER,
    raw JSONB,
    UNIQUE (run_id, symbol)
);

-- Option snapshots table
CREATE TABLE option_snapshots (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES snapshot_runs(id),
    symbol TEXT NOT NULL,
    expiry DATE NOT NULL,
    dte INTEGER,
    "right" TEXT NOT NULL,
    strike NUMERIC NOT NULL,
    bid NUMERIC,
    ask NUMERIC,
    mid NUMERIC,
    last NUMERIC,
    volume NUMERIC,
    open_interest NUMERIC,
    delta NUMERIC,
    gamma NUMERIC,
    iv NUMERIC,
    delta_bucket NUMERIC,
    is_bucket_pick BOOLEAN DEFAULT FALSE,
    quoted_at TIMESTAMPTZ NOT NULL,
    delay_seconds INTEGER,
    raw JSONB,
    UNIQUE (run_id, symbol, expiry, "right", strike)
);

-- Session labels table
CREATE TABLE session_labels (
    session_date DATE NOT NULL,
    symbol TEXT NOT NULL,
    r_from_slot_bp JSONB,
    rv_metrics JSONB,
    is_event_day BOOLEAN,
    event_tags TEXT[],
    meta JSONB,
    PRIMARY KEY (session_date, symbol)
);

-- Contract outcomes table (Phase 3/4)
CREATE TABLE contract_outcomes (
    session_date DATE NOT NULL,
    symbol TEXT NOT NULL,
    "right" TEXT NOT NULL,
    strike NUMERIC NOT NULL,
    entry_slot TEXT NOT NULL,
    entry_mid NUMERIC,
    entry_ask NUMERIC,
    max_mid NUMERIC,
    end_mid NUMERIC,
    max_multiple_mid NUMERIC,
    multiple_ask_to_bid NUMERIC,
    hit_3x BOOLEAN,
    hit_5x BOOLEAN,
    hit_10x BOOLEAN,
    delta_bucket NUMERIC,
    meta JSONB,
    PRIMARY KEY (session_date, symbol, "right", strike, entry_slot)
);

-- Indexes
CREATE INDEX idx_snapshot_runs_session_date ON snapshot_runs(session_date);
CREATE INDEX idx_snapshot_runs_status ON snapshot_runs(status);
CREATE INDEX idx_underlying_snapshots_run_id ON underlying_snapshots(run_id);
CREATE INDEX idx_underlying_snapshots_symbol ON underlying_snapshots(symbol);
CREATE INDEX idx_option_snapshots_run_id ON option_snapshots(run_id);
CREATE INDEX idx_option_snapshots_symbol ON option_snapshots(symbol);
CREATE INDEX idx_option_snapshots_is_bucket_pick ON option_snapshots(is_bucket_pick) WHERE is_bucket_pick = TRUE;
CREATE INDEX idx_session_labels_session_date ON session_labels(session_date);
CREATE INDEX idx_contract_outcomes_session_date ON contract_outcomes(session_date);

-- RLS: Deny anonymous writes (service role bypasses RLS)
ALTER TABLE instruments ENABLE ROW LEVEL SECURITY;
ALTER TABLE snapshot_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE underlying_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE option_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_labels ENABLE ROW LEVEL SECURITY;
ALTER TABLE contract_outcomes ENABLE ROW LEVEL SECURITY;

-- Allow service role full access (default)
-- Deny anon writes
CREATE POLICY "Deny anon writes on instruments" ON instruments FOR INSERT TO anon WITH CHECK (FALSE);
CREATE POLICY "Deny anon writes on snapshot_runs" ON snapshot_runs FOR INSERT TO anon WITH CHECK (FALSE);
CREATE POLICY "Deny anon writes on underlying_snapshots" ON underlying_snapshots FOR INSERT TO anon WITH CHECK (FALSE);
CREATE POLICY "Deny anon writes on option_snapshots" ON option_snapshots FOR INSERT TO anon WITH CHECK (FALSE);
CREATE POLICY "Deny anon writes on session_labels" ON session_labels FOR INSERT TO anon WITH CHECK (FALSE);
CREATE POLICY "Deny anon writes on contract_outcomes" ON contract_outcomes FOR INSERT TO anon WITH CHECK (FALSE);

-- Seed instruments
INSERT INTO instruments (symbol, name, collect_options, collect_underlying, active) VALUES
    ('SPY', 'SPDR S&P 500 ETF Trust', TRUE, TRUE, TRUE),
    ('QQQ', 'Invesco QQQ Trust', TRUE, TRUE, TRUE),
    ('SMH', 'VanEck Semiconductor ETF', TRUE, TRUE, TRUE),
    ('XLF', 'Financial Select Sector SPDR Fund', TRUE, TRUE, TRUE),
    ('XLE', 'Energy Select Sector SPDR Fund', TRUE, TRUE, TRUE),
    ('HYG', 'iShares iBoxx $ High Yield Corporate Bond ETF', TRUE, TRUE, TRUE);
