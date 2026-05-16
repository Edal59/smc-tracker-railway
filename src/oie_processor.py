"""
TradeX Tracker — Opportunity Intelligence Engine (OIE) Processor
Version: v17.16

Normalizes incoming webhook payloads from TradingView alertconditions into
clean opportunity records with human-readable decoded fields. Supports both
v17.16 (current) and legacy v17.12.3 payload formats.

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
    if version == "v17.16":
        return "v17.16"
    if version == "v17.14":
        return "v17.14"
    if version == "v17.12.3":
        return "v17.12.3"
    # Check for compact format (existing tracker format)
    if "e" in payload and "id" in payload:
        return "compact"
    return "legacy"


def is_oie_payload(payload: dict) -> bool:
    """
    Determine if a payload is an OIE v17.14+ format vs legacy compact/full format.

    OIE payloads have a 'type' field like 'sniper_long', 'sniper_short',
    'retrace_long', 'retrace_short' and a 'version' field starting with 'v17.14'.
    """
    ptype = payload.get("type", "")
    version = payload.get("version", "")
    return ptype in ("sniper_long", "sniper_short", "retrace_long", "retrace_short") and version.startswith("v17.14")


def is_sniper_payload(payload: dict) -> bool:
    return payload.get("type", "") in ("sniper_long", "sniper_short")


def is_retrace_payload(payload: dict) -> bool:
    return payload.get("type", "") in ("retrace_long", "retrace_short")


# ============================================================================
# Validation
# ============================================================================

def validate_oie_payload(payload: dict) -> tuple:
    """
    Validate a raw OIE webhook payload for required fields.
    Returns: (is_valid: bool, error_message: str)
    """
    if not payload or not isinstance(payload, dict):
        return False, "Empty or invalid payload"

    if not payload.get("type"):
        return False, "Missing required field: type"

    if not payload.get("symbol") and not payload.get("ticker"):
        return False, "Missing required field: symbol"

    # Check at least one price field exists
    has_entry = any(payload.get(k) is not None for k in
                    ("entry_price", "suggested_entry", "entry"))
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
    - v17.16 Sniper alerts (entry_price, stop_loss, take_profit)
    - v17.16 Retrace alerts (suggested_entry, target_sl, target_tp)
    - v17.14 format (without kill_zone)
    - v17.12.3 legacy format (backward compat)

    Returns:
        Dict with all opportunity fields ready for insert_opportunity()
    """
    is_valid, error = validate_oie_payload(payload)
    if not is_valid:
        raise ValueError(f"Invalid OIE payload: {error}")

    version = detect_version(payload)
    setup_type = payload.get("type", "unknown")
    symbol = payload.get("symbol") or payload.get("ticker", "UNKNOWN")
    symbol = symbol.upper().strip()

    # --- Extract price levels ---
    # Support both v17.16 field names and v17.14 shorthand with fallbacks
    if is_sniper_payload(payload):
        entry_price = _to_float(payload.get("entry_price") or payload.get("entry"))
        sl_price = _to_float(payload.get("stop_loss") or payload.get("sl"))
        tp_price = _to_float(payload.get("take_profit") or payload.get("tp"))
    elif is_retrace_payload(payload):
        entry_price = _to_float(payload.get("suggested_entry") or payload.get("entry"))
        sl_price = _to_float(payload.get("target_sl") or payload.get("sl"))
        tp_price = _to_float(payload.get("target_tp") or payload.get("tp"))
    else:
        # Legacy fallback
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
    Convert an OIE v17.16 payload into the compact format that the existing
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
        "v": payload.get("version", "v17.16").replace("v", ""),
        "h4": "BU" if decode_h4_bias(payload.get("h4_bias", 0)) == "Bullish" else "BE",
        "z": {"Premium": "P", "Discount": "D", "Equilibrium": "E"}.get(
            decode_pd_zone(payload.get("p_d_zone") or payload.get("pd_zone") or payload.get("zone", 0)),
            "E"
        ),
        "str": "BU" if is_long else "BE",
        "kz": _to_int(payload.get("kill_zone", 0)),
    }
