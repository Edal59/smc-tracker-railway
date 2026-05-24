"""
TradeX Tracker — Opportunity Intelligence Engine (OIE) Processor
Version: v17.54

Normalizes incoming webhook payloads from TradingView alert() calls into
clean opportunity records with human-readable decoded fields. Supports
v17.54 (current, dynamic JSON payloads), v17.25 (plot-based), and legacy formats.

Also bridges to the legacy signals pipeline so existing dashboard and
analytics continue to work seamlessly.
"""
import json
import logging
from datetime import datetime, timezone

from src.decoders import decode_h4_bias, decode_pd_zone, decode_guardian, decode_kill_zone
from src.database import get_pip_size

logger = logging.getLogger(__name__)


# ============================================================================
# Helpers
# ============================================================================

def _to_float(val, default=0.0) -> float:
    """Safely parse a string or number to float."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _to_int(val, default=0) -> int:
    """Safely parse to integer."""
    if val is None:
        return default
    try:
        return int(float(str(val)))
    except (ValueError, TypeError):
        return default


def calculate_pips(price1: float, price2: float, symbol: str) -> float:
    """
    Calculate pip distance between two prices.
    Uses pair_config pip_size from DB, falls back to standard forex conventions.
    """
    pip_size = get_pip_size(symbol)
    if pip_size <= 0:
        pip_size = 0.01 if 'JPY' in symbol.upper() or 'XAU' in symbol.upper() else 0.0001
    raw = abs(price1 - price2) / pip_size
    return round(raw, 1)


# ============================================================================
# Payload Detection
# ============================================================================

def detect_version(payload: dict) -> str:
    """Detect the payload format version."""
    version = payload.get("version", "")
    # v17.54 uses alert() architecture with dynamic JSON payloads
    if version.startswith("v17.5"):
        return "v17.54"
    if version == "v17.25":
        return "v17.25"
    if version == "v17.14":
        return "v17.14"
    if version == "v17.12.3":
        return "v17.12.3"
    # Check for v17.54 format by alert field presence
    if "alert" in payload and version:
        return "v17.54"
    # Check for compact format (existing tracker format)
    if "e" in payload and "id" in payload:
        return "compact"
    return "legacy"


# ── v17.54 alert type normalization ──
# v17.54 Pine Script uses alert() with dynamic JSON payloads.
# Alert types come as: "A_PLUS_SNIPER_BUY", "A+ SNIPER BUY", "RETRACE_LONG", etc.
_V17_54_ALERT_MAP = {
    "A_PLUS_SNIPER_BUY": "sniper_long",
    "A+ SNIPER BUY": "sniper_long",
    "SNIPER_LONG": "sniper_long",
    "SNIPER LONG": "sniper_long",
    "A_PLUS_SNIPER_SELL": "sniper_short",
    "A+ SNIPER SELL": "sniper_short",
    "SNIPER_SHORT": "sniper_short",
    "SNIPER SHORT": "sniper_short",
    "RETRACE_LONG": "retrace_long",
    "RETRACE LONG": "retrace_long",
    "RETRACE_SHORT": "retrace_short",
    "RETRACE SHORT": "retrace_short",
    "COUNTER_BUY": "counter_long",
    "COUNTER BUY": "counter_long",
    "COUNTER_SELL": "counter_short",
    "COUNTER SELL": "counter_short",
}


def normalize_v17_54_payload(payload: dict) -> dict:
    """
    Normalize a v17.54 dynamic JSON payload into the standard OIE format.

    v17.54 payloads look like:
        {"version":"v17.54","alert":"A_PLUS_SNIPER_BUY","symbol":"GBPUSD",
         "timeframe":"5","price":"1.34195","message":"v17.54 A+ SNIPER BUY - Aligned with Trend. Target 1:3 RR."}

    or with subtype:
        {"version":"v17.54","alert":"RETRACE LONG","subtype":"standard",
         "symbol":"AUDUSD","timeframe":"5","price":"0.71281","message":"v17.54 RETRACE LONG"}
    """
    alert_raw = payload.get("alert", "")
    setup_type = _V17_54_ALERT_MAP.get(alert_raw.upper().strip(), alert_raw.lower().replace(" ", "_"))

    symbol = (payload.get("symbol") or payload.get("ticker", "UNKNOWN")).upper().strip()
    price = _to_float(payload.get("price", 0))
    timeframe = payload.get("timeframe", "5")
    subtype = payload.get("subtype", "")
    message = payload.get("message", "")

    # v17.54 dynamic payloads provide entry price at {{close}}
    # SL/TP are estimated with standard R:R ratios since they're not in the payload
    is_long = "long" in setup_type or "buy" in setup_type
    pip_mult = 0.01 if any(x in symbol for x in ('JPY', 'XAU')) else 0.0001

    # Sniper entries get tighter stops (20 pips SL, 60 pips TP = 1:3 RR)
    # Retrace entries get wider stops (30 pips SL, 90 pips TP = 1:3 RR)
    is_sniper = "sniper" in setup_type
    sl_pips = 20 if is_sniper else 30
    tp_pips = 60 if is_sniper else 90

    sl_dist = sl_pips * pip_mult
    tp_dist = tp_pips * pip_mult

    if is_long:
        sl = round(price - sl_dist, 5)
        tp = round(price + tp_dist, 5)
    else:
        sl = round(price + sl_dist, 5)
        tp = round(price - tp_dist, 5)

    # Return in standard OIE format that normalize_oie_payload() expects
    return {
        "type": setup_type,
        "symbol": symbol,
        "entry_price": price,
        "stop_loss": sl,
        "take_profit": tp,
        "version": payload.get("version", "v17.54"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "timeframe": timeframe,
        "subtype": subtype,
        "message": message,
        "setup_id": f"{symbol}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        # Carry forward any extra fields from Pine Script
        "h4_bias": payload.get("h4_bias", 0),
        "p_d_zone": payload.get("p_d_zone", 0),
        "kill_zone": payload.get("kill_zone"),
        "guardian": payload.get("guardian", 0),
        "quality": payload.get("quality"),
        "poi": payload.get("poi"),
        "confluence": payload.get("confluence"),
        "dt_stage": payload.get("dt_stage"),
    }


def is_oie_payload(payload: dict) -> bool:
    """
    Determine if a payload is an OIE v17.14+ format vs legacy compact/full format.

    OIE payloads have:
    - v17.54+: 'alert' field with version starting with 'v17.5'
    - v17.25/v17.14: 'type' field like 'sniper_long', 'sniper_short', etc.
    """
    version = payload.get("version", "")

    # v17.54 dynamic JSON format (alert() architecture)
    if "alert" in payload and version.startswith("v17.5"):
        return True

    # v17.25 / v17.14 alertcondition() format
    ptype = payload.get("type", "")
    if ptype in ("sniper_long", "sniper_short", "retrace_long", "retrace_short"):
        if version.startswith("v17.1") or version.startswith("v17.2"):
            return True

    return False


def is_sniper_payload(payload: dict) -> bool:
    setup_type = payload.get("type", "")
    return "sniper" in setup_type.lower()


def is_retrace_payload(payload: dict) -> bool:
    setup_type = payload.get("type", "")
    return "retrace" in setup_type.lower()


# ============================================================================
# Validation
# ============================================================================

def validate_oie_payload(payload: dict) -> tuple:
    """
    Validate a raw OIE webhook payload for required fields.
    Returns: (is_valid: bool, error_message: str)

    Supports both v17.54 (alert field) and v17.25 (type field) formats.
    """
    if not payload or not isinstance(payload, dict):
        return False, "Empty or invalid payload"

    # v17.54 uses 'alert' field, v17.25 uses 'type' field
    if not payload.get("type") and not payload.get("alert"):
        return False, "Missing required field: type or alert"

    if not payload.get("symbol") and not payload.get("ticker"):
        return False, "Missing required field: symbol"

    # v17.54 uses 'price' (from {{close}}), v17.25 uses entry_price/suggested_entry
    has_entry = any(payload.get(k) is not None for k in
                    ("entry_price", "suggested_entry", "entry", "price"))
    if not has_entry:
        return False, "Missing required field: entry price"

    return True, ""


# ============================================================================
# Core Normalizer
# ============================================================================

def normalize_oie_payload(payload: dict) -> dict:
    """
    Normalize any v17.14+ webhook payload into a clean opportunity record
    with decoded categorical fields, ready for DB insertion.

    Handles:
    - v17.54 dynamic JSON payloads (alert() architecture with {{close}} price)
    - v17.25 Sniper alerts (entry_price, stop_loss, take_profit)
    - v17.25 Retrace alerts (suggested_entry, target_sl, target_tp)
    - v17.14 format (without kill_zone)
    - v17.12.3 legacy format (backward compat)

    Returns:
        Dict with all opportunity fields ready for insert_opportunity()
    """
    is_valid, error = validate_oie_payload(payload)
    if not is_valid:
        raise ValueError(f"Invalid OIE payload: {error}")

    version = detect_version(payload)

    # v17.54 dynamic JSON: normalize into standard format first
    if version == "v17.54" and "alert" in payload:
        payload = normalize_v17_54_payload(payload)

    setup_type = payload.get("type", "unknown")
    symbol = payload.get("symbol") or payload.get("ticker", "UNKNOWN")
    symbol = symbol.upper().strip()

    # --- Extract price levels ---
    # Support v17.54 (entry_price from normalization), v17.25, and v17.14 field names
    if is_sniper_payload(payload):
        entry_price = _to_float(payload.get("entry_price") or payload.get("entry"))
        sl_price = _to_float(payload.get("stop_loss") or payload.get("sl"))
        tp_price = _to_float(payload.get("take_profit") or payload.get("tp"))
    elif is_retrace_payload(payload):
        entry_price = _to_float(payload.get("suggested_entry") or payload.get("entry") or payload.get("entry_price"))
        sl_price = _to_float(payload.get("target_sl") or payload.get("sl") or payload.get("stop_loss"))
        tp_price = _to_float(payload.get("target_tp") or payload.get("tp") or payload.get("take_profit"))
    else:
        # Legacy / counter-trend fallback
        entry_price = _to_float(payload.get("entry_price") or payload.get("entry"))
        sl_price = _to_float(payload.get("stop_loss") or payload.get("sl"))
        tp_price = _to_float(payload.get("take_profit") or payload.get("tp"))

    # --- Calculate risk metrics ---
    risk_pips = calculate_pips(entry_price, sl_price, symbol)
    reward_pips = calculate_pips(tp_price, entry_price, symbol)
    rr_ratio = round(reward_pips / risk_pips, 2) if risk_pips > 0 else 0.0

    # --- Decode categorical fields ---
    h4_bias = decode_h4_bias(payload.get("h4_bias", 0))
    raw_pd = payload.get("p_d_zone") or payload.get("pd_zone") or payload.get("zone", 0)
    pd_zone = decode_pd_zone(raw_pd)
    guardian = decode_guardian(payload.get("guardian", 0))
    raw_kz = payload.get("kill_zone")
    kill_zone = decode_kill_zone(raw_kz) if raw_kz is not None else "Unknown"

    # --- Quality scores ---
    quality_score = _to_float(payload.get("quality"))
    poi_score = _to_int(payload.get("poi"))
    confluence = _to_int(payload.get("confluence"))
    dt_stage = _to_int(payload.get("dt_stage")) if is_sniper_payload(payload) else None

    # --- Timestamp ---
    timestamp = payload.get("timestamp") or datetime.now(timezone.utc).isoformat()

    return {
        "pair": symbol,
        "setup_type": setup_type,
        "setup_id": payload.get("setup_id", "dynamic"),
        "h4_bias": h4_bias,
        "pd_zone": pd_zone,
        "kill_zone": kill_zone,
        "guardian": guardian,
        "entry_price": entry_price,
        "sl_price": sl_price,
        "tp_price": tp_price,
        "risk_pips": risk_pips,
        "reward_pips": reward_pips,
        "rr_ratio": rr_ratio,
        "quality_score": quality_score,
        "poi_score": poi_score,
        "confluence": confluence,
        "dt_stage": dt_stage,
        "status": "identified",
        "identified_at": timestamp,
        "raw_payload": json.dumps(payload),
        "version": payload.get("version", "unknown"),
    }


# ============================================================================
# Bridge to Legacy Signals Pipeline
# ============================================================================

def oie_to_legacy_compact(payload: dict) -> dict:
    """
    Convert an OIE v17.54/v17.25 payload into the compact format that the existing
    processor.py understands, so it also gets recorded in the signals table
    for backward compatibility with dashboard/analytics.

    This allows the existing dashboard to continue showing signals while the
    new OIE pipeline tracks opportunities in parallel.
    """
    setup_type = payload.get("type", "")
    symbol = payload.get("symbol") or payload.get("ticker", "UNKNOWN")
    now = datetime.now(timezone.utc)
    ts = payload.get("timestamp", now.isoformat())

    # Map setup_type to direction
    is_long = "long" in setup_type.lower()
    direction = "L" if is_long else "S"

    # Map to signal type
    is_sniper = "sniper" in setup_type.lower()
    sig_type = "STD" if is_sniper else "CT"  # sniper=standard, retrace=counter-trend mapping

    # Extract prices
    if is_sniper:
        ep = _to_float(payload.get("entry_price"))
        sl = _to_float(payload.get("stop_loss"))
        tp = _to_float(payload.get("take_profit"))
    else:
        ep = _to_float(payload.get("suggested_entry"))
        sl = _to_float(payload.get("target_sl"))
        tp = _to_float(payload.get("target_tp"))

    signal_id = payload.get("setup_id") or f"{symbol}_{now.strftime('%Y%m%d_%H%M%S')}"

    return {
        "e": "ENTRY",
        "id": signal_id,
        "p": symbol.upper(),
        "d": direction,
        "st": sig_type,
        "ep": ep,
        "sl": sl,
        "tp": tp,
        "ps": _to_int(payload.get("poi", 0)),
        "rr": 3.0,
        "t": ts,
        "v": payload.get("version", "v17.54").replace("v", ""),
        "h4": "BU" if decode_h4_bias(payload.get("h4_bias", 0)) == "Bullish" else "BE",
        "z": {"Premium": "P", "Discount": "D", "Equilibrium": "E"}.get(
            decode_pd_zone(payload.get("p_d_zone") or payload.get("pd_zone") or payload.get("zone", 0)),
            "E"
        ),
        "str": "BU" if is_long else "BE",
        "kz": _to_int(payload.get("kill_zone", 0)),
    }
