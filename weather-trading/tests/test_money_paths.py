import importlib
import importlib.util
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

import database
from executor import OrderResult, OrderSnapshot, PolymarketExecutor, normalize_trade_event


@pytest.fixture
def money_db(tmp_path, monkeypatch):
    path = tmp_path / "money.db"
    monkeypatch.setattr(database, "DB_PATH", str(path))
    database.init_db()
    return path


def order(order_id="o1", status="LIVE", opportunity="opp-1", event="chicago::2026-07-12",
          shares=100, dollars=90, filled=0, reserved=None):
    return {
        "id": order_id, "positionId": None, "opportunityId": opportunity,
        "tokenId": "token", "city": "chicago", "bucket": "80-81F",
        "targetDate": "2026-07-12", "eventKey": event, "side": "YES",
        "price": 0.9, "sizeShares": shares, "sizeDollars": dollars,
        "status": status, "filledAmount": filled, "avgPrice": 0.9,
        "reservedDollars": dollars if reserved is None else reserved,
        "orderMode": "POST_ONLY", "createdAt": "2026-07-11T00:00:00+00:00",
    }


def test_migration_is_additive_idempotent_and_preserves_rows(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE positions (id TEXT PRIMARY KEY, opportunity_id TEXT, order_id TEXT,
          city TEXT NOT NULL, bucket TEXT NOT NULL, target_date TEXT NOT NULL, side TEXT NOT NULL,
          entry_price REAL NOT NULL, shares REAL NOT NULL DEFAULT 0, size REAL NOT NULL,
          current_price REAL, unrealized_pnl REAL DEFAULT 0, status TEXT DEFAULT 'OPEN',
          threshold_type TEXT, hours_remaining REAL, opened_at TEXT NOT NULL, closed_at TEXT, pnl REAL);
        CREATE TABLE orders (id TEXT PRIMARY KEY, position_id TEXT, opportunity_id TEXT,
          token_id TEXT, side TEXT NOT NULL, price REAL NOT NULL, size_shares REAL NOT NULL,
          size_dollars REAL NOT NULL, status TEXT DEFAULT 'PENDING', filled_amount REAL DEFAULT 0,
          avg_price REAL, created_at TEXT NOT NULL, updated_at TEXT, error TEXT);
        INSERT INTO orders VALUES ('legacy',NULL,'opp','tok','YES',.9,10,9,'LIVE',0,NULL,'now',NULL,NULL);
        INSERT INTO positions VALUES ('legacy-pos','opp','legacy','chicago','80-81F','2026-07-01',
          'YES',.9,10,9,NULL,0,'OPEN',NULL,NULL,'now',NULL,NULL);
    """)
    con.commit(); con.close()
    monkeypatch.setattr(database, "DB_PATH", str(path))
    database.init_db(); database.init_db()
    con = sqlite3.connect(path)
    assert con.execute("SELECT id FROM orders").fetchall() == [("legacy",)]
    assert con.execute("SELECT id,status FROM positions").fetchall() == [("legacy-pos", "UNCONFIRMED_LEGACY")]
    columns = {r[1] for r in con.execute("PRAGMA table_info(orders)")}
    assert {"reserved_dollars", "actual_cost", "order_mode", "event_key"} <= columns


def test_migration_quarantines_unverified_realized_history_but_preserves_outcome(tmp_path, monkeypatch):
    path = tmp_path / "legacy-realized.db"
    monkeypatch.setattr(database, "DB_PATH", str(path))
    database.init_db()
    with database.get_connection() as con:
        con.execute("""INSERT INTO positions
          (id,city,bucket,target_date,side,entry_price,shares,size,status,opened_at,pnl)
          VALUES ('legacy-win','nyc','80F','2026-01-01','YES',.9,10,9,'WON','old',1)""")
    database.init_db()
    row = database.load_positions()[0]
    assert row["status"] == "UNCONFIRMED_LEGACY"
    assert row["legacyStatus"] == "WON"
    assert row["pnl"] == 1
    assert row["fillVerified"] is False


def test_resting_and_matched_orders_are_reservations_not_positions(money_db):
    database.save_order(order())
    assert database.load_positions() == []
    assert database.get_exposure(opportunity_id="opp-1") == (0, 90)
    database.update_order_status("o1", "MATCHED", filled_amount=100, avg_price=.9)
    assert database.load_positions() == []
    assert database.get_exposure(opportunity_id="opp-1") == (0, 90)


def test_trade_events_aggregate_distinct_confirmations_idempotently(money_db):
    database.save_order(order())
    lifecycle = importlib.import_module("order_lifecycle")
    lifecycle.apply_authenticated_trade_event("o1", {"id": "t1", "status": "MATCHED", "size": 40, "price": .88})
    lifecycle.apply_authenticated_trade_event("o1", {"id": "t1", "status": "MINED", "size": 40, "price": .88})
    assert database.load_positions() == []
    lifecycle.apply_authenticated_trade_event(
        "o1", {"id": "t1", "status": "CONFIRMED", "size": 40, "price": .88,
               "actual_cost": 35.2, "fees": .2, "rebates": .05}
    )
    lifecycle.apply_authenticated_trade_event(
        "o1", {"id": "t1", "status": "CONFIRMED", "size": 40, "price": .88,
               "actual_cost": 35.2, "fees": .2, "rebates": .05}
    )
    partial = database.load_orders()[0]
    assert partial["status"] == "PARTIALLY_CONFIRMED"
    assert database.get_exposure(opportunity_id="opp-1") == pytest.approx((35.2, 54.0))
    lifecycle.apply_authenticated_trade_event(
        "o1", {"id": "t2", "status": "CONFIRMED", "size": 60, "price": .9,
               "actual_cost": 54, "fees": .1, "rebates": 0}
    )
    positions = database.load_positions()
    assert len(positions) == 1
    assert positions[0]["shares"] == 100
    assert positions[0]["actualCost"] == 89.2
    assert positions[0]["fees"] == pytest.approx(.3)
    assert database.get_exposure(opportunity_id="opp-1") == pytest.approx((89.2, 0))


def test_partial_confirmation_reserves_only_remaining_and_cancel_releases(money_db):
    database.save_order(order(shares=100, dollars=90))
    database.update_order_status("o1", "PARTIALLY_CONFIRMED", filled_amount=40,
                                 avg_price=.9, actual_cost=36)
    assert database.get_exposure(opportunity_id="opp-1") == pytest.approx((36, 54))
    database.update_order_status("o1", "CANCELED")
    assert database.get_exposure(opportunity_id="opp-1") == pytest.approx((36, 0))
    assert database.load_orders()[0]["canceled_at"] is not None
    # Cancellation of the remainder does not erase already-confirmed fill provenance.
    assert database.resolve_position(database.load_positions()[0]["id"], "LOST")["pnl"] == -36


def test_failed_match_releases_reservation_without_position(money_db):
    database.save_order(order())
    database.update_order_status("o1", "MATCHED", filled_amount=100)
    database.update_order_status("o1", "FAILED", filled_amount=0)
    assert database.get_exposure() == (0, 0)
    assert database.load_positions() == []


def test_resolution_requires_confirmed_fill_and_uses_fee_net_actual_cost(money_db):
    database.save_order(order())
    with database.get_connection() as con:
        con.execute("""INSERT INTO positions
          (id,opportunity_id,order_id,city,bucket,target_date,side,entry_price,shares,size,
           status,opened_at,actual_cost,fees,rebates) VALUES
          ('phantom','opp-1','o1','chicago','80-81F','2026-07-12','YES',.9,10,9,
           'OPEN','now',9,.1,.02)""")
    with pytest.raises(ValueError, match="confirmed fill"):
        database.resolve_position("phantom", "WON")
    database.update_order_status("o1", "CONFIRMED", filled_amount=10, avg_price=.9,
                                 actual_cost=9, fees=.1, rebates=.02)
    pos = database.load_positions()[0]
    won = database.resolve_position(pos["id"], "WON")
    assert won["pnl"] == pytest.approx(.92)


def test_event_and_opportunity_exposure_include_fills_plus_reservations(money_db):
    database.save_order(order("o1", opportunity="opp-1", dollars=90))
    database.save_order(order("o2", opportunity="opp-2", dollars=45, shares=50))
    assert database.get_exposure(event_key="chicago::2026-07-12") == (0, 135)
    assert database.get_exposure(opportunity_id="opp-1") == (0, 90)


def test_executor_forwards_post_only_and_does_not_infer_matched_fill(monkeypatch):
    class Client:
        builder = None
        funder = "f"; signature_type = 2
        def get_ok(self): return "OK"
        def get_tick_size(self, token): return "0.01"
        def get_neg_risk(self, token): return False
        def create_and_post_order(self, **kwargs):
            self.kwargs = kwargs
            return {"orderID": "o1", "status": "matched", "price": .9}
    ex = PolymarketExecutor.__new__(PolymarketExecutor)
    ex.dry_run = False; ex.client = Client()
    result = ex.place_order("tok", "BUY", 10, .9, post_only=True)
    assert ex.client.kwargs["post_only"] is True
    assert result.status == "matched"
    assert result.filled_amount == 0
    assert result.order_mode == "POST_ONLY"


def test_executor_filters_authenticated_taker_trade_for_local_order():
    class Client:
        def get_trades(self, *args, **kwargs):
            return [{
                "id": "trade-1", "taker_order_id": "o1", "asset_id": "tok",
                "status": "TRADE_STATUS_CONFIRMED", "size": "40", "price": ".9",
                "fee_rate_bps": "500", "maker_orders": [],
            }, {
                "id": "other", "taker_order_id": "not-o1", "asset_id": "tok",
                "status": "TRADE_STATUS_CONFIRMED", "size": "1", "price": ".5",
            }]
    ex = PolymarketExecutor.__new__(PolymarketExecutor)
    ex.dry_run = False; ex.client = Client()
    events = ex.get_order_trade_events("o1", "tok")
    assert len(events) == 1
    assert events[0].event_id == "trade-1:o1"
    assert events[0].status == "CONFIRMED"
    assert events[0].fees == pytest.approx(40 * .05 * .9 * .1)


def test_trade_event_status_mapping():
    assert normalize_trade_event("o", {"id": "t1", "status": "MINED", "size": 2, "price": .8}).status == "MATCHED"
    assert normalize_trade_event("o", {"id": "t1", "status": "CONFIRMED", "size": 2, "price": .8}).actual_cost == 1.6
    with pytest.raises(ValueError, match="trade id"):
        normalize_trade_event("o", {"status": "CONFIRMED", "size": 2, "price": .8})


def test_stale_rest_snapshot_cannot_downgrade_confirmation(money_db):
    database.save_order(order(shares=10, dollars=9))
    database.update_order_status("o1", "CONFIRMED", filled_amount=10, actual_cost=9)
    stale = database.update_order_status("o1", "LIVE", filled_amount=0)
    assert stale["status"] == "CONFIRMED"
    assert len(database.load_positions()) == 1


def test_confirmed_fill_and_cost_never_shrink_on_stale_events(money_db):
    database.save_order(order(shares=100, dollars=90))
    database.update_order_status("o1", "PARTIALLY_CONFIRMED", filled_amount=40,
                                 avg_price=.9, actual_cost=36, fees=.2)
    database.update_order_status("o1", "PARTIALLY_CONFIRMED", filled_amount=20,
                                 avg_price=.9, actual_cost=18, fees=.1)
    partial = database.load_positions()[0]
    assert (partial["shares"], partial["actualCost"], partial["fees"]) == (40, 36, .2)
    database.update_order_status("o1", "CONFIRMED", filled_amount=100,
                                 avg_price=.9, actual_cost=90, fees=.5)
    database.update_order_status("o1", "CONFIRMED", filled_amount=40,
                                 avg_price=.9, actual_cost=36, fees=.2)
    confirmed = database.load_positions()[0]
    assert (confirmed["shares"], confirmed["actualCost"], confirmed["fees"]) == (100, 90, .5)


def test_resolution_is_idempotent_but_cannot_flip_outcome(money_db):
    database.save_order(order(shares=10, dollars=9))
    database.update_order_status("o1", "CONFIRMED", filled_amount=10, actual_cost=9)
    pos = database.load_positions()[0]
    first = database.resolve_position(pos["id"], "WON")
    again = database.resolve_position(pos["id"], "WON")
    assert again["pnl"] == first["pnl"]
    with pytest.raises(ValueError, match="already resolved"):
        database.resolve_position(pos["id"], "LOST")


def test_resolution_loop_leaves_unknown_honest_then_scores_confirmed_fill(money_db):
    database.save_order(order(shares=10, dollars=9))
    database.update_order_status("o1", "CONFIRMED", filled_amount=10, actual_cost=9)
    pos = database.load_positions()[0]
    with database.get_connection() as con:
        con.execute("UPDATE positions SET status='RESOLUTION_PENDING' WHERE id=?", (pos["id"],))
    resolution = importlib.import_module("resolution")
    assert resolution.resolve_pending(lambda _: None) == []
    assert database.load_positions()[0]["pnl"] is None
    rows = resolution.resolve_pending(lambda _: "WON", source="fake_authority")
    assert rows[0]["pnl"] == 1
    assert rows[0]["resolutionSource"] == "fake_authority"


def test_status_and_stats_share_identical_money_view(money_db):
    database.save_order(order())
    api = importlib.import_module("api")
    api.state.positions = database.load_positions()
    status = api.get_status()
    stats = api.get_stats()
    assert (status["deployed"], status["reserved"], status["available"]) == (
        stats["deployed"], stats["reserved"], stats["available"]
    )


def test_backfill_selects_only_confirmed_and_calculates_fee_net(money_db):
    database.save_order(order("confirmed"))
    database.update_order_status("confirmed", "CONFIRMED", filled_amount=10,
                                 avg_price=.9, actual_cost=9, fees=.2, rebates=.05)
    database.save_order(order("live", opportunity="opp-2"))
    with database.get_connection() as con:
        con.execute("""INSERT INTO positions
          (id,opportunity_id,order_id,city,bucket,target_date,side,entry_price,shares,size,
           status,opened_at,actual_cost) VALUES
          ('legacy-phantom','opp-2','live','chicago','80-81F','2026-07-12','YES',.9,10,9,
           'OPEN','now',9)""")
    spec = importlib.util.spec_from_file_location("backfill_pnl", ROOT / "scripts/backfill_pnl.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    con = sqlite3.connect(money_db); con.row_factory = sqlite3.Row
    rows = module.select_confirmed_unresolved(con)
    assert len(rows) == 1
    assert rows[0]["opportunity_id"] == "opp-1"
    assert module.calculate_pnl(rows[0], True) == pytest.approx(.85)


def _configure_api(api, executor, *, opp_id="opp-1", event_date="2026-07-12"):
    api.state.bankroll = 1000
    api.state.positions = []
    api.state.opportunities = [{
        "id": opp_id, "city": "chicago", "bucket": "80-81F",
        "targetDate": event_date, "clobTokenIds": ["yes", "no"],
        "yesPrice": .9, "noPrice": .1, "hoursRemaining": 24,
        "acceptingOrders": True,
    }]
    api.state.edge_harvest_opportunities = []
    api.state.last_scan = datetime.now(timezone.utc).isoformat()
    api.state.executor = executor
    api.state.risk_settings = {
        "maxOpportunityExposureUsd": 150,
        "maxEventExposureUsd": 450,
        "defaultOrderMode": "GTC",
        "maxScanAgeMin": 15,
        "requoteTolerance": .02,
    }


def test_api_resting_order_has_no_position_and_duplicate_cap_counts_reservation(money_db, monkeypatch):
    api = importlib.import_module("api")
    monkeypatch.setattr(api, "get_edge_harvest_scanner", lambda: SimpleNamespace(
        _fetch_order_book=lambda _token: {"best_bid_price": .89, "best_ask_price": .90}
    ))
    class Executor:
        dry_run = False; client = object()
        def place_order(self, **kwargs):
            self.last_side = kwargs["side"]
            return OrderResult(True, f"live-{kwargs['size']}", 0, kwargs["price"],
                               status="live", order_mode="POST_ONLY" if kwargs["post_only"] else "GTC")
    _configure_api(api, Executor())
    first = api._execute_trade_inner(api.TradeRequest(
        opportunity_id="opp-1", side="YES", size=90, order_mode="POST_ONLY"
    ))
    assert first["order"]["side"] == "YES"
    assert api.state.executor.last_side == "BUY"
    assert first["order"]["price"] == .89
    assert first["position"] is None
    assert first["order"]["status"] == "LIVE"
    assert database.get_exposure(opportunity_id="opp-1") == (0, 90)
    with pytest.raises(api.HTTPException) as exc:
        api._execute_trade_inner(api.TradeRequest(opportunity_id="opp-1", side="YES", size=70))
    assert exc.value.status_code == 409
    assert exc.value.detail["reason"] == "opportunity_exposure"
    overridden = api._execute_trade_inner(api.TradeRequest(
        opportunity_id="opp-1", side="YES", size=70, override=True
    ))
    assert overridden["order"]["status"] == "LIVE"


def test_api_event_cap_aggregates_different_opportunities(money_db):
    api = importlib.import_module("api")
    class Executor:
        dry_run = False; client = object(); n = 0
        def place_order(self, **kwargs):
            self.n += 1
            return OrderResult(True, f"o{self.n}", status="live", avg_price=kwargs["price"])
    ex = Executor(); _configure_api(api, ex)
    api.state.risk_settings["maxEventExposureUsd"] = 100
    api._execute_trade_inner(api.TradeRequest(opportunity_id="opp-1", side="YES", size=60))
    api.state.opportunities[0]["id"] = "opp-2"
    with pytest.raises(api.HTTPException) as exc:
        api._execute_trade_inner(api.TradeRequest(opportunity_id="opp-2", side="YES", size=50))
    assert exc.value.detail["reason"] == "event_exposure"


def test_api_cancel_updates_local_order_and_releases_reservation(money_db):
    api = importlib.import_module("api")
    class Executor:
        dry_run = False; client = object()
        def cancel_order(self, order_id): return {"canceled": [order_id], "not_canceled": {}}
    database.save_order(order())
    api.state.is_live = True; api.state.executor = Executor()
    response = api.cancel_order("o1")
    assert response["order"]["status"] == "CANCELED"
    assert database.get_exposure() == (0, 0)


def test_api_cancel_requires_exchange_ack_and_preserves_reservation(money_db):
    api = importlib.import_module("api")
    class Executor:
        dry_run = False; client = object()
        def cancel_order(self, order_id):
            return {"canceled": [], "not_canceled": {order_id: "already matched"}}
    database.save_order(order())
    api.state.is_live = True; api.state.executor = Executor()
    with pytest.raises(api.HTTPException) as exc:
        api.cancel_order("o1")
    assert exc.value.status_code == 409
    assert database.load_orders()[0]["status"] == "LIVE"
    assert database.get_exposure() == (0, 90)


def test_api_reconcile_keeps_matched_nonterminal_then_confirms(money_db):
    api = importlib.import_module("api")
    class Executor:
        dry_run = False; client = object(); confirmed = False
        def get_order_snapshot(self, order_id):
            return OrderSnapshot(order_id, "CONFIRMED" if self.confirmed else "MATCHED",
                                 10, .9, 9)
    ex = Executor(); database.save_order(order(shares=10, dollars=9))
    api.state.is_live = True; api.state.executor = ex
    assert api.reconcile_order("o1")["order"]["status"] == "MATCHED"
    assert database.load_positions() == []
    ex.confirmed = True
    assert api.reconcile_order("o1")["order"]["status"] == "CONFIRMED"
    assert len(database.load_positions()) == 1


def test_active_poll_reconciles_confirmed_trade_into_partial_position(money_db):
    api = importlib.import_module("api")
    database.save_order(order(shares=100, dollars=90))
    class Client:
        def get_trades(self, **kwargs): return [{"id": "unused"}]
    class Executor:
        dry_run = False; client = Client()
        def get_order_snapshot(self, order_id):
            return OrderSnapshot(order_id, "MATCHED", 40, .9, 36)
        def get_order_trade_events(self, order_id, token_id, trades=None):
            return [OrderSnapshot(order_id, "CONFIRMED", 40, .9, 36,
                                  event_id="trade-1:o1")]
    api.state.is_live = True; api.state.executor = Executor()
    api._reconcile_active_local_orders()
    reconciled = database.load_orders()[0]
    assert reconciled["status"] == "PARTIALLY_CONFIRMED"
    assert reconciled["reserved_dollars"] == 54
    assert database.load_positions()[0]["shares"] == 40


def test_edge_scan_injects_nowcasts_and_serializes_profit_contract(monkeypatch, money_db):
    api = importlib.import_module("api")
    market = SimpleNamespace(
        city_key="chicago", target_date="2026-07-12", market_type="high",
        settlement_station="KORD",
        resolution_source_url="https://www.weather.gov/wrh/timeseries?site=KORD",
    )
    nowcast = SimpleNamespace(available=False, station_id="KORD")
    opp = SimpleNamespace(
        city="chicago", target_date="2026-07-12", bucket_str="80-81F",
        bucket_low=80, bucket_high=81, forecast_temp=75, hours_remaining=12,
        bands_away=3, degrees_away=5, threshold_type="CONSERVATIVE",
        yes_price=.05, no_price=.95, potential_return_pct=5.26,
        risk_tier="LOW", risk_score=2, risk_factors=[], model_spread=1,
        ecmwf_temp=75, gfs_temp=74, nws_temp=75, front_warning=None,
        front_warning_reason=None, recommended_side="NO", market_type="high",
        accepting_orders=True, clob_token_ids=("yes", "no"), market_url="url",
        liquidity=1000, best_ask_price=.95, best_ask_size=10, best_bid_price=.94,
        best_bid_size=10, spread=.01, market_id="market-1", event_key="event-1",
        gross_return_pct=5.2632, net_win_return_pct=5.0,
        estimated_fee_pct=.2632, fee_enabled=True, fee_rate_bps=25,
        fee_source="CLOB", fee_known=True, fee_model="taker",
        nowcast_status="UNKNOWN", nowcast_station="KORD",
        observed_extreme=None, nowcast_hard_bound=False,
    )
    class Scanner:
        def fetch_weather_markets(self, city_filter): return [market]
    class Forecaster:
        def get_daily_high_forecast(self, city, target): return object()
        def fetch_station_nowcast(self, city, target, **kwargs):
            assert kwargs == {
                "station_id": "KORD",
                "resolution_source_url": "https://www.weather.gov/wrh/timeseries?site=KORD",
            }
            return nowcast
    class Edge:
        def find_opportunities(self, markets, forecasts, nowcasts=None):
            assert nowcasts[("chicago", "2026-07-12", "high")] is nowcast
            return [opp]
    monkeypatch.setattr(api, "get_scanner", lambda: Scanner())
    monkeypatch.setattr(api, "get_forecaster", lambda: Forecaster())
    monkeypatch.setattr(api, "get_edge_harvest_scanner", lambda: Edge())
    monkeypatch.setattr(api, "_save_opp_cache", lambda *args: None)
    row = api._run_edge_harvest_scan(["chicago"])["opportunities"][0]
    assert row["marketId"] == "market-1"
    assert row["eventKey"] == "event-1"
    assert row["netWinReturnPct"] == 5.0
    assert row["feeKnown"] is True
    assert row["nowcastStatus"] == "UNKNOWN"
    assert row["nowcastHardBound"] is False
