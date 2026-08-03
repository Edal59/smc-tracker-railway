"""
Acceptance test for v17.85.34 Market Brief (MB) live execution alerts.

Runs all 10 live MB_* execution alert payloads (+ invalid cases) through the
REAL Flask webhook route (POST /api/v1/signal) against a temp database and
verifies:
  1. One trade created per live alert name (10 total).
  2. Entry price sourced correctly per lane (entry_price for RE_ENTRY /
     V_REVERSAL, price otherwise).
  3. SL / TP stored EXACTLY as received (never recalculated / invented).
  4. Direction taken from the payload 'direction' field (BUY->LONG/SELL->SHORT).
  5. Lane flags set (macro_express / fast_lane / re_entry) + geometry_valid.
  6. Invalid payloads (missing SL, bad geometry) -> HTTP 400 visible error,
     raw payload retained, NO trade created.
  7. Indicator 'version' preserved on every trade.
  8. Version / test-batch isolation via analytics filters.
"""
import os
import sys
import json
import tempfile

# ── temp DB + no-auth BEFORE importing app/config ──
_TMP = tempfile.mkdtemp(prefix="mb_test_")
os.environ["DATABASE_PATH"] = os.path.join(_TMP, "mb_test.db")
os.environ["REQUIRE_AUTH"] = "false"
os.environ["SMC_API_KEY"] = ""
os.environ["PRICE_TRACKER_ENABLED"] = "false"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database import init_db, get_signals, count_signals  # noqa: E402
from src.webhook_server.app import create_app  # noqa: E402

init_db()
app = create_app()
client = app.test_client()

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}  {detail}")


def post(payload):
    r = client.post("/api/v1/signal", json=payload)
    try:
        body = r.get_json()
    except Exception:
        body = None
    return r.status_code, body


VER = "v17.85.34"
BATCH = "acceptance_batch_A"

# Common EURUSD geometry. LONG: sl < entry < tp. SHORT: tp < entry < sl.
LONG_PRICE = {"price": 1.08500, "sl": 1.08300, "tp": 1.09100}
SHORT_PRICE = {"price": 1.08500, "sl": 1.08700, "tp": 1.07900}
LONG_ENTRY = {"entry_price": 1.08520, "sl": 1.08300, "tp": 1.09100}
SHORT_ENTRY = {"entry_price": 1.08480, "sl": 1.08700, "tp": 1.07900}


def base(alert, direction, mb_type, prices, **extra):
    d = {
        "version": VER, "alert": alert, "type": mb_type, "symbol": "EURUSD",
        "timeframe": "5", "message": "test", "action": "ENTRY",
        "direction": direction, "confidence": 82, "session": "London",
        "poi": 5, "time": "2026-08-02T10:15:00Z", "test_batch": BATCH,
    }
    d.update(prices)
    d.update(extra)
    return d


# ── The 12 live execution alert names (10 workflows) ──
# tuple: (alert, direction, mb_type, prices, extra_fields, expected_entry_source)
ALERTS = [
    ("MB_EXECUTE_LONG",    "BUY",  "WITH_TREND",   dict(LONG_PRICE),  {"entry": "Sniper"},                       "price"),
    ("MB_EXECUTE_SHORT",   "SELL", "WITH_TREND",   dict(SHORT_PRICE), {"entry": "Sniper"},                       "price"),
    ("MB_CONTINUE_LONG",   "BUY",  "CONTINUATION", dict(LONG_PRICE),  {"entry": "Continuation"},                 "price"),
    ("MB_CONTINUE_SHORT",  "SELL", "CONTINUATION", dict(SHORT_PRICE), {"entry": "Continuation"},                 "price"),
    ("MB_CT_LONG",         "BUY",  "COUNTER_TREND",dict(LONG_PRICE),  {"entry": "Counter-Trend"},                "price"),
    ("MB_CT_SHORT",        "SELL", "COUNTER_TREND",dict(SHORT_PRICE), {"entry": "Counter-Trend"},                "price"),
    ("MB_MACRO_LONG",      "BUY",  "WITH_TREND",   dict(LONG_PRICE),  {"entry": "Macro", "macro_express": 1},    "price"),
    ("MB_MACRO_SHORT",     "SELL", "WITH_TREND",   dict(SHORT_PRICE), {"entry": "Macro", "macro_express": 1},    "price"),
    ("MB_REENTRY_LONG",    "BUY",  "RE_ENTRY",     dict(LONG_ENTRY),  {"entry": "Re-Entry", "re_entry": 1},      "entry_price"),
    ("MB_REENTRY_SHORT",   "SELL", "RE_ENTRY",     dict(SHORT_ENTRY), {"entry": "Re-Entry", "re_entry": 1},      "entry_price"),
    ("MB_VREVERSAL_LONG",  "BUY",  "V_REVERSAL",   dict(LONG_ENTRY),  {"entry": "V-Shape-Breakout", "fast_lane": 1}, "entry_price"),
    ("MB_VREVERSAL_SHORT", "SELL", "V_REVERSAL",   dict(SHORT_ENTRY), {"entry": "V-Shape-Breakout", "fast_lane": 1}, "entry_price"),
]

print("\n=== 1. Live MB execution alerts (12 alert names / 10 workflows) ===")
created = {}
for alert, direction, mb_type, prices, extra, exp_source in ALERTS:
    payload = base(alert, direction, mb_type, prices, **extra)
    code, body = post(payload)
    ok = code == 200 and body and body.get("status") == "ok"
    check(f"{alert} accepted (200 ok)", ok, f"code={code} body={body}")
    if not ok:
        continue
    created[alert] = (payload, body)
    exp_dir = "LONG" if direction == "BUY" else "SHORT"
    check(f"{alert} direction {direction}->{exp_dir}", body.get("direction") == exp_dir,
          f"got {body.get('direction')}")
    check(f"{alert} entry_source={exp_source}", body.get("entry_source") == exp_source,
          f"got {body.get('entry_source')}")
    # entry value equals the correct source field
    exp_entry = prices.get("entry_price") if exp_source == "entry_price" else prices.get("price")
    check(f"{alert} entry_price preserved ({exp_entry})",
          abs(body.get("entry_price") - exp_entry) < 1e-9,
          f"got {body.get('entry_price')}")
    # SL / TP preserved exactly
    check(f"{alert} SL preserved ({prices['sl']})", abs(body.get("stop_loss") - prices["sl"]) < 1e-9,
          f"got {body.get('stop_loss')}")
    check(f"{alert} TP preserved ({prices['tp']})", abs(body.get("take_profit") - prices["tp"]) < 1e-9,
          f"got {body.get('take_profit')}")
    check(f"{alert} geometry_valid=1", body.get("geometry_valid") == 1)
    check(f"{alert} version preserved", body.get("version") == VER, f"got {body.get('version')}")
    # lane flags
    if "MACRO" in alert:
        check(f"{alert} macro_express=1", body.get("macro_express") == 1)
    if "VREVERSAL" in alert:
        check(f"{alert} fast_lane=1", body.get("fast_lane") == 1)
    if "REENTRY" in alert:
        check(f"{alert} re_entry=1", body.get("re_entry") == 1)

print(f"\n  → {len(created)} / 12 alert names created a trade")

print("\n=== 2. DB: one trade per alert, SL/TP verbatim, version stored ===")
rows = get_signals(limit=500, indicator_version=VER)
check("12 trades persisted for this version", len(rows) == 12, f"got {len(rows)}")
by_alert = {r.get("alert_name"): r for r in rows}
check("all 12 alert names present in DB", len(by_alert) == 12, f"got {sorted(by_alert)}")
for alert, direction, mb_type, prices, extra, exp_source in ALERTS:
    r = by_alert.get(alert)
    if not r:
        check(f"{alert} row exists", False)
        continue
    check(f"{alert} DB stop_loss verbatim", abs(r["stop_loss"] - prices["sl"]) < 1e-9)
    check(f"{alert} DB take_profit verbatim", abs(r["take_profit"] - prices["tp"]) < 1e-9)
    check(f"{alert} DB entry_source={exp_source}", r["entry_source"] == exp_source)
    check(f"{alert} DB raw_payload retained", bool(r.get("raw_payload")))

print("\n=== 3. Invalid payloads -> 400 visible error, no trade, raw retained ===")
before = count_signals(indicator_version=VER)

# (a) Missing SL
code, body = post(base("MB_EXECUTE_LONG", "BUY", "WITH_TREND",
                        {"price": 1.08500, "tp": 1.09100}))  # no sl
check("missing SL -> 400", code == 400, f"code={code}")
check("missing SL -> visible error text", bool(body and body.get("error")))
check("missing SL -> raw payload retained", bool(body and body.get("raw_payload")))

# (b) Bad geometry (LONG with sl > entry)
code, body = post(base("MB_EXECUTE_LONG", "BUY", "WITH_TREND",
                        {"price": 1.08500, "sl": 1.08900, "tp": 1.09100}))
check("bad geometry -> 400", code == 400, f"code={code}")
check("bad geometry -> visible error text", bool(body and body.get("error")))
check("bad geometry -> raw payload retained", bool(body and body.get("raw_payload")))

# (c) Missing direction
code, body = post(base("MB_EXECUTE_LONG", "", "WITH_TREND", dict(LONG_PRICE)))
check("missing direction -> 400", code == 400, f"code={code}")

after = count_signals(indicator_version=VER)
check("no trades created by invalid payloads", after == before, f"before={before} after={after}")

print("\n=== 4. Analytics filters (version + test-batch + lane isolation) ===")
check("filter by test_batch", count_signals(test_batch=BATCH) == 12,
      f"got {count_signals(test_batch=BATCH)}")
check("filter by mb_type=RE_ENTRY", count_signals(mb_type="RE_ENTRY") == 2,
      f"got {count_signals(mb_type='RE_ENTRY')}")
check("filter by mb_type=V_REVERSAL", count_signals(mb_type="V_REVERSAL") == 2)
check("filter by mb_type=COUNTER_TREND", count_signals(mb_type="COUNTER_TREND") == 2)
check("filter by macro_express=1", count_signals(macro_express=1) == 2)
check("filter by fast_lane=1", count_signals(fast_lane=1) == 2)
check("filter by re_entry=1", count_signals(re_entry=1) == 2)
check("filter by direction=LONG", count_signals(direction="LONG") == 6)
check("filter by unknown version isolates", count_signals(indicator_version="v99.0.0") == 0)

print("\n=== 5. Same-candle conflict setting (config) ===")
from src.config import config as _cfg  # noqa: E402
check("default same_candle_conflict = SL_FIRST", _cfg.same_candle_conflict == "SL_FIRST",
      f"got {_cfg.same_candle_conflict}")

print(f"\n{'='*50}\nRESULT: {PASS} passed, {FAIL} failed\n{'='*50}")
sys.exit(1 if FAIL else 0)
