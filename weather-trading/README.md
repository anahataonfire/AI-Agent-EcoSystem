# Weather Trading

Automated weather forecast scanning and edge calculation for Polymarket weather markets.

## Features

- **Forecast Fetching**: NWS, Open-Meteo, and other weather APIs
- **Market Scanning**: Find weather bracket markets on Polymarket
- **Edge Calculation**: Compare forecasts to market prices
- **Telegram Alerts**: Get notified of opportunities
- **Backtesting**: Test strategies against historical data
- **Trading**: Optional automated execution via CLOB

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your Telegram credentials

# Run a scan (dry-run mode)
python main.py --dry-run

# Run a full scan with alerts
python main.py
```

## CLI Options

```bash
python main.py [OPTIONS]

Options:
  --cities NYC LA SEA    Cities to scan (default: all active)
  --dry-run              Print results without sending alerts
  --verbose, -v          Enable debug logging
  --test-telegram        Test Telegram connection and exit
```

## Configuration

Edit `config.py` to customize:
- `ACTIVE_CITIES`: Cities to scan
- `EDGE_CONFIG`: Minimum edge thresholds
- `SCAN_CONFIG`: Scan frequency settings
- `POSITION_CONFIG`: Position sizing

## Directory Structure

```
weather-trading/
├── main.py           # CLI entry point
├── config.py         # Configuration
├── scanner.py        # Polymarket market scanner
├── forecaster.py     # Weather forecast fetching
├── edge_calculator.py # Edge calculation logic
├── alerter.py        # Telegram notifications
├── probability.py    # Temperature probability models
├── trader.py         # Trade execution
├── clob_client.py    # Polymarket CLOB client
├── backtester.py     # Backtesting framework
├── browser_scraper.py # Browser-based scraping
├── graph_client.py   # Subgraph queries
├── market_ids.py     # Market ID lookups
├── requirements.txt
└── .env.example
```

## Usage Examples

### Scan NYC and Seattle
```bash
python main.py --cities nyc seattle --dry-run
```

### Run as cron job (every 30 minutes)
```bash
*/30 * * * * cd /path/to/weather-trading && python main.py
```

### Test Telegram setup
```bash
python main.py --test-telegram
```

## How It Works

1. **Fetch Forecasts**: Get temperature forecasts from NWS/Open-Meteo
2. **Scan Markets**: Find weather bracket markets on Polymarket
3. **Calculate Edge**: Compare forecast probability to market price
4. **Alert**: Send Telegram notification if edge > threshold (15%)
5. **Optional Trade**: Execute trades via CLOB client

## License

MIT
