#!/usr/bin/env python3
"""
Polymarket Certainty Scanner CLI

Command-line tool to scan for high-certainty Polymarket opportunities.

Usage:
    python scripts/scan_polymarket.py --hours 4 --min-certainty 95 --min-liquidity 100
    python scripts/scan_polymarket.py --hours 24 --json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.polymarket_scanner import CertaintyScanner, format_opportunity


def main():
    parser = argparse.ArgumentParser(
        description="Scan Polymarket for high-certainty opportunities approaching resolution.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan for markets ending within 4 hours with 95%+ certainty
  python scripts/scan_polymarket.py --hours 4

  # Scan with custom parameters
  python scripts/scan_polymarket.py --hours 24 --min-certainty 90 --min-liquidity 500
  
  # Output as JSON for integration
  python scripts/scan_polymarket.py --hours 12 --json
        """
    )
    
    parser.add_argument(
        "--hours", "-H",
        type=float,
        default=4,
        help="Maximum hours until market resolution (default: 4)"
    )
    
    parser.add_argument(
        "--min-certainty", "-c",
        type=float,
        default=95,
        help="Minimum certainty percentage (default: 95, meaning 95%% Yes or 5%% No)"
    )
    
    parser.add_argument(
        "--min-liquidity", "-l",
        type=float,
        default=100,
        help="Minimum liquidity in USD (default: 100)"
    )
    
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output results as JSON"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be scanned without making API calls (for testing)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Convert certainty from percentage to decimal
    min_certainty = args.min_certainty / 100
    
    if args.dry_run:
        print("🔍 Dry run mode - would scan with parameters:")
        print(f"  • Time window: < {args.hours} hours")
        print(f"  • Min certainty: {args.min_certainty}%")
        print(f"  • Min liquidity: ${args.min_liquidity:,.0f}")
        print("\nNo API calls made.")
        return
    
    # Run the scan
    scanner = CertaintyScanner()
    opportunities = scanner.scan(
        max_hours=args.hours,
        min_certainty=min_certainty,
        min_liquidity=args.min_liquidity
    )
    
    # Output results
    if args.json:
        output = {
            "scan_parameters": {
                "max_hours": args.hours,
                "min_certainty_pct": args.min_certainty,
                "min_liquidity_usd": args.min_liquidity,
            },
            "opportunities_count": len(opportunities),
            "opportunities": [o.to_dict() for o in opportunities]
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\n🎯 Polymarket Certainty Scanner")
        print(f"   Time window: < {args.hours}h | Min certainty: {args.min_certainty}% | Min liquidity: ${args.min_liquidity:,.0f}")
        print("=" * 70)
        
        if opportunities:
            print(f"\n✅ Found {len(opportunities)} high-certainty opportunities:\n")
            for i, opp in enumerate(opportunities, 1):
                print(format_opportunity(opp, i))
            
            # Summary stats
            if len(opportunities) > 1:
                total_liq = sum(o.liquidity for o in opportunities)
                avg_apr = sum(o.apr_estimate for o in opportunities) / len(opportunities)
                print(f"\n📊 Summary:")
                print(f"   Total liquidity available: ${total_liq:,.0f}")
                print(f"   Average APR: {avg_apr:,.0f}%")
                print(f"   Soonest resolution: {min(o.hours_remaining for o in opportunities):.1f}h")
        else:
            print("\n❌ No opportunities found matching criteria.\n")
            print("Try adjusting parameters:")
            print("  • Increase --hours to widen the time window")
            print("  • Decrease --min-certainty (e.g., 90)")
            print("  • Decrease --min-liquidity (e.g., 50)")


if __name__ == "__main__":
    main()
