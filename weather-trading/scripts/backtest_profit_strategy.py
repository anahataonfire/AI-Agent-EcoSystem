#!/usr/bin/env python3
"""Run a chronological, fill-caveated price-band sensitivity backtest."""

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from profit_backtest import HistoricalTrade, chronological_split, sensitivity_grid


def load_trades(db_path: Path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    position_columns = {r[1] for r in conn.execute("PRAGMA table_info(positions)")}
    order_columns = {r[1] for r in conn.execute("PRAGMA table_info(orders)")}
    outcome_expr = "COALESCE(p.legacy_status,p.status)" if "legacy_status" in position_columns else "p.status"
    verified_terms = []
    if "confirmed_at" in order_columns:
        verified_terms.append("o.confirmed_at IS NOT NULL")
    if "fill_verified" in position_columns:
        verified_terms.append("COALESCE(p.fill_verified,0)=1")
    verified_expr = " OR ".join(verified_terms) or "0"
    rows = conn.execute(f"""
        SELECT p.target_date, p.entry_price, p.size, {outcome_expr} outcome_status, p.pnl,
               p.actual_cost,
               CASE WHEN ({verified_expr})
                          AND COALESCE(o.filled_amount,p.shares,0)>0
                    THEN 1 ELSE 0 END confirmed_fill
        FROM positions p
        LEFT JOIN orders o ON o.id=p.order_id
        WHERE {outcome_expr} IN ('WON','LOST') AND p.pnl IS NOT NULL
          AND p.entry_price > 0 AND p.entry_price < 1
        ORDER BY p.target_date, p.id
    """).fetchall()
    conn.close()
    return [HistoricalTrade(
        target_date=r["target_date"], price=float(r["entry_price"]),
        requested_cost=float(r["size"]), won=r["outcome_status"] == "WON",
        stored_pnl=float(r["pnl"]),
        actual_cost=float(r["actual_cost"]) if r["actual_cost"] is not None else None,
        confirmed_fill=bool(r["confirmed_fill"]),
    ) for r in rows]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=ROOT / "backend" / "weather_trading.db")
    parser.add_argument("--train-fraction", type=float, default=0.70)
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "profit_strategy_backtest.json")
    parser.add_argument("--band", action="append", default=[], metavar="FLOOR:CEILING",
                        help="Price band; repeat for sensitivity grid")
    parser.add_argument("--fee-bps", action="append", type=int, default=[],
                        help="Taker fee parameter; repeat for sensitivity grid")
    parser.add_argument("--slippage-bps", action="append", type=int, default=[],
                        help="Slippage guard; repeat for sensitivity grid")
    args = parser.parse_args()
    try:
        bands = [tuple(map(float, raw.split(":"))) for raw in args.band]
        if any(len(pair) != 2 or not 0 < pair[0] <= pair[1] < 1 for pair in bands):
            raise ValueError
    except ValueError:
        parser.error("each --band must be FLOOR:CEILING with 0 < floor <= ceiling < 1")
    grid_kwargs = {}
    if bands:
        grid_kwargs["bands"] = bands
    if args.fee_bps:
        grid_kwargs["fee_rates"] = args.fee_bps
    if args.slippage_bps:
        grid_kwargs["slippage_rates"] = args.slippage_bps
    trades = load_trades(args.db)
    verified = [t for t in trades if t.confirmed_fill and t.actual_cost is not None]
    train, test = chronological_split(trades, args.train_fraction)
    verified_train, verified_test = chronological_split(verified, args.train_fraction)
    results = (
        sensitivity_grid(train, "legacy_provisional_train", **grid_kwargs)
        + sensitivity_grid(test, "legacy_provisional_test", **grid_kwargs)
        + sensitivity_grid(verified_train, "verified_train", **grid_kwargs)
        + sensitivity_grid(verified_test, "verified_test", **grid_kwargs)
    )
    payload = {
        "source_db": str(args.db),
        "rows": len(trades),
        "legacy_provisional_rows": len(trades) - len(verified),
        "verified_rows": len(verified),
        "date_range": [min((t.target_date for t in trades), default=None),
                       max((t.target_date for t in trades), default=None)],
        "split": {
            "method": "chronological-by-unique-target-date",
            "train_fraction": args.train_fraction,
            "train_rows": len(train), "test_rows": len(test),
            "train_end": max((t.target_date for t in train), default=None),
            "test_start": min((t.target_date for t in test), default=None),
            "verified_train_rows": len(verified_train),
            "verified_test_rows": len(verified_test),
        },
        "fill_truth": {
            "confirmed_fill_rows": sum(t.confirmed_fill for t in trades),
            "actual_cost_rows": sum(t.actual_cost is not None for t in trades),
            "warning": (
                "legacy_provisional cohorts recover original WON/LOST from legacy_status when present "
                "and use requested size where actual cost is unavailable. They are hypothesis-generating. "
                "Only verified cohorts require CONFIRMED fill provenance plus actual_cost and may be used "
                "for forward profitability claims."
            ),
        },
        "sensitivity_inputs": {
            "bands": bands or "default-grid",
            "fee_bps": args.fee_bps or "default-grid",
            "slippage_bps": args.slippage_bps or "default-grid",
        },
        "results": [asdict(r) for r in results],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
