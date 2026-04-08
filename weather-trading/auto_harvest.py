#!/usr/bin/env python3
"""
Automated Edge Harvest Trader

Runs on a 12-hour schedule to:
1. Start WireGuard VPN (Japan)
2. Scan for conservative edge harvest opportunities (>= 0.5% return, LOW risk)
3. Wager full available liquidity on qualifying trades
4. Stop WireGuard VPN

Usage:
    python auto_harvest.py              # Dry run (default)
    python auto_harvest.py --live       # Real money
    python auto_harvest.py --no-vpn     # Skip VPN toggle (already connected)
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from config import ACTIVE_CITIES
from scanner import get_scanner
from forecaster import get_forecaster
from edge_harvest import EdgeHarvestScanner
# executor is imported lazily in execute_harvest() to avoid virtiofs locks on py_clob_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / "logs" / "auto_harvest.log"),
    ],
)
logger = logging.getLogger("auto_harvest")

# --- Configuration ---
VPN_TUNNEL_NAME = "Japan"
VPN_WAIT_SECONDS = 8          # Time to wait after VPN connect
VPN_VERIFY_HOST = "clob.polymarket.com"
MIN_RETURN_PCT = 0.5          # Minimum 0.5% return
MAX_RISK_SCORE = 4            # LOW risk only (score <= 4)
CONSERVATIVE_ONLY = True      # Only 3+ bands away
CONNECTIVITY_TIMEOUT = 15     # Seconds to wait for VPN connectivity


# --- VPN Management ---

def vpn_start() -> bool:
    """Start WireGuard Japan tunnel via macOS scutil."""
    logger.info(f"Starting WireGuard tunnel: {VPN_TUNNEL_NAME}")
    try:
        result = subprocess.run(
            ["scutil", "--nc", "start", VPN_TUNNEL_NAME],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            logger.error(f"VPN start failed: {result.stderr}")
            return False

        # Wait for tunnel to establish
        logger.info(f"Waiting {VPN_WAIT_SECONDS}s for tunnel to establish...")
        time.sleep(VPN_WAIT_SECONDS)

        # Verify connectivity
        return vpn_verify()

    except subprocess.TimeoutExpired:
        logger.error("VPN start timed out")
        return False
    except Exception as e:
        logger.error(f"VPN start error: {e}")
        return False


def vpn_stop():
    """Stop WireGuard Japan tunnel."""
    logger.info(f"Stopping WireGuard tunnel: {VPN_TUNNEL_NAME}")
    try:
        subprocess.run(
            ["scutil", "--nc", "stop", VPN_TUNNEL_NAME],
            capture_output=True, text=True, timeout=10,
        )
        logger.info("VPN stopped")
    except Exception as e:
        logger.warning(f"VPN stop error (non-fatal): {e}")


def vpn_is_connected() -> bool:
    """Check if VPN tunnel is currently connected."""
    try:
        result = subprocess.run(
            ["scutil", "--nc", "status", VPN_TUNNEL_NAME],
            capture_output=True, text=True, timeout=5,
        )
        return "Connected" in result.stdout
    except Exception:
        return False


def vpn_verify() -> bool:
    """Verify VPN is up by checking connectivity to Polymarket."""
    import urllib.request

    deadline = time.time() + CONNECTIVITY_TIMEOUT
    while time.time() < deadline:
        try:
            req = urllib.request.Request(
                f"https://{VPN_VERIFY_HOST}/",
                headers={"User-Agent": "WeatherBot/1.0"},
            )
            urllib.request.urlopen(req, timeout=5)
            logger.info("VPN connectivity verified")
            return True
        except Exception:
            time.sleep(2)

    logger.error("VPN connectivity check failed")
    return False


# --- Trading Logic ---

def get_available_balance(executor) -> float:
    """Get available USDC balance for trading."""
    if executor.dry_run:
        return 1000.0

    try:
        # Try to get real balance via CLOB API
        if executor.client:
            ok = executor.client.get_ok()
            if ok == "OK":
                # The CLOB SDK doesn't expose balance directly —
                # we'd need to query the USDC contract on Polygon.
                # For now, log that we're connected and use env-configured bankroll.
                bankroll = float(os.getenv("HARVEST_BANKROLL", "0"))
                if bankroll > 0:
                    logger.info(f"Using configured bankroll: ${bankroll:.2f}")
                    return bankroll
                logger.warning(
                    "HARVEST_BANKROLL not set in .env — set it to your available USDC balance. "
                    "Defaulting to $0 (no trades will execute)."
                )
                return 0.0
    except Exception as e:
        logger.error(f"Balance check failed: {e}")
    return 0.0


def filter_opportunities(opportunities: list) -> list:
    """Filter to only conservative, low-risk opportunities >= 0.5% return."""
    filtered = []
    for opp in opportunities:
        # Conservative only: 3+ bands away
        if CONSERVATIVE_ONLY and opp.threshold_type != "CONSERVATIVE":
            continue

        # Return threshold
        if opp.potential_return_pct < MIN_RETURN_PCT:
            continue

        # Risk filter
        if opp.risk_score > MAX_RISK_SCORE:
            continue

        # Skip if front warning is HIGH severity
        if opp.front_warning and opp.front_warning.severity == "HIGH":
            continue

        filtered.append(opp)

    return filtered


def calculate_wager(available_balance: float, num_opportunities: int, opp) -> float:
    """
    Calculate wager size. Strategy: spread full liquidity across all qualifying trades.
    Each trade gets an equal share of total available balance.
    """
    if num_opportunities == 0:
        return 0.0

    per_trade = available_balance / num_opportunities

    # Cap at 50% of reported market liquidity to avoid slippage
    if opp.liquidity and opp.liquidity > 0:
        liquidity_cap = opp.liquidity * 0.5
        per_trade = min(per_trade, liquidity_cap)

    # Floor at $1 to avoid dust trades
    if per_trade < 1.0:
        return 0.0

    return round(per_trade, 2)


def execute_harvest(dry_run: bool = True) -> dict:
    """Run one full harvest cycle. Returns summary dict."""
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "DRY_RUN" if dry_run else "LIVE",
        "markets_scanned": 0,
        "opportunities_found": 0,
        "opportunities_qualified": 0,
        "trades_attempted": 0,
        "trades_succeeded": 0,
        "total_wagered": 0.0,
        "errors": [],
    }

    # Step 1: Scan markets
    logger.info("Scanning markets...")
    try:
        market_scanner = get_scanner()
        markets = market_scanner.fetch_weather_markets(city_filter=ACTIVE_CITIES)
        summary["markets_scanned"] = len(markets)
    except Exception as e:
        logger.error(f"Market scan failed: {e}")
        summary["errors"].append(f"scan: {e}")
        return summary

    if not markets:
        logger.info("No markets found")
        return summary

    # Step 1b: Fetch forecasts for all city/date combos in discovered markets
    logger.info("Fetching forecasts...")
    forecaster = get_forecaster()
    forecasts = {}
    seen = set()
    for m in markets:
        key = (m.city_key, m.target_date)
        if key in seen:
            continue
        seen.add(key)
        fc = forecaster.get_daily_high_forecast(m.city_key, m.target_date)
        if fc:
            forecasts[key] = fc

    logger.info(f"Got forecasts for {len(forecasts)} city/date combos")

    # Step 2: Find edge harvest opportunities
    logger.info("Running edge harvest scanner...")
    scanner = EdgeHarvestScanner()
    opportunities = scanner.find_opportunities(markets, forecasts)
    summary["opportunities_found"] = len(opportunities)
    logger.info(f"Found {len(opportunities)} raw opportunities")

    # Step 3: Filter to conservative, low-risk, >0.5% return
    qualified = filter_opportunities(opportunities)
    summary["opportunities_qualified"] = len(qualified)
    logger.info(f"Qualified after filtering: {len(qualified)}")

    if not qualified:
        logger.info("No qualifying opportunities this cycle")
        return summary

    # Log qualified opportunities
    for opp in qualified:
        logger.info(
            f"  {opp.city.upper()} {opp.target_date} {opp.bucket} | "
            f"Return: {opp.potential_return_pct:.2f}% | "
            f"Risk: {opp.risk_score}/10 | Bands: {opp.bands_away}"
        )

    # Step 4: Initialize executor (lazy import to avoid virtiofs locks)
    try:
        from executor import PolymarketExecutor, OrderResult
        executor = PolymarketExecutor(dry_run=dry_run)
    except (ImportError, OSError) as e:
        logger.error(f"Executor init failed (virtiofs lock?): {e}")
        summary["errors"].append(f"executor_init: {e}")
        return summary

    available = get_available_balance(executor)
    logger.info(f"Available balance: ${available:.2f}")

    if available <= 0:
        logger.warning("No available balance — skipping trade execution")
        return summary

    # Step 5: Execute trades — full liquidity spread across opportunities
    for opp in qualified:
        wager = calculate_wager(available, len(qualified), opp)
        if wager <= 0:
            continue

        # We buy NO tokens (index 1 in clob_token_ids)
        no_token_id = opp.clob_token_ids[1] if len(opp.clob_token_ids) > 1 else None
        if not no_token_id:
            logger.warning(f"No NO token ID for {opp.city} {opp.bucket} — skipping")
            summary["errors"].append(f"missing_token: {opp.city} {opp.bucket}")
            continue

        # Price: buy NO at current ask (or estimated no_price + 1 cent buffer)
        buy_price = min(opp.no_price + 0.01, 0.99)
        shares = wager / buy_price

        logger.info(
            f"{'[DRY RUN] ' if dry_run else ''}Placing BUY NO: "
            f"{opp.city.upper()} {opp.bucket} | "
            f"${wager:.2f} ({shares:.1f} shares @ {buy_price:.3f})"
        )

        summary["trades_attempted"] += 1

        result = executor.place_order(
            token_id=no_token_id,
            side="BUY",
            size=shares,
            price=buy_price,
        )

        if result.success:
            summary["trades_succeeded"] += 1
            summary["total_wagered"] += wager
            logger.info(f"  Order placed: {result.order_id}")
        else:
            logger.error(f"  Order failed: {result.error}")
            summary["errors"].append(f"order_fail: {opp.city} {opp.bucket}: {result.error}")

    return summary


# --- Logging & Sync ---

BDC_FABRIC_ROOT = Path.home() / "Documents" / "bdc-fabric"
BDC_HARVEST_LOG = BDC_FABRIC_ROOT / "ops" / "logs" / "weather-harvest" / "harvest_runs.json"


def log_summary(summary: dict):
    """Append run summary to local log AND bdc-fabric repo log."""
    # Local log
    log_path = PROJECT_ROOT / "logs" / "harvest_runs.json"
    log_path.parent.mkdir(exist_ok=True)

    runs = []
    if log_path.exists():
        try:
            runs = json.loads(log_path.read_text())
        except Exception:
            runs = []

    runs.append(summary)
    runs = runs[-500:]
    log_path.write_text(json.dumps(runs, indent=2))

    # Also write to bdc-fabric for remote monitoring
    sync_to_bdc_fabric(runs)


def sync_to_bdc_fabric(runs: list):
    """Copy harvest log to bdc-fabric and git commit + push."""
    try:
        BDC_HARVEST_LOG.parent.mkdir(parents=True, exist_ok=True)
        BDC_HARVEST_LOG.write_text(json.dumps(runs, indent=2))
        logger.info(f"Synced harvest log to {BDC_HARVEST_LOG}")

        # Git add, commit, push from bdc-fabric
        git_env = {"GIT_DIR": str(BDC_FABRIC_ROOT / ".git"), "GIT_WORK_TREE": str(BDC_FABRIC_ROOT)}
        rel_path = "ops/logs/weather-harvest/harvest_runs.json"

        subprocess.run(
            ["git", "add", rel_path],
            cwd=str(BDC_FABRIC_ROOT), env={**os.environ, **git_env},
            capture_output=True, text=True, timeout=10,
        )

        # Check if there's actually something to commit
        status = subprocess.run(
            ["git", "diff", "--cached", "--quiet", rel_path],
            cwd=str(BDC_FABRIC_ROOT), env={**os.environ, **git_env},
            capture_output=True, timeout=10,
        )
        if status.returncode == 0:
            logger.info("No changes to commit (log unchanged)")
            return

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        commit_result = subprocess.run(
            ["git", "commit", "-m", f"auto-harvest: log update {timestamp}"],
            cwd=str(BDC_FABRIC_ROOT), env={**os.environ, **git_env},
            capture_output=True, text=True, timeout=15,
        )
        if commit_result.returncode != 0:
            logger.warning(f"Git commit failed: {commit_result.stderr}")
            return

        push_result = subprocess.run(
            ["git", "push"],
            cwd=str(BDC_FABRIC_ROOT), env={**os.environ, **git_env},
            capture_output=True, text=True, timeout=30,
        )
        if push_result.returncode != 0:
            logger.warning(f"Git push failed: {push_result.stderr}")
        else:
            logger.info("Harvest log committed and pushed to bdc-fabric")

    except Exception as e:
        logger.warning(f"bdc-fabric sync failed (non-fatal): {e}")


# --- Main ---

def main():
    parser = argparse.ArgumentParser(description="Automated Edge Harvest Trader")
    parser.add_argument("--live", action="store_true", help="Enable live trading (real money)")
    parser.add_argument("--no-vpn", action="store_true", help="Skip VPN start/stop")
    args = parser.parse_args()

    dry_run = not args.live
    use_vpn = not args.no_vpn

    logger.info("=" * 60)
    logger.info("AUTO HARVEST TRADER")
    logger.info(f"Mode: {'LIVE' if args.live else 'DRY RUN'} | VPN: {'Yes' if use_vpn else 'Skip'}")
    logger.info("=" * 60)

    if args.live:
        logger.warning("LIVE TRADING MODE — real money will be used")

    # Start VPN
    if use_vpn:
        if vpn_is_connected():
            logger.info("VPN already connected")
        else:
            if not vpn_start():
                logger.error("VPN failed to connect — aborting")
                return 1

    try:
        summary = execute_harvest(dry_run=dry_run)
    finally:
        # Always stop VPN when done
        if use_vpn:
            vpn_stop()

    # Log results
    log_summary(summary)

    logger.info("=" * 60)
    logger.info(f"RESULTS: {summary['trades_succeeded']}/{summary['trades_attempted']} trades | "
                f"${summary['total_wagered']:.2f} wagered | "
                f"{len(summary['errors'])} errors")
    logger.info("=" * 60)

    return 0 if not summary["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
