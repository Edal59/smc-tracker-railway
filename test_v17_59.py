#!/usr/bin/env python3
"""
Test suite for v17.59 — EMERGENCY FIX: Inverted Logic During Strong Trends.

v17.59 adds 9 OPTIONAL webhook fields that are IN-MEMORY ONLY (NO DB migration,
NO schema change) — mirroring the v17.57 PDH/PDL in-memory pattern:
  Trend override (4): htf_override_active, ltf_override_active,
                      htf_trend_final, ltf_trend_final
  Range debug    (2): range_anchor_time, range_force_expanded
  AMD velocity   (1): amd_velocity (% of ATR)
  Strong trend   (1): strong_trend_mode (BEARISH / BULLISH / NONE)
  Plus amd_state may be overridden with a velocity-based value (existing field).

Covers:
  1. version.py single source of truth (VERSION bump + 2 new feature flags,
     existing flags preserved) + normalize_strong_trend_mode helper
  2. v17.59 payload decodes the 9 new fields (correct types)
  3. decode_payload() universal dispatcher routes v17.59 correctly
  4. Backward compatibility: v17.58 / v17.57 / v17.56.9 / v17.56.8 / v17.56.7 /
     legacy payloads default the new fields (False / 0 / 0.0 / '' / 'NONE')
  5. Graceful coercion of invalid / missing values
  6. strong_trend_mode domain {BEARISH, BULLISH, NONE}
  7. IN-MEMORY ONLY: the 9 fields are NOT persisted to the signals table
  8. /health returns >= v17.59 + new feature flags (Flask test client)
  9. POST /signal echoes the 9 new fields
 10. GET /latest surfaces the 9 new fields

Run from repo root:  python3 test_v17_59.py
"""
import os
import sys
import sqlite3
import tempfile

# ── Test environment (mirrors test_v17_58.py) ──
TEST_DB = os.path.join(tempfile.gettempdir(), 'tradex_test_v17_59.db')
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)
os.environ['DATABASE_PATH'] = TEST_DB
os.environ['REQUIRE_AUTH'] = 'false'
os.environ['PRICE_TRACKER_ENABLED'] = 'false'
os.environ['SMC_API_KEY'] = 'test-key'

from src.config import config
config.load()

# Initialize the DB up-front: normalize_oie_payload -> calculate_pips needs the
# pair_config table. (init_db is idempotent; STEP 7 re-reads the schema.)
from src.database import init_db
init_db(TEST_DB)

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


# The 9 in-memory-only v17.59 fields.
NEW_FIELDS = [
    "htf_override_active", "ltf_override_active",
    "htf_trend_final", "ltf_trend_final",
    "range_anchor_time", "range_force_expanded",
    "amd_velocity", "strong_trend_mode",
    "amd_state",  # existing field, may be velocity-overridden — passed through
]


print("=" * 70)
print("STEP 1: version.py — VERSION bump + 2 new feature flags")
print("=" * 70)
from src.version import (
    VERSION, get_version, get_features,
    normalize_strong_trend_mode, DEFAULT_STRONG_TREND_MODE,
)
check_true("VERSION >= v17.59", VERSION >= "v17.59")
check_true("get_version() >= v17.59", get_version() >= "v17.59")
check_true("features include trend_override_logic",
           "trend_override_logic" in get_features())
check_true("features include amd_velocity_detection",
           "amd_velocity_detection" in get_features())
# Existing flags must be preserved (NOT dropped).
check_true("features still include sequence_state_machine (carryover)",
           "sequence_state_machine" in get_features())
check_true("features still include bos_anchored_ranges (carryover)",
           "bos_anchored_ranges" in get_features())
check_true("features still include pdh_pdl_liquidity (carryover)",
           "pdh_pdl_liquidity" in get_features())
check_true("features still include guardian_htf_gating (carryover)",
           "guardian_htf_gating" in get_features())
check_true("features still include invalid_classification (carryover)",
           "invalid_classification" in get_features())

# normalize_strong_trend_mode helper
check("normalize_strong_trend_mode('BEARISH')", normalize_strong_trend_mode("BEARISH"), "BEARISH")
check("normalize_strong_trend_mode('bullish')", normalize_strong_trend_mode("bullish"), "BULLISH")
check("normalize_strong_trend_mode('NONE')", normalize_strong_trend_mode("NONE"), "NONE")
check("normalize_strong_trend_mode('garbage') -> NONE", normalize_strong_trend_mode("garbage"), "NONE")
check("normalize_strong_trend_mode(None) -> NONE", normalize_strong_trend_mode(None), "NONE")
check("DEFAULT_STRONG_TREND_MODE is NONE", DEFAULT_STRONG_TREND_MODE, "NONE")


print("\n" + "=" * 70)
print("STEP 2: v17.59 payload decode (9 new fields parsed)")
print("=" * 70)
from src.oie_processor import (
    decode_payload, decode_v17_59_payload, decode_v17_58_payload,
    decode_v17_57_payload, decode_v17_56_9_payload, decode_v17_56_8_payload,
    decode_v17_56_7_payload, decode_legacy_payload, normalize_oie_payload,
    is_oie_payload, _apply_trend_override_fields,
)

payload_59 = {
    "version": "v17.59",
    "mode": "EXECUTION",
    "session": "NY",
    "symbol": "NZDUSD",
    "direction": "SHORT",
    "setup": "OB_RETEST",
    "poi": 5,
    "entry": 0.59100,
    "sl": 0.59300,
    "tp": 0.58500,
    "valid": True,
    "amd_state": "markdown",
    # v17.59 trend override
    "htf_override_active": 1,
    "ltf_override_active": 0,
    "htf_trend_final": -1,
    "ltf_trend_final": -1,
    # v17.59 range debug
    "range_anchor_time": "2026-06-06T09:30:00Z",
    "range_force_expanded": 1,
    # v17.59 AMD velocity + strong trend mode
    "amd_velocity": 87.5,
    "strong_trend_mode": "BEARISH",
    "timestamp": "2026-06-06T14:30:00Z",
}
dec = decode_v17_59_payload(payload_59)
check("v17.59 htf_override_active (bool)", dec["htf_override_active"], True)
check("v17.59 ltf_override_active (bool)", dec["ltf_override_active"], False)
check("v17.59 htf_trend_final (int)", dec["htf_trend_final"], -1)
check("v17.59 ltf_trend_final (int)", dec["ltf_trend_final"], -1)
check("v17.59 range_anchor_time (text)", dec["range_anchor_time"], "2026-06-06T09:30:00Z")
check("v17.59 range_force_expanded (bool)", dec["range_force_expanded"], True)
check("v17.59 amd_velocity (float)", dec["amd_velocity"], 87.5)
check("v17.59 strong_trend_mode (text)", dec["strong_trend_mode"], "BEARISH")
check("v17.59 amd_state (passthrough/normalized)", dec["amd_state"], "MARKDOWN")
check_true("v17.59 htf_override_active is bool", isinstance(dec["htf_override_active"], bool))
check_true("v17.59 htf_trend_final is int", isinstance(dec["htf_trend_final"], int))
check_true("v17.59 amd_velocity is float", isinstance(dec["amd_velocity"], float))
check_true("v17.59 range_anchor_time is str", isinstance(dec["range_anchor_time"], str))
check_true("v17.59 strong_trend_mode is str", isinstance(dec["strong_trend_mode"], str))
# carryover of prior version fields
check_true("v17.59 carries v17.58 sequence_state", "sequence_state" in dec)
check_true("v17.59 carries v17.57 pdh", "pdh" in dec)
check_true("is_oie_payload(v17.59)", is_oie_payload(payload_59))
check("v17.59 record version key", dec["version"], "v17.59")


print("\n" + "=" * 70)
print("STEP 3: decode_payload() universal dispatcher routes v17.59")
print("=" * 70)
check("dispatch v17.59 strong_trend_mode", decode_payload(payload_59)["strong_trend_mode"], "BEARISH")
check("dispatch v17.59 amd_velocity", decode_payload(payload_59)["amd_velocity"], 87.5)
check("dispatch v17.59 htf_override_active", decode_payload(payload_59)["htf_override_active"], True)
check("dispatch v17.59 htf_trend_final", decode_payload(payload_59)["htf_trend_final"], -1)
# minor version suffix still routes via startswith
p_suffix = dict(payload_59)
p_suffix["version"] = "v17.59.1"
check("dispatch v17.59.1 (startswith) strong_trend_mode",
      decode_payload(p_suffix)["strong_trend_mode"], "BEARISH")


print("\n" + "=" * 70)
print("STEP 4: Backward compatibility (9 fields default False/0/0.0/''/NONE)")
print("=" * 70)
payload_58 = {
    "version": "v17.58", "mode": "EXECUTION", "session": "NY",
    "symbol": "EURUSD", "direction": "LONG", "setup": "A+ SNIPER", "poi": 7,
    "entry": 1.08550, "sl": 1.08250, "tp": 1.09450, "valid": True,
    "sequence_state": 5, "sequence_step": "EXECUTION", "sequence_complete": 1,
    "bos_trend": 1,
}
dec58 = decode_v17_58_payload(payload_58)
check("v17.58 htf_override_active default", dec58["htf_override_active"], False)
check("v17.58 ltf_override_active default", dec58["ltf_override_active"], False)
check("v17.58 htf_trend_final default", dec58["htf_trend_final"], 0)
check("v17.58 ltf_trend_final default", dec58["ltf_trend_final"], 0)
check("v17.58 range_anchor_time default", dec58["range_anchor_time"], "")
check("v17.58 range_force_expanded default", dec58["range_force_expanded"], False)
check("v17.58 amd_velocity default", dec58["amd_velocity"], 0.0)
check("v17.58 strong_trend_mode default", dec58["strong_trend_mode"], "NONE")
check("v17.58 sequence_state still parsed (carryover)", dec58["sequence_state"], 5)

payload_57 = {
    "version": "v17.57", "mode": "EXECUTION", "session": "NY",
    "symbol": "GBPUSD", "direction": "LONG", "setup": "A+ SNIPER", "poi": 6,
    "entry": 1.27000, "sl": 1.26800, "tp": 1.27600, "valid": True, "pdh": 1.2750,
}
dec57 = decode_v17_57_payload(payload_57)
check("v17.57 strong_trend_mode default", dec57["strong_trend_mode"], "NONE")
check("v17.57 amd_velocity default", dec57["amd_velocity"], 0.0)
check("v17.57 range_anchor_time default", dec57["range_anchor_time"], "")
check("v17.57 pdh still parsed (carryover)", dec57["pdh"], 1.2750)

payload_9 = {
    "version": "v17.56.9", "mode": "EXECUTION", "session": "NY",
    "symbol": "USDJPY", "direction": "SHORT", "setup": "A+ SNIPER", "poi": 5,
    "entry": 150.00, "sl": 150.20, "tp": 149.40, "valid": True, "guardian_risk": 1,
}
dec9 = decode_v17_56_9_payload(payload_9)
check("v17.56.9 htf_override_active default", dec9["htf_override_active"], False)
check("v17.56.9 strong_trend_mode default", dec9["strong_trend_mode"], "NONE")
check("v17.56.9 guardian_risk still parsed", dec9["guardian_risk"], 1)

payload_8 = {
    "version": "v17.56.8", "mode": "DATA", "session": "LONDON",
    "symbol": "AUDUSD", "direction": "LONG", "setup": "A+ SNIPER", "poi": 4,
    "entry": 0.66000, "sl": 0.65800, "tp": 0.66600, "valid": True, "amd_state": "markup",
}
dec8 = decode_v17_56_8_payload(payload_8)
check("v17.56.8 amd_velocity default", dec8["amd_velocity"], 0.0)
check("v17.56.8 range_force_expanded default", dec8["range_force_expanded"], False)
check("v17.56.8 amd_state still parsed (carryover)", dec8["amd_state"], "MARKUP")

payload_7 = {
    "version": "v17.56.7", "mode": "DATA", "session": "NY",
    "symbol": "NZDUSD", "direction": "LONG", "setup": "A+ SNIPER", "poi": 4,
    "entry": 0.61000, "sl": 0.60800, "tp": 0.61600, "valid": True,
}
dec7 = decode_v17_56_7_payload(payload_7)
check("v17.56.7 strong_trend_mode default", dec7["strong_trend_mode"], "NONE")
check("v17.56.7 htf_trend_final default", dec7["htf_trend_final"], 0)

legacy = {
    "type": "sniper_long", "symbol": "XAUUSD", "entry_price": "2400.0",
    "stop_loss": "2390.0", "take_profit": "2430.0", "version": "v17.15",
}
decl = decode_legacy_payload(legacy)
check("legacy strong_trend_mode default", decl["strong_trend_mode"], "NONE")
check("legacy amd_velocity default", decl["amd_velocity"], 0.0)
check("legacy range_anchor_time default", decl["range_anchor_time"], "")


print("\n" + "=" * 70)
print("STEP 5: Graceful coercion (invalid -> default)")
print("=" * 70)
p_bad = dict(payload_59)
p_bad["htf_override_active"] = "yes"     # non-int -> 0 -> False
p_bad["htf_trend_final"] = None           # None -> 0
p_bad["amd_velocity"] = "not_a_number"   # garbage -> 0.0
p_bad["strong_trend_mode"] = "sideways"  # out of domain -> NONE
p_bad["range_force_expanded"] = ""        # empty -> False
rec_bad = decode_payload(p_bad)
check("invalid htf_override_active -> False", rec_bad["htf_override_active"], False)
check("None htf_trend_final -> 0", rec_bad["htf_trend_final"], 0)
check("garbage amd_velocity -> 0.0", rec_bad["amd_velocity"], 0.0)
check("out-of-domain strong_trend_mode -> NONE", rec_bad["strong_trend_mode"], "NONE")
check("empty range_force_expanded -> False", rec_bad["range_force_expanded"], False)
# _apply on an empty payload
rec_empty = {}
_apply_trend_override_fields({}, rec_empty)
check("_apply on empty htf_override_active", rec_empty["htf_override_active"], False)
check("_apply on empty htf_trend_final", rec_empty["htf_trend_final"], 0)
check("_apply on empty amd_velocity", rec_empty["amd_velocity"], 0.0)
check("_apply on empty range_anchor_time", rec_empty["range_anchor_time"], "")
check("_apply on empty strong_trend_mode", rec_empty["strong_trend_mode"], "NONE")


print("\n" + "=" * 70)
print("STEP 6: strong_trend_mode domain {BEARISH, BULLISH, NONE}")
print("=" * 70)
for mode in ("BEARISH", "BULLISH", "NONE"):
    p = dict(payload_59)
    p["strong_trend_mode"] = mode
    check("strong_trend_mode " + mode, decode_payload(p)["strong_trend_mode"], mode)
# htf_trend_final / ltf_trend_final domain -1/0/1
for tr in (-1, 0, 1):
    p = dict(payload_59)
    p["htf_trend_final"] = tr
    check("htf_trend_final " + str(tr), decode_payload(p)["htf_trend_final"], tr)


print("\n" + "=" * 70)
print("STEP 7: IN-MEMORY ONLY — 9 fields NOT persisted (no schema change)")
print("=" * 70)
from src.database import init_db
db_path = init_db(TEST_DB)
print(f"  DB initialized at {db_path}")
conn = sqlite3.connect(TEST_DB)
sig_cols = [c[1] for c in conn.execute("PRAGMA table_info(signals)").fetchall()]
conn.close()
for f in ("htf_override_active", "ltf_override_active", "htf_trend_final",
          "ltf_trend_final", "range_anchor_time", "range_force_expanded",
          "amd_velocity", "strong_trend_mode"):
    check_true(f"signals table does NOT have column '{f}' (in-memory only)",
               f not in sig_cols)
# sanity: existing persisted v17.58 column still present (we didn't break schema)
check_true("signals table still has sequence_state (v17.58 persisted)",
           "sequence_state" in sig_cols)


print("\n" + "=" * 70)
print("STEP 8: /health endpoint via Flask test client")
print("=" * 70)
from src.webhook_server.app import create_app
app = create_app()
client = app.test_client()
resp = client.get('/api/v1/health')
data = resp.get_json()
check("/health status code", resp.status_code, 200)
check_true("/health version >= v17.59", data["version"] >= "v17.59")
check_true("/health features include trend_override_logic",
           "trend_override_logic" in data["features"])
check_true("/health features include amd_velocity_detection",
           "amd_velocity_detection" in data["features"])


print("\n" + "=" * 70)
print("STEP 9: POST /signal echoes the 9 v17.59 fields")
print("=" * 70)
post_payload = dict(payload_59)
post_payload["symbol"] = "GBPJPY"
post_payload["setup_id"] = "TEST_POST_59"
resp = client.post('/api/v1/signal', json=post_payload)
data = resp.get_json()
check("POST /signal status code", resp.status_code, 200)
check("POST /signal echoes htf_override_active", data.get("htf_override_active"), True)
check("POST /signal echoes ltf_override_active", data.get("ltf_override_active"), False)
check("POST /signal echoes htf_trend_final", data.get("htf_trend_final"), -1)
check("POST /signal echoes ltf_trend_final", data.get("ltf_trend_final"), -1)
check("POST /signal echoes range_anchor_time", data.get("range_anchor_time"), "2026-06-06T09:30:00Z")
check("POST /signal echoes range_force_expanded", data.get("range_force_expanded"), True)
check("POST /signal echoes amd_velocity", data.get("amd_velocity"), 87.5)
check("POST /signal echoes strong_trend_mode", data.get("strong_trend_mode"), "BEARISH")


print("\n" + "=" * 70)
print("STEP 10: GET /latest surfaces the 9 v17.59 fields (in-memory snapshot)")
print("=" * 70)
resp = client.get('/api/v1/latest')
data = resp.get_json()
check("/latest status code", resp.status_code, 200)
check_true("/latest version >= v17.59", data.get("version", "") >= "v17.59")
sig = data.get("signal") or {}
check_true("/latest has a cached signal", bool(sig))
check("/latest htf_override_active", sig.get("htf_override_active"), True)
check("/latest ltf_override_active", sig.get("ltf_override_active"), False)
check("/latest htf_trend_final", sig.get("htf_trend_final"), -1)
check("/latest ltf_trend_final", sig.get("ltf_trend_final"), -1)
check("/latest range_anchor_time", sig.get("range_anchor_time"), "2026-06-06T09:30:00Z")
check("/latest range_force_expanded", sig.get("range_force_expanded"), True)
check("/latest amd_velocity", sig.get("amd_velocity"), 87.5)
check("/latest strong_trend_mode", sig.get("strong_trend_mode"), "BEARISH")


print("\n" + "=" * 70)
print(f"RESULTS: {PASS} passed, {FAIL} failed")
print("=" * 70)
sys.exit(1 if FAIL else 0)
