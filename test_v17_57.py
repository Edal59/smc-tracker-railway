#!/usr/bin/env python3
"""
Test suite for v17.57 — PDH/PDL Institutional Liquidity Levels.

Verifies:
  1. version.py single source of truth (VERSION + pdh_pdl_liquidity feature)
  2. v17.57 payload decodes the 6 new fields (pdh / pdl / near_pdh /
     near_pdl / pdh_swept / pdl_swept) with correct types
  3. v17.56.9 / v17.56.8 / v17.56.7 / legacy backward compatibility
     (PDH/PDL default to 0.0 / False; all prior fields still parsed)
  4. decode_payload() universal dispatcher routes v17.57 correctly
  5. Graceful float/bool coercion ('invalid' -> 0.0, missing -> default)
  6. Four institutional-liquidity integration scenarios
  7. NO database schema change — PDH/PDL columns are NOT persisted
  8. /health returns v17.57 + pdh_pdl_liquidity feature (Flask test client)
  9. POST /signal response echoes the PDH/PDL fields
 10. GET /latest surfaces the in-memory PDH/PDL snapshot
 11. /signals still works (no regression; PDH/PDL absent from DB rows)

Run from repo root:  python3 test_v17_57.py
"""
import os
import sys
import sqlite3
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Isolated temp DB + no auth for the test client
TEST_DB = os.path.join(tempfile.gettempdir(), 'tradex_test_v17_57.db')
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
print("STEP 1: version.py — VERSION bump + pdh_pdl_liquidity feature")
print("=" * 70)
from src.version import VERSION, get_version, get_features
check("VERSION", VERSION, "v17.57")
check("get_version()", get_version(), "v17.57")
check_true("features include pdh_pdl_liquidity", "pdh_pdl_liquidity" in get_features())
check_true("features still include guardian_htf_gating (carryover)",
           "guardian_htf_gating" in get_features())
check_true("features still include hud_sync (carryover)", "hud_sync" in get_features())


print("\n" + "=" * 70)
print("STEP 2: DB init — NO new PDH/PDL columns (in-memory only)")
print("=" * 70)
from src.database import init_db, insert_signal, get_signals, get_signal, count_signals
db_path = init_db(TEST_DB)
print(f"  DB initialized at {db_path}")
conn = sqlite3.connect(TEST_DB)
sig_cols = [c[1] for c in conn.execute("PRAGMA table_info(signals)").fetchall()]
opp_cols = [c[1] for c in conn.execute("PRAGMA table_info(opportunities)").fetchall()]
conn.close()
for col in ("pdh", "pdl", "near_pdh", "near_pdl", "pdh_swept", "pdl_swept"):
    check_true(f"signals.{col} NOT persisted (in-memory only)", col not in sig_cols)
    check_true(f"opportunities.{col} NOT persisted (in-memory only)", col not in opp_cols)


print("\n" + "=" * 70)
print("STEP 3: v17.57 payload decode (6 new PDH/PDL fields parsed)")
print("=" * 70)
from src.oie_processor import (
    decode_payload, decode_v17_57_payload, decode_v17_56_9_payload,
    decode_v17_56_8_payload, decode_v17_56_7_payload, decode_legacy_payload,
    normalize_oie_payload, oie_to_legacy_compact, is_oie_payload,
    _apply_pdh_pdl_fields,
)

payload_57 = {
    "version": "v17.57",
    "mode": "EXECUTION",
    "session": "NY",
    "symbol": "EURUSD",
    "direction": "LONG",
    "setup": "A+ SNIPER",
    "poi": 7,
    "align": "ALIGNED",
    "htf_bias": "BULLISH",
    "ltf_bias": "BULLISH",
    "entry": 1.08550,
    "sl": 1.08250,
    "tp": 1.09450,
    "valid": True,
    "amd_state": "manipulation",
    "sniper_today": "3",
    "execution_today": 5,
    "guardian_label": "CONTINUATION BUY (HTF ALIGNED)",
    "guardian_risk": 0,
    "pdh": 1.08230,
    "pdl": 1.07910,
    "near_pdh": 0,
    "near_pdl": 1,
    "pdh_swept": 0,
    "pdl_swept": 1,
    "timestamp": "2026-06-04T14:30:00Z",
}
dec = decode_v17_57_payload(payload_57)
check("v17.57 pdh (float)", dec["pdh"], 1.08230)
check("v17.57 pdl (float)", dec["pdl"], 1.07910)
check("v17.57 near_pdh (bool)", dec["near_pdh"], False)
check("v17.57 near_pdl (bool)", dec["near_pdl"], True)
check("v17.57 pdh_swept (bool)", dec["pdh_swept"], False)
check("v17.57 pdl_swept (bool)", dec["pdl_swept"], True)
check_true("v17.57 pdh is float type", isinstance(dec["pdh"], float))
check_true("v17.57 near_pdl is bool type", isinstance(dec["near_pdl"], bool))
# Carryover of prior version fields
check("v17.57 guardian_risk (carryover)", dec["guardian_risk"], 0)
check("v17.57 amd_state (carryover)", dec["amd_state"], "MANIPULATION")
check("v17.57 sniper_today (carryover)", dec["sniper_today"], 3)
check_true("is_oie_payload(v17.57)", is_oie_payload(payload_57))


print("\n" + "=" * 70)
print("STEP 4: Backward compatibility (PDH/PDL default to 0.0 / False)")
print("=" * 70)
payload_9 = {
    "version": "v17.56.9", "mode": "EXECUTION", "session": "NY",
    "symbol": "GBPUSD", "direction": "LONG", "setup": "A+ SNIPER", "poi": 6,
    "entry": 1.27000, "sl": 1.26800, "tp": 1.27600, "valid": True,
    "guardian_label": "CONTINUATION BUY (HTF ALIGNED)", "guardian_risk": 1,
}
dec9 = decode_v17_56_9_payload(payload_9)
check("v17.56.9 pdh default", dec9["pdh"], 0.0)
check("v17.56.9 pdl default", dec9["pdl"], 0.0)
check("v17.56.9 near_pdh default", dec9["near_pdh"], False)
check("v17.56.9 near_pdl default", dec9["near_pdl"], False)
check("v17.56.9 pdh_swept default", dec9["pdh_swept"], False)
check("v17.56.9 pdl_swept default", dec9["pdl_swept"], False)
check("v17.56.9 guardian_risk still parsed", dec9["guardian_risk"], 1)

payload_8 = {
    "version": "v17.56.8", "mode": "EXECUTION", "session": "NY",
    "symbol": "USDJPY", "direction": "SHORT", "setup": "A+ SNIPER", "poi": 5,
    "entry": 150.00, "sl": 150.20, "tp": 149.40, "valid": True,
    "amd_state": "markup",
}
dec8 = decode_v17_56_8_payload(payload_8)
check("v17.56.8 pdh default", dec8["pdh"], 0.0)
check("v17.56.8 pdl_swept default", dec8["pdl_swept"], False)
check("v17.56.8 guardian_risk default", dec8["guardian_risk"], 0)
check("v17.56.8 amd_state still parsed", dec8["amd_state"], "MARKUP")

payload_7 = {
    "version": "v17.56.7", "mode": "DATA", "session": "LONDON",
    "symbol": "AUDUSD", "direction": "LONG", "setup": "A+ SNIPER", "poi": 4,
    "entry": 0.66000, "sl": 0.65800, "tp": 0.66600, "valid": True,
}
dec7 = decode_v17_56_7_payload(payload_7)
check("v17.56.7 pdh default", dec7["pdh"], 0.0)
check("v17.56.7 near_pdl default", dec7["near_pdl"], False)
check("v17.56.7 amd_state default", dec7["amd_state"], "ACCUMULATION")

legacy = {
    "type": "sniper_long", "symbol": "NZDUSD", "entry_price": "0.6100",
    "stop_loss": "0.6080", "take_profit": "0.6160", "version": "v17.15",
}
decl = decode_legacy_payload(legacy)
check("legacy pdh default", decl["pdh"], 0.0)
check("legacy pdl_swept default", decl["pdl_swept"], False)


print("\n" + "=" * 70)
print("STEP 5: decode_payload() universal dispatcher routes v17.57")
print("=" * 70)
check("dispatch v17.57 pdl_swept", decode_payload(payload_57)["pdl_swept"], True)
check("dispatch v17.57 pdh", decode_payload(payload_57)["pdh"], 1.08230)
check("dispatch v17.56.9 pdh default", decode_payload(payload_9)["pdh"], 0.0)
check("dispatch v17.56.8 pdl default", decode_payload(payload_8)["pdl"], 0.0)
check("dispatch v17.56.7 near_pdh default", decode_payload(payload_7)["near_pdh"], False)
check("dispatch legacy pdh default", decode_payload(legacy)["pdh"], 0.0)


print("\n" + "=" * 70)
print("STEP 6: Graceful coercion (invalid -> 0.0, missing -> default)")
print("=" * 70)
p_bad = dict(payload_57)
p_bad["pdh"] = "invalid"
p_bad["pdl"] = None
p_bad["near_pdh"] = "yes"   # non-int -> default 0 -> False
p_bad["pdl_swept"] = ""
rec_bad = decode_payload(p_bad)
check("invalid pdh -> 0.0", rec_bad["pdh"], 0.0)
check("None pdl -> 0.0", rec_bad["pdl"], 0.0)
check("non-int near_pdh -> False", rec_bad["near_pdh"], False)
check("empty pdl_swept -> False", rec_bad["pdl_swept"], False)
# _apply on a record with no payload fields
rec_empty = {}
_apply_pdh_pdl_fields({}, rec_empty)
check("_apply_pdh_pdl_fields on empty payload pdh", rec_empty["pdh"], 0.0)
check("_apply_pdh_pdl_fields on empty payload near_pdl", rec_empty["near_pdl"], False)


print("\n" + "=" * 70)
print("STEP 7: Four institutional-liquidity integration scenarios")
print("=" * 70)
scenarios = [
    # (name, near_pdh, near_pdl, pdh_swept, pdl_swept)
    ("near PDH, no sweep", 1, 0, 0, 0),
    ("PDH swept (raid high)", 0, 0, 1, 0),
    ("near PDL + PDL swept", 0, 1, 0, 1),
    ("away from both levels", 0, 0, 0, 0),
]
for i, (name, nh, nl, sh, sl) in enumerate(scenarios):
    p = dict(payload_57)
    p["symbol"] = f"TEST{i}"
    p["near_pdh"], p["near_pdl"] = nh, nl
    p["pdh_swept"], p["pdl_swept"] = sh, sl
    rec = decode_payload(p)
    check_true(f"scenario '{name}' near_pdh", rec["near_pdh"] == bool(nh))
    check_true(f"scenario '{name}' near_pdl", rec["near_pdl"] == bool(nl))
    check_true(f"scenario '{name}' pdh_swept", rec["pdh_swept"] == bool(sh))
    check_true(f"scenario '{name}' pdl_swept", rec["pdl_swept"] == bool(sl))


print("\n" + "=" * 70)
print("STEP 8: normalize_oie_payload carries PDH/PDL (in-memory record)")
print("=" * 70)
opp = normalize_oie_payload(payload_57)
check("normalized opp pdh", opp["pdh"], 1.08230)
check("normalized opp pdl", opp["pdl"], 1.07910)
check("normalized opp near_pdl", opp["near_pdl"], True)
check("normalized opp pdl_swept", opp["pdl_swept"], True)


print("\n" + "=" * 70)
print("STEP 9: /health endpoint via Flask test client")
print("=" * 70)
from src.webhook_server.app import create_app
app = create_app()
client = app.test_client()
resp = client.get('/api/v1/health')
data = resp.get_json()
check("/health status code", resp.status_code, 200)
check("/health version", data["version"], "v17.57")
check_true("/health features include pdh_pdl_liquidity",
           "pdh_pdl_liquidity" in data["features"])


print("\n" + "=" * 70)
print("STEP 10: POST /signal echoes PDH/PDL + GET /latest surfaces snapshot")
print("=" * 70)
resp = client.post('/api/v1/signal', json=payload_57)
data = resp.get_json()
check("POST /signal status code", resp.status_code, 200)
check("POST /signal echoes pdh", data.get("pdh"), 1.08230)
check("POST /signal echoes pdl", data.get("pdl"), 1.07910)
check("POST /signal echoes near_pdl", data.get("near_pdl"), True)
check("POST /signal echoes pdl_swept", data.get("pdl_swept"), True)

resp = client.get('/api/v1/latest')
data = resp.get_json()
check("/latest status code", resp.status_code, 200)
check("/latest version", data.get("version"), "v17.57")
sig = data.get("signal")
check_true("/latest signal is populated", sig is not None)
if sig:
    check("/latest pdh", sig["pdh"], 1.08230)
    check("/latest pdl", sig["pdl"], 1.07910)
    check("/latest near_pdl", sig["near_pdl"], True)
    check("/latest pdl_swept", sig["pdl_swept"], True)
    check("/latest pair", sig["pair"], "EURUSD")


print("\n" + "=" * 70)
print("STEP 11: /signals still works (no regression; PDH/PDL not in DB rows)")
print("=" * 70)
resp = client.get('/api/v1/signals')
data = resp.get_json()
check("/signals status code", resp.status_code, 200)
signals = data.get("signals", [])
check_true("/signals returns >= 1 signal", len(signals) >= 1)
if signals:
    s0 = signals[0]
    check_true("/signals row has NO pdh column (in-memory only)", "pdh" not in s0)
    check_true("/signals row still has guardian_risk (persisted)", "guardian_risk" in s0)


print("\n" + "=" * 70)
print(f"RESULTS: {PASS} passed, {FAIL} failed")
print("=" * 70)
sys.exit(1 if FAIL else 0)
