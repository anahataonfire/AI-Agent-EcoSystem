# Polymarket Scanner

Scan Polymarket for high-certainty trading opportunities approaching resolution.

## Features

- **Certainty Scanner**: Find markets where Yes or No is ≥95% (or custom threshold)
- **APR Calculation**: Annualized return estimates for each opportunity
- **Multiple Sources**: Scans standard events, recurring series, and crypto dailies
- **Trader Tracking**: Optional scraping of successful trader positions

## Quick Start

```bash
# No installation needed for basic scanning!
python scanner.py

# With options
python scanner.py --max-hours 12 --min-certainty 90 --min-liquidity 500

# Output as JSON
python scanner.py --json
```

## CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--max-hours` | 24 | Markets resolving within this window |
| `--min-certainty` | 95 | Minimum certainty % (Yes or No) |
| `--min-liquidity` | 100 | Minimum liquidity in USD |
| `--json` | false | Output results as JSON |
| `-v, --verbose` | false | Enable debug logging |

## Example Output

```
🎯 Polymarket Certainty Scanner - Results (<24h window)
=================================================================

Found 3 high-certainty opportunities:

#1 | 2.3h remaining | APR: 4,521%
   Question: "Will BTC be up on January 24?"
   Certainty: YES @ 98.2% | Liquidity: $1,234
   Link: https://polymarket.com/event/...
```

## Configuration

Edit `config.py` to customize:
- Target series (crypto, stocks, forex)
- Target tags (politics, sports, etc.)
- Default thresholds

## Trader Tracking (Optional)

Requires Playwright for browser automation:

```bash
pip install playwright
playwright install chromium

# Scrape trader positions
python -c "from tracker import get_neobrother_data; print(get_neobrother_data())"
```

## Directory Structure

```
polymarket-scanner/
├── scanner.py       # Main scanner with CLI
├── config.py        # Configuration settings
├── tracker/         # Trader tracking tools
│   ├── neobrother_scraper.py
│   └── intercept_api.py
├── requirements.txt
└── .env.example
```

## License

MIT
