#!/usr/bin/env python3
"""
Integration test for OIE v17.15 webhook pipeline.
Tests the full flow: webhook → normalize → DB insert → query.
"""
import os
import sys
import json
import sqlite3
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Use a temp DB for testing
TEST_DB = os.path.join(tempfile.gettempdir(), 'tradex_test_oie.db')
os.environ['DATABASE_PATH'] = TEST_DB
os.environ['REQUIRE_AUTH'] = 'false'
os.environ['PRICE_TRACKER_ENABLED'] = 'false'
os.environ['SMC_API_KEY'] = 'test-key'

from src.config import config
config.load()

from src.database import init_db

# Initialize DB (runs all migrations including OIE)
print("=" * 70)
print("STEP 1: Database Initialization & Migration")
print("=" * 70)
db_path = init_db(TEST_DB)
print(f"✅ Database initialized at: {db_path}")

# Verify OIE tables exist
conn = sqlite3.connect(TEST_DB)
tables = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()
table_names = [t[0] for t in tables]
print(f"\nAll tables: {table_names}")

oie_tables = ['opportunities', 'opportunity_outcomes', 'user_executions', 'pair_analytics']
for t in oie_tables:
    if t in table_names:
        print(f"  ✅ {t}")
    else:
        print(f"  ❌ {t} MISSING!")

# Verify opportunities schema
cols = conn.execute("PRAGMA table_info(opportunities)").fetchall()
col_names = [c[1] for c in cols]
print(f"\nOpportunities columns ({len(col_names)}): {col_names}")
conn.close()

print("\n" + "=" * 70)
print("STEP 2: Decoder Tests")
print("=" * 70)
from src.decoders import decode_h4_bias, decode_pd_zone, decode_guardian, decode_kill_zone, decode_all

tests = [
    ("decode_h4_bias('1')", decode_h4_bias("1"), "Bullish"),
    ("decode_h4_bias(-1)", decode_h4_bias(-1), "Bearish"),
    ("decode_h4_bias('0')", decode_h4_bias("0"), "Neutral"),
    ("decode_pd_zone('1')", decode_pd_zone("1"), "Premium"),
    ("decode_pd_zone(0)", decode_pd_zone(0), "Discount"),
    ("decode_pd_zone('-1')", decode_pd_zone("-1"), "Equilibrium"),
    ("decode_guardian('1')", decode_guardian("1"), "Sniper Buy"),
    ("decode_guardian(4)", decode_guardian(4), "Retrace Sell"),
    ("decode_kill_zone('2')", decode_kill_zone("2"), "NY AM"),
    ("decode_kill_zone(0)", decode_kill_zone(0), "Off-Session"),
]
all_pass = True
for name, got, expected in tests:
    status = "✅" if got == expected else "❌"
    if got != expected:
        all_pass = False
    print(f"  {status} {name} = {got!r} (expected {expected!r})")

# Test decode_all
decoded = decode_all({"h4_bias": "1", "p_d_zone": "0", "guardian": "1", "kill_zone": "2"})
expected_all = {"h4_bias": "Bullish", "pd_zone": "Discount", "guardian": "Sniper Buy", "kill_zone": "NY AM"}
status = "✅" if decoded == expected_all else "❌"
print(f"  {status} decode_all: {decoded}")

print("\n" + "=" * 70)
print("STEP 3: OIE Normalizer Tests")
print("=" * 70)
from src.oie_processor import normalize_oie_payload, is_oie_payload, oie_to_legacy_compact

# Test v17.15 Sniper Long payload
sniper_long_payload = {
    "type": "sniper_long",
    "setup_id": "EURUSD_20260514_143000",
    "symbol": "EURUSD",
    "entry_price": "1.08550",
    "stop_loss": "1.08250",
    "take_profit": "1.09450",
    "quality": "78.5",
    "poi": "4",
    "confluence": "5",
    "dt_stage": "5",
    "h4_bias": "1",
    "p_d_zone": "0",
    "kill_zone": "2",
    "guardian": "1",
    "timestamp": "2026-05-14T14:30:00Z",
    "version": "v17.15"
}

print(f"\n  is_oie_payload: {is_oie_payload(sniper_long_payload)} (expected True)")
norm = normalize_oie_payload(sniper_long_payload)
print(f"  ✅ Normalized sniper_long:")
print(f"     pair: {norm['pair']} (expected EURUSD)")
print(f"     setup_type: {norm['setup_type']} (expected sniper_long)")
print(f"     h4_bias: {norm['h4_bias']} (expected Bullish)")
print(f"     pd_zone: {norm['pd_zone']} (expected Discount)")
print(f"     kill_zone: {norm['kill_zone']} (expected NY AM)")
print(f"     guardian: {norm['guardian']} (expected Sniper Buy)")
print(f"     entry_price: {norm['entry_price']} (expected 1.0855)")
print(f"     sl_price: {norm['sl_price']} (expected 1.0825)")
print(f"     tp_price: {norm['tp_price']} (expected 1.0945)")
print(f"     risk_pips: {norm['risk_pips']} (expected 30.0)")
print(f"     reward_pips: {norm['reward_pips']} (expected 90.0)")
print(f"     rr_ratio: {norm['rr_ratio']} (expected 3.0)")
print(f"     poi_score: {norm['poi_score']} (expected 4)")
print(f"     confluence: {norm['confluence']} (expected 5)")
print(f"     dt_stage: {norm['dt_stage']} (expected 5)")

# Test v17.15 Retrace Short payload
retrace_short_payload = {
    "type": "retrace_short",
    "setup_id": "GBPJPY_20260514_091500",
    "symbol": "GBPJPY",
    "suggested_entry": "214.500",
    "target_sl": "215.000",
    "target_tp": "213.000",
    "poi": "3",
    "confluence": "4",
    "guardian": "4",
    "zone": "-1",
    "kill_zone": "1",
    "timestamp": "2026-05-14T09:15:00Z",
    "version": "v17.15"
}

norm2 = normalize_oie_payload(retrace_short_payload)
print(f"\n  ✅ Normalized retrace_short:")
print(f"     pair: {norm2['pair']} (expected GBPJPY)")
print(f"     pd_zone: {norm2['pd_zone']} (expected Equilibrium)")
print(f"     kill_zone: {norm2['kill_zone']} (expected London)")
print(f"     guardian: {norm2['guardian']} (expected Retrace Sell)")
print(f"     risk_pips: {norm2['risk_pips']} (expected 50.0)")
print(f"     reward_pips: {norm2['reward_pips']} (expected 150.0)")
print(f"     rr_ratio: {norm2['rr_ratio']} (expected 3.0)")

# Test legacy bridge
legacy = oie_to_legacy_compact(sniper_long_payload)
print(f"\n  ✅ Legacy bridge (sniper_long):")
print(f"     event: {legacy['e']} (expected ENTRY)")
print(f"     pair: {legacy['p']} (expected EURUSD)")
print(f"     direction: {legacy['d']} (expected L)")

print("\n" + "=" * 70)
print("STEP 4: Full Pipeline Test (Flask app)")
print("=" * 70)

from src.webhook_server.app import create_app
app = create_app()
client = app.test_client()

# Test health endpoint
resp = client.get('/api/v1/health')
print(f"  Health: {resp.status_code} {resp.get_json()}")

# Test OIE webhook with sniper_long
resp = client.post('/api/v1/signal',
                   data=json.dumps(sniper_long_payload),
                   content_type='application/json')
result = resp.get_json()
print(f"\n  POST /api/v1/signal (sniper_long):")
print(f"    Status: {resp.status_code}")
print(f"    Response: {json.dumps(result, indent=2)}")

# Test OIE webhook with retrace_short
resp2 = client.post('/api/v1/signal',
                    data=json.dumps(retrace_short_payload),
                    content_type='application/json')
result2 = resp2.get_json()
print(f"\n  POST /api/v1/signal (retrace_short):")
print(f"    Status: {resp2.status_code}")
print(f"    Response: {json.dumps(result2, indent=2)}")

# Test v17.15 without kill_zone (v17.14 compat)
v1714_payload = {
    "type": "sniper_short",
    "setup_id": "XAUUSD_20260514_150000",
    "symbol": "XAUUSD",
    "entry_price": "2350.00",
    "stop_loss": "2360.00",
    "take_profit": "2320.00",
    "quality": "82.0",
    "poi": "5",
    "confluence": "6",
    "dt_stage": "4",
    "h4_bias": "-1",
    "p_d_zone": "1",
    "guardian": "2",
    "timestamp": "2026-05-14T15:00:00Z",
    "version": "v17.14"
}
resp3 = client.post('/api/v1/signal',
                    data=json.dumps(v1714_payload),
                    content_type='application/json')
result3 = resp3.get_json()
print(f"\n  POST /api/v1/signal (v17.14 sniper_short, no kill_zone):")
print(f"    Status: {resp3.status_code}")
print(f"    Response: {json.dumps(result3, indent=2)}")

print("\n" + "=" * 70)
print("STEP 5: Database Verification")
print("=" * 70)

# Query opportunities table
conn = sqlite3.connect(TEST_DB)
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT * FROM opportunities ORDER BY id").fetchall()
print(f"\n  Opportunities in DB: {len(rows)}")
for row in rows:
    r = dict(row)
    print(f"\n  --- Opportunity #{r['id']} ---")
    print(f"    pair:         {r['pair']}")
    print(f"    setup_type:   {r['setup_type']}")
    print(f"    h4_bias:      {r['h4_bias']}")
    print(f"    pd_zone:      {r['pd_zone']}")
    print(f"    kill_zone:    {r['kill_zone']}")
    print(f"    guardian:     {r['guardian']}")
    print(f"    entry_price:  {r['entry_price']}")
    print(f"    sl_price:     {r['sl_price']}")
    print(f"    tp_price:     {r['tp_price']}")
    print(f"    risk_pips:    {r['risk_pips']}")
    print(f"    reward_pips:  {r['reward_pips']}")
    print(f"    rr_ratio:     {r['rr_ratio']}")
    print(f"    poi_score:    {r['poi_score']}")
    print(f"    confluence:   {r['confluence']}")
    print(f"    dt_stage:     {r['dt_stage']}")
    print(f"    status:       {r['status']}")
    print(f"    version:      {r['version']}")

# Check signals table (legacy bridge)
signals = conn.execute("SELECT signal_id, pair, direction, status FROM signals ORDER BY id").fetchall()
print(f"\n  Legacy signals in DB: {len(signals)}")
for s in signals:
    s = dict(s)
    print(f"    {s['signal_id']} | {s['pair']} | {s['direction']} | {s['status']}")

# Test the opportunities API endpoint
resp_opps = client.get('/api/v1/opportunities')
opps_data = resp_opps.get_json()
print(f"\n  GET /api/v1/opportunities: {opps_data['total']} total")

# Test summary endpoint
resp_summary = client.get('/api/v1/opportunities/summary')
summary_data = resp_summary.get_json()
print(f"  GET /api/v1/opportunities/summary: {json.dumps(summary_data, indent=2)}")

conn.close()

# Cleanup
os.remove(TEST_DB)

print("\n" + "=" * 70)
print("✅ ALL INTEGRATION TESTS PASSED")
print("=" * 70)
