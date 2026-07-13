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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from config import ACTIVE_CITIES, EXECUTION_CONFIG, STRATEGY_CONFIG
from scanner import get_scanner
from forecaster import get_forecaster
from edge_harvest import EdgeHarvestScanner
from strategy import calculate_return_metrics, detect_complete_event_arbitrage
from identifiers import canonical_event_key
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
MIN_NO_PRICE = 0.75           # Hard floor: never buy NO below 75c (PD-147)
CONNECTIVITY_TIMEOUT = 15     # Seconds to wait for VPN connectivity


@dataclass(frozen=True)
class HarvestPolicy:
    """All strategy gates are explicit and overridable per run."""
    price_floor: float = STRATEGY_CONFIG["price_floor"]
    price_ceiling: float = STRATEGY_CONFIG["price_ceiling"]
    min_net_win_return_pct: float = STRATEGY_CONFIG["min_net_win_return_pct"]
    max_risk_score: int = STRATEGY_CONFIG["max_risk_score"]
    max_position_usd: float = STRATEGY_CONFIG["max_position_usd"]
    max_event_exposure_usd: float = STRATEGY_CONFIG["max_event_exposure_usd"]
    max_cycle_exposure_usd: float = STRATEGY_CONFIG["max_cycle_exposure_usd"]
    max_open_orders: int = STRATEGY_CONFIG["max_open_orders"]
    requote_tolerance: float = STRATEGY_CONFIG["requote_tolerance"]
    required_recommendation_status: str = STRATEGY_CONFIG["required_recommendation_status"]
    required_basis_confidence: str = STRATEGY_CONFIG["required_basis_confidence"]
    allow_open_buckets: bool = STRATEGY_CONFIG["allow_open_buckets"]
    allow_unknown_fees: bool = STRATEGY_CONFIG["allow_unknown_fees"]
    allow_outside_price_band: bool = False
    conservative_only: bool = True
    max_liquidity_fraction: float = 0.50
    max_level_depth_fraction: float = STRATEGY_CONFIG["max_level_depth_fraction"]
    order_mode: str = EXECUTION_CONFIG["default_order_mode"]
    arbitrage_min_profit_pct: float = STRATEGY_CONFIG["arbitrage_min_profit_pct"]
    arbitrage_slippage_bps: int = STRATEGY_CONFIG["arbitrage_slippage_bps"]
    arbitrage_signal_only: bool = STRATEGY_CONFIG["arbitrage_signal_only"]


DEFAULT_POLICY = HarvestPolicy()
_LOCAL_RESERVATIONS = set()
_QUARANTINE_PATH = PROJECT_ROOT / "logs" / "accepted_order_quarantine.jsonl"


def _load_quarantined_reservations() -> set:
    keys = set()
    if not _QUARANTINE_PATH.exists():
        return keys
    try:
        for line in _QUARANTINE_PATH.read_text().splitlines():
            row = json.loads(line)
            if row.get("opportunity_key") and not row.get("cleared_at"):
                keys.add(row["opportunity_key"])
    except (OSError, json.JSONDecodeError) as exc:
        logging.getLogger(__name__).error("Could not load durable order quarantine: %s", exc)
    return keys


def persist_order_quarantine(opp_key: str, event_key: str, wager: float,
                             order_id: str, error: str) -> None:
    """Durably block retries after an accepted order cannot reach SQLite."""
    _QUARANTINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "opportunity_key": opp_key,
        "event_key": event_key,
        "reserved_dollars": wager,
        "order_id": order_id,
        "error": error,
    }
    with _QUARANTINE_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


_QUARANTINED_RESERVATIONS = _load_quarantined_reservations()


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


def _entry_price(opp) -> float:
    side = getattr(opp, "recommended_side", "NO")
    book = float(getattr(opp, "best_ask_price", 0) or 0)
    return book or float(getattr(opp, "yes_price" if side == "YES" else "no_price", 0) or 0)


def opportunity_key(opp) -> str:
    market = getattr(opp, "market_id", "") or (
        f"{opp.city}:{opp.target_date}:{opp.market_type}:{opp.bucket}"
    )
    return f"{market}:{getattr(opp, 'recommended_side', 'NO')}"


def persist_live_order(result, opp, token_id: str, shares: float, wager: float,
                       price: float, opp_key: str, event_key: str) -> None:
    """Persist every accepted live order so future cycles see its reservation."""
    from database import save_order, update_order_status
    status = (getattr(result, "status", "") or "UNKNOWN").upper()
    filled = float(getattr(result, "filled_amount", 0) or 0)
    actual_cost = float(getattr(result, "actual_cost", 0) or 0)
    if actual_cost <= 0 and status in {"CONFIRMED", "PARTIALLY_CONFIRMED"}:
        actual_cost = filled * float(getattr(result, "avg_price", 0) or price)
    fees = float(getattr(result, "fees", 0) or 0)
    rebates = float(getattr(result, "rebates", 0) or 0)
    save_order({
        "id": result.order_id,
        "opportunityId": opp_key,
        "tokenId": token_id,
        "side": getattr(opp, "recommended_side", "NO"),
        "price": price,
        "sizeShares": shares,
        "sizeDollars": wager,
        "status": status,
        "filledAmount": filled,
        "avgPrice": getattr(result, "avg_price", None),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "city": opp.city,
        "bucket": opp.bucket,
        "targetDate": opp.target_date,
        "eventKey": event_key,
        "thresholdType": opp.threshold_type,
        "hoursRemaining": opp.hours_remaining,
        "orderMode": getattr(result, "order_mode", None) or "GTC",
        "reservedDollars": (
            0.0 if status in {"CONFIRMED", "CANCELED", "FAILED", "REJECTED"}
            else max(0.0, wager - actual_cost) if status == "PARTIALLY_CONFIRMED"
            else wager
        ),
        "actualCost": actual_cost,
        "fees": fees,
        "rebates": rebates,
        "rawStatus": status,
    })
    if status in {"CONFIRMED", "PARTIALLY_CONFIRMED"}:
        # save_order establishes immutable order identity/context; the canonical
        # transition stamps confirmed_at and upserts only the confirmed amount.
        update_order_status(
            result.order_id, status, filled_amount=filled,
            avg_price=float(getattr(result, "avg_price", 0) or price),
            actual_cost=actual_cost, fees=fees, rebates=rebates,
            raw_status=status,
        )


def order_fill_accounting(result, *, dry_run: bool, fallback_price: float):
    """Return (classification, actual_wager); accepted/resting is never a fill."""
    if not getattr(result, "success", False):
        return "FAILED", 0.0
    if dry_run:
        return "PAPER", 0.0
    status = (getattr(result, "status", "") or "").lower()
    filled = float(getattr(result, "filled_amount", 0) or 0)
    if status not in {"confirmed", "partially_confirmed"} or filled <= 0:
        return "UNFILLED", 0.0
    price = float(getattr(result, "avg_price", 0) or fallback_price)
    actual_cost = float(getattr(result, "actual_cost", 0) or 0)
    return "FILLED", actual_cost if actual_cost > 0 else filled * price


def select_live_order_price(*, best_ask: float, best_ask_size: float,
                            best_bid: float, best_bid_size: float,
                            order_mode: str):
    """Return (price, displayed_size, role), or None for an unsafe book."""
    if best_ask <= 0:
        return None
    if order_mode == "POST_ONLY":
        if best_bid <= 0 or best_bid >= best_ask or best_bid_size <= 0:
            return None
        return best_bid, best_bid_size, "maker"
    if best_ask_size <= 0:
        return None
    return best_ask, best_ask_size, "taker"


def count_active_orders(orders, active_statuses) -> int:
    return sum(
        1 for order in orders
        if str(order.get("status", "")).upper() in active_statuses
    )


def spendable_balance(bankroll: float, deployed: float, reserved: float) -> float:
    return max(0.0, float(bankroll) - float(deployed) - float(reserved))


def qualification_reasons(opp, policy: HarvestPolicy = DEFAULT_POLICY) -> list:
    """Return every failed canonical gate; empty means qualified."""
    reasons = []
    price = _entry_price(opp)
    authoritative_hard_bound = (
        getattr(opp, "nowcast_hard_bound", False)
        and getattr(opp, "nowcast_status", "") == "BUCKET_ELIMINATED"
        and bool(getattr(opp, "nowcast_station", None))
        and getattr(opp, "recommended_side", "NO") == "NO"
    )
    if not getattr(opp, "accepting_orders", False):
        reasons.append("market-not-accepting-orders")
    if policy.conservative_only and getattr(opp, "threshold_type", "") != "CONSERVATIVE":
        reasons.append("not-conservative")
    if not policy.allow_outside_price_band and not (policy.price_floor <= price <= policy.price_ceiling):
        reasons.append("outside-forward-test-price-band")
    if getattr(opp, "risk_score", 10) > policy.max_risk_score:
        reasons.append("risk-score")
    if getattr(opp, "front_warning", None) and opp.front_warning.severity == "HIGH":
        reasons.append("high-front-warning")
    if (not authoritative_hard_bound and policy.required_recommendation_status and
            getattr(opp, "recommendation_status", "UNCORRECTED") != policy.required_recommendation_status):
        reasons.append("insufficient-settlement-room")
    if (not authoritative_hard_bound and policy.required_basis_confidence and
            getattr(opp, "basis_confidence", "UNPROVEN") != policy.required_basis_confidence):
        reasons.append("untrusted-settlement-basis")
    if getattr(opp, "open_bucket", False) and not policy.allow_open_buckets:
        reasons.append("open-tail-bucket")
    metrics = calculate_return_metrics(
        price, fee_enabled=getattr(opp, "fee_enabled", None),
        fee_rate_bps=getattr(opp, "fee_rate_bps", None),
        liquidity_role="maker" if policy.order_mode == "POST_ONLY" else "taker",
    )
    net = metrics.net_win_return_pct
    if net is None:
        if not policy.allow_unknown_fees:
            reasons.append("unknown-fee-net-return")
    elif net < policy.min_net_win_return_pct:
        reasons.append("net-return")
    return reasons


def filter_opportunities(opportunities: list, policy: HarvestPolicy = DEFAULT_POLICY) -> list:
    """Apply the same configurable gates used immediately before execution."""
    filtered = []
    for opp in opportunities:
        if not qualification_reasons(opp, policy):
            filtered.append(opp)

    return filtered


def calculate_wager(available_balance: float, num_opportunities: int, opp,
                    policy: HarvestPolicy = DEFAULT_POLICY) -> float:
    """
    Calculate wager size. Strategy: spread full liquidity across all qualifying trades.
    Each trade gets an equal share of total available balance.
    """
    if num_opportunities == 0:
        return 0.0

    per_trade = available_balance / num_opportunities

    # Cap at 10% of available balance per trade (PD-147)
    max_per_trade = available_balance * 0.10
    per_trade = min(per_trade, max_per_trade)
    per_trade = min(per_trade, policy.max_position_usd)

    # Cap at 50% of reported market liquidity to avoid slippage
    if opp.liquidity and opp.liquidity > 0:
        liquidity_cap = opp.liquidity * policy.max_liquidity_fraction
        per_trade = min(per_trade, liquidity_cap)

    # Cap against the displayed executable level, not aggregate market
    # liquidity. Live execution repeats this using the fresh re-quote.
    level_size = float(getattr(opp, "best_ask_size", 0) or 0)
    level_price = _entry_price(opp)
    if level_size > 0 and level_price > 0:
        per_trade = min(
            per_trade, level_size * level_price * policy.max_level_depth_fraction
        )

    # Floor at $1 to avoid dust trades
    if per_trade < 1.0:
        return 0.0

    return round(per_trade, 2)


def execute_harvest(dry_run: bool = True, policy: HarvestPolicy = DEFAULT_POLICY,
                    reservation_callback=None, exposure_callback=None) -> dict:
    """Run one full harvest cycle. Returns summary dict."""
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "DRY_RUN" if dry_run else "LIVE",
        "markets_scanned": 0,
        "opportunities_found": 0,
        "opportunities_qualified": 0,
        "trades_attempted": 0,
        "trades_succeeded": 0,
        "trades_filled": 0,
        "paper_orders": 0,
        "total_wagered": 0.0,
        "arbitrage_signals": [],
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
    nowcasts = {}
    seen = set()
    for m in markets:
        key = (m.city_key, m.target_date)
        if key not in seen:
            seen.add(key)
            fc = forecaster.get_daily_high_forecast(m.city_key, m.target_date)
            if fc:
                forecasts[key] = fc
        nowcast_key = (m.city_key, m.target_date, getattr(m, "market_type", "high"))
        if nowcast_key not in nowcasts:
            nc = forecaster.fetch_station_nowcast(
                m.city_key, m.target_date,
                station_id=getattr(m, "settlement_station", None),
                resolution_source_url=getattr(m, "resolution_source_url", None),
            )
            if nc.available:
                nowcasts[nowcast_key] = nc

    logger.info(f"Got forecasts for {len(forecasts)} city/date combos")

    # Step 2: Find edge harvest opportunities
    logger.info("Running edge harvest scanner...")
    scanner = EdgeHarvestScanner()
    opportunities = scanner.find_opportunities(markets, forecasts, nowcasts=nowcasts)
    arbitrage = detect_complete_event_arbitrage(
        markets,
        min_profit_pct=policy.arbitrage_min_profit_pct,
        slippage_bps=policy.arbitrage_slippage_bps,
        allow_unknown_fees=policy.allow_unknown_fees,
        signal_only=policy.arbitrage_signal_only,
        quote_provider=lambda m: scanner._fetch_order_book(m.clob_token_ids[0]).get(
            "best_ask_price", 0
        ) if getattr(m, "clob_token_ids", (None,))[0] else 0,
    )
    summary["arbitrage_signals"] = [
        {"event_key": a.event_key, "profit_pct": round(a.profit_pct, 4),
         "guarded_cost": round(a.guarded_cost, 6), "signal_only": a.signal_only}
        for a in arbitrage
    ]
    summary["opportunities_found"] = len(opportunities)
    logger.info(f"Found {len(opportunities)} raw opportunities")

    # Step 3: Filter to conservative, low-risk, >0.5% return
    qualified = filter_opportunities(opportunities, policy)
    summary["opportunities_qualified"] = len(qualified)
    logger.info(f"Qualified after filtering: {len(qualified)}")

    if not qualified:
        logger.info("No qualifying opportunities this cycle")
        return summary

    # Log qualified opportunities
    for opp in qualified:
        logger.info(
            f"  {opp.city.upper()} {opp.target_date} {opp.bucket} | "
            f"Gross/net: {opp.gross_return_pct:.2f}%/"
            f"{opp.net_win_return_pct if opp.net_win_return_pct is not None else 'UNKNOWN'} | "
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
    if not dry_run and available > 0:
        try:
            from database import get_exposure
            deployed, reserved_global = get_exposure()
            available = spendable_balance(available, deployed, reserved_global)
            logger.info(
                f"Spendable after confirmed exposure/reservations: ${available:.2f} "
                f"(deployed=${deployed:.2f}, reserved=${reserved_global:.2f})"
            )
        except Exception as exc:
            logger.error(f"Global exposure lookup failed; failing closed: {exc}")
            summary["errors"].append(f"global_exposure: {exc}")
            return summary
    logger.info(f"Available balance: ${available:.2f}")

    if available <= 0:
        logger.warning("No available balance — skipping trade execution")
        return summary

    # Step 5: Execute trades — full liquidity spread across opportunities
    cycle_reserved = 0.0
    event_reserved = {}
    open_order_count = 0
    for opp in qualified:
        wager = calculate_wager(available, len(qualified), opp, policy)
        event_key = canonical_event_key(
            opp.city, opp.target_date, getattr(opp, "market_type", "high")
        )
        opp_key = opportunity_key(opp)
        if exposure_callback:
            opp_exposure, event_exposure, current_open_orders = exposure_callback(opp_key, event_key)
        else:
            try:
                from database import ACTIVE_ORDER_STATUSES, get_exposure, load_orders
                of, oreserved = get_exposure(opportunity_id=opp_key)
                ef, ereserved = get_exposure(event_key=event_key)
                opp_exposure, event_exposure = of + oreserved, ef + ereserved
                current_open_orders = count_active_orders(
                    load_orders(), ACTIVE_ORDER_STATUSES
                ) + len(_QUARANTINED_RESERVATIONS)
            except Exception as exc:
                logger.warning(f"Exposure lookup unavailable; failing closed: {exc}")
                summary["errors"].append(f"exposure_lookup: {exc}")
                continue
        if opp_exposure > 0:
            logger.info(f"Duplicate exposure exists for {opp_key}; skipping")
            continue
        if current_open_orders + open_order_count >= policy.max_open_orders:
            continue
        event_remaining = policy.max_event_exposure_usd - event_exposure - event_reserved.get(event_key, 0.0)
        cycle_remaining = policy.max_cycle_exposure_usd - cycle_reserved
        wager = min(wager, event_remaining, cycle_remaining)
        if wager <= 0:
            continue

        side = getattr(opp, "recommended_side", "NO")
        token_index = 0 if side == "YES" else 1
        token_id = opp.clob_token_ids[token_index] if len(opp.clob_token_ids) > token_index else None
        if not token_id:
            logger.warning(f"No {side} token ID for {opp.city} {opp.bucket} — skipping")
            summary["errors"].append(f"missing_token: {opp.city} {opp.bucket}")
            continue

        displayed_price = _entry_price(opp)
        # Mandatory live re-quote. A zero/missing live ask fails closed.
        if dry_run:
            live_ask = displayed_price
            live_ask_size = float(getattr(opp, "best_ask_size", 0) or 0)
            live_bid = float(getattr(opp, "best_bid_price", 0) or 0)
            live_bid_size = float(getattr(opp, "best_bid_size", 0) or 0)
        else:
            live_book = scanner._fetch_order_book(token_id)
            live_ask = float(live_book.get("best_ask_price", 0) or 0)
            live_ask_size = float(live_book.get("best_ask_size", 0) or 0)
            live_bid = float(live_book.get("best_bid_price", 0) or 0)
            live_bid_size = float(live_book.get("best_bid_size", 0) or 0)
            if live_ask <= 0 or abs(live_ask - displayed_price) > policy.requote_tolerance:
                logger.info(f"Re-quote rejected {opp_key}: displayed={displayed_price:.3f} live={live_ask:.3f}")
                continue
        selected_quote = select_live_order_price(
            best_ask=live_ask, best_ask_size=live_ask_size,
            best_bid=live_bid, best_bid_size=live_bid_size,
            order_mode=policy.order_mode,
        )
        if selected_quote is None:
            logger.info(f"No safe fresh displayed level for {opp_key} ({policy.order_mode})")
            continue
        buy_price, level_size, liquidity_role = selected_quote
        wager = min(wager, level_size * buy_price * policy.max_level_depth_fraction)
        if wager < 1.0:
            continue
        live_metrics = calculate_return_metrics(
            buy_price, fee_enabled=getattr(opp, "fee_enabled", None),
            fee_rate_bps=getattr(opp, "fee_rate_bps", None), liquidity_role=liquidity_role,
        )
        live_net = live_metrics.net_win_return_pct
        if (not policy.allow_outside_price_band and
                not policy.price_floor <= buy_price <= policy.price_ceiling):
            continue
        if live_net is None and not policy.allow_unknown_fees:
            continue
        if live_net is not None and live_net < policy.min_net_win_return_pct:
            continue
        shares = wager / buy_price

        logger.info(
            f"{'[DRY RUN] ' if dry_run else ''}Placing BUY {side}: "
            f"{opp.city.upper()} {opp.bucket} | "
            f"${wager:.2f} ({shares:.1f} shares @ {buy_price:.3f})"
        )

        reserved = False
        persist_failed = False
        try:
            if reservation_callback:
                reserved = bool(reservation_callback("acquire", opp_key, event_key, wager))
            else:
                reserved = opp_key not in _LOCAL_RESERVATIONS
                if reserved:
                    _LOCAL_RESERVATIONS.add(opp_key)
            if not reserved:
                logger.info(f"Reservation rejected duplicate {opp_key}")
                continue
            cycle_reserved += wager
            event_reserved[event_key] = event_reserved.get(event_key, 0.0) + wager
            open_order_count += 1
            summary["trades_attempted"] += 1
            result = executor.place_order(
                token_id=token_id, side="BUY", size=shares, price=buy_price,
                post_only=policy.order_mode == "POST_ONLY",
            )
            status = (getattr(result, "status", "") or "").lower()
            filled_amount = float(getattr(result, "filled_amount", 0) or 0)
            if not dry_run and result.success:
                try:
                    persist_live_order(result, opp, token_id, shares, wager, buy_price, opp_key, event_key)
                except Exception as exc:
                    logger.error(f"Accepted order could not be persisted: {exc}")
                    summary["errors"].append(f"order_persist: {result.order_id}: {exc}")
                    persist_failed = True
                    _QUARANTINED_RESERVATIONS.add(opp_key)
                    try:
                        persist_order_quarantine(
                            opp_key, event_key, wager, str(result.order_id), str(exc)
                        )
                    except OSError as quarantine_error:
                        logger.critical(
                            "Could not persist accepted-order quarantine: %s", quarantine_error
                        )
            classification, actual_wager = order_fill_accounting(
                result, dry_run=dry_run, fallback_price=buy_price
            )
            if classification == "PAPER":
                summary["paper_orders"] += 1
                logger.info(f"  Paper order: {result.order_id}")
            elif classification == "FILLED":
                summary["trades_succeeded"] += 1
                summary["trades_filled"] += 1
                summary["total_wagered"] += actual_wager
                logger.info(f"  Filled order: {result.order_id} ({filled_amount:.4f} shares)")
            elif result.success:
                logger.info(f"  Order accepted but unfilled ({status or 'unknown'}): {result.order_id}")
            else:
                logger.error(f"  Order failed: {result.error}")
                summary["errors"].append(f"order_fail: {opp.city} {opp.bucket}: {result.error}")
        finally:
            if reserved:
                if persist_failed:
                    if reservation_callback:
                        reservation_callback("quarantine", opp_key, event_key, wager)
                    # Keep the local reservation until an operator reconciles
                    # the accepted-but-untracked external order.
                elif reservation_callback:
                    reservation_callback("release", opp_key, event_key, wager)
                else:
                    _LOCAL_RESERVATIONS.discard(opp_key)
        if persist_failed:
            logger.error("Halting cycle after accepted order persistence failure")
            break

    return summary


# --- Logging & Sync ---

BDC_FABRIC_ROOT = Path.home() / "Documents" / "bdc-fabric"
BDC_HARVEST_LOG = BDC_FABRIC_ROOT / "ops" / "logs" / "weather-harvest" / "harvest_runs.json"


def log_summary(summary: dict, *, sync_external: bool = False):
    """Append locally; external bdc-fabric mutation requires explicit opt-in."""
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

    if sync_external:
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
    parser.add_argument("--sync-bdc-fabric", action="store_true",
                        help="Commit/push live-run summary to bdc-fabric (never in dry-run)")
    parser.add_argument("--price-floor", type=float, default=DEFAULT_POLICY.price_floor)
    parser.add_argument("--price-ceiling", type=float, default=DEFAULT_POLICY.price_ceiling)
    parser.add_argument("--min-net-win-return-pct", "--min-net-return-pct", type=float,
                        dest="min_net_win_return_pct",
                        default=DEFAULT_POLICY.min_net_win_return_pct,
                        help="Minimum conditional fee-net return if the share wins")
    parser.add_argument("--max-risk-score", type=int, default=DEFAULT_POLICY.max_risk_score)
    parser.add_argument("--max-position-usd", type=float, default=DEFAULT_POLICY.max_position_usd)
    parser.add_argument("--max-event-exposure-usd", type=float, default=DEFAULT_POLICY.max_event_exposure_usd)
    parser.add_argument("--max-cycle-exposure-usd", type=float, default=DEFAULT_POLICY.max_cycle_exposure_usd)
    parser.add_argument("--max-open-orders", type=int, default=DEFAULT_POLICY.max_open_orders)
    parser.add_argument("--requote-tolerance", type=float, default=DEFAULT_POLICY.requote_tolerance)
    parser.add_argument("--max-liquidity-fraction", type=float, default=DEFAULT_POLICY.max_liquidity_fraction)
    parser.add_argument("--max-level-depth-fraction", type=float, default=DEFAULT_POLICY.max_level_depth_fraction)
    parser.add_argument("--order-mode", choices=("GTC", "POST_ONLY"),
                        default=DEFAULT_POLICY.order_mode)
    parser.add_argument("--arbitrage-min-profit-pct", type=float,
                        default=DEFAULT_POLICY.arbitrage_min_profit_pct)
    parser.add_argument("--arbitrage-slippage-bps", type=int,
                        default=DEFAULT_POLICY.arbitrage_slippage_bps)
    parser.add_argument("--arbitrage-signal-only", action=argparse.BooleanOptionalAction,
                        default=DEFAULT_POLICY.arbitrage_signal_only,
                        help="Keep complete-set arbitrage informational; never auto-executed")
    parser.add_argument("--required-recommendation-status", default=DEFAULT_POLICY.required_recommendation_status)
    parser.add_argument("--required-basis-confidence", default=DEFAULT_POLICY.required_basis_confidence)
    parser.add_argument("--allow-open-buckets", action=argparse.BooleanOptionalAction,
                        default=DEFAULT_POLICY.allow_open_buckets)
    parser.add_argument("--allow-unknown-fees", action=argparse.BooleanOptionalAction,
                        default=DEFAULT_POLICY.allow_unknown_fees)
    parser.add_argument("--allow-outside-price-band", action=argparse.BooleanOptionalAction,
                        default=DEFAULT_POLICY.allow_outside_price_band)
    parser.add_argument("--conservative-only", action=argparse.BooleanOptionalAction,
                        default=DEFAULT_POLICY.conservative_only)
    parser.add_argument("--allow-no-room", action="store_true",
                        help="Override the default ROOM requirement")
    parser.add_argument("--allow-untrusted-basis", action="store_true",
                        help="Override the default TRUSTED basis requirement")
    args = parser.parse_args()

    policy = HarvestPolicy(
        price_floor=args.price_floor, price_ceiling=args.price_ceiling,
        min_net_win_return_pct=args.min_net_win_return_pct, max_risk_score=args.max_risk_score,
        max_position_usd=args.max_position_usd,
        max_event_exposure_usd=args.max_event_exposure_usd,
        max_cycle_exposure_usd=args.max_cycle_exposure_usd,
        max_open_orders=args.max_open_orders, requote_tolerance=args.requote_tolerance,
        required_recommendation_status=("" if args.allow_no_room else args.required_recommendation_status),
        required_basis_confidence=("" if args.allow_untrusted_basis else args.required_basis_confidence),
        allow_open_buckets=args.allow_open_buckets,
        allow_unknown_fees=args.allow_unknown_fees,
        allow_outside_price_band=args.allow_outside_price_band,
        conservative_only=args.conservative_only,
        max_liquidity_fraction=args.max_liquidity_fraction,
        max_level_depth_fraction=args.max_level_depth_fraction,
        order_mode=args.order_mode,
        arbitrage_min_profit_pct=args.arbitrage_min_profit_pct,
        arbitrage_slippage_bps=args.arbitrage_slippage_bps,
        arbitrage_signal_only=args.arbitrage_signal_only,
    )
    if not 0 < policy.price_floor <= policy.price_ceiling < 1:
        parser.error("price band must satisfy 0 < floor <= ceiling < 1")
    if not 0 < policy.max_level_depth_fraction <= 1:
        parser.error("max level depth fraction must be in (0, 1]")

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
        summary = execute_harvest(dry_run=dry_run, policy=policy)
    finally:
        # Always stop VPN when done
        if use_vpn:
            vpn_stop()

    # Log results
    log_summary(summary, sync_external=bool(args.live and args.sync_bdc_fabric))

    logger.info("=" * 60)
    logger.info(f"RESULTS: {summary['trades_succeeded']}/{summary['trades_attempted']} trades | "
                f"${summary['total_wagered']:.2f} wagered | "
                f"{len(summary['errors'])} errors")
    logger.info("=" * 60)

    return 0 if not summary["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
