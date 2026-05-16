"""
TradeX Tracker — Decoder Functions for SMC Premium/Discount Confluence Engine
Version: v17.19

Translates numeric codes from Pine Script {{plot_X}} webhook payloads into
human-readable strings. Webhook payloads deliver all numeric values as
quoted strings (e.g., "1" not 1), so every decoder accepts both str and int.
"""


def _to_num(value) -> int:
    """Safely coerce a webhook value (string or number) to an integer."""
    if value is None:
        return 0
    try:
        return int(float(str(value)))
    except (ValueError, TypeError):
        return 0


# ============================================================================
# Individual Decoders
# ============================================================================

def decode_h4_bias(value) -> str:
    """
    Decode H4 Bias code from webhook payload.

    Mapping:
        1  → "Bullish"
        -1 → "Bearish"
        0  → "Neutral"
    """
    n = _to_num(value)
    return {1: "Bullish", -1: "Bearish", 0: "Neutral"}.get(n, "Unknown")


def decode_pd_zone(value) -> str:
    """
    Decode Premium & Discount zone code from webhook payload.

    ⚠️ Counter-intuitive mapping: 0 = Discount, not Equilibrium.

    Mapping:
        1  → "Premium"
        0  → "Discount"
        -1 → "Equilibrium"
    """
    n = _to_num(value)
    return {1: "Premium", 0: "Discount", -1: "Equilibrium"}.get(n, "Unknown")


def decode_guardian(value) -> str:
    """
    Decode Guardian execution mode from webhook payload.

    Mapping:
        0 → "Waiting"
        1 → "Sniper Buy"
        2 → "Sniper Sell"
        3 → "Retrace Buy"
        4 → "Retrace Sell"
        5 → "Trap Buy"
        6 → "Trap Sell"
    """
    n = _to_num(value)
    return {
        0: "Waiting",
        1: "Sniper Buy",
        2: "Sniper Sell",
        3: "Retrace Buy",
        4: "Retrace Sell",
        5: "Trap Buy",
        6: "Trap Sell",
    }.get(n, "Unknown")


def decode_kill_zone(value) -> str:
    """
    Decode Kill Zone session code from webhook payload.

    Mapping:
        0 → "Off-Session"
        1 → "London"
        2 → "NY AM"
        3 → "NY PM"
        4 → "Asian"
    """
    n = _to_num(value)
    return {
        0: "Off-Session",
        1: "London",
        2: "NY AM",
        3: "NY PM",
        4: "Asian",
    }.get(n, "Unknown")


# ============================================================================
# Convenience — decode all fields at once
# ============================================================================

def decode_all(payload: dict) -> dict:
    """
    Decode all four categorical fields from a webhook payload in one call.

    Args:
        payload: Dict with raw numeric/string fields from the webhook.
                 Expected keys: h4_bias, p_d_zone (or pd_zone or zone),
                 guardian, kill_zone

    Returns:
        Dict with decoded human-readable values:
        {
            "h4_bias": "Bullish",
            "pd_zone": "Discount",
            "guardian": "Sniper Buy",
            "kill_zone": "NY AM"
        }
    """
    raw_pd = payload.get("p_d_zone") or payload.get("pd_zone") or payload.get("zone", 0)
    return {
        "h4_bias": decode_h4_bias(payload.get("h4_bias", 0)),
        "pd_zone": decode_pd_zone(raw_pd),
        "guardian": decode_guardian(payload.get("guardian", 0)),
        "kill_zone": decode_kill_zone(payload.get("kill_zone")),
    }
