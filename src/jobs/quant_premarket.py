#!/usr/bin/env python3
"""
Quant Pre-Market Job

Runs daily at 03:30 HST (09:30 ET) before market open.
Produces a Pre-Market Pack with 10 candidates following quant_output_contract.

Usage:
    python -m src.jobs.quant_premarket
"""

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Configuration
ARTIFACTS_DIR = Path.home() / ".gemini/antigravity/brain"
QUANT_CONTRACTS_DIR = ARTIFACTS_DIR  # Will need session-specific path
OUTPUT_DIR = Path.home() / "Documents/001 AI Agents/AI Agent EcoSystem 2.0/data/quant_outputs"

FOCUS_ASSETS = ["XAU", "XAG", "GME", "BTC"]


def generate_run_id() -> str:
    """Generate unique run ID."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"quant_premarket_{ts}"


def generate_determinism_hash(data: dict) -> str:
    """Generate SHA256 hash of run data for reproducibility."""
    serialized = json.dumps(data, sort_keys=True)
    return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


def create_snapshot_ids() -> dict:
    """Create snapshot IDs for current run."""
    epoch = int(datetime.now(timezone.utc).timestamp())
    return {
        "market_snapshot_id": f"mkt_multi_{epoch}",
        "news_snapshot_id": f"news_multi_{epoch}",
        "policy_snapshot_id": f"pol_{epoch}"
    }


def load_narrative_traps() -> list:
    """Load active narrative traps from memory."""
    # TODO: Load from narrative_trap_memory.json
    return ["GME-MSFT-2024-001"]


def fetch_market_data() -> dict:
    """Fetch current market data for focus assets using Alpaca."""
    try:
        from src.data.alpaca_client import create_client, Snapshot
        
        client = create_client()
        
        # Separate stock and crypto symbols
        stock_symbols = ["GLD", "SLV", "GME"]  # ETF proxies for XAU/XAG
        crypto_symbols = ["BTC"]
        
        snapshot = client.get_snapshot(
            stock_symbols=stock_symbols,
            crypto_symbols=crypto_symbols,
            freshness_threshold_seconds=300.0
        )
        
        # Map to focus asset names
        result = {
            "status": "LIVE",
            "snapshot_id": snapshot.snapshot_id,
            "is_stale": snapshot.is_stale,
            "freshness_seconds": snapshot.freshness_seconds,
            "assets": {}
        }
        
        # Map ETF proxies to focus names
        symbol_map = {"GLD": "XAU", "SLV": "XAG", "GME": "GME", "BTC": "BTC"}
        for symbol, quote in snapshot.quotes.items():
            focus_name = symbol_map.get(symbol, symbol)
            result["assets"][focus_name] = {
                "price": quote.price,
                "bid": quote.bid,
                "ask": quote.ask,
                "timestamp": quote.timestamp.isoformat()
            }
        
        return result
        
    except Exception as e:
        print(f"Warning: Alpaca fetch failed: {e}")
        return {
            "status": "FALLBACK",
            "warning": f"Alpaca unavailable: {e}",
            "assets": {asset: None for asset in FOCUS_ASSETS}
        }


def apply_risk_gatekeeper(candidates: list) -> list:
    """Apply risk gatekeeper rules to candidates."""
    # TODO: Load quant_risk_gatekeeper.json and apply rules
    return candidates


def generate_premarket_pack() -> dict:
    """Generate the full pre-market pack with live market data."""
    run_id = generate_run_id()
    snapshots = create_snapshot_ids()
    traps = load_narrative_traps()
    
    # Fetch live market data
    market_data = fetch_market_data()
    print(f"[{datetime.now()}] Market data status: {market_data.get('status')}")
    
    # Update snapshot ID if we got live data
    if market_data.get("snapshot_id"):
        snapshots["market_snapshot_id"] = market_data["snapshot_id"]
    
    # Determine market status
    if market_data.get("is_stale"):
        market_status = "STALE_DATA"
        liquidity_warning = f"Data is {market_data.get('freshness_seconds', 0):.0f}s old"
    elif market_data.get("status") == "LIVE":
        market_status = "LIVE"
        liquidity_warning = None
    else:
        market_status = "FALLBACK"
        liquidity_warning = market_data.get("warning")
    
    pack = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "snapshots": snapshots,
        "market_context": {
            "trading_day": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "market_status": market_status,
            "liquidity_warning": liquidity_warning
        },
        "market_data": market_data.get("assets", {}),
        "candidates": [],
        "summary": {
            "directional_signals": 0,
            "options_defined_risk": 0,
            "no_trade_traps": 0,
            "total_candidates": 0,
            "narrative_traps_active": traps
        },
        "gatekeeper_applied": {
            "force_no_trade": market_data.get("is_stale", False),
            "rules_triggered": ["RG-005_DATA_STALE"] if market_data.get("is_stale") else [],
            "candidates_blocked": 0
        }
    }
    
    # Add determinism hash
    pack["determinism_hash"] = generate_determinism_hash(pack)
    
    return pack


def save_output(pack: dict) -> Path:
    """Save pre-market pack to output directory."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    output_file = OUTPUT_DIR / f"premarket_{date_str}.json"
    
    with open(output_file, "w") as f:
        json.dump(pack, f, indent=2)
    
    return output_file


def main():
    """Main entry point for pre-market job."""
    print(f"[{datetime.now()}] Quant Pre-Market Job Starting...")
    
    try:
        # Generate pack
        pack = generate_premarket_pack()
        
        # Save output
        output_file = save_output(pack)
        print(f"[{datetime.now()}] Output saved to: {output_file}")
        
        # Log summary
        print(f"[{datetime.now()}] Run ID: {pack['run_id']}")
        print(f"[{datetime.now()}] Candidates: {pack['summary']['total_candidates']}")
        print(f"[{datetime.now()}] Traps Active: {len(pack['summary']['narrative_traps_active'])}")
        print(f"[{datetime.now()}] Quant Pre-Market Job Complete")
        
        return 0
        
    except Exception as e:
        print(f"[{datetime.now()}] ERROR: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
