#!/usr/bin/env python3
"""
Test suite for v17.58 — Sequence State Machine & BOS-Anchored Ranges.

Covers:
  1. version.py single source of truth (VERSION + 2 new feature flags)
  2. DB migration adds the 17 new columns to the signals table
  3. v17.58 payload decodes the 17 new fields (sequence_state / sequence_step /
     missing_step / sequence_complete / bos_range_* / bos_trend / 5 state flags /
     4 liquidity-shift flags)
  4. decode_payload() universal dispatcher routes v17.58 correctly
  5. Backward compatibility: v17.57 / v17.56.9 / v17.56.8 / v17.56.7 / legacy
     payloads default the new fields (0 / 0.0 / None / False)
  6. Graceful coercion of invalid / missing values
  7. 5-state sequence progression scenarios
  8. bos_trend domain {1, -1, 0}
  9. End-to-end DB persistence roundtrip (legacy bridge -> insert_signal -> read)
 10. /health returns >= v17.58 + new feature flags (Flask test client)
 11. POST /signal echoes the new fields + persists them to /signals rows
 12. NEW GET /sequence-analytics endpoint

Run from repo root:  python3 test_v17_58.py
"""
import os
import sys
import sqlite3
import tempfile

# ── Test environment (mirrors test_v17_57.py) ──
TEST_DB = os.path.join(tempfile.gettempdir(), 'tradex_test_v17_58.db')
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
    if got == expected:
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


# The 17 persisted v17.58 fields.
NEW_COLUMNS = [
    "sequence_state", "sequence_step", "missing_step", "sequence_complete",
    "bos_range_high", "bos_range_low", "bos_equilibrium", "bos_trend",
    "state1_location", "state2_liquidity", "state3_displacement",
    "state4_mitigation", "state5_execution",
    "liquidity_swept", "ltf_shift_detected", "displacement_detected",
    "mitigation_zone",
]


print("=" * 70)
print("STEP 1: version.py — VERSION bump + 2 new feature flags")
print("=" * 70)
from src.version import (
    VERSION, get_version, get_features,
    normalize_sequence_state, normalize_bos_trend,
)
check_true("VERSION >= v17.58", VERSION >= "v17.58")
check_true("get_version() >= v17.58", get_version() >= "v17.58")
check_true("features include sequence_state_machine",
           "sequence_state_machine" in get_features())
check_true("features include bos_anchored_ranges",
           "bos_anchored_ranges" in get_features())
check_true("features still include pdh_pdl_liquidity (carryover)",
           "pdh_pdl_liquidity" in get_features())
check_true("features still include guardian_htf_gating (carryover)",
           "guardian_htf_gating" in get_features())

# normalize helpers
check("normalize_sequence_state(5)", normalize_sequence_state(5), 5)
check("normalize_sequence_state('3')", normalize_sequence_state("3"), 3)
check("normalize_sequence_state(99) -> default 0", normalize_sequence_state(99), 0)
check("normalize_sequence_state(None) -> default 0", normalize_sequence_state(None), 0)
check("normalize_sequence_state('x') -> default 0", normalize_sequence_state("x"), 0)
check("normalize_bos_trend(1)", normalize_bos_trend(1), 1)
check("normalize_bos_trend(-1)", normalize_bos_trend(-1), -1)
check("normalize_bos_trend(0)", normalize_bos_trend(0), 0)
check("normalize_bos_trend(7) -> default 0", normalize_bos_trend(7), 0)
check("normalize_bos_trend(None) -> default 0", normalize_bos_trend(None), 0)


print("\n" + "=" * 70)
print("STEP 2: DB init — the 17 v17.58 columns ARE persisted in signals table")
print("=" * 70)
from src.database import (
    init_db, insert_signal, get_signals, get_signal, count_signals,
)
db_path = init_db(TEST_DB)
print(f"  DB initialized at {db_path}")
conn = sqlite3.connect(TEST_DB)
sig_cols = [c[1] for c in conn.execute("PRAGMA table_info(signals)").fetchall()]
idx = [r[1] for r in conn.execute("PRAGMA index_list(signals)").fetchall()]
conn.close()
for col in NEW_COLUMNS:
    check_true(f"signals.{col} persisted", col in sig_cols)
check_true("idx_signals_sequence_state index exists",
           "idx_signals_sequence_state" in idx)
# idempotency: re-running migration must not error
init_db(TEST_DB)
check_true("init_db() is idempotent (re-run OK)", True)


print("\n" + "=" * 70)
print("STEP 3: v17.58 payload decode (17 new fields parsed)")
print("=" * 70)
from src.oie_processor import (
    decode_payload, decode_v17_58_payload, decode_v17_57_payload,
    decode_v17_56_9_payload, decode_v17_56_8_payload, decode_v17_56_7_payload,
    decode_legacy_payload, normalize_oie_payload, oie_to_legacy_compact,
    is_oie_payload, _apply_sequence_bos_fields,
)

payload_58 = {
    "version": "v17.58",
    "mode": "EXECUTION",
    "session": "NY",
    "symbol": "EURUSD",
    "direction": "LONG",
    "setup": "A+ SNIPER",
    "poi": 7,
    "entry": 1.08550,
    "sl": 1.08250,
    "tp": 1.09450,
    "valid": True,
    "amd_state": "manipulation",
    "guardian_risk": 0,
    "pdh": 1.08230,
    "pdl": 1.07910,
    # v17.58 sequence state machine
    "sequence_state": 5,
    "sequence_step": "EXECUTION",
    "missing_step": "",
    "sequence_complete": 1,
    # BOS-anchored ranges
    "bos_range_high": 1.09000,
    "bos_range_low": 1.08000,
    "bos_equilibrium": 1.08500,
    "bos_trend": 1,
    # state completion flags
    "state1_location": 1,
    "state2_liquidity": 1,
    "state3_displacement": 1,
    "state4_mitigation": 1,
    "state5_execution": 1,
    # liquidity / shift detection
    "liquidity_swept": 1,
    "ltf_shift_detected": 1,
    "displacement_detected": 1,
    "mitigation_zone": 1,
    "timestamp": "2026-06-04T14:30:00Z",
}
dec = decode_v17_58_payload(payload_58)
check("v17.58 sequence_state (int)", dec["sequence_state"], 5)
check("v17.58 sequence_step (text)", dec["sequence_step"], "EXECUTION")
check("v17.58 missing_step (text)", dec["missing_step"], "")
check("v17.58 sequence_complete (bool)", dec["sequence_complete"], True)
check("v17.58 bos_range_high (float)", dec["bos_range_high"], 1.09000)
check("v17.58 bos_range_low (float)", dec["bos_range_low"], 1.08000)
check("v17.58 bos_equilibrium (float)", dec["bos_equilibrium"], 1.08500)
check("v17.58 bos_trend (int)", dec["bos_trend"], 1)
check("v17.58 state1_location (bool)", dec["state1_location"], True)
check("v17.58 state5_execution (bool)", dec["state5_execution"], True)
check("v17.58 liquidity_swept (bool)", dec["liquidity_swept"], True)
check("v17.58 ltf_shift_detected (bool)", dec["ltf_shift_detected"], True)
check("v17.58 displacement_detected (bool)", dec["displacement_detected"], True)
check("v17.58 mitigation_zone (bool)", dec["mitigation_zone"], True)
check_true("v17.58 sequence_state is int", isinstance(dec["sequence_state"], int))
check_true("v17.58 bos_range_high is float", isinstance(dec["bos_range_high"], float))
check_true("v17.58 sequence_complete is bool", isinstance(dec["sequence_complete"], bool))
# carryover of prior version fields
check("v17.58 pdh (carryover)", dec["pdh"], 1.08230)
check("v17.58 amd_state (carryover)", dec["amd_state"], "MANIPULATION")
check_true("is_oie_payload(v17.58)", is_oie_payload(payload_58))


print("\n" + "=" * 70)
print("STEP 4: Backward compatibility (new fields default to 0 / 0.0 / None / False)")
print("=" * 70)
payload_57 = {
    "version": "v17.57", "mode": "EXECUTION", "session": "NY",
    "symbol": "GBPUSD", "direction": "LONG", "setup": "A+ SNIPER", "poi": 6,
    "entry": 1.27000, "sl": 1.26800, "tp": 1.27600, "valid": True,
    "pdh": 1.2750, "pdl": 1.2680,
}
dec57 = decode_v17_57_payload(payload_57)
check("v17.57 sequence_state default", dec57["sequence_state"], 0)
check("v17.57 sequence_step default", dec57["sequence_step"], None)
check("v17.57 sequence_complete default", dec57["sequence_complete"], False)
check("v17.57 bos_range_high default", dec57["bos_range_high"], 0.0)
check("v17.57 bos_trend default", dec57["bos_trend"], 0)
check("v17.57 state1_location default", dec57["state1_location"], False)
check("v17.57 liquidity_swept default", dec57["liquidity_swept"], False)
check("v17.57 pdh still parsed (carryover)", dec57["pdh"], 1.2750)

payload_9 = {
    "version": "v17.56.9", "mode": "EXECUTION", "session": "NY",
    "symbol": "USDJPY", "direction": "SHORT", "setup": "A+ SNIPER", "poi": 5,
    "entry": 150.00, "sl": 150.20, "tp": 149.40, "valid": True,
    "guardian_risk": 1,
}
dec9 = decode_v17_56_9_payload(payload_9)
check("v17.56.9 sequence_state default", dec9["sequence_state"], 0)
check("v17.56.9 bos_equilibrium default", dec9["bos_equilibrium"], 0.0)
check("v17.56.9 state5_execution default", dec9["state5_execution"], False)
check("v17.56.9 guardian_risk still parsed", dec9["guardian_risk"], 1)

payload_8 = {
    "version": "v17.56.8", "mode": "DATA", "session": "LONDON",
    "symbol": "AUDUSD", "direction": "LONG", "setup": "A+ SNIPER", "poi": 4,
    "entry": 0.66000, "sl": 0.65800, "tp": 0.66600, "valid": True,
    "amd_state": "markup",
}
dec8 = decode_v17_56_8_payload(payload_8)
check("v17.56.8 sequence_complete default", dec8["sequence_complete"], False)
check("v17.56.8 bos_trend default", dec8["bos_trend"], 0)
check("v17.56.8 amd_state still parsed", dec8["amd_state"], "MARKUP")

payload_7 = {
    "version": "v17.56.7", "mode": "DATA", "session": "NY",
    "symbol": "NZDUSD", "direction": "LONG", "setup": "A+ SNIPER", "poi": 4,
    "entry": 0.61000, "sl": 0.60800, "tp": 0.61600, "valid": True,
}
dec7 = decode_v17_56_7_payload(payload_7)
check("v17.56.7 sequence_state default", dec7["sequence_state"], 0)
check("v17.56.7 mitigation_zone default", dec7["mitigation_zone"], False)

legacy = {
    "type": "sniper_long", "symbol": "XAUUSD", "entry_price": "2400.0",
    "stop_loss": "2390.0", "take_profit": "2430.0", "version": "v17.15",
}
decl = decode_legacy_payload(legacy)
check("legacy sequence_state default", decl["sequence_state"], 0)
check("legacy displacement_detected default", decl["displacement_detected"], False)


print("\n" + "=" * 70)
print("STEP 5: decode_payload() universal dispatcher routes v17.58")
print("=" * 70)
check("dispatch v17.58 sequence_state", decode_payload(payload_58)["sequence_state"], 5)
check("dispatch v17.58 sequence_complete", decode_payload(payload_58)["sequence_complete"], True)
check("dispatch v17.58 bos_trend", decode_payload(payload_58)["bos_trend"], 1)
check("dispatch v17.57 sequence_state default", decode_payload(payload_57)["sequence_state"], 0)
check("dispatch v17.56.9 bos_range_high default", decode_payload(payload_9)["bos_range_high"], 0.0)
check("dispatch legacy sequence_complete default", decode_payload(legacy)["sequence_complete"], False)


print("\n" + "=" * 70)
print("STEP 6: Graceful coercion (invalid -> default)")
print("=" * 70)
p_bad = dict(payload_58)
p_bad["sequence_state"] = "invalid"   # non-int -> 0
p_bad["sequence_complete"] = ""        # empty -> False
p_bad["bos_range_high"] = None         # None -> 0.0
p_bad["bos_trend"] = 42                 # out of domain -> 0
p_bad["state1_location"] = "yes"       # non-int -> 0 -> False
rec_bad = decode_payload(p_bad)
check("invalid sequence_state -> 0", rec_bad["sequence_state"], 0)
check("empty sequence_complete -> False", rec_bad["sequence_complete"], False)
check("None bos_range_high -> 0.0", rec_bad["bos_range_high"], 0.0)
check("out-of-domain bos_trend -> 0", rec_bad["bos_trend"], 0)
check("non-int state1_location -> False", rec_bad["state1_location"], False)
# _apply on an empty payload
rec_empty = {}
_apply_sequence_bos_fields({}, rec_empty)
check("_apply on empty payload sequence_state", rec_empty["sequence_state"], 0)
check("_apply on empty payload sequence_step", rec_empty["sequence_step"], None)
check("_apply on empty payload bos_range_low", rec_empty["bos_range_low"], 0.0)
check("_apply on empty payload mitigation_zone", rec_empty["mitigation_zone"], False)


print("\n" + "=" * 70)
print("STEP 7: 5-state sequence progression scenarios")
print("=" * 70)
progression = [
    # (state, step, complete, flags-active-up-to)
    (0, "IDLE", 0, []),
    (1, "LOCATION", 0, ["state1_location"]),
    (2, "LIQUIDITY", 0, ["state1_location", "state2_liquidity"]),
    (3, "DISPLACEMENT", 0, ["state1_location", "state2_liquidity", "state3_displacement"]),
    (4, "MITIGATION", 0, ["state1_location", "state2_liquidity", "state3_displacement", "state4_mitigation"]),
    (5, "EXECUTION", 1, ["state1_location", "state2_liquidity", "state3_displacement", "state4_mitigation", "state5_execution"]),
]
for state, step, complete, active_flags in progression:
    p = dict(payload_58)
    p["symbol"] = f"SEQ{state}"
    p["sequence_state"] = state
    p["sequence_step"] = step
    p["sequence_complete"] = complete
    for fk in ("state1_location", "state2_liquidity", "state3_displacement",
               "state4_mitigation", "state5_execution"):
        p[fk] = 1 if fk in active_flags else 0
    rec = decode_payload(p)
    check_true(f"state {state} sequence_state", rec["sequence_state"] == state)
    check_true(f"state {state} sequence_step '{step}'", rec["sequence_step"] == step)
    check_true(f"state {state} sequence_complete", rec["sequence_complete"] == bool(complete))
    check_true(f"state {state} state1_location flag",
               rec["state1_location"] == ("state1_location" in active_flags))


print("\n" + "=" * 70)
print("STEP 8: bos_trend domain {1, -1, 0}")
print("=" * 70)
for trend in (1, -1, 0):
    p = dict(payload_58)
    p["bos_trend"] = trend
    check("bos_trend " + str(trend), decode_payload(p)["bos_trend"], trend)


print("\n" + "=" * 70)
print("STEP 9: End-to-end DB persistence roundtrip (legacy bridge -> DB)")
print("=" * 70)
from src.tracker.processor import expand_compact_entry
p_persist = dict(payload_58)
p_persist["setup_id"] = "TEST_SEQ_PERSIST"
p_persist["symbol"] = "EURUSD"
compact = oie_to_legacy_compact(p_persist)
check("compact carries _sequence_state", compact["_sequence_state"], 5)
check("compact carries _bos_trend", compact["_bos_trend"], 1)
rec = expand_compact_entry(compact)
insert_signal(rec)
row = get_signal("TEST_SEQ_PERSIST")
check_true("persisted row exists", row is not None)
check("persisted sequence_state", row["sequence_state"], 5)
check("persisted sequence_step", row["sequence_step"], "EXECUTION")
check("persisted sequence_complete (1)", row["sequence_complete"], 1)
check("persisted bos_range_high", row["bos_range_high"], 1.09000)
check("persisted bos_trend", row["bos_trend"], 1)
check("persisted state5_execution (1)", row["state5_execution"], 1)
check("persisted liquidity_swept (1)", row["liquidity_swept"], 1)
check("persisted displacement_detected (1)", row["displacement_detected"], 1)
# count_signals filters
check_true("count_signals(sequence_state=5) >= 1", count_signals(sequence_state=5) >= 1)
check_true("count_signals(sequence_complete=1) >= 1", count_signals(sequence_complete=1) >= 1)


print("\n" + "=" * 70)
print("STEP 10: /health endpoint via Flask test client")
print("=" * 70)
from src.webhook_server.app import create_app
app = create_app()
client = app.test_client()
resp = client.get('/api/v1/health')
data = resp.get_json()
check("/health status code", resp.status_code, 200)
check_true("/health version >= v17.58", data["version"] >= "v17.58")
check_true("/health features include sequence_state_machine",
           "sequence_state_machine" in data["features"])
check_true("/health features include bos_anchored_ranges",
           "bos_anchored_ranges" in data["features"])


print("\n" + "=" * 70)
print("STEP 11: POST /signal echoes + persists v17.58 fields")
print("=" * 70)
post_payload = dict(payload_58)
post_payload["symbol"] = "GBPJPY"
post_payload["setup_id"] = "TEST_POST_58"
resp = client.post('/api/v1/signal', json=post_payload)
data = resp.get_json()
check("POST /signal status code", resp.status_code, 200)
check("POST /signal echoes sequence_state", data.get("sequence_state"), 5)
check("POST /signal echoes sequence_step", data.get("sequence_step"), "EXECUTION")
check("POST /signal echoes sequence_complete", data.get("sequence_complete"), True)
check("POST /signal echoes bos_trend", data.get("bos_trend"), 1)
check("POST /signal echoes bos_range_high", data.get("bos_range_high"), 1.09000)

# Verify persisted in /signals rows
resp = client.get('/api/v1/signals')
data = resp.get_json()
check("/signals status code", resp.status_code, 200)
signals = data.get("signals", [])
check_true("/signals returns >= 1 signal", len(signals) >= 1)
if signals:
    s0 = signals[0]
    check_true("/signals row HAS sequence_state column (persisted)", "sequence_state" in s0)
    check_true("/signals row HAS bos_trend column (persisted)", "bos_trend" in s0)
    check_true("/signals row still has guardian_risk (carryover)", "guardian_risk" in s0)
# filter by sequence_state
resp = client.get('/api/v1/signals?sequence_state=5')
data = resp.get_json()
check_true("/signals?sequence_state=5 returns rows", len(data.get("signals", [])) >= 1)


print("\n" + "=" * 70)
print("STEP 12: NEW GET /sequence-analytics endpoint")
print("=" * 70)
resp = client.get('/api/v1/sequence-analytics')
data = resp.get_json()
check("/sequence-analytics status code", resp.status_code, 200)
check_true("/sequence-analytics version >= v17.58", data.get("version", "") >= "v17.58")
check_true("/sequence-analytics has total_signals", "total_signals" in data)
check_true("/sequence-analytics total_signals >= 1", data.get("total_signals", 0) >= 1)
check_true("/sequence-analytics has sequence_complete count", "sequence_complete" in data)
check_true("/sequence-analytics has completion_rate_pct", "completion_rate_pct" in data)
dist = data.get("state_distribution", {})
check_true("/sequence-analytics distribution has 6 states (0-5)", len(dist) == 6)
check_true("/sequence-analytics state 5 labelled 'execution'",
           dist.get("5", {}).get("label") == "execution")
check_true("/sequence-analytics state 5 count >= 1",
           dist.get("5", {}).get("count", 0) >= 1)
check_true("/sequence-analytics state 0 labelled 'idle'",
           dist.get("0", {}).get("label") == "idle")


print("\n" + "=" * 70)
print(f"RESULTS: {PASS} passed, {FAIL} failed")
print("=" * 70)
sys.exit(1 if FAIL else 0)
