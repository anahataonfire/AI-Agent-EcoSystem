from types import SimpleNamespace

import pytest
import auto_harvest

from auto_harvest import (
    HarvestPolicy, order_fill_accounting, persist_live_order,
    qualification_reasons, select_live_order_price, count_active_orders,
    spendable_balance,
)
from edge_harvest import EdgeHarvestScanner
from forecaster import DailyForecast, StationNowcast, WeatherForecaster
from profit_backtest import HistoricalTrade, chronological_split, evaluate_band
from scanner import WeatherMarket, _parse_fee_metadata, _parse_resolution_station
from strategy import (
    calculate_return_metrics,
    detect_complete_event_arbitrage,
    has_complete_bucket_coverage,
)


def test_dynamic_taker_fee_formula_at_midpoint_and_ninety_cents():
    mid = calculate_return_metrics(.5, fee_enabled=True, fee_rate_bps=500)
    high = calculate_return_metrics(.9, fee_enabled=True, fee_rate_bps=500)
    assert mid.estimated_fee_per_share == pytest.approx(.0125)
    assert high.estimated_fee_per_share == pytest.approx(.0045)
    assert high.net_win_return_pct == pytest.approx((.1 - .0045) / .9 * 100)


def test_maker_fee_is_zero_and_unknown_taker_stays_unknown():
    maker = calculate_return_metrics(.9, fee_enabled=True, fee_rate_bps=None,
                                     liquidity_role="post-only")
    taker = calculate_return_metrics(.9, fee_enabled=True, fee_rate_bps=None)
    assert maker.fee_known and maker.estimated_fee_per_share == 0
    assert taker.net_win_return_pct is None and not taker.fee_known


def test_accepted_order_quarantine_survives_process_restart(tmp_path, monkeypatch):
    path = tmp_path / "quarantine.jsonl"
    monkeypatch.setattr(auto_harvest, "_QUARANTINE_PATH", path)
    auto_harvest.persist_order_quarantine("opp", "event", 9, "order-1", "db down")
    assert auto_harvest._load_quarantined_reservations() == {"opp"}


@pytest.mark.parametrize("market, expected", [
    ({"feesEnabled": False}, (False, 0, "GAMMA_KNOWN_ZERO")),
    ({"feesEnabled": True, "feeRateBps": 250}, (True, 250, "GAMMA_MARKET_RATE")),
    ({"feesEnabled": True, "baseFee": .05}, (True, 500, "GAMMA_MARKET_RATE")),
    ({"feesEnabled": True}, (True, 500, "WEATHER_CATEGORY_DEFAULT")),
    ({}, (None, None, "UNKNOWN")),
])
def test_fee_metadata_provenance(market, expected):
    assert _parse_fee_metadata(market) == expected


def _market(mid, lo, hi, price, *, fee=False):
    return SimpleNamespace(
        market_id=mid, city_key="nyc", target_date="2026-07-11", market_type="high",
        bucket_low=lo, bucket_high=hi, bucket_unit="F", yes_price=price,
        accepting_orders=True, clob_token_ids=(f"yes-{mid}", f"no-{mid}"),
        fee_enabled=fee, fee_rate_bps=0 if not fee else 500,
        event_id="event-1",
    )


def test_complete_event_arbitrage_requires_both_tails_and_contiguous_buckets():
    markets = [_market("a", None, 70, .30), _market("b", 71, 72, .30),
               _market("c", 73, None, .30)]
    assert has_complete_bucket_coverage(markets) == (True, "complete")
    signals = detect_complete_event_arbitrage(markets, min_profit_pct=1,
                                              slippage_bps=0)
    assert len(signals) == 1
    assert signals[0].signal_only
    assert signals[0].profit_per_set == pytest.approx(.1)
    markets[1].bucket_low = 72
    assert not has_complete_bucket_coverage(markets)[0]


def test_complete_event_arbitrage_rejects_missing_or_mixed_event_identity():
    markets = [_market("a", None, 70, .30), _market("b", 71, 72, .30),
               _market("c", 73, None, .30)]
    markets[0].event_id = ""
    assert detect_complete_event_arbitrage(markets, min_profit_pct=1, slippage_bps=0) == []
    markets[0].event_id = "different-event"
    assert detect_complete_event_arbitrage(markets, min_profit_pct=1, slippage_bps=0) == []


def test_low_market_front_warning_uses_low_models():
    scanner = EdgeHarvestScanner()
    forecast = SimpleNamespace(
        ecmwf_high=80, gfs_high=80, ecmwf_low=45, gfs_low=54, confidence=.9,
    )
    warnings = scanner.detect_front_warnings("nyc", "2026-07-11", forecast,
                                             market_type="low")
    assert warnings[0].severity == "HIGH"
    assert warnings[0].model_spread == 9


def test_authoritative_hard_bound_can_replace_forecast_basis_gate():
    opp = SimpleNamespace(
        accepting_orders=True, threshold_type="CONSERVATIVE", best_ask_price=.92,
        no_price=.92, recommended_side="NO", risk_score=2, front_warning=None,
        recommendation_status="UNCORRECTED", basis_confidence="UNPROVEN",
        open_bucket=False, net_win_return_pct=5.0,
        fee_enabled=False, fee_rate_bps=0,
        nowcast_hard_bound=True, nowcast_status="BUCKET_ELIMINATED",
        nowcast_station="KNYC",
    )
    assert qualification_reasons(opp, HarvestPolicy()) == []
    opp.nowcast_station = None
    reasons = qualification_reasons(opp, HarvestPolicy())
    assert "insufficient-settlement-room" in reasons
    assert "untrusted-settlement-basis" in reasons


def test_resting_order_never_counts_as_filled_wager():
    live = SimpleNamespace(success=True, status="live", filled_amount=0, avg_price=0)
    matched = SimpleNamespace(success=True, status="matched", filled_amount=10, avg_price=.91)
    assert order_fill_accounting(live, dry_run=False, fallback_price=.92) == ("UNFILLED", 0)
    confirmed = SimpleNamespace(success=True, status="confirmed", filled_amount=10, avg_price=.91)
    partial = SimpleNamespace(success=True, status="partially_confirmed", filled_amount=5,
                              avg_price=.91, actual_cost=4.6)
    assert order_fill_accounting(matched, dry_run=False, fallback_price=.92) == ("UNFILLED", 0)
    assert order_fill_accounting(confirmed, dry_run=False, fallback_price=.92) == ("FILLED", 9.1)
    assert order_fill_accounting(partial, dry_run=False, fallback_price=.92) == ("FILLED", 4.6)


def test_matched_persistence_keeps_full_reservation(monkeypatch):
    saved = []
    monkeypatch.setattr("database.save_order", saved.append)
    result = SimpleNamespace(order_id="o1", status="matched", filled_amount=10,
                             avg_price=.91, order_mode="POST_ONLY")
    opp = SimpleNamespace(recommended_side="NO", city="nyc", bucket="70-71F",
                          target_date="2026-07-11", threshold_type="CONSERVATIVE",
                          hours_remaining=8)
    persist_live_order(result, opp, "token", 10, 9.1, .91, "opp", "event")
    assert saved[0]["reservedDollars"] == 9.1
    assert saved[0]["orderMode"] == "POST_ONLY"


def test_immediate_confirmed_order_runs_canonical_transition_with_money(monkeypatch):
    saved, transitioned = [], []
    monkeypatch.setattr("database.save_order", saved.append)
    monkeypatch.setattr("database.update_order_status",
                        lambda *args, **kwargs: transitioned.append((args, kwargs)))
    result = SimpleNamespace(order_id="o2", status="confirmed", filled_amount=10,
                             avg_price=.91, actual_cost=9.1, fees=.04, rebates=.01,
                             order_mode="GTC")
    opp = SimpleNamespace(recommended_side="NO", city="nyc", bucket="70-71F",
                          target_date="2026-07-11", threshold_type="CONSERVATIVE",
                          hours_remaining=8)
    persist_live_order(result, opp, "token", 10, 9.1, .91, "opp", "event")
    assert saved[0]["fees"] == .04 and saved[0]["rebates"] == .01
    assert transitioned[0][0] == ("o2", "CONFIRMED")
    assert transitioned[0][1]["actual_cost"] == 9.1


def test_post_only_price_joins_bid_and_never_crosses_ask():
    assert select_live_order_price(best_ask=.93, best_ask_size=50,
                                   best_bid=.91, best_bid_size=20,
                                   order_mode="POST_ONLY") == (.91, 20, "maker")
    assert select_live_order_price(best_ask=.92, best_ask_size=50,
                                   best_bid=.92, best_bid_size=20,
                                   order_mode="POST_ONLY") is None


def test_open_order_gate_counts_persisted_active_statuses():
    orders = [{"status": "LIVE"}, {"status": "MATCHED"},
              {"status": "CONFIRMED"}, {"status": "CANCELED"}]
    assert count_active_orders(orders, {"LIVE", "MATCHED"}) == 2
    assert spendable_balance(1000, 700, 250) == 50
    assert spendable_balance(1000, 700, 400) == 0


def test_accepted_unpersisted_order_quarantines_and_halts(monkeypatch):
    import auto_harvest
    import executor as executor_module

    market = _market("m1", None, 70, .08)
    market.no_price = .92
    market.city = "New York City"
    market.end_time = SimpleNamespace()
    opps = []
    for mid in ("m1", "m2"):
        opps.append(SimpleNamespace(
            city="nyc", target_date="2026-07-11", market_type="high", bucket="<=70F",
            market_id=mid, event_key="nyc:2026-07-11:high", recommended_side="NO",
            accepting_orders=True, threshold_type="CONSERVATIVE", best_ask_price=.92,
            best_ask_size=100, best_bid_price=.91, best_bid_size=100,
            no_price=.92, yes_price=.08, risk_score=2, front_warning=None,
            recommendation_status="ROOM", basis_confidence="TRUSTED", open_bucket=False,
            fee_enabled=False, fee_rate_bps=0, net_win_return_pct=8,
            gross_return_pct=8, clob_token_ids=(f"y-{mid}", f"n-{mid}"),
            liquidity=1000, hours_remaining=8, bands_away=5,
        ))

    class MarketScanner:
        def fetch_weather_markets(self, city_filter=None):
            return [market]

    class Forecaster:
        def get_daily_high_forecast(self, *_):
            return object()
        def fetch_station_nowcast(self, *_, **__):
            return SimpleNamespace(available=False)

    class EdgeScanner:
        def find_opportunities(self, *_, **__):
            return opps
        def _fetch_order_book(self, _token):
            return {"best_ask_price": .92, "best_ask_size": 100,
                    "best_bid_price": .91, "best_bid_size": 100}

    placed = []
    class Executor:
        client = object()
        def __init__(self, dry_run=False):
            pass
        def place_order(self, **kwargs):
            placed.append(kwargs)
            return SimpleNamespace(success=True, order_id="external-1", status="live",
                                   filled_amount=0, avg_price=0, order_mode="GTC")

    monkeypatch.setattr(auto_harvest, "get_scanner", lambda: MarketScanner())
    monkeypatch.setattr(auto_harvest, "get_forecaster", lambda: Forecaster())
    monkeypatch.setattr(auto_harvest, "EdgeHarvestScanner", EdgeScanner)
    monkeypatch.setattr(auto_harvest, "get_available_balance", lambda _: 100)
    monkeypatch.setattr(executor_module, "PolymarketExecutor", Executor)
    monkeypatch.setattr("database.get_exposure", lambda **_: (0, 0))
    monkeypatch.setattr("database.load_orders", lambda: [])
    monkeypatch.setattr(auto_harvest, "persist_live_order",
                        lambda *_, **__: (_ for _ in ()).throw(RuntimeError("disk")))
    auto_harvest._LOCAL_RESERVATIONS.clear()
    auto_harvest._QUARANTINED_RESERVATIONS.clear()
    summary = auto_harvest.execute_harvest(dry_run=False)
    assert len(placed) == 1
    assert "m1:NO" in auto_harvest._QUARANTINED_RESERVATIONS
    assert any("order_persist" in e for e in summary["errors"])
    auto_harvest._LOCAL_RESERVATIONS.clear()
    auto_harvest._QUARANTINED_RESERVATIONS.clear()


def test_post_only_uses_known_zero_maker_fee_for_qualification():
    opp = SimpleNamespace(
        accepting_orders=True, threshold_type="CONSERVATIVE", best_ask_price=.92,
        no_price=.92, recommended_side="NO", risk_score=2, front_warning=None,
        recommendation_status="ROOM", basis_confidence="TRUSTED", open_bucket=False,
        fee_enabled=True, fee_rate_bps=None, nowcast_hard_bound=False,
    )
    assert "unknown-fee-net-return" in qualification_reasons(opp, HarvestPolicy())
    maker = HarvestPolicy(order_mode="POST_ONLY")
    assert "unknown-fee-net-return" not in qualification_reasons(opp, maker)


def test_every_new_strategy_gate_is_constructible_as_a_run_override():
    policy = HarvestPolicy(
        price_floor=.80, price_ceiling=.99, min_net_win_return_pct=-1,
        max_risk_score=10, max_position_usd=999, max_event_exposure_usd=999,
        max_cycle_exposure_usd=1999, max_open_orders=99, requote_tolerance=.10,
        required_recommendation_status="", required_basis_confidence="",
        allow_open_buckets=True, allow_unknown_fees=True,
        allow_outside_price_band=True, conservative_only=False,
        max_liquidity_fraction=1, max_level_depth_fraction=1,
        order_mode="POST_ONLY", arbitrage_min_profit_pct=-1,
        arbitrage_slippage_bps=0, arbitrage_signal_only=False,
    )
    assert policy.order_mode == "POST_ONLY"
    assert policy.allow_open_buckets and policy.allow_outside_price_band


def test_local_logging_does_not_sync_external_without_opt_in(monkeypatch, tmp_path):
    import auto_harvest
    synced = []
    monkeypatch.setattr(auto_harvest, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(auto_harvest, "sync_to_bdc_fabric", synced.append)
    auto_harvest.log_summary({"mode": "DRY_RUN"})
    assert synced == []
    assert (tmp_path / "logs" / "harvest_runs.json").exists()


def test_time_split_keeps_dates_disjoint_and_fee_sensitivity_is_applied():
    trades = [
        HistoricalTrade("2026-01-01", .92, 100, True, 8.0),
        HistoricalTrade("2026-01-02", .92, 100, False, -100),
        HistoricalTrade("2026-01-03", .92, 100, True, 8.0),
        HistoricalTrade("2026-01-04", .92, 100, True, 8.0),
    ]
    train, test = chronological_split(trades, .5)
    assert {t.target_date for t in train}.isdisjoint({t.target_date for t in test})
    no_fee = evaluate_band(test, .9, .95, cohort="test", fee_rate_bps=0, slippage_bps=0)
    fee = evaluate_band(test, .9, .95, cohort="test", fee_rate_bps=500, slippage_bps=20)
    assert fee.modeled_pnl < no_fee.modeled_pnl


def test_station_nowcast_fails_honest_without_explicit_station():
    forecaster = WeatherForecaster()
    result = forecaster.fetch_station_nowcast("london", "2026-07-11")
    assert not result.available
    assert result.reason == "no-authoritative-nws-station"


def test_resolution_station_provenance_distinguishes_wunderground_from_nws():
    wu = _parse_resolution_station({}, {"resolutionSource":
        "https://www.wunderground.com/history/daily/us/ny/new-york-city/KLGA"})
    nws = _parse_resolution_station({}, {"description":
        "source https://www.weather.gov/wrh/timeseries?site=LLBG for this market"})
    assert wu[1:] == ("KLGA", "WUNDERGROUND")
    assert nws[1:] == ("LLBG", "NWS_OBSERVATIONS")


def test_missing_accepting_orders_metadata_fails_closed():
    from datetime import datetime, timezone
    market = WeatherMarket(
        market_id="m", question="q", city="NYC", city_key="nyc",
        target_date="2026-07-11", bucket_low=70, bucket_high=71,
        bucket_unit="F", yes_price=.5, no_price=.5, liquidity=1,
        volume_24h=1, end_time=datetime.now(timezone.utc), market_url="",
    )
    assert market.accepting_orders is False


def test_open_meteo_daily_carries_per_model_lows(monkeypatch):
    forecaster = WeatherForecaster()
    monkeypatch.setattr(forecaster, "_make_request", lambda _url: {"daily": {
        "time": ["2026-07-11"],
        "temperature_2m_max_best_match": [25.0],
        "temperature_2m_min_best_match": [15.0],
        "temperature_2m_max_ecmwf_ifs025": [24.0],
        "temperature_2m_max_gfs_seamless": [26.0],
        "temperature_2m_min_ecmwf_ifs025": [13.0],
        "temperature_2m_min_gfs_seamless": [17.0],
    }})
    day = forecaster.fetch_open_meteo_daily("nyc")["2026-07-11"]
    assert day["ecmwf_low_f"] == pytest.approx(55.4)
    assert day["gfs_low_f"] == pytest.approx(62.6)


def test_low_hard_bound_direction():
    scanner = EdgeHarvestScanner()
    nc = StationNowcast("nyc", "2026-07-11", "KNYC", "NWS_OBSERVATIONS", True,
                        observed_high_f=80, observed_low_f=60, observation_count=10)
    status, observed, station, hard = scanner._nowcast_bound(nc, "low", "F", 61, 62)
    assert (status, station, hard) == ("BUCKET_ELIMINATED", "KNYC", True)
    assert observed == 60
