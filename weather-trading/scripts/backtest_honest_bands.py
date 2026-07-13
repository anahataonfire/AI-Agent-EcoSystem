#!/usr/bin/env python3
"""
PD-340 v3 increment #5 — TIME-SPLIT backtest + threshold sweep of the honest-bands engine.

For every settled (WON/LOST) position, reconstruct what the engine WOULD have shown, using
ONLY settlements before that bet (no future leakage, Codex AMEND-6). Sweeps ROOM_STDEV_THRESHOLD
to show the precision/recall tradeoff: low threshold => more ROOM (keep wins, miss losses);
high threshold => less ROOM (catch losses, suppress wins). Validates the LOCATION correction
(raw forecast proxied by Open-Meteo archive at config coords; not forecast-model error, AMEND-8).
"""
import sqlite3, urllib.request, json, time, re, os, statistics
import config
import edge_harvest as eh

DB = os.path.expanduser("~/Documents/Projects/Ecosystem/weather-trading/backend/weather_trading.db")
UA = {"User-Agent": "Mozilla/5.0"}
MO = ["", "january","february","march","april","may","june","july","august","september","october","november","december"]

def slug(city, date, mt):
    y, m, d = date.split("-")
    return f"{'highest' if mt=='high' else 'lowest'}-temperature-in-{city.replace('_','-')}-on-{MO[int(m)]}-{int(d)}-{y}"

def gamma(s, cache):
    if s in cache: return cache[s]
    r = None
    try:
        req = urllib.request.Request(f"https://gamma-api.polymarket.com/events?slug={s}", headers=UA)
        with urllib.request.urlopen(req, timeout=15) as resp: r = (json.load(resp) or [None])[0]
    except Exception: r = None
    cache[s] = r; time.sleep(0.2); return r

def to_c(v, unit): return v if unit == "C" else (v - 32) / 1.8

def win_center_c(ev):
    for m in ev.get("markets", []):
        op = m.get("outcomePrices")
        try: op = json.loads(op) if isinstance(op, str) else op
        except: pass
        if not op or str(op[0]) not in ("1", "1.0"): continue
        t = m.get("groupItemTitle") or ""
        unit = "C" if "C" in t else "F"
        if re.search(r"or (below|higher)", t, re.I): return None
        mr = re.match(r"(-?\d+)\s*-\s*(-?\d+)", t)
        if mr: return to_c((int(mr.group(1)) + int(mr.group(2))) / 2, unit)
        ms = re.match(r"(-?\d+)", t)
        if ms: return to_c(float(ms.group(1)), unit)
    return None

def archive_c(lat, lon, start, end):
    url = (f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}"
           f"&start_date={start}&end_date={end}&daily=temperature_2m_max,temperature_2m_min&timezone=auto")
    try:
        with urllib.request.urlopen(url, timeout=30) as r: d = json.load(r)
        dd = d["daily"]; return {t: {"max": hi, "min": lo} for t, hi, lo in
                                 zip(dd["time"], dd["temperature_2m_max"], dd["temperature_2m_min"])}
    except Exception: return {}

def parse_bucket(b):
    unit = "C" if "C" in b else "F"
    nums = [float(x) for x in re.findall(r"(-?\d+(?:\.\d+)?)", b)]
    if "≤" in b: return (None, nums[0], unit)
    if "≥" in b: return (nums[0], None, unit)
    if len(nums) >= 2: return (min(nums[0], nums[1]), max(nums[0], nums[1]), unit)
    return (nums[0], nums[0], unit) if nums else (None, None, unit)

con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
pos = con.execute(
    "SELECT id, city, bucket, target_date, status, "
    "CASE WHEN opportunity_id LIKE '%_low_%' THEN 'low' ELSE 'high' END mt "
    "FROM positions WHERE status IN ('WON','LOST') ORDER BY target_date"
).fetchall()

dates = [p["target_date"] for p in pos]
gstart, gend = min(dates), max(dates)
cache = {}; ev_info = {}; arch_by_city = {}
print(f"Settled positions: {len(pos)} | range {gstart}..{gend}\nReconstructing per-event settlement + config-coords actual...")
for p in pos:
    key = (p["city"], p["mt"], p["target_date"])
    if key in ev_info: continue
    c = config.WEATHER_CITIES.get(p["city"], {}); lat, lon = c.get("lat"), c.get("lon")
    if not lat: ev_info[key] = None; continue
    if p["city"] not in arch_by_city: arch_by_city[p["city"]] = archive_c(lat, lon, gstart, gend)
    a = arch_by_city[p["city"]].get(p["target_date"])
    ev = gamma(slug(p["city"], p["target_date"], p["mt"]), cache)
    wc = win_center_c(ev) if ev and ev.get("closed") else None
    if wc is None or not a: ev_info[key] = None; continue
    om_c = a["max"] if p["mt"] == "high" else a["min"]
    if om_c is None: ev_info[key] = None; continue
    ev_info[key] = {"delta_c": round(wc - om_c, 2), "om_c": om_c}

deltas_by = {}
for (city, mt, date), info in ev_info.items():
    if info: deltas_by.setdefault((city, mt), []).append((date, info["delta_c"]))

# precompute per-position inputs once (as-of profile + raw forecast proxy + bucket)
evals = []; skipped = 0
for p in pos:
    info = ev_info.get((p["city"], p["mt"], p["target_date"]))
    if not info: skipped += 1; continue
    lo, hi, unit = parse_bucket(p["bucket"])
    W = 1.0 if unit == "C" else (2 / 1.8)
    prior = [d for (dt, d) in deltas_by.get((p["city"], p["mt"]), []) if dt < p["target_date"]]
    prof = None
    if len(prior) >= 1:
        prof = {"n": len(prior), "mean_delta_c": round(statistics.mean(prior), 2),
                "stdev_delta_c": round(statistics.pstdev(prior), 2) if len(prior) >= 2 else None,
                "bucket_width_c": round(W, 3)}
    om_market = info["om_c"] if unit == "C" else round(info["om_c"] * 9 / 5 + 32, 1)
    evals.append((p["status"], p["city"], p["mt"], unit, om_market, lo, hi, prof))

scanner = eh.EdgeHarvestScanner()
def pc(d, k):
    tot = sum(d.values()) or 1
    return 100 * d.get(k, 0) / tot

nL = sum(1 for e in evals if e[0] == "LOST"); nW = sum(1 for e in evals if e[0] == "WON")
print(f"\nskipped (no settlement/coords, incl. open-bucket losses): {skipped} | evaluable: {len(evals)}  (LOST={nL}, WON={nW})")
print("=" * 74)
print(f"  {'thr(σ)':8}{'LOSS→ROOM%':13}{'LOSS caught%':15}{'WIN→ROOM%':13}{'separation':11}")
print("  (false green↓)         (want high↑)        (edge kept↑)     (pts↑)")
print("-" * 74)
for thr in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5]:
    scanner.ROOM_STDEV_THRESHOLD = thr
    t = {"WON": {}, "LOST": {}}
    for status, city, mt, unit, om, lo, hi, prof in evals:
        scanner._basis_cache = {"profiles": {city: {mt: prof}} if prof else {}, "basis_version": 0}
        rb, _ = scanner.calculate_bands_away(om, lo, hi, unit)
        st = scanner._apply_basis(city, mt, unit, om, lo, hi, rb)["recommendation_status"]
        t[status][st] = t[status].get(st, 0) + 1
    lr, wr = pc(t["LOST"], "ROOM"), pc(t["WON"], "ROOM")
    star = "  <--" if abs(thr - scanner.ROOM_STDEV_THRESHOLD) < 1e-9 and thr == 1.5 else ""
    print(f"  {thr:<8}{lr:<13.1f}{100-lr:<15.1f}{wr:<13.1f}{wr-lr:+.1f}{star}")
print("-" * 74)
print("  UNCORRECTED (threshold-independent) absorbs thin-data / coords-suspect cities.")
print("  Trade: lower σ keeps more wins ROOM but lets more losses show green; higher σ")
print("  catches more losses but suppresses more wins. Pick the knee.")
