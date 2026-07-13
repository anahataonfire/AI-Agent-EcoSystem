"""Fill-caveated historical evaluation for price-band strategy policies."""

from dataclasses import asdict, dataclass
from datetime import date
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class HistoricalTrade:
    target_date: str
    price: float
    requested_cost: float
    won: bool
    stored_pnl: float
    actual_cost: float | None = None
    confirmed_fill: bool = False


@dataclass(frozen=True)
class BacktestResult:
    cohort: str
    price_floor: float
    price_ceiling: float
    trades: int
    wins: int
    requested_cost: float
    modeled_pnl: float
    roi_pct: float | None
    fee_rate_bps: int
    slippage_bps: int
    confirmed_fill_rows: int


def chronological_split(trades: Sequence[HistoricalTrade], train_fraction: float = 0.70):
    """Split by unique target date so one event date cannot leak across cohorts."""
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction must be between zero and one")
    dates = sorted({t.target_date for t in trades})
    if len(dates) < 2:
        return list(trades), []
    cut = max(1, min(len(dates) - 1, int(len(dates) * train_fraction)))
    train_dates = set(dates[:cut])
    return ([t for t in trades if t.target_date in train_dates],
            [t for t in trades if t.target_date not in train_dates])


def evaluate_band(
    trades: Iterable[HistoricalTrade],
    price_floor: float,
    price_ceiling: float,
    *,
    cohort: str,
    fee_rate_bps: int = 500,
    slippage_bps: int = 20,
) -> BacktestResult:
    """Evaluate a band using requested cost and explicit current-fee sensitivity.

    Fee model matches the platform formula for takers: shares * rate*p*(1-p).
    Slippage is a conservative cost haircut. Historical requested cost is used
    only when actual confirmed cost is unavailable and is disclosed in results.
    """
    selected = [t for t in trades if price_floor <= t.price <= price_ceiling]
    cost = sum(t.actual_cost if t.actual_cost is not None else t.requested_cost for t in selected)
    pnl = 0.0
    for trade in selected:
        trade_cost = trade.actual_cost if trade.actual_cost is not None else trade.requested_cost
        shares = trade_cost / trade.price
        gross = shares * (1.0 - trade.price) if trade.won else -trade_cost
        fee = shares * (fee_rate_bps / 10_000.0) * trade.price * (1.0 - trade.price)
        slippage = trade_cost * slippage_bps / 10_000.0
        pnl += gross - fee - slippage
    return BacktestResult(
        cohort=cohort, price_floor=price_floor, price_ceiling=price_ceiling,
        trades=len(selected), wins=sum(t.won for t in selected),
        requested_cost=round(cost, 4), modeled_pnl=round(pnl, 4),
        roi_pct=round(pnl / cost * 100.0, 4) if cost else None,
        fee_rate_bps=fee_rate_bps, slippage_bps=slippage_bps,
        confirmed_fill_rows=sum(t.confirmed_fill for t in selected),
    )


def sensitivity_grid(
    trades: Sequence[HistoricalTrade], cohort: str, *,
    bands=((0.85, 0.95), (0.90, 0.93), (0.90, 0.95), (0.90, 0.97), (0.95, 0.99)),
    fee_rates=(0, 500),
    slippage_rates=(0, 20, 50),
) -> List[BacktestResult]:
    results = []
    for floor, ceiling in bands:
        for fee in fee_rates:
            for slippage in slippage_rates:
                results.append(evaluate_band(
                    trades, floor, ceiling, cohort=cohort,
                    fee_rate_bps=fee, slippage_bps=slippage,
                ))
    return results
