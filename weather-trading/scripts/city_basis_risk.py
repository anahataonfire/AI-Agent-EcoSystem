#!/usr/bin/env python3
"""
PD-340 v3 — per-(city, market_type) settlement-LOCATION-delta profile.

Measures, for every city+market_type the operator has traded:
  delta = (settlement temp, from Polymarket's winning bucket center)
        - (Open-Meteo archive ACTUAL at config coords; max for HIGH markets, min for LOW)
  all in °C.

This is a LOCATION / settlement delta (config-coords actual vs settlement station), NOT a
forecast basis — positions store no trade-time forecast snapshot (PD-340 R2-A). It isolates
the coordinate-mispin that sank the loss population.

  mean(delta)  -> systematic location mispin (the offset the recommender applies, shrunk for thin n)
  stdev(delta) -> day-to-day volatility (feeds confidence; large => untrustworthy even at high n)

USAGE:
  python scripts/city_basis_risk.py                 # diagnostic table (read-only)
  python scripts/city_basis_risk.py --write-json    # + emit backend/city_basis.json (atomic)
"""
import sqlite3, urllib.request, json, time, re, os, statistics, sys, tempfile
from datetime import datetime, timezone
import config

DB = os.path.expanduser("~/Documents/Projects/Ecosystem/weather-trading/backend/weather_trading.db")
OUT = os.path.expanduser("~/Documents/Projects/Ecosystem/weather-trading/backend/city_basis.json")
UA = {"User-Agent": "Mozilla/5.0"}
MO = ["", "january","february","march","april","may","june","july","august","september","october","november","december"]
BASIS_VERSION = 1

def slug(city, date, mt):
    y, m, d = date.split("-")
    return f"{'highest' if mt=='high' else 'lowest'}-temperature-in-{city.replace('_','-')}-on-{MO[int(m)]}-{int(d)}-{y}"

def gamma(s, cache):
    if s in cache: return cache[s]
    r = None
    try:
        req = urllib.request.Request(f"https://gamma-api.polymarket.com/events?slug={s}", headers=UA)
        with urllib.request.urlopen(req, timeout=15) as resp:
            d = json.load(resp)
        r = d[0] if d else None
    except Exception:
        r = None
    cache[s] = r; time.sleep(0.2); return r

def to_c(v, unit):
    return v if unit == "C" else (v - 32) / 1.8

def win_center_c(ev):
    """Center temp (°C) of the YES-resolved bucket. None if open-ended/unresolved. Handles negatives."""
    for m in ev.get("markets", []):
        op = m.get("outcomePrices")
        try: op = json.loads(op) if isinstance(op, str) else op
        except: pass
        if not op or str(op[0]) not in ("1", "1.0"): continue
        t = (m.get("groupItemTitle") or "")
        unit = "C" if "C" in t else "F"
        if re.search(r"or (below|higher)", t, re.I):
            return None  # open bucket: no center
        mr = re.match(r"(-?\d+)\s*-\s*(-?\d+)", t)        # range, negatives allowed
        if mr: return to_c((int(mr.group(1)) + int(mr.group(2))) / 2, unit)
        ms = re.match(r"(-?\d+)", t)                       # single, negatives allowed
        if ms: return to_c(float(ms.group(1)), unit)
    return None

def archive_c(lat, lon, start, end):
    """One bulk Open-Meteo archive call -> {date: {'max':°C, 'min':°C}}."""
    url = (f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}"
           f"&start_date={start}&end_date={end}&daily=temperature_2m_max,temperature_2m_min&timezone=auto")
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            d = json.load(r)
        dd = d["daily"]; out = {}
        for t, hi, lo in zip(dd["time"], dd["temperature_2m_max"], dd["temperature_2m_min"]):
            out[t] = {"max": hi, "min": lo}
        return out
    except Exception:
        return {}

con = sqlite3.connect(DB); con.row_factory = sqlite3.Row

def city_unit(city):
    # Derive from ALL of a city's buckets, not a single row. A city is °F only if it
    # uses °F and never °C (non-US cities trade °C; prefer °C when any °C market exists).
    rows = con.execute("SELECT DISTINCT bucket FROM positions WHERE city=?", (city,)).fetchall()
    buckets = " ".join((r[0] or "") for r in rows)
    if "C" in buckets: return "C"
    if "F" in buckets: return "F"
    return "C"

events = con.execute(
    "SELECT DISTINCT city, target_date, "
    "CASE WHEN opportunity_id LIKE '%_low_%' THEN 'low' ELSE 'high' END mt "
    "FROM positions ORDER BY city, target_date"
).fetchall()

by_city = {}
for e in events: by_city.setdefault(e["city"], []).append((e["target_date"], e["mt"]))
all_dates = [e["target_date"] for e in events]
gstart, gend = min(all_dates), max(all_dates)

cache = {}
# deltas[(city, mt)] = [delta_c, ...]
deltas = {}
print(f"Cities: {len(by_city)} | events: {len(events)} | range {gstart}..{gend}\n")

for city, evs in by_city.items():
    c = config.WEATHER_CITIES.get(city, {})
    lat, lon = c.get("lat"), c.get("lon")
    if not lat: continue
    arch = archive_c(lat, lon, gstart, gend)
    for date, mt in evs:
        ev = gamma(slug(city, date, mt), cache)
        if not ev or not ev.get("closed"): continue
        wc = win_center_c(ev)
        a = arch.get(date)
        if wc is None or a is None: continue
        actual = a["max"] if mt == "high" else a["min"]
        if actual is None: continue
        deltas.setdefault((city, mt), []).append(round(wc - actual, 2))

# aggregate
rows, profiles = [], {}
for (city, mt), ds in sorted(deltas.items()):
    unit = city_unit(city)
    W = 1.0 if unit == "C" else (2 / 1.8)
    n = len(ds)
    mean = round(statistics.mean(ds), 2) if n else None
    sd = round(statistics.pstdev(ds), 2) if n >= 2 else None
    rows.append((city, mt, n, mean, sd, W, unit))
    if n >= 1:
        profiles.setdefault(city, {})[mt] = {
            "n": n, "mean_delta_c": mean, "stdev_delta_c": sd, "unit": unit,
            "bucket_width_c": round(W, 3),
        }

# diagnostic table
rows.sort(key=lambda r: (-(abs(r[3]) if r[3] is not None else -1), -(r[4] or 0)))
print(f"{'city':14}{'mkt':5}{'n':4}{'mean°C':8}{'stdev°C':9}{'W°C':6}{'conf':11}{'status'}")
print("-" * 74)
for city, mt, n, mean, sd, W, unit in rows:
    if n < 3: conf, status = "UNPROVEN", "uncorrected (n<3)"
    elif n >= 10 and sd is not None and sd <= 1.0 * W: conf, status = "TRUSTED", "corrected"
    else: conf, status = "PROVISIONAL", "corrected"
    if mean is not None and sd is not None and abs(mean) > W and sd > 2 * W:
        status = "uncorrected (coords-suspect)"
    eff = round(mean * n / (n + 5), 2) if mean is not None else None  # shrunk offset preview
    ms = f"{mean:+.2f}" if mean is not None else "  -"
    ss = f"{sd:.2f}" if sd is not None else "  -"
    print(f"{city[:13]:14}{mt:5}{n:<4}{ms:8}{ss:9}{W:<6.2f}{conf:11}{status} (eff {eff})")

if "--write-json" in sys.argv:
    payload = {
        "basis_version": BASIS_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "shrinkage_k": 5,
        "profiles": profiles,
    }
    # atomic write: temp in same dir + os.replace
    d = os.path.dirname(OUT)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".city_basis.", suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, OUT)
    ncity = len(profiles); nprof = sum(len(v) for v in profiles.values())
    print(f"\n  WROTE {OUT}  ({ncity} cities / {nprof} (city,market_type) profiles, basis_version={BASIS_VERSION})")
else:
    print("\n  diagnostic only — re-run with --write-json to emit backend/city_basis.json")
