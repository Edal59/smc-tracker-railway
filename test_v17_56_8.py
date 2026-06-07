#!/usr/bin/env python3
"""
Test suite for v17.56.8 — HUD Sync + AMD Context Awareness + Daily Counters.

Verifies:
  1. version.py single source of truth + amd_state normalization
  2. v17.56.8 payload decodes with new fields (amd_state, sniper_today, execution_today)
  3. v17.56.7 payload backward compatibility (safe defaults applied)
  4. decode_payload() universal dispatcher routes correctly
  5. DB migration adds new columns to signals + opportunities
  6. Signal insert / retrieve roundtrip carries the new fields
  7. Opportunity insert / retrieve roundtrip carries the new fields
  8. /health returns v17.56.8 + extended features (Flask test client)
  9. /signals API response includes the new fields

Run from repo root:  python3 test_v17_56_8.py
"""
import os
import sys
import sqlite3
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Isolated temp DB + no auth for the test client
TEST_DB = os.path.join(tempfile.gettempdir(), 'tradex_test_v17_56_8.db')
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
print("STEP 1: version.py — single source of truth")
print("=" * 70)
from src.version import (
    VERSION, get_version, get_features, normalize_amd_state,
    VALID_AMD_STATES, DEFAULT_AMD_STATE,
)
# VERSION is a single source of truth that advances with each release; assert
# it is at least v17.56.8 (the release that introduced these HUD-sync features).
check_true("VERSION >= v17.56.8", VERSION >= "v17.56.8")
check_true("get_version() >= v17.56.8", get_version() >= "v17.56.8")
check_true("features include hud_sync", "hud_sync" in get_features())
check_true("features include amd_context_awareness", "amd_context_awareness" in get_features())
check_true("features include daily_counters", "daily_counters" in get_features())
check("DEFAULT_AMD_STATE", DEFAULT_AMD_STATE, "ACCUMULATION")
check("normalize_amd_state('manipulation')", normalize_amd_state("manipulation"), "MANIPULATION")
check("normalize_amd_state('BOGUS')", normalize_amd_state("BOGUS"), "ACCUMULATION")
check("normalize_amd_state(None)", normalize_amd_state(None), "ACCUMULATION")
check("normalize_amd_state('  markup ')", normalize_amd_state("  markup "), "MARKUP")


print("\n" + "=" * 70)
print("STEP 2: DB init + migration adds new columns")
print("=" * 70)
from src.database import init_db, insert_signal, get_signals, get_signal, count_signals
db_path = init_db(TEST_DB)
print(f"  DB initialized at {db_path}")
conn = sqlite3.connect(TEST_DB)
sig_cols = [c[1] for c in conn.execute("PRAGMA table_info(signals)").fetchall()]
opp_cols = [c[1] for c in conn.execute("PRAGMA table_info(opportunities)").fetchall()]
conn.close()
for col in ("amd_state", "sniper_today", "execution_today"):
    check_true(f"signals.{col} exists", col in sig_cols)
for col in ("amd_state", "sniper_today", "execution_today"):
    check_true(f"opportunities.{col} exists", col in opp_cols)

# idempotency: re-run init_db should not error
init_db(TEST_DB)
check_true("init_db re-run is idempotent", True)


print("\n" + "=" * 70)
print("STEP 3: v17.56.8 payload decode (new fields parsed)")
print("=" * 70)
from src.oie_processor import (
    decode_payload, decode_v17_56_8_payload, decode_v17_56_7_payload,
    decode_legacy_payload, normalize_oie_payload, oie_to_legacy_compact,
    is_oie_payload,
)

payload_8 = {
    "version": "v17.56.8",
    "mode": "EXECUTION",
    "session": "NY",
    "symbol": "EURUSD",
    "direction": "LONG",
    "setup": "A+ SNIPER",
    "poi": 6,
    "align": "WITH_TREND",
    "htf_bias": "BULLISH",
    "ltf_bias": "BULLISH",
    "entry": 1.08550,
    "sl": 1.08250,
    "tp": 1.09450,
    "valid": True,
    "amd_state": "manipulation",
    "sniper_today": "3",
    "execution_today": 5,
    "timestamp": "2026-06-03T14:30:00Z",
}
dec8 = decode_v17_56_8_payload(payload_8)
check("v17.56.8 amd_state", dec8["amd_state"], "MANIPULATION")
check("v17.56.8 sniper_today", dec8["sniper_today"], 3)
check("v17.56.8 execution_today", dec8["execution_today"], 5)
check_true("is_oie_payload(v17.56.8)", is_oie_payload(payload_8))


print("\n" + "=" * 70)
print("STEP 4: v17.56.7 backward compatibility (defaults applied)")
print("=" * 70)
payload_7 = {
    "version": "v17.56.7",
    "mode": "DATA",
    "session": "LONDON",
    "symbol": "GBPUSD",
    "direction": "LONG",
    "setup": "A+ SNIPER",
    "poi": 5,
    "align": "WITH_TREND",
    "htf_bias": "BULLISH",
    "ltf_bias": "BULLISH",
    "entry": 1.27000,
    "sl": 1.26800,
    "tp": 1.27600,
    "valid": True,
    "timestamp": "2026-06-03T09:00:00Z",
}
dec7 = decode_v17_56_7_payload(payload_7)
check("v17.56.7 amd_state default", dec7["amd_state"], "ACCUMULATION")
check("v17.56.7 sniper_today default", dec7["sniper_today"], 0)
check("v17.56.7 execution_today default", dec7["execution_today"], 0)


print("\n" + "=" * 70)
print("STEP 5: decode_payload() universal dispatcher")
print("=" * 70)
check("dispatch v17.56.8", decode_payload(payload_8)["amd_state"], "MANIPULATION")
check("dispatch v17.56.7", decode_payload(payload_7)["amd_state"], "ACCUMULATION")
legacy = {
    "type": "sniper_long",
    "symbol": "USDJPY",
    "entry_price": "150.00",
    "stop_loss": "149.80",
    "take_profit": "150.60",
    "version": "v17.15",
}
check("dispatch legacy amd_state", decode_payload(legacy)["amd_state"], "ACCUMULATION")
check("dispatch legacy sniper_today", decode_payload(legacy)["sniper_today"], 0)


print("\n" + "=" * 70)
print("STEP 6: Opportunity insert/retrieve roundtrip")
print("=" * 70)
from src.oie_database import insert_opportunity, get_opportunity
opp = normalize_oie_payload(payload_8)
check("normalized opp amd_state", opp["amd_state"], "MANIPULATION")
opp_id = insert_opportunity(opp, db_path=TEST_DB)
fetched = get_opportunity(opp_id, db_path=TEST_DB)
check("opp DB amd_state", fetched["amd_state"], "MANIPULATION")
check("opp DB sniper_today", fetched["sniper_today"], 3)
check("opp DB execution_today", fetched["execution_today"], 5)


print("\n" + "=" * 70)
print("STEP 7: Signal insert/retrieve roundtrip (legacy bridge)")
print("=" * 70)
from src.tracker.processor import expand_compact_entry
compact = oie_to_legacy_compact(payload_8)
check("compact carries _amd_state", compact.get("_amd_state"), "MANIPULATION")
record = expand_compact_entry(compact)
check("expanded record amd_state", record.get("amd_state"), "MANIPULATION")
check("expanded record sniper_today", record.get("sniper_today"), 3)
check("expanded record execution_today", record.get("execution_today"), 5)
sig_id = insert_signal(record, db_path=TEST_DB)
sig = get_signal(sig_id, db_path=TEST_DB)
check("signal DB amd_state", sig["amd_state"], "MANIPULATION")
check("signal DB sniper_today", sig["sniper_today"], 3)
check("signal DB execution_today", sig["execution_today"], 5)

# amd_state filter on get_signals / count_signals
filtered = get_signals(amd_state="MANIPULATION", db_path=TEST_DB)
check_true("get_signals(amd_state=MANIPULATION) returns row", len(filtered) >= 1)
check_true("count_signals(amd_state=MANIPULATION) >= 1",
           count_signals(amd_state="MANIPULATION", db_path=TEST_DB) >= 1)
check("count_signals(amd_state=DISTRIBUTION) == 0",
      count_signals(amd_state="DISTRIBUTION", db_path=TEST_DB), 0)


print("\n" + "=" * 70)
print("STEP 8: /health endpoint via Flask test client")
print("=" * 70)
from src.webhook_server.app import create_app
app = create_app()
client = app.test_client()
resp = client.get('/api/v1/health')
data = resp.get_json()
check("/health status code", resp.status_code, 200)
check_true("/health version >= v17.56.8", data["version"] >= "v17.56.8")
check_true("/health features include hud_sync", "hud_sync" in data["features"])
check_true("/health features include amd_context_awareness",
           "amd_context_awareness" in data["features"])
check_true("/health features include daily_counters", "daily_counters" in data["features"])


print("\n" + "=" * 70)
print("STEP 9: /signals API includes new fields")
print("=" * 70)
resp = client.get('/api/v1/signals')
data = resp.get_json()
check("/signals status code", resp.status_code, 200)
signals = data.get("signals", [])
check_true("/signals returns >= 1 signal", len(signals) >= 1)
if signals:
    s0 = signals[0]
    check_true("/signals row has amd_state key", "amd_state" in s0)
    check_true("/signals row has sniper_today key", "sniper_today" in s0)
    check_true("/signals row has execution_today key", "execution_today" in s0)
check_true("/signals filters echo amd_state", "amd_state" in data.get("filters", {}))


print("\n" + "=" * 70)
print(f"RESULTS: {PASS} passed, {FAIL} failed")
print("=" * 70)
sys.exit(1 if FAIL else 0)
