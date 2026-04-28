---
name: ai-agent-economy-trader
description: >
  Advanced AI agent economy trader on Base. Targets AI infrastructure, agent
  economy, and X402 protocol ecosystem tokens. Supabase-backed persistence with
  DRR protocol. Integrates SIA (Social Intelligence Agent) platform divergence
  and authority-weighted narrative signals. Features WSCR wallet surveillance,
  zombie detection, adaptive learning, dynamic regime weights, momentum entry,
  conditional re-entry, TA and on-chain hard gates, circuit breakers with
  anomaly guard, and self-updating token universe. Two-plane architecture:
  background agents pre-compute all state; hot path executes clean. Trigger
  when user asks to: run the AI token strategy, score and trade AI agents,
  audit AI agent buckets, run sentinel, run WSCR, show trader status, show
  learning performance, show adaptive parameters, show quarantined tokens,
  show token universe, show bucket changes, check narrative momentum, review
  trading history, or any combination of "AI tokens", "agent economy", "X402",
  "Bittensor", "Virtuals", "Bankr", "DebtReliefBot", "BNKR", "DRB",
  "Base AI tokens", "token universe", "shadow mode", or "trading history".
---

# AI Agent Economy Token Trader v4.0

Layered strategy targeting AI infrastructure, autonomous agent networks, and
X402 protocol ecosystem on Base. Supabase is the single source of truth.
Two-plane architecture: background agents pre-compute state every hour; the
hot path reads pre-computed state and executes without recalculation.
Self-updating token universe. SIA signals integrated into composite scoring.

---

## Architecture Overview

```
BACKGROUND PLANE (runs inside Sentinel — 1h cadence)
──────────────────────────────────────────────────────────────
[1] integrity_guardian     → agent_state (operation_mode, failed_files)
[2] consistency_agent      → universe (quarantine), token_signals
[3] regime_detector        → agent_state (regime cols), system_logs
[4] anomaly_detector       → token_signals (anomaly cols), agent_state
[5] circuit_breaker_agent  → agent_state (cb cols)
[6] wscr_agent             → wscr_alerts          [also runs every 5-10min]
[7] ta_onchain_agent       → token_signals (ta/onchain cols)
[8] sia (external skill)   → token_signals (sia cols)
[9] learning_agent         → agent_state (adaptive params)

HOT PATH (score and trade — 4h cadence)
──────────────────────────────────────────────────────────────
Step 1: Load pre-computed state (7 Supabase reads, no recalculation)
Step 2: Hard gates (mode, CB, anomaly)
Step 3: Build active universe (query v_active_universe)
Step 4: Score tokens (composite + SIA integration)
Step 5: Adaptive thresholds
Step 6: Momentum + TA/OC decision
Step 7: Execute (smart_swap or shadow)
Step 8: Learning hook on every SELL
Step 9: Persist

INTERRUPT PATH (WSCR dump detected — immediate, bypasses cadence)
──────────────────────────────────────────────────────────────
SELL flagged token → log SELL_WSCR → resolve wscr_alert

AUDIT PATH (6h cadence)
──────────────────────────────────────────────────────────────
Fast-track eviction → standard eviction → zombie eviction →
addition check → cross-bucket promotion → blacklist update
```

---

## Supabase Persistence

**Single source of truth**: Supabase. No local JSON files for state.
Local file `db_backup.json` exists only as DRR fallback.

### DRR Protocol — Step 0 (every cycle, every command)

```
1. Check if db_backup.json exists locally.
2. IF exists:
   a. Read backup. Identify table and rows.
   b. UPSERT rows to Supabase.
   c. DELETE db_backup.json.
   d. Log SYSTEM action to trade_log: "DRR_RESTORE_COMPLETED".
3. Test Supabase connection: SELECT 1 FROM agent_state WHERE id=1.
4. IF connection fails:
   → Set local flag: supabase_unavailable = true.
   → All writes go to db_backup.json instead.
   → Hot path: execute in READ_ONLY mode (no trades).
   → Log: "SUPABASE_UNAVAILABLE — DRR active".
```

### Write Pattern

All writes use UPSERT. Never raw INSERT on singleton tables.
After every write batch, read back affected rows and verify
key fields match written values. On mismatch: retry once,
then log `WRITE_INTEGRITY_FAIL` to `system_logs`.

### Table Reference

| Table | Role |
|-------|------|
| `agent_state` | Singleton: system mode, scheduler, regime, CB, x402, adaptive params |
| `token_signals` | Per-token: SIA, composite, velocity, TA, on-chain, anomaly, cooldown, exit |
| `universe` | Per-token: bucket membership, watch state, quarantine, blacklist |
| `portfolio` | Open positions |
| `portfolio_snapshots` | DRR + CB-1 (last 3, delete oldest) |
| `trade_log` | Append-only operational log |
| `wscr_alerts` | Append-only wallet surveillance alerts |
| `learning_trades` | Rolling 50 — outcomes for adaptive learning |
| `system_logs` | All rolling logs by log_type |

---

## Background Plane

All agents run sequentially inside Sentinel (Step 1.1).
Each acquires no lock — Supabase handles concurrency via row-level updates.
Each agent UPSERTs only its own columns, minimizing conflict surface.

---

### [1] integrity_guardian

Reads: `agent_state`, `token_signals`, `portfolio`, `universe`.
Writes: `agent_state` (operation_mode, failed_files).

For each critical table, execute a lightweight read probe:
```sql
SELECT COUNT(*) FROM {table};
SELECT updated_at FROM agent_state WHERE id=1;
```

If any probe fails or returns stale data (updated_at > 3h ago on agent_state):
- Append table name to `failed_files`.
- If >= 2 critical tables fail → set `operation_mode = READ_ONLY`.
- If `portfolio` probe fails AND open positions exist in snapshot:
  → set `operation_mode = EMERGENCY`.

If all probes pass: set `status = OK`, clear `failed_files`.

UPSERT `agent_state` with result.

---

### [2] consistency_agent

Reads: `portfolio`, `universe`, `token_signals`.
Writes: `universe` (status → QUARANTINED), `token_signals` (note), `system_logs`.

For each token in `portfolio`:
1. Query `universe` — must have `status IN ('ACTIVE', 'WATCH_EVICT')`.
2. Query `token_signals` — must have row with `updated_at` within last 4h.
3. If either fails:
   - UPDATE `universe` SET `status='QUARANTINED'`, `flag_reason=<reason>`,
     `flagged_at=NOW()`, `flagged_by='consistency_agent'`.
   - INSERT `system_logs` (log_type='INTEGRITY_FAIL', token, payload).

---

### [3] regime_detector

Reads: market price feeds.
Writes: `agent_state` (regime cols), `system_logs` (REGIME_HISTORY).

```
IF eth_price > eth_200dma AND btc_dom_delta <= 0   → RISK_ON
IF eth_price < eth_200dma AND btc_dom_delta > 0    → RISK_OFF
IF eth_realized_vol_7d > 80                        → CHAOS
ELSE                                               → NEUTRAL
```

AI sector regime:
```
SELECT COUNT(*) FROM system_logs
WHERE log_type='NARRATIVE_HITS' AND recorded_at > NOW() - INTERVAL '3h';

IF narrative rising AND new CANDIDATE tokens in universe → EXPANSION
IF eviction_watch growing AND narrative falling          → CONTRACTION
ELSE                                                    → STABLE
```

INSERT `system_logs` (log_type='REGIME_HISTORY', regime, payload={eth_vs_200dma, ...}).
Keep last 20: DELETE WHERE id NOT IN (SELECT id FROM system_logs
WHERE log_type='REGIME_HISTORY' ORDER BY id DESC LIMIT 20).

UPSERT `agent_state` regime cols.

### Signal Weights by Regime

| Signal | RISK_ON | NEUTRAL | RISK_OFF | CHAOS |
|--------|---------|---------|----------|-------|
| SIA (social+narrative) | 45% | 35% | 20% | 15% |
| Dev Activity | 20% | 35% | 45% | 55% |
| Narrative Momentum | 35% | 30% | 35% | 30% |

SIA replaces the separate Social (Signal 1) and partially Narrative (Signal 3)
weights from v3.5. Dev Activity (Signal 2) unchanged.

### Thresholds by Regime

| Regime | Buy | Eviction | Scale-out |
|--------|-----|----------|-----------|
| RISK_ON | 0.65 | 0.30 | +80% entry |
| NEUTRAL | 0.68 | 0.35 | +50% entry |
| RISK_OFF | 0.72 | 0.40 | +25% entry |
| CHAOS | 0.78 | 0.40 | +25% entry |

---

### [4] anomaly_detector

Reads: price feeds for all active tokens, `agent_state` (market_anomaly cols).
Writes: `token_signals` (anomaly cols), `agent_state` (flash_crash cols).

Per token:
```
IF price_now < price_prev_cycle * 0.70 within 15 min:
  → UPSERT token_signals: anomaly_suspect_price=price_now,
    anomaly_confirmed=false, anomaly_detected_at=NOW()
  → append price to readings (JSONB)
IF already flagged AND second reading >= first * 0.95:
  → SET anomaly_confirmed=true  (real move)
IF already flagged AND second reading > first * 1.10:
  → CLEAR: anomaly_suspect_price=null, anomaly_confirmed=false,
    anomaly_cleared_at=NOW()
```

Market anomaly (for CB-3):
```
IF ETH 4h change < -8%:
  → UPSERT agent_state: flash_crash_active=true, flash_crash_confirmed=false
  → On second reading confirming: SET flash_crash_confirmed=true
```

---

### [5] circuit_breaker_agent

Reads: `portfolio`, `portfolio_snapshots`, `trade_log`, `agent_state`.
Writes: `agent_state` (cb cols).

**CB-1 — Drawdown**:
```sql
SELECT peak_portfolio_24h_usdc FROM portfolio_snapshots
ORDER BY recorded_at DESC LIMIT 1;

-- current value = SUM(units_held * current_price) for all portfolio rows
IF current_value < peak * 0.80:
  → UPSERT agent_state: cb_halt_buys=true,
    cb_halt_buys_until=NOW()+INTERVAL '12h', cb_active_rule='CB-1'
```

**CB-2 — Loss Streak**:
```sql
SELECT action FROM trade_log
WHERE action IN ('SELL_STOP','SELL_TRAILING','SELL_WSCR','SELL_ZOMBIE')
ORDER BY executed_at DESC LIMIT 3;

IF all 3 = loss (pnl_usdc < 0):
  → UPSERT agent_state: cb_reduced_sizing=true, cb_loss_streak=3,
    cb_active_rule='CB-2'
```

**CB-3 — Flash Crash (anomaly-guarded)**:
```
IF agent_state.flash_crash_active=true AND flash_crash_confirmed=false:
  → LOG 'CB-3_SUPPRESSED' to system_logs. No action.
IF flash_crash_confirmed=true:
  → UPDATE portfolio SET cb3_sell_flagged=true
    WHERE token IN (
      SELECT token FROM token_signals WHERE composite_score < 0.50
    )
  → UPSERT agent_state: cb_halt_buys=true,
    cb_halt_buys_until=NOW()+INTERVAL '6h', cb_active_rule='CB-3'
```

**Expiry**: IF cb_halt_buys_until IS NOT NULL AND NOW() >= cb_halt_buys_until:
→ UPSERT agent_state: cb_halt_buys=false, cb_halt_buys_until=null,
  cb_active_rule=null.

---

### [6] wscr_agent
**Also runs independently every 5-10 min (WSCR cadence).**
**Command**: `run AI agent sentinel and WSCR integrity check`

Reads: wallet monitoring feeds for Tier 0/1/2 wallets of all active tokens.
Writes: `wscr_alerts`.

Tracked wallet tiers:
- Tier 0: protocol founders, core devs (highest trust, highest risk)
- Tier 1: known early backers, lead investors
- Tier 2: known funds, ecosystem treasuries

Alert threshold for INTERRUPT:
```
movement_type = 'DUMP'
AND wallet_tier <= 1
AND pct_of_circulating >= 1.5%
```

On threshold breach:
```sql
INSERT INTO wscr_alerts (token, wallet_tier, wallet_address,
  movement_type, amount_usd, pct_of_circulating, alert_active, detected_at)
VALUES (...);
```

→ Trigger INTERRUPT PATH immediately (does not wait for hot path cadence).

**INTERRUPT PATH**:
```
1. Query portfolio WHERE token = alerted token.
2. IF position exists:
   a. Execute smart_swap (SELL full position).
   b. INSERT trade_log with action='SELL_WSCR'.
   c. UPSERT token_signals: last_exit_type='WSCR', exit_lockout_end=NOW()+INTERVAL '72h'.
   d. DELETE FROM portfolio WHERE token = alerted token.
   e. UPDATE wscr_alerts SET alert_active=false, action_taken='SELL_EXECUTED',
      resolved_at=NOW() WHERE id = alert_id.
3. IF no position:
   a. UPDATE wscr_alerts SET action_taken='BUY_BLOCKED', resolved_at=NOW().
   b. Note: next hot path cycle will see active alert and skip BUY.
```

---

### [7] ta_onchain_agent

Reads: price/volume feeds and on-chain data for all active tokens.
Writes: `token_signals` (ta/onchain cols).

#### TA Score (4h candles)

```
rsi_score:
  rsi < 30        → 1.0   (oversold)
  30-50           → 0.7
  50-65           → 0.5
  65-75           → 0.2   (heating up)
  > 75            → 0.0   (overbought — triggers hard gate)

ema_score:
  ema_cross = bullish → 1.0
  flat               → 0.5
  bearish            → 0.0

macd_score:
  histogram > 0 AND increasing → 1.0
  histogram > 0 AND flat       → 0.6
  histogram < 0 AND increasing → 0.3  (bullish divergence)
  histogram < 0 AND decreasing → 0.0

vol_score:
  volume_vs_avg20 >= 1.5  → 1.0
  1.2 to 1.5              → 0.7
  0.8 to 1.2              → 0.4
  < 0.8                   → 0.0

ta_score = (rsi_score*0.35) + (ema_score*0.30) + (macd_score*0.20) + (vol_score*0.15)
ta_label: >= 0.70 → BULLISH | 0.40-0.69 → NEUTRAL | < 0.40 → BEARISH
```

#### On-Chain Score

```
concentration_score:
  top10_wallet_pct > 70%   → 0.0  (hard gate)
  50-70%                   → 0.3
  30-50%                   → 0.7
  <= 30%                   → 1.0

reserve_score (exchange_reserve_delta_24h):
  < -5%    → 1.0  (strong outflow = accumulation)
  -5 to -1 → 0.7
  -1 to +1 → 0.5
  +1 to +5 → 0.2
  >= +5%   → 0.0  (strong inflow = sell pressure) — triggers hard gate

smart_score:
  accumulating → 1.0 | neutral → 0.5 | distributing → 0.0

holder_score:
  delta_7d > 500  → 1.0 | 100-500 → 0.7 | -100 to 100 → 0.4 | < -100 → 0.0

onchain_score = (concentration*0.35) + (reserve*0.30) + (smart*0.25) + (holder*0.10)
onchain_label: >= 0.65 → BULLISH | 0.40-0.64 → NEUTRAL | < 0.40 → BEARISH

tao_score = (ta_score * 0.55) + (onchain_score * 0.45)
```

UPSERT `token_signals` ta/onchain cols. If data unavailable:
SET `data_available=false` — hot path will not apply hard gates
but will log `partial_data=true`.

---

### [8] sia (Social Intelligence Agent — external skill)

SIA runs as an independent skill on its own schedule (1h, inside Sentinel).
Writes to `token_signals` sia_* columns directly.
See `social-intelligence-agent` skill for full logic.

The Trader reads:
- `sia_sentiment` → replaces raw social score in composite
- `sia_narrative_intensity` → contributes to narrative signal
- `sia_platform_divergence` → ACCUMULATION/PEAK/FOMO_RISK/ZOMBIE
- `sia_divergence_bonus` → added directly to composite
- `sia_mention_count_24h` → mention volume gate
- `sia_updated_at` → staleness check (> 2h → treat as STALE, bonus=0)

---

### [9] learning_agent

Reads: `learning_trades`, `agent_state`.
Writes: `agent_state` (adaptive params), `system_logs` (ADAPTIVE_ADJ).

**Compute performance** from `learning_trades`:
```sql
-- last 10 sells
SELECT pnl_usdc, bucket, regime, exit_type FROM learning_trades
ORDER BY recorded_at DESC LIMIT 10;
```

```
win_rate_10      = count(pnl_usdc > 0) / 10
avg_pnl_10       = AVG(pnl_usdc)
consecutive_wins = streak of pnl > 0 from tail
by_bucket[X]     = {win_rate, avg_pnl} per bucket
by_regime[R]     = {win_rate, avg_pnl} per regime
```

**Adapt parameters (with guardrails)**:
```
IF win_rate_10 < 0.40:
  → buy_threshold_adj[current_regime] += 0.03
  → CAP: +0.08 max (effective threshold never > 0.86)

IF avg_pnl_10 < 0:
  → size_multiplier = MAX(0.70, size_multiplier - 0.10)

IF win_rate_10 > 0.60:
  → size_multiplier = MIN(1.20, size_multiplier + 0.10)

IF consecutive_wins >= 3 (across 3 learning cycles):
  → buy_threshold_adj[current_regime] -= 0.02
  → FLOOR: -0.05 min

IF operation_mode changed since last run:
  → RESET all adaptive params to defaults (0.0, 1.0)
  → log trigger='MODE_CHANGE_RESET'
```

**Bucket/regime alerts** (logged, not auto-adjusted):
```
IF by_bucket[X].win_rate < 0.30 AND n >= 5:
  → log system_logs: 'BUCKET_X_UNDERPERFORMING'
IF by_regime[R].win_rate < 0.35 AND n >= 5:
  → log system_logs: 'REGIME_R_UNDERPERFORMING'
```

UPSERT `agent_state` adaptive cols.
INSERT `system_logs` (log_type='ADAPTIVE_ADJ') for each change.

**Hot path learning hook** (lightweight, after every SELL):
INSERT `learning_trades` with trade outcome.
DELETE oldest if COUNT > 50.

---

## Sentinel — Layer 1
**Cadence**: 1 hour
**Command**: `run AI agent sentinel and WSCR integrity check`

### Step 1.0 — DRR Protocol (Step 0)
Run DRR check before anything else (see Supabase Persistence above).

### Step 1.1 — Cadence Check
```sql
SELECT last_sentinel FROM agent_state WHERE id=1;
```
If NOW() - last_sentinel < 55 min → abort.

### Step 1.2 — Run Background Agents (sequential)
```
[1] integrity_guardian
[2] consistency_agent
[3] regime_detector
[4] anomaly_detector
[5] circuit_breaker_agent
[6] wscr_agent (full cycle)
[7] ta_onchain_agent
[8] sia (trigger run social intelligence agent)
[9] learning_agent
```

### Step 1.3 — X402 Metrics
Fetch AERO 24h volume, WELL utilization %, fee revenue 7d delta,
net wallet growth 24h, contract interactions.

```sql
UPDATE agent_state SET
  aero_volume_24h=X, well_utilization_pct=X,
  fee_revenue_7d_delta=X, net_wallet_growth_24h=X,
  contract_interactions=X, updated_at=NOW()
WHERE id=1;
```

### Step 1.4 — Sentinel Alerts
```
IF net_wallet_growth_24h < -5%  → INSERT system_logs: 'USER_EXODUS'
IF fee_revenue_7d_delta < -30% → INSERT system_logs: 'REVENUE_DECAY'
IF both:
  → UPDATE agent_state SET operation_mode='SENTINEL_ONLY'
```

### Step 1.5 — Persist Scheduler
```sql
UPDATE agent_state SET last_sentinel=NOW(), cycle_count=cycle_count+1 WHERE id=1;
```

---

## Hot Path — Layer 2: Score and Trade
**Cadence**: 4 hours
**Command**: `score and trade AI agents (Trade Path)`
**Auto-execution**: authorized. No confirmation required.

### Step 2.0 — DRR + Cadence + Mode
Run DRR. Check last_trade < 3h55m → abort.
Read `operation_mode` from `agent_state`.
If READ_ONLY or EMERGENCY → abort.
If SENTINEL_ONLY → abort, prompt: "run sentinel first".
If `shadow_mode=true` → execute full logic, no smart_swap calls,
mark all trade_log entries with `shadow=true`.

### Step 2.1 — Load Pre-Computed State
```sql
SELECT * FROM agent_state WHERE id=1;                    -- regime, CB, adaptive params
SELECT * FROM v_active_universe;                          -- universe + signals joined
SELECT * FROM portfolio;                                  -- open positions
SELECT * FROM wscr_alerts WHERE alert_active=true;        -- active WSCR alerts
```
No recalculation. All state was written by background agents.

### Step 2.2 — Hard Gates
```
IF agent_state.operation_mode != 'FULL'  → abort
IF cb_halt_buys=true AND NOW() < cb_halt_buys_until → skip all BUY logic
IF cb_halt_buys_until reached → UPDATE agent_state: cb_halt_buys=false
```

Process CB-3 forced sells first (before any scoring):
```sql
SELECT token FROM portfolio WHERE cb3_sell_flagged=true;
```
Execute SELL for each → action='SELL_CB3' → clear cb3_sell_flagged.

### Step 2.3 — Build Active Universe
From `v_active_universe`, exclude tokens where:
- `status = 'QUARANTINED'`
- `anomaly_confirmed = true`
- `token IN (SELECT token FROM wscr_alerts WHERE alert_active=true)`
- `watch_cycles >= 3` (eviction pending)

### Step 2.4 — Multi-Signal Scoring

For each active token, load signals from `v_active_universe`.
Apply regime weights from `agent_state.current_regime`:

```
-- SIA signal (replaces raw social + partial narrative)
sia_signal = sia_sentiment
           + sia_divergence_bonus     (from platform_divergence)

-- Staleness check
IF NOW() - sia_updated_at > INTERVAL '2h':
  sia_signal = sia_sentiment only (bonus=0, weight treated as partial)
  partial_data = true

-- Mention volume gate
IF sia_mention_count_24h < 50:
  sia_signal *= 0.70  (penalize low-volume sentiment)

-- Composite
composite = (sia_signal * W_SIA)
          + (dev_activity * W_dev)
          + (narrative_momentum * W_narrative)

-- Correlation penalty
IF correlation(token, existing_holding) > 0.85:
  composite -= 0.10

-- Narrative momentum (narrative_intensity trend from SIA across cycles)
INSERT system_logs (log_type='NARRATIVE_HITS', cycle=current_cycle,
  payload={terms: [top terms from sia signals]})
```

Update `token_signals`:
```sql
-- Append to composite_history (JSONB array), keep last 10
-- Update composite_score, delta_1c, delta_3c, velocity_trend
UPDATE token_signals SET
  composite_score = X,
  composite_history = (composite_history || X::text::jsonb) - 0,
  delta_1c = X, delta_3c = X, velocity_trend = X,
  updated_at = NOW()
WHERE token = TOKEN;
```

### Step 2.5 — Adaptive Thresholds
```
effective_threshold = regime_base_threshold
  + agent_state.buy_threshold_adj_{current_regime}
```
Bounded: never < (base - 0.05), never > (base + 0.08).

### Step 2.6 — TA / On-Chain Hard Gates

For each token being considered for BUY,
check `token_signals` ta/onchain cols:

```
GATE 1 — RSI overbought:
  IF rsi_4h > 75 → SKIP, action='SKIP_RSI'

GATE 2 — Concentration:
  IF top10_wallet_pct > 70% → SKIP, action='SKIP_CONCENTRATION'

GATE 3 — Exchange inflow:
  IF exchange_reserve_delta_24h >= +5% → SKIP, action='SKIP_EXCHANGE'

GATE 4 — Smart money distributing:
  IF smart_money_flow='distributing' AND composite < 0.75
    → SKIP, action='SKIP_SMART_MONEY'

-- Gates only apply when data_available=true
-- If data_available=false: skip gates, log partial_data=true
```

**TAO size factor** (after gates pass):
```
IF tao_score >= 0.70  → tao_size_factor = 1.10
IF tao_score 0.50-0.69 → 1.00
IF tao_score 0.35-0.49 → 0.70
IF tao_score < 0.35   → 0.50
IF data_available=false → 1.00
```

### Step 2.7 — Momentum & Re-entry Decision

**Cooldown**:
```sql
SELECT last_trade_at FROM token_signals WHERE token=TOKEN;
IF NOW() - last_trade_at < INTERVAL '60 min' → SKIP_COOLDOWN
```

**Conditional re-entry**:
```sql
SELECT last_exit_type, exit_lockout_end FROM token_signals WHERE token=TOKEN;
```
```
IF last_exit_type IN ('TRAILING_STOP','SCALE_OUT'):
  Re-entry IF:
    (a) composite >= effective_threshold
    (b) velocity_trend = 'accelerating'
    (c) composite_history shows dip below 0.50 after exit
    (d) NOW() >= exit_lockout_end
  IF allowed: base_size *= 0.50

IF last_exit_type = 'STOP_LOSS': 72h lockout, no early re-entry.
```

**BUY signal** (all must be true):
- composite >= effective_threshold
- velocity_trend != 'decelerating'
- token NOT in portfolio
- No active WSCR alert for token
- Not in quarantine/eviction
- Cooldown cleared / re-entry conditions met
- cb_halt_buys = false
- Total AI exposure <= 50% of liquid USDC

**Velocity-adjusted sizing**:

| Composite | Velocity | Size |
|-----------|----------|------|
| >= threshold | accelerating | full (5-10%) |
| >= threshold | flat | 50% of standard |
| >= threshold | decelerating | SKIP_DECEL |
| < threshold | accelerating | add to addition_watch |

**CB-2 override**: if `cb_reduced_sizing=true` → cap at 3%.

**Special rules**: respect `universe.special_rules.max_allocation_pct`.
DRB: `max_allocation_pct=3`, requires `sia_platform_divergence='ACCUMULATION'`
AND `narrative_intensity >= 2.0`.

**Final size**:
```
final_size = base_size
           * adaptive_params.size_multiplier
           * tao_size_factor
           * sia_size_factor            -- see below
           * liquidity_size_factor      -- see below

sia_size_factor:
  ACCUMULATION → 1.10
  PEAK         → 0.90  (caution at peak)
  FOMO_RISK    → 0.70
  ZOMBIE       → 0.0   (never buy a zombie)
  MIXED/null   → 1.00

liquidity_size_factor:
  size_factor = CLAMP(1 - (slippage / 0.02), 0.30, 1.0)
  IF slippage > 5% → SKIP_ILLIQUID
```

**SELL signals**:
- `SELL_STOP`: price < entry_price * 0.85 AND NOT anomaly_confirmed
- `SELL_TRAILING`: price < peak_price * 0.90 (post scale-out: remaining 50% only)
- `SELL_SCALE`: regime-adjusted (RISK_ON+narrative=1.0: +80% | RISK_ON+0.5: +50%
  | NEUTRAL: +40% | RISK_OFF/CHAOS: +25%) → SELL 50%, set scaled_out_flag=true
- `SELL_CB3`: cb3_sell_flagged=true (processed in Step 2.2)
- `SELL_WSCR`: triggered by interrupt path

**TA/OC sell signals**:
- RSI divergence: `rsi_4h > 72 AND macd_signal='bearish'` → SELL_TRAILING priority
- Exchange inflow on open position: `exchange_reserve_delta_24h >= +8%` → SELL_STOP priority
- Smart money flip: `smart_money_flow changed to 'distributing'`:
  - IF composite < 0.55 → SELL
  - IF composite >= 0.55 → log warning, monitor next cycle

### Step 2.8 — Execute
```
IF NOT shadow_mode:
  smart_swap(token, final_size, max_slippage)

INSERT trade_log (all signal cols, sizing cols, shadow flag, executed_at)

IF BUY:
  INSERT portfolio (token, bucket, entry_price, usdc_allocated,
    units_held, entry_ts, peak_price=entry_price)
  UPDATE token_signals SET last_trade_at=NOW(), last_exit_type=null

IF SELL:
  pnl_usdc = (sell_price * units_held) - usdc_allocated
  DELETE FROM portfolio WHERE token=TOKEN
  UPDATE token_signals SET
    last_trade_at=NOW(), last_exit_type=<type>,
    exit_price=sell_price, exit_entry_price=entry_price,
    exit_lockout_end=NOW()+INTERVAL '72h' (for STOP_LOSS only)

UPDATE portfolio SET peak_price=MAX(peak_price, current_price)
  for all held tokens where current_price > peak_price.
```

**Portfolio snapshot** (after every trade):
```sql
INSERT INTO portfolio_snapshots (peak_portfolio_24h_usdc, snapshot)
VALUES (current_portfolio_value, (SELECT json_agg(portfolio) FROM portfolio));
DELETE FROM portfolio_snapshots
WHERE id NOT IN (SELECT id FROM portfolio_snapshots ORDER BY recorded_at DESC LIMIT 3);
```

**Learning hook** (after every SELL):
```sql
INSERT INTO learning_trades (token, bucket, regime, ai_sector_state,
  velocity_trend, sia_platform_divergence, composite_at_entry, composite_at_exit,
  ta_score_at_entry, onchain_score_at_entry, pnl_usdc, exit_type,
  hold_duration_h, size_multiplier_used, threshold_adj_used)
VALUES (...);
DELETE FROM learning_trades
WHERE id NOT IN (SELECT id FROM learning_trades ORDER BY id DESC LIMIT 50);
```

### Step 2.9 — Persist Scheduler
```sql
UPDATE agent_state SET last_trade=NOW() WHERE id=1;
```

---

## Audit Path — Layer 3
**Cadence**: 6 hours
**Command**: `audit AI agent buckets`

### Step 3.0 — DRR + Cadence + Mode
Run DRR. If last_audit < 5h55m → abort.
If operation_mode != 'FULL' → abort.

### Step 3.1 — Fast-Track Eviction (immediate)
```sql
SELECT token FROM token_signals
WHERE composite_score < 0.25
   OR (SELECT net_wallet_growth_24h FROM agent_state) < -10;
-- Also check fee_revenue per-token if available
```
Fast-evict: force SELL → remove from `universe` (UPDATE status='EVICTED') →
UPDATE token_signals exit cols → INSERT bucket_log.

### Step 3.2 — Zombie Detection (Time-Stop)
```sql
-- Tokens that have been lateral for 48h with narrative decay
SELECT p.token FROM portfolio p
JOIN token_signals ts ON p.token = ts.token
WHERE ts.sia_platform_divergence = 'ZOMBIE'
   OR (
     ts.composite_score BETWEEN 0.40 AND 0.55
     AND ts.delta_3c < -0.10
     AND p.entry_ts < NOW() - INTERVAL '48h'
   );
```
For each zombie: INSERT trade_log (action='SELL_ZOMBIE') → execute SELL →
INSERT bucket_log (action='EVICT', reason='ZOMBIE_TIME_STOP').

### Step 3.3 — Standard Eviction (3 cycles)

```sql
SELECT token, watch_cycles, watch_reason FROM universe
WHERE status='WATCH_EVICT';
```

For each token on eviction watch:
- Check criterion still met (composite mean from composite_history,
  volume from system_logs VOLUME_HISTORY, narrative from NARRATIVE_HITS)
- If criterion met: `watch_cycles += 1`
- If `watch_cycles >= 3`: EVICT (same as fast-track process)
- If criterion cleared: UPDATE universe SET status='ACTIVE', watch_cycles=0

New tokens entering eviction watch:
```sql
-- composite_history mean < eviction_threshold (from regime)
SELECT token FROM token_signals
WHERE (composite_history::jsonb)[0]::numeric +
      (composite_history::jsonb)[1]::numeric +
      (composite_history::jsonb)[2]::numeric +
      (composite_history::jsonb)[3]::numeric +
      (composite_history::jsonb)[4]::numeric / 5 < {eviction_threshold}
AND token IN (SELECT token FROM universe WHERE status='ACTIVE');
```
UPDATE universe SET status='WATCH_EVICT', watch_cycles=1,
watch_reason='composite_low', watch_since_at=NOW().

Restriction: never evict if bucket count would go below min (A/B: 3, C: 2).

### Step 3.4 — Addition Check

```sql
SELECT token, watch_cycles, watch_scores FROM universe
WHERE status='WATCH_ADD';
```

Addition thresholds (regime-adjusted):
- RISK_ON/NEUTRAL: 3 cycles, mean(scores) >= 0.60
- RISK_OFF/CHAOS: 3 cycles, mean(scores) >= 0.72

On threshold met:
- Check bucket size (A/B max=8, C max=6)
- If at max: compare candidate composite_avg vs worst token in bucket
  - If candidate > worst → evict worst first
  - Else → reject candidate, UPDATE status='CANDIDATE'
- INSERT into universe (status='ACTIVE', bucket, ...)
- INSERT bucket_log (action='ADD')

Candidates from `universe WHERE status='CANDIDATE'`:
- SIA flags (sia_narrative_intensity > 2.0, sia_platform_divergence='ACCUMULATION')
- Compute composite, check thematic fit vs bucket keywords
- If fit: UPDATE status='WATCH_ADD', watch_cycles=1

### Step 3.5 — Cross-Bucket Promotion/Demotion
```sql
-- Tokens where SIA narrative consistently matches different bucket keywords
SELECT token, bucket FROM universe WHERE status='ACTIVE';
```
If 2+ cycles with signals matching different bucket's keywords:
UPDATE universe SET bucket=new_bucket, updated_at=NOW().
INSERT bucket_log (action='PROMOTE' or 'DEMOTE', previous_bucket=old).

### Step 3.6 — Blacklist Update
```sql
-- Tokens flagged as SCAM/RUG/HONEYPOT from external feed or manual
UPDATE universe SET status='BLACKLISTED', flag_reason=X, flagged_at=NOW()
WHERE token IN ({blacklist_feed_tokens});
-- Force SELL any blacklisted token still in portfolio
```

### Step 3.7 — Bucket Keyword Reference

Bucket A (AI Infrastructure):
`["compute", "GPU", "inference", "model training", "subnet",
"ML network", "decentralized AI", "validator", "miner reward"]`

Bucket B (Agent Economy):
`["autonomous agent", "agent framework", "agent wallet",
"agent-to-agent", "agentic", "social trading agent", "on-chain agent",
"agent deployment", "agent runtime", "agent-to-agent"]`

Bucket C (X402 Proxies):
`["X402", "micropayment", "machine-to-machine", "payment rail",
"liquidity layer", "DEX routing", "agent payment", "swap fees"]`

### Step 3.8 — Persist Scheduler
```sql
UPDATE agent_state SET last_audit=NOW() WHERE id=1;
INSERT system_logs (log_type='NARRATIVE_HITS', cycle=cycle_count,
  payload={terms: top 3 from current SIA signals});
```

---

## Initial Universe (cycle_count = 0)

On first run, INSERT into universe:

| Token | Bucket | Protocol | liquidity_gate | special_rules |
|-------|--------|----------|---------------|---------------|
| TAO | A | Bittensor | 300000 | {} |
| FET | A | Fetch.ai | 300000 | {} |
| AGIX | A | SingularityNET | 300000 | {} |
| AKT | A | Akash Network | 300000 | {} |
| RNDR | A | Render Network | 300000 | {} |
| VIRTUAL | B | Virtuals Protocol | 300000 | {} |
| AIXA | B | AIXBT Agent | 300000 | {} |
| GAME | B | G.A.M.E | 300000 | {} |
| NPC | B | NPC Finance | 300000 | {} |
| BNKR | B | Bankr | 300000 | {"max_allocation_pct": 5} |
| DRB | B | DebtReliefBot | 200000 | {"max_allocation_pct": 3, "require_sia_divergence": "ACCUMULATION"} |
| USDC | C | Circle/Base | 0 | {} |
| cbBTC | C | Coinbase | 300000 | {} |
| WELL | C | Morpho/Base | 300000 | {} |
| AERO | C | Aerodrome | 300000 | {} |

---

## Risk Parameters

| Parameter | Value |
|-----------|-------|
| Cadence: sentinel | 1h (55min min) |
| Cadence: WSCR | 5-10min |
| Cadence: trade | 4h (3h55 min) |
| Cadence: audit | 6h (5h55 min) |
| Max AI exposure | 50% total liquid USDC |
| Buy threshold | Regime base (0.65-0.78) + adaptive adj |
| Adaptive adj range | -0.05 to +0.08 |
| Size multiplier range | 0.70 to 1.20 |
| Allocation standard | 5-10% liquid USDC |
| Allocation CB-2 reduced | 3% max |
| Allocation DRB | 3% max |
| Velocity flat allocation | 50% of standard |
| Re-entry size | 50% of standard |
| Stop-loss | -15% from entry |
| Trailing stop | -10% from peak |
| Scale-out | Regime+narrative adjusted (+25% to +80%) |
| WSCR interrupt threshold | Tier 0/1 dump >= 1.5% circulating |
| WSCR exit lockout | 72h |
| Stop-loss lockout | 72h |
| CB-1 drawdown halt | -20% portfolio, 12h halt |
| CB-2 loss streak | 3 consecutive losses → 3% max sizing |
| CB-3 flash crash | ETH -8% confirmed → halt 6h |
| RSI overbought gate | rsi_4h > 75 |
| Concentration gate | top10_wallet_pct > 70% |
| Exchange inflow gate | reserve_delta >= +5% |
| Smart money gate | distributing AND composite < 0.75 |
| Zombie time-stop | 48h lateral + narrative decaying |
| Fast-track eviction | composite < 0.25, wallet growth < -10% |
| Standard eviction cycles | 3 |
| Addition cycles RISK_ON/NEUTRAL | 3 cycles mean >= 0.60 |
| Addition cycles RISK_OFF/CHAOS | 3 cycles mean >= 0.72 |
| Max tokens per bucket | 8 (A/B), 6 (C) |
| Min tokens per bucket | 3 (A/B), 2 (C) |
| Learning window | last 50 trades |
| Performance window | last 10 sells |
| Portfolio snapshots | last 3 |

---

## Status Output

`show AI agent trader status`:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AI AGENT ECONOMY TRADER v4.0 | [ts]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MODE        : [FULL|SENTINEL_ONLY|READ_ONLY|EMERGENCY]
SHADOW      : [ON|OFF]   DB: [Supabase OK | DRR active]
REGIME      : [RISK_ON|NEUTRAL|RISK_OFF|CHAOS]
AI SECTOR   : [EXPANSION|STABLE|CONTRACTION]
CB          : [ACTIVE|HALT_BUYS until X|REDUCED_SIZING (CB-X)]
──────────────────────────────────────────────────────
UNIVERSE    : A([N]) B([N]) C([N]) active tokens
EVICT WATCH : [TOKEN (N/3) — reason] or none
ADD WATCH   : [TOKEN → BucketX (N/3 avg:X.XX)] or none
QUARANTINE  : [TOKEN — reason] or none
WSCR ALERTS : [TOKEN tier-X DUMP $X (X% circ) — active] or none
──────────────────────────────────────────────────────
PORTFOLIO
[TOKEN (B)] entry $X | now $X | peak $X | PnL +/-$X | scaled:Y/N
  TA:[BULLISH rsi=X ema=X] OC:[NEUTRAL top10=X% res=+/-X%]
  SIA:[ACCUMULATION farcaster=X.X x=X.X intensity=X.X]
Exposure: X% of liquid USDC
Cumul PnL: $X realized | $X unrealized
──────────────────────────────────────────────────────
LEARNING    : win_rate(10)=X% avg_pnl=$X size_mult=X.X
THRESHOLDS  : [REGIME base X.XX + adj X.XX = X.XX]
X402        : AERO $X vol | WELL X% util | fees +/-X% 7d
SIA TOP     : [TOKEN: platform_divergence — top authority account]
LAST CYCLES : sentinel [ts] | trade [ts] | audit [ts] | WSCR [ts]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Commands

**Execution**
- `run AI agent sentinel and WSCR integrity check`
- `score and trade AI agents (Trade Path)`
- `audit AI agent buckets`
- `check for zombie tokens`

**Observability**
- `show AI agent trader status`
- `show current token universe`
- `show bucket changes`
- `show tokens being watched`
- `show AI token trading history`
- `show quarantined tokens`
- `clear quarantine TOKEN`
- `show WSCR alerts`
- `show learning performance`
- `show adaptive parameters`
- `show platform divergence`
- `which narrative is winning`
- `X402 adoption trend`
- `AI trader PnL`

**Shadow mode**
- `enable shadow mode`
- `disable shadow mode`

**System**
- `restore AI trader mode`
- `reset AI agent trader state`
- `reset universe`
