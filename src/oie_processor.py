"""
TradeX Tracker — Opportunity Intelligence Engine (OIE) Processor
Version: v17.56.8

Normalizes incoming webhook payloads from TradingView alert() calls into
clean opportunity records with human-readable decoded fields. Supports
v17.56.8 (HUD sync), v17.56.7 (dual mode), v17.56.6, v17.54.x, v17.25, and
legacy formats.

v17.56.8 additions (HUD sync):
- amd_state: market AMD/Wyckoff state
  (ACCUMULATION | MANIPULATION | DISTRIBUTION | MARKUP | MARKDOWN)
- sniper_today: count of A+ SNIPER alerts fired today (HUD counter)
- execution_today: count of EXECUTION-mode alerts fired today (HUD counter)
- Fully backward compatible with v17.56.7 payloads (missing fields default).

v17.56.7 additions:
- mode: "DATA" vs "EXECUTION" alert classification
- session: "LONDON" vs "NY" trade session tagging
- valid: true/false for zombie trade prevention
- direction: exact from JSON (no inference/flipping)

Also bridges to the legacy signals pipeline so existing dashboard and
analytics continue to work seamlessly.
"""
import json
import logging
from datetime import datetime, timezone

from src.decoders import decode_h4_bias, decode_pd_zone, decode_guardian, decode_kill_zone
from src.database import get_pip_size
from src.version import VERSION, normalize_amd_state, DEFAULT_AMD_STATE

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


def parse_poi_field(val) -> dict:
    """
    Parse a POI field that may be an integer, a string like "5/6", or "5/6 (OTE)".
    v17.56.6: Supports new /6 denominator and (OTE) tag extraction.

    Returns:
        {"score": int, "max": int, "has_ote": bool, "display": str}
    """
    result = {"score": 0, "max": 6, "has_ote": False, "display": "0/6"}

    if val is None:
        return result

    val_str = str(val).strip()
    if not val_str:
        return result

    # Check for (OTE) tag
    result["has_ote"] = "(OTE)" in val_str
    clean = val_str.replace("(OTE)", "").strip()

    # Parse "X/Y" format or plain integer
    if "/" in clean:
        parts = clean.split("/")
        result["score"] = _to_int(parts[0])
        result["max"] = _to_int(parts[1], default=6)
    else:
        result["score"] = _to_int(clean)

    result["display"] = val_str
    return result


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
    # v17.54.x uses alert() architecture with dynamic JSON payloads
    # Supports v17.54.1, v17.54.2, and any future v17.5x patches
    if version.startswith("v17.5"):
        return version  # Preserve actual version (v17.54.1, v17.54.2, etc.)
    if version == "v17.25":
        return "v17.25"
    if version == "v17.14":
        return "v17.14"
    if version == "v17.12.3":
        return "v17.12.3"
    # Check for v17.54.x format by alert field presence
    if "alert" in payload and version:
        return version if version.startswith("v17") else "v17.56.6"
    # Check for compact format (existing tracker format)
    if "e" in payload and "id" in payload:
        return "compact"
    return "legacy"


# ── v17.54.x alert type normalization ──
# v17.54.x Pine Script uses alert() with dynamic JSON payloads.
# Alert types come as: "A+ SNIPER BUY", "A+ SNIPER SELL", "RETRACE LONG", etc.
# Legacy underscore forms ("A_PLUS_SNIPER_BUY", "RETRACE_LONG") kept for backward compat.
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
    # v17.56.6: CONTINUATION alerts (renamed from RETRACE in Pine Script v17.56.x)
    "CONTINUATION_LONG": "retrace_long",
    "CONTINUATION LONG": "retrace_long",
    "CONTINUATION_SHORT": "retrace_short",
    "CONTINUATION SHORT": "retrace_short",
}


def normalize_v17_54_payload(payload: dict) -> dict:
    """
    Normalize a v17.54.x dynamic JSON payload into the standard OIE format.

    v17.54.x payloads look like:
        {"version":"v17.54.2","alert":"A+ SNIPER BUY","symbol":"GBPUSD",
         "timeframe":"5","price":"1.34195","message":"v17.54.2 A+ SNIPER BUY - Aligned with Trend. Target 1:3 RR."}

    or with subtype:
        {"version":"v17.54.2","alert":"RETRACE LONG","subtype":"standard",
         "symbol":"AUDUSD","timeframe":"5","price":"0.71281","message":"v17.54.2 RETRACE LONG"}
    """
    alert_raw = payload.get("alert", "")
    setup_type = _V17_54_ALERT_MAP.get(alert_raw.upper().strip(), alert_raw.lower().replace(" ", "_"))

    symbol = (payload.get("symbol") or payload.get("ticker", "UNKNOWN")).upper().strip()
    price = _to_float(payload.get("price", 0))
    timeframe = payload.get("timeframe", "5")
    subtype = payload.get("subtype", "")
    message = payload.get("message", "")

    # v17.54.x dynamic payloads provide entry price at {{close}}
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
        "version": payload.get("version", "v17.56.6"),
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
    - v17.56.7+: 'direction' + 'setup' + version starting with 'v17.56.7'
    - v17.54.x-v17.56.6: 'alert' field with version starting with 'v17.5'
    - v17.25/v17.14: 'type' field like 'sniper_long', 'sniper_short', etc.
    """
    version = payload.get("version", "")

    # v17.56.7+: New dual-mode JSON format with direction/setup/mode/session
    if "direction" in payload and "setup" in payload and version.startswith("v17.5"):
        return True

    # v17.54.x-v17.56.6 dynamic JSON format (alert() architecture)
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

    Supports v17.56.7 (setup+direction), v17.54.x (alert), and v17.25 (type) formats.
    """
    if not payload or not isinstance(payload, dict):
        return False, "Empty or invalid payload"

    # v17.56.7 uses 'setup' + 'direction', v17.54.x uses 'alert', v17.25 uses 'type'
    if not payload.get("type") and not payload.get("alert") and not payload.get("setup"):
        return False, "Missing required field: type, alert, or setup"

    if not payload.get("symbol") and not payload.get("ticker"):
        return False, "Missing required field: symbol"

    # v17.56.7 uses 'entry', v17.54.x uses 'price', v17.25 uses entry_price/suggested_entry
    has_entry = any(payload.get(k) is not None for k in
                    ("entry_price", "suggested_entry", "entry", "price"))
    if not has_entry:
        return False, "Missing required field: entry price"

    return True, ""


# ============================================================================
# Core Normalizer
# ============================================================================

def _is_v17_56_7_payload(payload: dict) -> bool:
    """Detect v17.56.7+ dual-mode payload format (v17.56.7 and v17.56.8)."""
    return ("direction" in payload and "setup" in payload
            and payload.get("version", "").startswith(("v17.56.7", "v17.56.8")))


def _is_v17_56_8_payload(payload: dict) -> bool:
    """Detect a v17.56.8 HUD-sync payload format."""
    return ("direction" in payload and "setup" in payload
            and payload.get("version", "").startswith("v17.56.8"))


def normalize_v17_56_7_payload(payload: dict) -> dict:
    """
    Normalize a v17.56.7 dual-mode JSON payload into the standard OIE format.

    v17.56.7 payloads:
        {"version":"v17.56.7","mode":"EXECUTION","session":"LONDON",
         "symbol":"GBPUSD","direction":"LONG","setup":"A+ SNIPER",
         "poi":6,"align":"WITH_TREND","htf_bias":"BULLISH","ltf_bias":"BULLISH",
         "timestamp":"...","entry":1.34195,"sl":1.33800,"tp":1.35385,"valid":true}

    Direction is taken EXACTLY from the JSON — no inference or flipping.
    """
    symbol = (payload.get("symbol") or payload.get("ticker", "UNKNOWN")).upper().strip()
    direction = str(payload.get("direction", "LONG")).upper().strip()
    setup_raw = str(payload.get("setup", "")).upper().strip()
    mode = str(payload.get("mode", "DATA")).upper().strip()
    session = str(payload.get("session", "NY")).upper().strip()
    valid = payload.get("valid", True)

    # Map setup name to standard type
    setup_map = {
        "A+ SNIPER": "sniper_long" if direction == "LONG" else "sniper_short",
        "SNIPER": "sniper_long" if direction == "LONG" else "sniper_short",
        "CONTINUATION": "retrace_long" if direction == "LONG" else "retrace_short",
        "RETRACE": "retrace_long" if direction == "LONG" else "retrace_short",
        "COUNTER": "counter_long" if direction == "LONG" else "counter_short",
    }
    setup_type = setup_map.get(setup_raw, setup_raw.lower().replace(" ", "_"))
    if not setup_type:
        setup_type = f"sniper_{'long' if direction == 'LONG' else 'short'}"

    entry_price = _to_float(payload.get("entry"))
    sl_price = _to_float(payload.get("sl"))
    tp_price = _to_float(payload.get("tp"))
    timestamp = payload.get("timestamp") or datetime.now(timezone.utc).isoformat()

    # v17.56.8: HUD sync fields (default-safe for v17.56.7 payloads)
    amd_state = normalize_amd_state(payload.get("amd_state"))
    sniper_today = _to_int(payload.get("sniper_today"), default=0)
    execution_today = _to_int(payload.get("execution_today"), default=0)

    return {
        "type": setup_type,
        "symbol": symbol,
        "direction": direction,
        "entry_price": entry_price,
        "stop_loss": sl_price,
        "take_profit": tp_price,
        "version": payload.get("version", VERSION),
        "timestamp": timestamp,
        "setup_id": f"{symbol}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        # v17.56.7: New fields
        "mode": mode,
        "session": session,
        "valid": valid,
        "align": payload.get("align", ""),
        "htf_bias": payload.get("htf_bias", ""),
        "ltf_bias": payload.get("ltf_bias", ""),
        # v17.56.8: HUD sync fields
        "amd_state": amd_state,
        "sniper_today": sniper_today,
        "execution_today": execution_today,
        # Carry forward standard fields
        "h4_bias": payload.get("h4_bias", payload.get("htf_bias", "")),
        "poi": payload.get("poi"),
        "kill_zone": payload.get("kill_zone"),
        "guardian": payload.get("guardian", 0),
        "quality": payload.get("quality"),
        "confluence": payload.get("confluence"),
        "dt_stage": payload.get("dt_stage"),
    }


def normalize_oie_payload(payload: dict) -> dict:
    """
    Normalize any v17.14+ webhook payload into a clean opportunity record
    with decoded categorical fields, ready for DB insertion.

    Handles:
    - v17.56.7 dual-mode JSON payloads (direction/setup/mode/session)
    - v17.54.x dynamic JSON payloads (alert() architecture with {{close}} price)
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

    # v17.56.7 dual-mode format: normalize first
    if _is_v17_56_7_payload(payload):
        payload = normalize_v17_56_7_payload(payload)
    # v17.54.x-v17.56.6 dynamic JSON: normalize into standard format first
    elif version.startswith("v17.5") and "alert" in payload:
        payload = normalize_v17_54_payload(payload)

    setup_type = payload.get("type", "unknown")
    symbol = payload.get("symbol") or payload.get("ticker", "UNKNOWN")
    symbol = symbol.upper().strip()

    # --- v17.56.7: Extract direction EXACTLY from JSON ---
    direction = payload.get("direction", "").upper().strip()
    if not direction:
        # Fallback: infer from setup_type for older payloads
        direction = "LONG" if ("long" in setup_type or "buy" in setup_type) else "SHORT"

    # --- Extract price levels ---
    # Support v17.56.7 (entry/sl/tp), v17.54.x, v17.25, and v17.14 field names
    entry_price = _to_float(
        payload.get("entry_price") or payload.get("entry") or payload.get("suggested_entry")
    )
    sl_price = _to_float(
        payload.get("stop_loss") or payload.get("sl") or payload.get("target_sl")
    )
    tp_price = _to_float(
        payload.get("take_profit") or payload.get("tp") or payload.get("target_tp")
    )

    # --- Calculate risk metrics ---
    risk_pips = calculate_pips(entry_price, sl_price, symbol)
    reward_pips = calculate_pips(tp_price, entry_price, symbol)
    rr_ratio = round(reward_pips / risk_pips, 2) if risk_pips > 0 else 0.0

    # --- Decode categorical fields ---
    # v17.56.7: htf_bias is a string like "BULLISH"/"BEARISH", decode_h4_bias takes numeric
    raw_h4 = payload.get("h4_bias", 0)
    if isinstance(raw_h4, str) and raw_h4.upper() in ("BULLISH", "BEARISH", "NEUTRAL"):
        h4_bias = raw_h4.capitalize()
    else:
        h4_bias = decode_h4_bias(raw_h4)

    raw_pd = payload.get("p_d_zone") or payload.get("pd_zone") or payload.get("zone", 0)
    pd_zone = decode_pd_zone(raw_pd)
    guardian = decode_guardian(payload.get("guardian", 0))
    raw_kz = payload.get("kill_zone")
    kill_zone = decode_kill_zone(raw_kz) if raw_kz is not None else "Unknown"

    # --- Quality scores ---
    quality_score = _to_float(payload.get("quality"))
    # v17.56.6+: Parse POI with /6 denominator and (OTE) tag support
    poi_parsed = parse_poi_field(payload.get("poi"))
    poi_score = poi_parsed["score"]
    poi_max = poi_parsed["max"]
    has_ote = poi_parsed["has_ote"]
    confluence = _to_int(payload.get("confluence"))
    dt_stage = _to_int(payload.get("dt_stage")) if is_sniper_payload(payload) else None

    # --- Timestamp ---
    timestamp = payload.get("timestamp") or datetime.now(timezone.utc).isoformat()

    # --- v17.56.7: Mode, session, valid ---
    mode = str(payload.get("mode", "DATA")).upper().strip()
    if mode not in ("DATA", "EXECUTION"):
        mode = "DATA"
    session_tag = str(payload.get("session", "NY")).upper().strip()
    if session_tag not in ("LONDON", "NY"):
        session_tag = "NY"
    valid = payload.get("valid", True)
    if isinstance(valid, str):
        valid = valid.lower() not in ("false", "0", "no")

    # --- v17.56.8: AMD state + daily HUD counters ---
    amd_state = normalize_amd_state(payload.get("amd_state"))
    sniper_today = _to_int(payload.get("sniper_today"), default=0)
    execution_today = _to_int(payload.get("execution_today"), default=0)

    result = {
        "pair": symbol,
        "direction": direction,
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
        "poi_max": poi_max,
        "has_ote": has_ote,
        "confluence": confluence,
        "dt_stage": dt_stage,
        "status": "identified",
        "identified_at": timestamp,
        "raw_payload": json.dumps(payload),
        "version": payload.get("version", "unknown"),
        # v17.56.7: Dual mode fields
        "mode": mode,
        "session_tag": session_tag,
        "valid": valid,
        # v17.56.8: HUD sync fields
        "amd_state": amd_state,
        "sniper_today": sniper_today,
        "execution_today": execution_today,
    }

    return result


# ============================================================================
# Bridge to Legacy Signals Pipeline
# ============================================================================

def oie_to_legacy_compact(payload: dict) -> dict:
    """
    Convert an OIE v17.54.x/v17.25/v17.56.7 payload into the compact format that the
    existing processor.py understands, so it also gets recorded in the signals table
    for backward compatibility with dashboard/analytics.

    v17.56.7: Uses direction from JSON exactly. Passes mode/session_tag/valid.
    """
    setup_type = payload.get("type", "") or payload.get("setup", "")
    symbol = payload.get("symbol") or payload.get("ticker", "UNKNOWN")
    now = datetime.now(timezone.utc)
    ts = payload.get("timestamp", now.isoformat())

    # v17.56.7: Use direction from JSON exactly if available
    raw_dir = payload.get("direction", "").upper().strip()
    if raw_dir in ("LONG", "SHORT"):
        is_long = raw_dir == "LONG"
        direction = "L" if is_long else "S"
    else:
        # Fallback: infer from setup_type
        is_long = "long" in setup_type.lower() or "buy" in setup_type.lower()
        direction = "L" if is_long else "S"

    # Map to signal type
    is_sniper = "sniper" in setup_type.lower()
    sig_type = "STD" if is_sniper else "CT"

    # Extract prices — unified for all versions
    ep = _to_float(payload.get("entry_price") or payload.get("entry") or payload.get("suggested_entry"))
    sl = _to_float(payload.get("stop_loss") or payload.get("sl") or payload.get("target_sl"))
    tp = _to_float(payload.get("take_profit") or payload.get("tp") or payload.get("target_tp"))

    signal_id = payload.get("setup_id") or f"{symbol}_{now.strftime('%Y%m%d_%H%M%S')}"

    # v17.56.7: Extract mode/session/valid for passthrough
    mode = str(payload.get("mode", "DATA")).upper().strip()
    session_tag = str(payload.get("session", "NY")).upper().strip()
    valid = payload.get("valid", True)

    # v17.56.8: Extract HUD sync fields for passthrough
    amd_state = normalize_amd_state(payload.get("amd_state"))
    sniper_today = _to_int(payload.get("sniper_today"), default=0)
    execution_today = _to_int(payload.get("execution_today"), default=0)

    # Decode h4_bias — handle both string and numeric forms
    raw_h4 = payload.get("h4_bias", 0)
    if isinstance(raw_h4, str) and raw_h4.upper() in ("BULLISH", "BEARISH"):
        h4_code = "BU" if raw_h4.upper() == "BULLISH" else "BE"
    else:
        h4_code = "BU" if decode_h4_bias(raw_h4) == "Bullish" else "BE"

    return {
        "e": "ENTRY",
        "id": signal_id,
        "p": symbol.upper(),
        "d": direction,
        "st": sig_type,
        "ep": ep,
        "sl": sl,
        "tp": tp,
        "ps": parse_poi_field(payload.get("poi"))["score"],
        "rr": 3.0,
        "t": ts,
        "v": payload.get("version", "v17.56.7").replace("v", ""),
        "h4": h4_code,
        "z": {"Premium": "P", "Discount": "D", "Equilibrium": "E"}.get(
            decode_pd_zone(payload.get("p_d_zone") or payload.get("pd_zone") or payload.get("zone", 0)),
            "E"
        ),
        "str": "BU" if is_long else "BE",
        "kz": _to_int(payload.get("kill_zone", 0)),
        # v17.56.7: Dual mode fields passed through to processor
        "_mode": mode,
        "_session_tag": session_tag,
        "_valid": valid,
        # v17.56.8: HUD sync fields passed through to processor
        "_amd_state": amd_state,
        "_sniper_today": sniper_today,
        "_execution_today": execution_today,
    }



# ============================================================================
# v17.56.8: Explicit Versioned Decoder API
# ----------------------------------------------------------------------------
# Thin, well-documented wrappers around normalize_oie_payload() that make the
# version-detection contract explicit and easy to unit test. The webhook route
# uses normalize_oie_payload() directly; these helpers provide a stable,
# version-aware decoding surface (and guarantee backward compatibility).
# ============================================================================

def decode_v17_56_8_payload(payload: dict) -> dict:
    """Decode a v17.56.8 payload (HUD sync fields) into a normalized record.

    Parses the new v17.56.8 fields (amd_state, sniper_today, execution_today)
    in addition to all existing v17.56.7 dual-mode fields.
    """
    record = normalize_oie_payload(payload)
    # Guarantee the v17.56.8 fields are present and validated.
    record["amd_state"] = normalize_amd_state(record.get("amd_state"))
    record["sniper_today"] = _to_int(record.get("sniper_today"), default=0)
    record["execution_today"] = _to_int(record.get("execution_today"), default=0)
    return record


def decode_v17_56_7_payload(payload: dict) -> dict:
    """Decode a v17.56.7 payload, defaulting the v17.56.8 HUD fields.

    Ensures backward compatibility: v17.56.7 payloads (which lack amd_state /
    sniper_today / execution_today) get safe defaults.
    """
    record = normalize_oie_payload(payload)
    record.setdefault("amd_state", DEFAULT_AMD_STATE)
    record.setdefault("sniper_today", 0)
    record.setdefault("execution_today", 0)
    record["amd_state"] = normalize_amd_state(record.get("amd_state"))
    return record


def decode_legacy_payload(payload: dict) -> dict:
    """Decode any pre-v17.56.7 payload (v17.54.x / v17.25 / compact / legacy).

    New HUD-sync fields default to ACCUMULATION / 0 / 0.
    """
    record = normalize_oie_payload(payload)
    record.setdefault("amd_state", DEFAULT_AMD_STATE)
    record.setdefault("sniper_today", 0)
    record.setdefault("execution_today", 0)
    return record


def decode_payload(payload: dict) -> dict:
    """Universal decoder with version detection.

    Routes the payload to the correct version-specific decoder and always
    returns a normalized record that includes the v17.56.8 HUD-sync fields
    (with safe defaults for older payloads).
    """
    version = str(payload.get("version", "unknown"))

    if version.startswith("v17.56.8"):
        return decode_v17_56_8_payload(payload)
    elif version.startswith("v17.56.7"):
        return decode_v17_56_7_payload(payload)
    else:
        return decode_legacy_payload(payload)
