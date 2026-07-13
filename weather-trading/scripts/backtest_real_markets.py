"""
PD-193 — Real-market per-side backtest for weather trading.

Joins archived Polymarket prices (`poly_data_prices`) + observed daily highs
(`actual_temps`) + archived Open-Meteo model forecasts to produce YES/NO
win-rate tables per |edge| tier. Output is one markdown + one CSV file in
`weather-trading/reports/`. Operator reads; decides whether to flip
`EXECUTION_CONFIG.short_side_execution_enabled`.

Usage:
    python3 scripts/backtest_real_markets.py
    python3 scripts/backtest_real_markets.py --cities nyc,london --since 2025-09-01
    python3 scripts/backtest_real_markets.py --no-cache --verbose
"""

import argparse
import csv
import json
import logging
import sqlite3
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta, date as date_cls
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from config import WEATHER_CITIES, EDGE_CONFIG
from edge_calculator import bucket_probability

DB_PATH = ROOT / "weather_backtest.db"
CACHE_DIR = ROOT / ".cache" / "openmeteo"
REPORTS_DIR = ROOT / "reports"

OPEN_METEO_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
MODEL_PRIORITY = ["ecmwf_ifs04", "gfs_seamless"]
TICK_WINDOW_SECONDS = 3 * 3600  # ±3h search window around reference time
REFERENCE_HOUR_LOCAL = 12  # noon local on target day as snapshot reference
TIER_BANDS = [
    ("40%+", 0.40, float("inf")),
    ("25-40%", 0.25, 0.40),
    ("15-25%", 0.15, 0.25),
]

logger = logging.getLogger("pd193.backtest")


# -------------------------- data classes --------------------------


@dataclass
class TradeCandidate:
    city: str
    target_date: str
    bucket_low: float
    bucket_high: float
    side: str  # "YES" or "NO"
    forecast_high: float
    forecast_source: str
    entry_price: float
    our_prob: float
    edge: float
    tier: str
    actual_high: float
    won: bool


@dataclass
class TierStats:
    n: int = 0
    wins: int = 0
    sum_abs_edge: float = 0.0
    sum_entry_price: float = 0.0

    @property
    def win_rate(self) -> float:
        return self.wins / self.n if self.n else 0.0

    @property
    def mean_abs_edge(self) -> float:
        return self.sum_abs_edge / self.n if self.n else 0.0

    @property
    def mean_price(self) -> float:
        return self.sum_entry_price / self.n if self.n else 0.0


# -------------------------- forecast archive --------------------------


class ForecastArchive:
    """Open-Meteo historical-forecast archive, with on-disk cache."""

    def __init__(self, use_cache: bool = True, timeout: float = 15.0):
        self.use_cache = use_cache
        self.timeout = timeout
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._last_call = 0.0

    def _throttle(self, min_gap: float = 0.12):
        elapsed = time.time() - self._last_call
        if elapsed < min_gap:
            time.sleep(min_gap - elapsed)
        self._last_call = time.time()

    def _cache_path(self, city_key: str, target_date: str) -> Path:
        return CACHE_DIR / f"{city_key}_{target_date}.json"

    def _fetch_remote(self, city_key: str, target_date: str) -> Optional[dict]:
        city = WEATHER_CITIES.get(city_key)
        if not city:
            return None
        lat, lon = city["lat"], city["lon"]
        tz = city.get("timezone", "UTC")
        models = ",".join(MODEL_PRIORITY)
        params = (
            f"?latitude={lat}&longitude={lon}"
            f"&start_date={target_date}&end_date={target_date}"
            f"&daily=temperature_2m_max"
            f"&temperature_unit=fahrenheit"
            f"&timezone={tz}"
            f"&models={models}"
        )
        url = OPEN_METEO_URL + params
        self._throttle()
        try:
            req = Request(url, headers={"User-Agent": "pd193-backtest/1.0"})
            with urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode())
        except (URLError, HTTPError, json.JSONDecodeError) as e:
            logger.debug(f"Open-Meteo fetch failed for {city_key} {target_date}: {e}")
            return None

    def fetch(self, city_key: str, target_date: str) -> Tuple[Optional[float], Optional[str]]:
        """
        Return (forecast_high_f, model_name) for a (city, date). None if unavailable.
        """
        cache_path = self._cache_path(city_key, target_date)
        raw = None
        if self.use_cache and cache_path.exists():
            try:
                raw = json.loads(cache_path.read_text())
            except json.JSONDecodeError:
                raw = None
        if raw is None:
            raw = self._fetch_remote(city_key, target_date)
            if raw is not None and self.use_cache:
                try:
                    cache_path.write_text(json.dumps(raw))
                except OSError:
                    pass
        if raw is None:
            return None, None
        daily = raw.get("daily") or {}
        times = daily.get("time") or []
        if not times:
            return None, None
        idx = 0  # single day requested
        for model in MODEL_PRIORITY:
            key = f"temperature_2m_max_{model}"
            values = daily.get(key) or []
            if idx < len(values) and values[idx] is not None:
                return float(values[idx]), model
        return None, None


# -------------------------- db helpers --------------------------


def load_joinable_events(conn: sqlite3.Connection,
                         cities: Optional[List[str]] = None,
                         since: Optional[str] = None) -> List[Tuple[str, str, float]]:
    """Return (city_key, target_date, actual_high_f) tuples where both sides exist."""
    where = ["EXISTS (SELECT 1 FROM poly_data_prices p WHERE p.city_key=a.city_key AND p.target_date=a.date)"]
    params: List = []
    if cities:
        where.append(f"a.city_key IN ({','.join(['?'] * len(cities))})")
        params.extend(cities)
    if since:
        where.append("a.date >= ?")
        params.append(since)
    sql = f"""
        SELECT a.city_key, a.date, a.actual_high_f
        FROM actual_temps a
        WHERE {' AND '.join(where)}
        ORDER BY a.city_key, a.date
    """
    return [(r[0], r[1], r[2]) for r in conn.execute(sql, params)]


def load_buckets_for_event(conn: sqlite3.Connection,
                            city_key: str,
                            target_date: str) -> List[Tuple[float, float]]:
    """Return distinct (bucket_low, bucket_high) tuples for this event."""
    sql = """
        SELECT DISTINCT bucket_low, bucket_high
        FROM poly_data_prices
        WHERE city_key = ? AND target_date = ?
    """
    return [(r[0], r[1]) for r in conn.execute(sql, (city_key, target_date))]


def closest_price(conn: sqlite3.Connection,
                  city_key: str,
                  target_date: str,
                  bucket_low: float,
                  bucket_high: float,
                  side: str,
                  ref_unix: int) -> Optional[Tuple[float, int]]:
    """Find price+timestamp for a (bucket,side) closest to ref_unix within ±TICK_WINDOW_SECONDS."""
    lo = ref_unix - TICK_WINDOW_SECONDS
    hi = ref_unix + TICK_WINDOW_SECONDS
    sql = """
        SELECT price, timestamp
        FROM poly_data_prices
        WHERE city_key=? AND target_date=? AND bucket_low=? AND bucket_high=? AND side=?
          AND timestamp BETWEEN ? AND ?
        ORDER BY ABS(timestamp - ?) ASC
        LIMIT 1
    """
    row = conn.execute(sql, (city_key, target_date, bucket_low, bucket_high, side, lo, hi, ref_unix)).fetchone()
    if row is None:
        return None
    return float(row[0]), int(row[1])


# -------------------------- scoring --------------------------


def reference_unix(city_key: str, target_date: str) -> Optional[int]:
    """Unix UTC seconds for noon local on target_date. None if timezone unknown."""
    city = WEATHER_CITIES.get(city_key)
    if not city:
        return None
    tz_name = city.get("timezone") or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    y, m, d = [int(x) for x in target_date.split("-")]
    local_noon = datetime(y, m, d, REFERENCE_HOUR_LOCAL, 0, 0, tzinfo=tz)
    return int(local_noon.astimezone(timezone.utc).timestamp())


def in_band(actual: float, bucket_low: float, bucket_high: float) -> bool:
    """True if actual falls in [bucket_low, bucket_high), handling inf bounds."""
    lo_ok = actual >= bucket_low  # -inf always True
    hi_ok = actual < bucket_high  # +inf always True
    return lo_ok and hi_ok


def classify_tier(abs_edge: float) -> Optional[str]:
    for name, lo, hi in TIER_BANDS:
        if lo <= abs_edge < hi:
            return name
    return None


def score_event(conn: sqlite3.Connection,
                city_key: str,
                target_date: str,
                actual_high: float,
                forecast_high: float,
                forecast_source: str,
                std_dev: float,
                ref_unix: int) -> List[TradeCandidate]:
    """Produce trade candidates (both sides, all buckets with ticks in window)."""
    candidates: List[TradeCandidate] = []
    for bucket_low, bucket_high in load_buckets_for_event(conn, city_key, target_date):
        prob = bucket_probability(forecast_high, bucket_low, bucket_high, std_dev)
        yes_win = in_band(actual_high, bucket_low, bucket_high)
        for side in ("YES", "NO"):
            tick = closest_price(conn, city_key, target_date, bucket_low, bucket_high, side, ref_unix)
            if tick is None:
                continue
            entry_price, _ts = tick
            if side == "YES":
                edge = prob - entry_price
                won = yes_win
            else:
                edge = (1.0 - prob) - entry_price
                won = not yes_win
            # Only keep trades the model would actually recommend:
            # this side must be underpriced (edge > 0). Overpriced-side ticks are
            # the mirror; the model picks the OTHER side at that bucket/tick.
            if edge <= 0:
                continue
            tier = classify_tier(abs(edge))
            if tier is None:
                continue
            candidates.append(TradeCandidate(
                city=city_key,
                target_date=target_date,
                bucket_low=bucket_low,
                bucket_high=bucket_high,
                side=side,
                forecast_high=forecast_high,
                forecast_source=forecast_source,
                entry_price=entry_price,
                our_prob=prob,
                edge=edge,
                tier=tier,
                actual_high=actual_high,
                won=won,
            ))
    return candidates


# -------------------------- aggregation + emit --------------------------


def aggregate(trades: List[TradeCandidate]):
    by_side_tier: Dict[Tuple[str, str], TierStats] = defaultdict(TierStats)
    by_city_side: Dict[Tuple[str, str], TierStats] = defaultdict(TierStats)
    for t in trades:
        ks = (t.side, t.tier)
        s = by_side_tier[ks]
        s.n += 1
        s.wins += int(t.won)
        s.sum_abs_edge += abs(t.edge)
        s.sum_entry_price += t.entry_price
        kc = (t.city, t.side)
        c = by_city_side[kc]
        c.n += 1
        c.wins += int(t.won)
        c.sum_abs_edge += abs(t.edge)
        c.sum_entry_price += t.entry_price
    return by_side_tier, by_city_side


def fmt_band(lo: float, hi: float) -> str:
    if lo == float("-inf"):
        return f"≤{hi:.0f}"
    if hi == float("inf"):
        return f"≥{lo:.0f}"
    return f"{lo:.0f}-{hi:.0f}"


def write_markdown(path: Path, *, trades, by_side_tier, by_city_side,
                   cities_used, since, n_events_scored, n_events_skipped,
                   std_dev: float, generated_at: datetime):
    lines: List[str] = []
    lines.append("# PD-193 — Real-market weather backtest")
    lines.append("")
    lines.append(f"Generated: {generated_at.isoformat()}")
    lines.append(f"Dataset: `weather_backtest.db` @ `{DB_PATH}`")
    lines.append(f"Forecast source: Open-Meteo historical-forecast archive (models: {', '.join(MODEL_PRIORITY)})")
    lines.append(f"Cities: {', '.join(cities_used) if cities_used else '(all joinable)'}")
    lines.append(f"Since: {since or '(all dates)'}")
    lines.append(f"Events scored: {n_events_scored}  |  Events skipped (no forecast / no ticks): {n_events_skipped}")
    lines.append(f"Trade candidates: {len(trades)}")
    lines.append(f"Reference snapshot: noon local on target day (±3h tick search)")
    lines.append(f"std_dev: {std_dev:.2f}°F  |  Tier bands (|edge|): 15-25%, 25-40%, 40%+")
    lines.append("")
    lines.append("## Table 1 — Win rate per side × |edge| tier (model-recommended trades only)")
    lines.append("")
    lines.append("Trades listed below are ONLY those where our model flags the side as underpriced (signed edge > 0).")
    lines.append("Breakeven = mean entry price. Profitable = win rate comfortably exceeds breakeven.")
    lines.append("")
    lines.append("| Side | Tier | Trades | Wins | Win Rate | Mean \\|Edge\\| | Mean Entry Price | Margin over Breakeven |")
    lines.append("|------|------|-------:|-----:|---------:|---------------:|-----------------:|----------------------:|")
    for side in ("YES", "NO"):
        for tier_name, _, _ in TIER_BANDS:
            s = by_side_tier.get((side, tier_name), TierStats())
            if s.n == 0:
                lines.append(f"| {side} | {tier_name} | 0 | 0 | — | — | — | — |")
            else:
                margin = s.win_rate - s.mean_price
                lines.append(
                    f"| {side} | {tier_name} | {s.n} | {s.wins} | {s.win_rate*100:.1f}% | "
                    f"{s.mean_abs_edge*100:.1f}% | ${s.mean_price:.3f} | {margin*100:+.1f}pts |"
                )
    lines.append("")
    lines.append("## Table 2 — Per-city × per-side aggregate (all tiers combined)")
    lines.append("")
    lines.append("| City | Side | Trades | Wins | Win Rate |")
    lines.append("|------|------|-------:|-----:|---------:|")
    cities_sorted = sorted({k[0] for k in by_city_side})
    for city in cities_sorted:
        for side in ("YES", "NO"):
            s = by_city_side.get((city, side), TierStats())
            if s.n == 0:
                lines.append(f"| {city} | {side} | 0 | 0 | — |")
            else:
                lines.append(f"| {city} | {side} | {s.n} | {s.wins} | {s.win_rate*100:.1f}% |")
    lines.append("")
    lines.append("## Caveats & methodology")
    lines.append("")
    lines.append("- Forecast is a single daily-max snapshot from Open-Meteo archive (ECMWF IFS-04 preferred, GFS Seamless fallback). Not a multi-lead-time analysis.")
    lines.append("- Price snapshot: closest tick in `poly_data_prices` within ±3h of noon local on target day per bucket+side. Different buckets may snapshot at different exact ticks.")
    lines.append("- `poly_data_prices.price` comes from Polymarket CLOB `/prices-history` at 1-hour fidelity — last-trade or last-known-price per interval. Does NOT capture bid-ask spread. Execution at these prices assumes we could fill at the displayed price, which may overstate profitability on illiquid tail bands.")
    lines.append("- No liquidity or slippage filter applied in this pass. Live scanner requires `liquidity ≥ $100` (`ALERT_CONFIG.min_liquidity`); incorporating that filter is a v1.1 refinement.")
    lines.append("- `|edge|` tier lower bound = `EDGE_CONFIG.min_edge_scan` (0.15). Trades below the floor are not counted.")
    lines.append("- Resolution: `bucket_low ≤ actual_high_f < bucket_high` (YES). NO = not that. Infinite bounds handled.")
    lines.append("- No position sizing / P&L modeling. Win rate only.")
    lines.append("- Data skewed heavily toward NYC; per-city rows with small `n` are indicative, not decisive. See Table 2.")
    lines.append("")
    lines.append("## Decision guidance")
    lines.append("")
    lines.append("Per `weather-trading/config.py` EDGE_CONFIG, the YES-side synthetic backtest claimed 80% win rate at |edge|≥40%.")
    lines.append("For the **real-market NO-side 40%+ tier** above to justify flipping `EXECUTION_CONFIG.short_side_execution_enabled`, win rate should clear the price-implied breakeven (mean entry price, since wins pay $1 and losses cost `entry_price`).")
    lines.append("If NO-side win rate exceeds mean entry price by a reasonable margin (e.g. +10 percentage points), flag it for flag flip.")
    lines.append("If NO-side win rate is at or below mean price, keep the gate closed and revisit with a refined design (multiple lead times, liquidity filter, P&L sim).")
    lines.append("")
    path.write_text("\n".join(lines) + "\n")


def write_csv(path: Path, trades: List[TradeCandidate]):
    with path.open("w", newline="") as fp:
        w = csv.writer(fp)
        w.writerow([
            "city", "target_date", "bucket_low", "bucket_high", "side",
            "forecast_high", "forecast_source", "entry_price",
            "our_prob", "edge", "abs_edge", "tier", "actual_high", "won"
        ])
        for t in trades:
            w.writerow([
                t.city, t.target_date,
                "-inf" if t.bucket_low == float("-inf") else t.bucket_low,
                "inf" if t.bucket_high == float("inf") else t.bucket_high,
                t.side, round(t.forecast_high, 2), t.forecast_source,
                round(t.entry_price, 4), round(t.our_prob, 4), round(t.edge, 4),
                round(abs(t.edge), 4), t.tier, round(t.actual_high, 2), int(t.won),
            ])


# -------------------------- main --------------------------


def run(cities: Optional[List[str]],
        since: Optional[str],
        use_cache: bool,
        verbose: bool) -> Path:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    conn = sqlite3.connect(str(DB_PATH))
    arc = ForecastArchive(use_cache=use_cache)
    events = load_joinable_events(conn, cities=cities, since=since)
    logger.info(f"Loaded {len(events)} joinable events")

    std_dev = float(EDGE_CONFIG["std_dev_default"])
    all_trades: List[TradeCandidate] = []
    scored = 0
    skipped = 0

    for i, (city_key, target_date, actual_high) in enumerate(events):
        forecast_high, model = arc.fetch(city_key, target_date)
        if forecast_high is None:
            skipped += 1
            continue
        ref_unix = reference_unix(city_key, target_date)
        if ref_unix is None:
            skipped += 1
            continue
        trades = score_event(
            conn, city_key, target_date, actual_high,
            forecast_high, model or "?", std_dev, ref_unix
        )
        if trades:
            all_trades.extend(trades)
            scored += 1
        else:
            skipped += 1
        if (i + 1) % 50 == 0:
            logger.info(f"  progress: {i+1}/{len(events)} events, {len(all_trades)} trades so far")

    logger.info(f"Scoring complete: {scored} events scored, {skipped} skipped, {len(all_trades)} trade candidates")
    by_side_tier, by_city_side = aggregate(all_trades)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")
    md_path = REPORTS_DIR / f"pd193_backtest_{stamp}.md"
    csv_path = REPORTS_DIR / f"pd193_backtest_{stamp}.csv"

    write_markdown(
        md_path,
        trades=all_trades,
        by_side_tier=by_side_tier,
        by_city_side=by_city_side,
        cities_used=sorted({e[0] for e in events}) if cities is None else cities,
        since=since,
        n_events_scored=scored,
        n_events_skipped=skipped,
        std_dev=std_dev,
        generated_at=datetime.now(timezone.utc),
    )
    write_csv(csv_path, all_trades)

    logger.info(f"Wrote {md_path}")
    logger.info(f"Wrote {csv_path}")

    # Console summary
    print("\n=== PD-193 Real-market backtest summary ===")
    print(f"events scored: {scored}  |  trade candidates: {len(all_trades)}")
    for side in ("YES", "NO"):
        for tier_name, _, _ in TIER_BANDS:
            s = by_side_tier.get((side, tier_name), TierStats())
            if s.n:
                print(f"  {side:3} {tier_name:>6}: n={s.n:4d}  wins={s.wins:4d}  "
                      f"win_rate={s.win_rate*100:5.1f}%  "
                      f"mean_|edge|={s.mean_abs_edge*100:4.1f}%  mean_price=${s.mean_price:.3f}")
            else:
                print(f"  {side:3} {tier_name:>6}: n=0")
    print(f"\nreport: {md_path}")
    return md_path


def parse_cli() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PD-193 real-market weather backtest")
    p.add_argument("--cities", help="Comma-separated city_keys (default: all joinable)")
    p.add_argument("--since", help="Only events on or after YYYY-MM-DD")
    p.add_argument("--no-cache", action="store_true", help="Bypass Open-Meteo disk cache")
    p.add_argument("--verbose", "-v", action="store_true", help="DEBUG logging")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_cli()
    cities = [c.strip() for c in args.cities.split(",")] if args.cities else None
    run(cities=cities, since=args.since, use_cache=not args.no_cache, verbose=args.verbose)
