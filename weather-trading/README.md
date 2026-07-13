# Weather Trading

Polymarket weather-market scanner, paper/live order operator, lifecycle ledger, and fill-caveated strategy backtester.

The application is paper-first. A submitted, LIVE, MATCHED, or MINED order reserves cash but is not a position. Only an authenticated CONFIRMED trade event creates verified exposure and eligible P&L.

## Start

```bash
python -m venv .venv
./.venv/bin/pip install -r requirements.txt
# Terminal 1
cd backend && ../.venv/bin/python -m uvicorn api:app --reload --port 8000

# Terminal 2
cd ui && npm run dev
```

The backend binds to `127.0.0.1:8000`; the Next.js dashboard runs on `127.0.0.1:3000`.

## Strategy surfaces

- Multi-model HIGH and LOW forecasts with separate model-spread risk.
- Settlement-basis correction on both YES and NO candidates.
- Exact-station hard bounds only when market rules identify an authoritative `weather.gov` station.
- Polymarket dynamic taker-fee modeling and explicit maker-zero post-only handling.
- Configurable 90–95¢ forward-test cohort, book-depth cap, price re-quote, event exposure, and cycle exposure.
- Complete-set weather arbitrage detection with shared Gamma event identity, full bucket coverage, fee/slippage guards, and signal-only default.

Conditional net winning payoff is not expected value. The repository currently has no verified resolved fill cohort, so historical returns are hypothesis-generating only.

## Validate

```bash
PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m pytest -p no:cacheprovider
./.venv/bin/python -m compileall -q -f -x 'ui|\.venv|\.next|data-old' .
PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin npm --prefix ui exec tsc -- --noEmit --incremental false
```

## Backtest

```bash
./.venv/bin/python scripts/backtest_profit_strategy.py \
  --band 0.90:0.95 \
  --fee-bps 500 \
  --slippage-bps 20 \
  --output reports/profit_strategy_backtest.json
```

The output separates provisional legacy outcomes from verified fills and splits train/test chronologically by target date. Bands, fee parameters, slippage, split, source database, and output path are CLI-overridable.

## Automation

```bash
# Paper mode; local logs only
./.venv/bin/python auto_harvest.py --no-vpn --order-mode POST_ONLY

# Inspect every override
./.venv/bin/python auto_harvest.py --help
```

Live mode requires explicit `--live`, valid Polymarket credentials, and available bankroll. External bdc-fabric log sync requires both live mode and explicit `--sync-bdc-fabric`; dry-run cannot trigger it.

## Runtime controls

The dashboard and `/api/settings` expose bankroll, opportunity exposure, event exposure, maximum scan age, re-quote tolerance, and default `GTC`/`POST_ONLY` order mode. Trade requests can provide a per-order mode and explicit gate override.

See [docs/weather-trading-operations.html](docs/weather-trading-operations.html) for the lifecycle, profit-screen, backtest, and operating runbook.
