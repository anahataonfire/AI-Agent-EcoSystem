---
description: Polymarket scanner operations - scan for high-certainty opportunities
---

# /scan Workflow

Scan Polymarket for high-certainty trading opportunities.

## Quick Scan

```bash
// turbo
python -c "from src.polymarket_scanner import CertaintyScanner; s = CertaintyScanner(); opps = s.scan(); print(f'Found {len(opps)} opportunities'); [print(f'  {o.question[:60]}... | {o.certainty:.1%} | APR: {o.annualized_apr:.0%}') for o in opps[:5]]"
```

## Detailed Scan

```bash
python debug_scanner.py
```

## Custom Parameters

### Extended Time Window (8 hours)
```bash
python -c "from src.polymarket_scanner import CertaintyScanner; s = CertaintyScanner(); opps = s.scan(max_hours=8); print(f'Found {len(opps)} opportunities in 8h window')"
```

### Lower Certainty Threshold (90%)
```bash
python -c "from src.polymarket_scanner import CertaintyScanner; s = CertaintyScanner(); opps = s.scan(min_certainty=0.90); print(f'Found {len(opps)} opportunities at 90%+ certainty')"
```

### Higher Liquidity Threshold ($500)
```bash
python -c "from src.polymarket_scanner import CertaintyScanner; s = CertaintyScanner(); opps = s.scan(min_liquidity=500); print(f'Found {len(opps)} high-liquidity opportunities')"
```

## Debugging

If markets are missing:

1. **Check date parsing**: Does `_extract_date_from_question()` handle the format?
2. **Check series slugs**: Is the series in `config/polymarket_config.py`?
3. **Check API response**: Is the market returned by API?
4. **Check hours_remaining**: Is it calculated correctly?

## Key Files

| File | Purpose |
|------|---------|
| `src/polymarket_scanner.py` | Scanner implementation |
| `config/polymarket_config.py` | Thresholds and series |
| `debug_scanner.py` | Debug script |
