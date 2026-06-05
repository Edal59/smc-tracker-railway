#!/usr/bin/env python3
"""
Test suite for v17.56.9 — Guardian HTF-Gating & Risk Labels.

Verifies:
  1. version.py single source of truth + guardian_risk normalization
  2. v17.56.9 payload decodes with new fields (guardian_label, guardian_risk)
  3. v17.56.8 / v17.56.7 payload backward compatibility (safe defaults applied)
  4. decode_payload() universal dispatcher routes correctly
  5. DB migration adds new columns to signals + opportunities (idempotent)
  6. Opportunity insert / retrieve roundtrip carries the new fields
  7. Signal insert / retrieve roundtrip carries the new fields (legacy bridge)
  8. guardian_risk filter on get_signals / count_signals
  9. Three Guardian risk scenarios (0=low, 1=medium, 2=high)
 10. /health returns v17.56.9 + guardian_htf_gating feature (Flask test client)
 11. /signals API response includes the new fields + guardian_risk filter

Run from repo root:  python3 test_v17_56_9.py
"""
import os
import sys
import sqlite3
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Isolated temp DB + no auth for the test client
TEST_DB = os.path.join(tempfile.gettempdir(), 'tradex_test_v17_56_9.db')
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)
os.environ['DATABASE_PATH'] = TEST_DB
os.environ['REQUIRE_AUTH'] = 'false'
os.environ['PRICE_TRACKER_ENABLED'] = 'false'
os.environ['SMC_API_KEY'] = 'test-key'

from src.config import config
config.load()

PASS = 0
FAIL = 0


def check(name, got, expected):
    global PASS, FAIL
    ok = got == expected
    if ok:
        PASS += 1
        print(f"  ✅ {name} = {got!r}")
    else:
        FAIL += 1
        print(f"  ❌ {name} = {got!r} (expected {expected!r})")


def check_true(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}")


print("=" * 70)
print("STEP 1: version.py — single source of truth + guardian_risk normalize")
print("=" * 70)
from src.version import (
    VERSION, get_version, get_features, normalize_guardian_risk,
    VALID_GUARDIAN_RISK, DEFAULT_GUARDIAN_RISK,
)
# VERSION is a single source of truth that advances with each release; assert
# monotonic progression so later releases (e.g. v17.57) don't break this suite.
check_true("VERSION >= v17.56.9", VERSION >= "v17.56.9")
check_true("get_version() >= v17.56.9", get_version() >= "v17.56.9")
check_true("features include guardian_htf_gating", "guardian_htf_gating" in get_features())
check_true("features still include hud_sync (carryover)", "hud_sync" in get_features())
check("DEFAULT_GUARDIAN_RISK", DEFAULT_GUARDIAN_RISK, 0)
check("VALID_GUARDIAN_RISK", tuple(VALID_GUARDIAN_RISK), (0, 1, 2))
check("normalize_guardian_risk(0)", normalize_guardian_risk(0), 0)
check("normalize_guardian_risk(1)", normalize_guardian_risk(1), 1)
check("normalize_guardian_risk(2)", normalize_guardian_risk(2), 2)
check("normalize_guardian_risk('2')", normalize_guardian_risk("2"), 2)
check("normalize_guardian_risk(99) -> default", normalize_guardian_risk(99), 0)
check("normalize_guardian_risk(-1) -> default", normalize_guardian_risk(-1), 0)
check("normalize_guardian_risk(None) -> default", normalize_guardian_risk(None), 0)
check("normalize_guardian_risk(True) -> default", normalize_guardian_risk(True), 0)
check("normalize_guardian_risk('bogus') -> default", normalize_guardian_risk("bogus"), 0)


print("\n" + "=" * 70)
print("STEP 2: DB init + migration adds guardian columns (idempotent)")
print("=" * 70)
from src.database import init_db, insert_signal, get_signals, get_signal, count_signals
db_path = init_db(TEST_DB)
print(f"  DB initialized at {db_path}")
conn = sqlite3.connect(TEST_DB)
sig_cols = [c[1] for c in conn.execute("PRAGMA table_info(signals)").fetchall()]
opp_cols = [c[1] for c in conn.execute("PRAGMA table_info(opportunities)").fetchall()]
conn.close()
for col in ("guardian_label", "guardian_risk"):
    check_true(f"signals.{col} exists", col in sig_cols)
for col in ("guardian_label", "guardian_risk"):
    check_true(f"opportunities.{col} exists", col in opp_cols)

# idempotency: re-run init_db should not error
init_db(TEST_DB)
check_true("init_db re-run is idempotent", True)


print("\n" + "=" * 70)
print("STEP 3: v17.56.9 payload decode (new guardian fields parsed)")
print("=" * 70)
from src.oie_processor import (
    decode_payload, decode_v17_56_9_payload, decode_v17_56_8_payload,
    decode_v17_56_7_payload, decode_legacy_payload, normalize_oie_payload,
    oie_to_legacy_compact, is_oie_payload,
)

payload_9 = {
    "version": "v17.56.9",
    "mode": "EXECUTION",
    "session": "NY",
    "symbol": "EURUSD",
    "direction": "LONG",
    "setup": "A+ SNIPER",
    "poi": 6,
    "align": "COUNTER_TREND",
    "htf_bias": "BEARISH",
    "ltf_bias": "BULLISH",
    "entry": 1.08550,
    "sl": 1.08250,
    "tp": 1.09450,
    "valid": True,
    "amd_state": "manipulation",
    "sniper_today": "3",
    "execution_today": 5,
    "guardian_label": "CONTINUATION BUY (HTF COUNTER — STANDBY)",
    "guardian_risk": 2,
    "timestamp": "2026-06-03T14:30:00Z",
}
dec9 = decode_v17_56_9_payload(payload_9)
check("v17.56.9 guardian_label", dec9["guardian_label"],
      "CONTINUATION BUY (HTF COUNTER — STANDBY)")
check("v17.56.9 guardian_risk", dec9["guardian_risk"], 2)
check("v17.56.9 amd_state (carryover)", dec9["amd_state"], "MANIPULATION")
check("v17.56.9 sniper_today (carryover)", dec9["sniper_today"], 3)
check_true("is_oie_payload(v17.56.9)", is_oie_payload(payload_9))


print("\n" + "=" * 70)
print("STEP 4: v17.56.8 / v17.56.7 backward compatibility (defaults applied)")
print("=" * 70)
payload_8 = {
    "version": "v17.56.8",
    "mode": "EXECUTION",
    "session": "NY",
    "symbol": "GBPUSD",
    "direction": "LONG",
    "setup": "A+ SNIPER",
    "poi": 5,
    "entry": 1.27000,
    "sl": 1.26800,
    "tp": 1.27600,
    "valid": True,
    "amd_state": "markup",
    "sniper_today": 2,
    "execution_today": 1,
    "timestamp": "2026-06-03T09:00:00Z",
}
dec8 = decode_v17_56_8_payload(payload_8)
check("v17.56.8 guardian_label default", dec8["guardian_label"], None)
check("v17.56.8 guardian_risk default", dec8["guardian_risk"], 0)
check("v17.56.8 amd_state still parsed", dec8["amd_state"], "MARKUP")

payload_7 = {
    "version": "v17.56.7",
    "mode": "DATA",
    "session": "LONDON",
    "symbol": "USDJPY",
    "direction": "SHORT",
    "setup": "A+ SNIPER",
    "poi": 4,
    "entry": 150.00,
    "sl": 150.20,
    "tp": 149.40,
    "valid": True,
    "timestamp": "2026-06-03T08:00:00Z",
}
dec7 = decode_v17_56_7_payload(payload_7)
check("v17.56.7 guardian_label default", dec7["guardian_label"], None)
check("v17.56.7 guardian_risk default", dec7["guardian_risk"], 0)
check("v17.56.7 amd_state default", dec7["amd_state"], "ACCUMULATION")


print("\n" + "=" * 70)
print("STEP 5: decode_payload() universal dispatcher")
print("=" * 70)
check("dispatch v17.56.9 guardian_risk", decode_payload(payload_9)["guardian_risk"], 2)
check("dispatch v17.56.8 guardian default", decode_payload(payload_8)["guardian_risk"], 0)
check("dispatch v17.56.7 guardian default", decode_payload(payload_7)["guardian_risk"], 0)
legacy = {
    "type": "sniper_long",
    "symbol": "AUDUSD",
    "entry_price": "0.6600",
    "stop_loss": "0.6580",
    "take_profit": "0.6660",
    "version": "v17.15",
}
check("dispatch legacy guardian_label", decode_payload(legacy)["guardian_label"], None)
check("dispatch legacy guardian_risk", decode_payload(legacy)["guardian_risk"], 0)


print("\n" + "=" * 70)
print("STEP 6: Opportunity insert/retrieve roundtrip (guardian fields)")
print("=" * 70)
from src.oie_database import insert_opportunity, get_opportunity
opp = normalize_oie_payload(payload_9)
check("normalized opp guardian_label", opp["guardian_label"],
      "CONTINUATION BUY (HTF COUNTER — STANDBY)")
check("normalized opp guardian_risk", opp["guardian_risk"], 2)
opp_id = insert_opportunity(opp, db_path=TEST_DB)
fetched = get_opportunity(opp_id, db_path=TEST_DB)
check("opp DB guardian_label", fetched["guardian_label"],
      "CONTINUATION BUY (HTF COUNTER — STANDBY)")
check("opp DB guardian_risk", fetched["guardian_risk"], 2)


print("\n" + "=" * 70)
print("STEP 7: Signal insert/retrieve roundtrip (legacy bridge)")
print("=" * 70)
from src.tracker.processor import expand_compact_entry
compact = oie_to_legacy_compact(payload_9)
check("compact carries _guardian_label", compact.get("_guardian_label"),
      "CONTINUATION BUY (HTF COUNTER — STANDBY)")
check("compact carries _guardian_risk", compact.get("_guardian_risk"), 2)
record = expand_compact_entry(compact)
check("expanded record guardian_label", record.get("guardian_label"),
      "CONTINUATION BUY (HTF COUNTER — STANDBY)")
check("expanded record guardian_risk", record.get("guardian_risk"), 2)
sig_id = insert_signal(record, db_path=TEST_DB)
sig = get_signal(sig_id, db_path=TEST_DB)
check("signal DB guardian_label", sig["guardian_label"],
      "CONTINUATION BUY (HTF COUNTER — STANDBY)")
check("signal DB guardian_risk", sig["guardian_risk"], 2)


print("\n" + "=" * 70)
print("STEP 8: guardian_risk filter on get_signals / count_signals")
print("=" * 70)
filtered = get_signals(guardian_risk=2, db_path=TEST_DB)
check_true("get_signals(guardian_risk=2) returns row", len(filtered) >= 1)
check_true("count_signals(guardian_risk=2) >= 1",
           count_signals(guardian_risk=2, db_path=TEST_DB) >= 1)
check("count_signals(guardian_risk=1) == 0",
      count_signals(guardian_risk=1, db_path=TEST_DB), 0)


print("\n" + "=" * 70)
print("STEP 9: Three Guardian risk scenarios (0=low, 1=medium, 2=high)")
print("=" * 70)
scenarios = [
    ("low / HTF aligned", 0, "CONTINUATION BUY (HTF ALIGNED)"),
    ("medium / minor mismatch", 1, "CONTINUATION SELL (HTF MINOR MISMATCH)"),
    ("high / counter-trend standby", 2, "CONTINUATION BUY (HTF COUNTER — STANDBY)"),
]
for name, risk, label in scenarios:
    p = dict(payload_9)
    p["symbol"] = f"TEST{risk}"
    p["guardian_risk"] = risk
    p["guardian_label"] = label
    rec = decode_payload(p)
    check(f"scenario {name} guardian_risk", rec["guardian_risk"], risk)
    check(f"scenario {name} guardian_label", rec["guardian_label"], label)


print("\n" + "=" * 70)
print("STEP 10: /health endpoint via Flask test client")
print("=" * 70)
from src.webhook_server.app import create_app
app = create_app()
client = app.test_client()
resp = client.get('/api/v1/health')
data = resp.get_json()
check("/health status code", resp.status_code, 200)
check_true("/health version >= v17.56.9", data["version"] >= "v17.56.9")
check_true("/health features include guardian_htf_gating",
           "guardian_htf_gating" in data["features"])


print("\n" + "=" * 70)
print("STEP 11: /signals API includes guardian fields + filter echo")
print("=" * 70)
resp = client.get('/api/v1/signals')
data = resp.get_json()
check("/signals status code", resp.status_code, 200)
signals = data.get("signals", [])
check_true("/signals returns >= 1 signal", len(signals) >= 1)
if signals:
    s0 = signals[0]
    check_true("/signals row has guardian_label key", "guardian_label" in s0)
    check_true("/signals row has guardian_risk key", "guardian_risk" in s0)
check_true("/signals filters echo guardian_risk", "guardian_risk" in data.get("filters", {}))

# guardian_risk query filter
resp = client.get('/api/v1/signals?guardian_risk=2')
data = resp.get_json()
check("/signals?guardian_risk=2 status", resp.status_code, 200)
check_true("/signals?guardian_risk=2 returns >= 1", len(data.get("signals", [])) >= 1)
check("/signals?guardian_risk=2 filter value", data["filters"]["guardian_risk"], 2)


print("\n" + "=" * 70)
print(f"RESULTS: {PASS} passed, {FAIL} failed")
print("=" * 70)
sys.exit(1 if FAIL else 0)
