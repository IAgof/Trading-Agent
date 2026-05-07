-- ============================================================
-- AI Agent Economy Trader v4 — Supabase Schema
-- Single source of truth. Run once to initialize.
-- ============================================================

-- ── SYSTEM ──────────────────────────────────────────────────

CREATE TABLE system_status (
  id              SERIAL PRIMARY KEY,
  operation_mode  TEXT    NOT NULL DEFAULT 'FULL',   -- FULL | SENTINEL_ONLY | READ_ONLY | EMERGENCY
  status          TEXT    NOT NULL DEFAULT 'OK',     -- OK | DEGRADED | FAILED
  failed_files    JSONB   NOT NULL DEFAULT '[]',
  mode_reason     TEXT,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Single row: id=1 always. Use UPSERT.

CREATE TABLE scheduler_state (
  id              SERIAL PRIMARY KEY,
  cycle_count     INT     NOT NULL DEFAULT 0,
  last_sentinel   TIMESTAMPTZ,
  last_trade      TIMESTAMPTZ,
  last_audit      TIMESTAMPTZ,
  last_wscr       TIMESTAMPTZ,
  shadow_mode     BOOLEAN NOT NULL DEFAULT FALSE,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Single row: id=1.

-- ── REGIME ──────────────────────────────────────────────────

CREATE TABLE regime_state (
  id                      SERIAL PRIMARY KEY,
  current_regime          TEXT NOT NULL DEFAULT 'NEUTRAL',  -- RISK_ON | NEUTRAL | RISK_OFF | CHAOS
  eth_vs_200dma           NUMERIC(10,4),
  btc_dom_delta           NUMERIC(8,4),
  eth_realized_vol_7d     NUMERIC(8,2),
  ai_sector_state         TEXT NOT NULL DEFAULT 'STABLE',  -- EXPANSION | STABLE | CONTRACTION
  narrative_intensity_trend NUMERIC(6,4),
  token_velocity          NUMERIC(6,4),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Single row: id=1.

CREATE TABLE regime_history (
  id              SERIAL PRIMARY KEY,
  regime          TEXT NOT NULL,
  eth_vs_200dma   NUMERIC(10,4),
  btc_dom_delta   NUMERIC(8,4),
  eth_realized_vol_7d NUMERIC(8,2),
  recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Rolling: keep last 20. Delete oldest on insert if count > 20.

-- ── SIGNALS (SIA output) ─────────────────────────────────────

CREATE TABLE ai_trader_signals (
  token                   TEXT PRIMARY KEY,
  sentiment_score         NUMERIC(5,4),    -- -1.0 to 1.0
  narrative_intensity     NUMERIC(8,4),    -- authority-weighted, time-decayed
  platform_divergence     TEXT,            -- ACCUMULATION | FOMO_RISK | PEAK | ZOMBIE
  platform_divergence_bonus NUMERIC(5,3),  -- -0.20 to +0.15
  authority_score         NUMERIC(6,2),    -- weighted composite
  farcaster_score         NUMERIC(5,4),
  x_score                 NUMERIC(5,4),
  mention_count_24h       INT,
  top_authority_accounts  JSONB DEFAULT '[]',  -- [{handle, authority, sentiment}]
  data_quality            TEXT DEFAULT 'OK',   -- OK | PARTIAL | STALE
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── SIGNAL ENGINE ────────────────────────────────────────────

CREATE TABLE composite_history (
  token           TEXT NOT NULL,
  composite       NUMERIC(5,4) NOT NULL,
  regime          TEXT NOT NULL,
  recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (token, recorded_at)
);
-- Per token: keep last 10. Delete oldest on insert when count(token) > 10.

CREATE TABLE score_velocity (
  token           TEXT PRIMARY KEY,
  delta_1c        NUMERIC(6,4),
  delta_3c        NUMERIC(6,4),
  trend           TEXT,          -- accelerating | flat | decelerating
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE addition_watch (
  token           TEXT PRIMARY KEY,
  bucket_tentative TEXT NOT NULL,
  cycles          INT NOT NULL DEFAULT 1,
  scores          JSONB NOT NULL DEFAULT '[]',
  first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE eviction_watch (
  token           TEXT PRIMARY KEY,
  cycles          INT NOT NULL DEFAULT 1,
  reason          TEXT NOT NULL,
  since_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── TA / ON-CHAIN ────────────────────────────────────────────

CREATE TABLE ta_onchain_signals (
  token               TEXT PRIMARY KEY,
  rsi_4h              NUMERIC(6,2),
  ema20_4h            NUMERIC(16,6),
  ema50_4h            NUMERIC(16,6),
  ema_cross           TEXT,          -- bullish | flat | bearish
  macd_histogram_4h   NUMERIC(10,6),
  macd_signal         TEXT,          -- bullish | flat | bearish
  volume_vs_avg20     NUMERIC(6,3),
  ta_score            NUMERIC(5,4),
  ta_label            TEXT,          -- BULLISH | NEUTRAL | BEARISH
  top10_wallet_pct    NUMERIC(6,2),
  top50_wallet_pct    NUMERIC(6,2),
  exchange_reserve_delta_24h NUMERIC(8,3),
  exchange_reserve_pct       NUMERIC(6,2),
  active_addresses_7d_delta  NUMERIC(8,2),
  smart_money_flow    TEXT,          -- accumulating | neutral | distributing
  holder_count_delta_7d INT,
  onchain_score       NUMERIC(5,4),
  onchain_label       TEXT,          -- BULLISH | NEUTRAL | BEARISH
  tao_score           NUMERIC(5,4),  -- combined TA+OC score
  data_available      BOOLEAN NOT NULL DEFAULT TRUE,
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── ANOMALIES ────────────────────────────────────────────────

CREATE TABLE anomaly_flags (
  token           TEXT PRIMARY KEY,
  suspect_price   NUMERIC(24,10),
  readings        JSONB NOT NULL DEFAULT '[]',
  confirmed       BOOLEAN NOT NULL DEFAULT FALSE,
  detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  cleared_at      TIMESTAMPTZ,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE market_anomaly (
  id                      SERIAL PRIMARY KEY,
  flash_crash             BOOLEAN NOT NULL DEFAULT FALSE,
  flash_crash_confirmed   BOOLEAN NOT NULL DEFAULT FALSE,
  detected_at             TIMESTAMPTZ,
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Single row: id=1.

-- ── CIRCUIT BREAKER ──────────────────────────────────────────

CREATE TABLE cb_state (
  id              SERIAL PRIMARY KEY,
  halt_buys       BOOLEAN NOT NULL DEFAULT FALSE,
  halt_buys_until TIMESTAMPTZ,
  reduced_sizing  BOOLEAN NOT NULL DEFAULT FALSE,
  loss_streak     INT NOT NULL DEFAULT 0,
  active_rule     TEXT,   -- null | CB-1 | CB-2 | CB-3
  last_evaluated  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Single row: id=1.

-- ── WSCR ─────────────────────────────────────────────────────

CREATE TABLE wscr_alerts (
  id                  SERIAL PRIMARY KEY,
  token               TEXT NOT NULL,
  wallet_tier         INT NOT NULL,     -- 0=founder/dev, 1=early backer, 2=known fund
  wallet_address      TEXT NOT NULL,
  movement_type       TEXT NOT NULL,    -- DUMP | ACCUMULATE | TRANSFER
  amount_usd          NUMERIC(18,2),
  pct_of_circulating  NUMERIC(8,4),
  alert_active        BOOLEAN NOT NULL DEFAULT TRUE,
  action_taken        TEXT,             -- null | SELL_EXECUTED | BUY_BLOCKED
  detected_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at         TIMESTAMPTZ
);

CREATE INDEX idx_wscr_active ON wscr_alerts (token, alert_active)
  WHERE alert_active = TRUE;

-- ── STRATEGY / UNIVERSE ───────────────────────────────────────

CREATE TABLE buckets (
  token           TEXT PRIMARY KEY,
  bucket          TEXT NOT NULL,           -- A | B | C
  protocol        TEXT NOT NULL,
  thesis          TEXT NOT NULL,
  added_cycle     INT NOT NULL,
  liquidity_gate  NUMERIC(18,2) NOT NULL,
  special_rules   JSONB NOT NULL DEFAULT '{}',
  composite_history JSONB NOT NULL DEFAULT '[]',  -- last 5, FIFO
  added_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE bucket_log (
  id              SERIAL PRIMARY KEY,
  cycle           INT NOT NULL,
  action          TEXT NOT NULL,     -- ADD | EVICT | PROMOTE | DEMOTE
  token           TEXT NOT NULL,
  bucket          TEXT NOT NULL,
  previous_bucket TEXT,
  reason          TEXT NOT NULL,
  composite_avg   NUMERIC(5,4),
  recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE blacklist (
  token           TEXT PRIMARY KEY,
  reason          TEXT NOT NULL,      -- SCAM | RUG | HONEYPOT | MANUAL
  added_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  added_by        TEXT DEFAULT 'audit_agent'
);

CREATE TABLE volume_history (
  token           TEXT NOT NULL,
  volume_24h      NUMERIC(24,2) NOT NULL,
  recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (token, recorded_at)
);
-- Per token: keep last 5.

-- ── PORTFOLIO ────────────────────────────────────────────────

CREATE TABLE portfolio (
  token               TEXT PRIMARY KEY,
  bucket              TEXT NOT NULL,
  entry_price         NUMERIC(24,10) NOT NULL,
  usdc_allocated      NUMERIC(18,4) NOT NULL,
  units_held          NUMERIC(24,10) NOT NULL,
  entry_ts            TIMESTAMPTZ NOT NULL,
  peak_price          NUMERIC(24,10) NOT NULL,
  scaled_out_flag     BOOLEAN NOT NULL DEFAULT FALSE,
  cb3_sell_flagged    BOOLEAN NOT NULL DEFAULT FALSE,
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE portfolio_snapshots (
  id              SERIAL PRIMARY KEY,
  snapshot        JSONB NOT NULL,
  peak_portfolio_24h_usdc NUMERIC(18,4),
  recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Keep last 3. Replaces state_backup.

-- ── EXECUTION ────────────────────────────────────────────────

CREATE TABLE trade_log (
  id                          SERIAL PRIMARY KEY,
  cycle                       INT NOT NULL,
  token                       TEXT NOT NULL,
  bucket                      TEXT NOT NULL,
  action                      TEXT NOT NULL,  -- BUY | SELL_STOP | SELL_TRAILING | SELL_SCALE | SELL_WSCR | SELL_ZOMBIE | SELL_CB3 | SKIP_*
  composite_score             NUMERIC(5,4),
  sia_narrative_intensity     NUMERIC(8,4),
  sia_platform_divergence     TEXT,
  velocity_trend              TEXT,
  ta_score                    NUMERIC(5,4),
  onchain_score               NUMERIC(5,4),
  tao_score                   NUMERIC(5,4),
  rsi_at_entry                NUMERIC(6,2),
  top10_wallet_pct_at_entry   NUMERIC(6,2),
  exchange_reserve_delta_at_entry NUMERIC(8,3),
  smart_money_at_entry        TEXT,
  hard_gates_passed           JSONB DEFAULT '[]',
  signals                     JSONB,          -- {social, dev_activity, narrative}
  amount_usdc                 NUMERIC(18,4),
  price                       NUMERIC(24,10),
  slippage_est                NUMERIC(6,4),
  size_factor                 NUMERIC(6,4),
  size_multiplier_used        NUMERIC(6,4),
  threshold_adjustment_used   NUMERIC(6,4),
  tao_size_factor             NUMERIC(6,4),
  sia_size_factor             NUMERIC(6,4),
  pnl_usdc                    NUMERIC(18,4),
  partial_data                BOOLEAN DEFAULT FALSE,
  shadow                      BOOLEAN DEFAULT FALSE,
  reason                      TEXT,
  executed_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE cooldowns (
  token           TEXT PRIMARY KEY,
  last_trade_at   TIMESTAMPTZ NOT NULL,
  exit_type       TEXT
);

CREATE TABLE exit_log (
  token           TEXT PRIMARY KEY,
  exit_type       TEXT NOT NULL,     -- STOP_LOSS | TRAILING_STOP | SCALE_OUT | WSCR | CB3 | ZOMBIE
  exit_price      NUMERIC(24,10) NOT NULL,
  entry_price     NUMERIC(24,10) NOT NULL,
  pnl_usdc        NUMERIC(18,4),
  lockout_end     TIMESTAMPTZ,
  exit_ts         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE quarantine (
  token           TEXT PRIMARY KEY,
  reason          TEXT NOT NULL,
  quarantined_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  cleared_at      TIMESTAMPTZ,
  cleared_by      TEXT          -- manual | consistency_agent
);

-- ── MARKET DATA ───────────────────────────────────────────────

CREATE TABLE x402_metrics (
  id                      SERIAL PRIMARY KEY,
  aero_volume_24h         NUMERIC(24,2),
  well_utilization_pct    NUMERIC(6,2),
  fee_revenue_7d_delta    NUMERIC(8,3),
  net_wallet_growth_24h   NUMERIC(8,3),
  contract_interactions   BIGINT,
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Single row: id=1.

CREATE TABLE narrative_hits (
  id              SERIAL PRIMARY KEY,
  cycle           INT NOT NULL,
  terms           JSONB NOT NULL DEFAULT '[]',
  recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Rolling: keep last 20 cycles.

CREATE TABLE candidates (
  token           TEXT PRIMARY KEY,
  bucket_tentative TEXT,
  detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── LEARNING ─────────────────────────────────────────────────

CREATE TABLE learning_trades (
  id                          SERIAL PRIMARY KEY,
  token                       TEXT NOT NULL,
  bucket                      TEXT NOT NULL,
  regime                      TEXT NOT NULL,
  ai_sector_state             TEXT,
  velocity_trend              TEXT,
  sia_platform_divergence     TEXT,
  composite_at_entry          NUMERIC(5,4),
  composite_at_exit           NUMERIC(5,4),
  ta_score_at_entry           NUMERIC(5,4),
  onchain_score_at_entry      NUMERIC(5,4),
  pnl_usdc                    NUMERIC(18,4) NOT NULL,
  exit_type                   TEXT NOT NULL,
  hold_duration_h             NUMERIC(8,2),
  size_multiplier_used        NUMERIC(6,4),
  threshold_adjustment_used   NUMERIC(6,4),
  recorded_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Keep last 50 rows. Delete oldest on insert when count > 50.

CREATE TABLE adaptive_params (
  id                      SERIAL PRIMARY KEY,
  buy_threshold_adj_risk_on   NUMERIC(6,4) DEFAULT 0.0,
  buy_threshold_adj_neutral   NUMERIC(6,4) DEFAULT 0.0,
  buy_threshold_adj_risk_off  NUMERIC(6,4) DEFAULT 0.0,
  buy_threshold_adj_chaos     NUMERIC(6,4) DEFAULT 0.0,
  size_multiplier             NUMERIC(6,4) DEFAULT 1.0,
  sia_weight_boost            NUMERIC(6,4) DEFAULT 0.0,  -- learned adjustment to SIA weight
  update_reason               TEXT,
  updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Single row: id=1.

CREATE TABLE adaptive_params_log (
  id              SERIAL PRIMARY KEY,
  trigger         TEXT NOT NULL,
  regime          TEXT,
  delta_threshold NUMERIC(6,4),
  delta_size      NUMERIC(6,4),
  win_rate_snap   NUMERIC(6,4),
  avg_pnl_snap    NUMERIC(10,4),
  recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── DRR BACKUP ───────────────────────────────────────────────
-- Local file: /.memory/project_ai_trader/db_backup.json
-- Schema: { "table": "...", "rows": [...], "backed_up_at": "ISO_TS" }
-- Written only on Supabase failure. Restored on Step 0 of every cycle.

-- ── ROW LEVEL SECURITY (recommended) ────────────────────────
ALTER TABLE portfolio ENABLE ROW LEVEL SECURITY;
ALTER TABLE trade_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE wscr_alerts ENABLE ROW LEVEL SECURITY;
-- Apply service_role key in agent; anon key for read-only dashboards.

-- ── USEFUL VIEWS ─────────────────────────────────────────────

CREATE VIEW v_portfolio_with_signals AS
SELECT
  p.token, p.bucket, p.entry_price, p.usdc_allocated, p.units_held,
  p.peak_price, p.scaled_out_flag,
  s.sentiment_score, s.narrative_intensity, s.platform_divergence,
  t.ta_score, t.ta_label, t.onchain_score, t.tao_score,
  t.rsi_4h, t.top10_wallet_pct, t.exchange_reserve_delta_24h,
  t.smart_money_flow
FROM portfolio p
LEFT JOIN ai_trader_signals s ON p.token = s.token
LEFT JOIN ta_onchain_signals t ON p.token = t.token;

CREATE VIEW v_active_universe AS
SELECT
  b.token, b.bucket, b.protocol, b.thesis, b.liquidity_gate,
  b.special_rules, b.composite_history,
  s.narrative_intensity, s.platform_divergence,
  t.tao_score, t.ta_label,
  sv.trend AS velocity_trend,
  CASE WHEN q.token IS NOT NULL THEN TRUE ELSE FALSE END AS quarantined,
  CASE WHEN bl.token IS NOT NULL THEN TRUE ELSE FALSE END AS blacklisted
FROM buckets b
LEFT JOIN ai_trader_signals s ON b.token = s.token
LEFT JOIN ta_onchain_signals t ON b.token = t.token
LEFT JOIN score_velocity sv ON b.token = sv.token
LEFT JOIN quarantine q ON b.token = q.token AND q.cleared_at IS NULL
LEFT JOIN blacklist bl ON b.token = bl.token;

-- Normies Intelligence Agent MVP persistence.
CREATE TABLE IF NOT EXISTS normies_signals (
  token_id INT PRIMARY KEY CHECK (token_id BETWEEN 0 AND 9999),
  owner_address TEXT,
  type_trait TEXT,
  gender_trait TEXT,
  age_trait TEXT,
  hair_trait TEXT,
  facial_trait TEXT,
  eyes_trait TEXT,
  expression_trait TEXT,
  accessory_trait TEXT,
  pixel_count INT,
  customized BOOLEAN,
  level INT,
  action_points INT,
  added_pixels INT,
  removed_pixels INT,
  net_pixel_change INT,
  rarity_score NUMERIC(6,4) NOT NULL DEFAULT 0,
  visual_density_score NUMERIC(6,4) NOT NULL DEFAULT 0,
  canvas_activity_score NUMERIC(6,4) NOT NULL DEFAULT 0,
  holder_activity_score NUMERIC(6,4) NOT NULL DEFAULT 0,
  burn_momentum_score NUMERIC(6,4) NOT NULL DEFAULT 0,
  composite_score NUMERIC(6,4) NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'ok',
  anomaly_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
