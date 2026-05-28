#!/usr/bin/env python3
"""
SMC Performance Tracker — Webhook Test Script
==============================================
Sends test v17.54.2 alerts to the live Railway endpoint and displays results.

Usage:
    python3 scripts/test_webhook.py                    # Run all default tests
    python3 scripts/test_webhook.py --alert "A+ SNIPER BUY"  # Specific alert
    python3 scripts/test_webhook.py --url http://localhost:5000/api/v1/signal  # Local
    python3 scripts/test_webhook.py --dry-run           # Show payloads without sending

Environment:
    SMC_API_KEY   — override API key (or edit DEFAULT_API_KEY below)
    WEBHOOK_URL   — override endpoint URL
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    print("❌ 'requests' not installed. Run: pip install requests")
    sys.exit(1)

# ── Configuration ──────────────────────────────────────────────
DEFAULT_URL = "https://web-production-b63af.up.railway.app/api/v1/signal"
DEFAULT_API_KEY = "3mrirFh5Q7-jwpBDPVUh1dU7ZFsXk1h-"

# ── Test Payloads ──────────────────────────────────────────────
TEST_ALERTS = {
    "A+ SNIPER BUY": {
        "version": "v17.54.2",
        "alert": "A+ SNIPER BUY",
        "symbol": "BTCUSD",
        "timeframe": "240",
        "price": "68500.00",
        "message": "v17.54.2 A+ SNIPER BUY - Aligned with Trend. Target 1:3 RR."
    },
    "A+ SNIPER SELL": {
        "version": "v17.54.2",
        "alert": "A+ SNIPER SELL",
        "symbol": "EURUSD",
        "timeframe": "60",
        "price": "1.08750",
        "message": "v17.54.2 A+ SNIPER SELL - Aligned with Trend. Target 1:3 RR."
    },
    "RETRACE LONG": {
        "version": "v17.54.2",
        "alert": "RETRACE LONG",
        "subtype": "standard",
        "symbol": "GBPUSD",
        "timeframe": "15",
        "price": "1.27450",
        "message": "v17.54.2 RETRACE LONG - Target: EQ Line."
    },
    "RETRACE SHORT": {
        "version": "v17.54.2",
        "alert": "RETRACE SHORT",
        "subtype": "standard",
        "symbol": "AUDUSD",
        "timeframe": "5",
        "price": "0.66120",
        "message": "v17.54.2 RETRACE SHORT - Target: EQ Line."
    },
    "COUNTER BUY": {
        "version": "v17.54.2",
        "alert": "COUNTER BUY",
        "symbol": "XAUUSD",
        "timeframe": "60",
        "price": "2365.50",
        "message": "v17.54.2 COUNTER BUY - Counter-trend entry."
    },
    "COUNTER SELL": {
        "version": "v17.54.2",
        "alert": "COUNTER SELL",
        "symbol": "USDJPY",
        "timeframe": "240",
        "price": "157.250",
        "message": "v17.54.2 COUNTER SELL - Counter-trend entry."
    },
}


def send_test_alert(url: str, api_key: str, payload: dict, dry_run: bool = False) -> dict:
    """Send a single test alert and return the result."""
    # Inject API key into payload body (the endpoint checks body.api_key or body.k)
    full_payload = {**payload, "api_key": api_key}

    result = {
        "alert": payload["alert"],
        "symbol": payload["symbol"],
        "payload": full_payload,
        "status_code": None,
        "response": None,
        "success": False,
        "error": None,
        "elapsed_ms": None,
    }

    if dry_run:
        result["response"] = {"dry_run": True, "message": "Payload not sent"}
        print(f"  🔸 DRY RUN — payload prepared but not sent")
        return result

    try:
        start = time.time()
        resp = requests.post(
            url,
            json=full_payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        elapsed = (time.time() - start) * 1000

        result["status_code"] = resp.status_code
        result["elapsed_ms"] = round(elapsed, 1)

        try:
            result["response"] = resp.json()
        except Exception:
            result["response"] = resp.text[:500]

        result["success"] = resp.status_code == 200

    except requests.exceptions.ConnectionError:
        result["error"] = "Connection refused — is the server running?"
    except requests.exceptions.Timeout:
        result["error"] = "Request timed out (15s)"
    except Exception as e:
        result["error"] = str(e)

    return result


def print_result(result: dict):
    """Pretty-print a single test result."""
    icon = "✅" if result["success"] else "❌"
    alert = result["alert"]
    symbol = result["symbol"]
    code = result["status_code"] or "N/A"
    elapsed = f"{result['elapsed_ms']}ms" if result["elapsed_ms"] else "N/A"

    print(f"\n  {icon} {alert} on {symbol}")
    print(f"     Status: {code}  |  Time: {elapsed}")

    if result["error"]:
        print(f"     Error:  {result['error']}")
    elif result["response"]:
        resp = result["response"]
        if isinstance(resp, dict):
            # Highlight key fields
            if resp.get("pipeline") == "oie":
                print(f"     Pipeline:       OIE (v17.54.2)")
                print(f"     Opportunity ID: {resp.get('opportunity_id')}")
                print(f"     Setup Type:     {resp.get('setup_type')}")
                print(f"     Pair:           {resp.get('pair')}")
                print(f"     Kill Zone:      {resp.get('kill_zone')}")
                print(f"     RR Ratio:       {resp.get('rr_ratio')}")
                if resp.get("legacy_signal_id"):
                    print(f"     Legacy Signal:  {resp.get('legacy_signal_id')}")
            else:
                print(f"     Response: {json.dumps(resp, indent=2)[:300]}")
        else:
            print(f"     Response: {resp[:200]}")


def main():
    parser = argparse.ArgumentParser(description="Test SMC webhook with v17.54.2 alerts")
    parser.add_argument("--url", default=os.environ.get("WEBHOOK_URL", DEFAULT_URL),
                        help="Webhook endpoint URL")
    parser.add_argument("--api-key", default=os.environ.get("SMC_API_KEY", DEFAULT_API_KEY),
                        help="API key for authentication")
    parser.add_argument("--alert", nargs="*", choices=list(TEST_ALERTS.keys()),
                        help="Specific alert type(s) to test (default: all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show payloads without sending")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Delay between requests in seconds (default: 1.0)")
    args = parser.parse_args()

    # Determine which alerts to send
    alerts_to_test = args.alert if args.alert else ["A+ SNIPER BUY", "RETRACE LONG"]

    print("=" * 65)
    print("  SMC Performance Tracker — Webhook Test")
    print("=" * 65)
    print(f"  Endpoint:  {args.url}")
    print(f"  API Key:   {args.api_key[:8]}{'*' * 12}")
    print(f"  Alerts:    {', '.join(alerts_to_test)}")
    print(f"  Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    if args.dry_run:
        print(f"  Mode:      🔸 DRY RUN (no requests sent)")
    print("=" * 65)

    results = []
    for i, alert_name in enumerate(alerts_to_test):
        payload = TEST_ALERTS[alert_name]
        print(f"\n📤 Sending [{i+1}/{len(alerts_to_test)}]: {alert_name} ({payload['symbol']})")
        print(f"   Payload: {json.dumps(payload, separators=(',', ':'))}")

        result = send_test_alert(args.url, args.api_key, payload, dry_run=args.dry_run)
        print_result(result)
        results.append(result)

        if i < len(alerts_to_test) - 1 and not args.dry_run:
            time.sleep(args.delay)

    # ── Summary ──
    passed = sum(1 for r in results if r["success"])
    total = len(results)
    print("\n" + "=" * 65)
    print(f"  Summary: {passed}/{total} passed")
    if passed == total:
        print("  🎉 All alerts processed successfully!")
    else:
        failed = [r["alert"] for r in results if not r["success"]]
        print(f"  ⚠️  Failed: {', '.join(failed)}")
    print("=" * 65)

    # ── Next Steps ──
    base_url = args.url.rsplit("/api/", 1)[0]
    print(f"\n📊 Next steps:")
    print(f"   • View dashboard:      {base_url}/")
    print(f"   • View opportunities:  {base_url}/api/v1/opportunities")
    print(f"   • View active signals: {base_url}/api/v1/signals/active")
    print(f"   • View system log:     {base_url}/api/v1/system-log")
    print()

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
