"""
TradeX Tracker — Market Brief (MB) Execution Alert Processor
Version: v17.85.34 compatibility

Handles the live TradingView execution alerts emitted by the SMC PD Pine
indicator v17.85.x. These are the *tradeable* alerts — the ones a trade is
actually created from — as opposed to the informational OIE/data payloads
handled by ``oie_processor.py``.

There are exactly 10 live execution alert names, grouped into 3 payload shapes:

  1. EXECUTION lane  (payload shape A — NO entry_price, uses ``price``)
       MB_EXECUTE_LONG / MB_EXECUTE_SHORT      type = WITH_TREND
       MB_CONTINUE_LONG / MB_CONTINUE_SHORT    type = CONTINUATION
       MB_CT_LONG / MB_CT_SHORT                type = COUNTER_TREND
       MB_MACRO_LONG / MB_MACRO_SHORT          type = WITH_TREND, macro_express=1

  2. RE-ENTRY lane   (payload shape B — HAS entry_price, re_entry=1)
       MB_REENTRY_LONG / MB_REENTRY_SHORT      type = RE_ENTRY

  3. V-REVERSAL lane (payload shape C — HAS entry_price, fast_lane=1)
       MB_VREVERSAL_LONG / MB_VREVERSAL_SHORT  type = V_REVERSAL

All 10 route into the SAME trade-creation workflow. Key rules (from spec):

  * Direction comes from the ``direction`` field (BUY/SELL), NEVER by parsing
    the alert name.  BUY -> LONG, SELL -> SHORT.
  * Entry price: use ``entry_price`` when present and numeric (V-Reversal +
    Re-Entry); otherwise use ``price`` (Execution / Continuation / CT / Macro).
    NOTE: the ``entry`` field is a *string* entry-mode label (e.g. "Re-Entry",
    "V-Shape-Breakout", "Sweep-Reversal") — it is NOT a numeric price and must
    never be parsed as one.
  * SL / TP are taken EXACTLY as received. They are NEVER recalculated when a
    valid numeric value is present. (No invented 12/30/90-pip stops here.)
  * If the required entry price, SL, or TP is missing / non-numeric /
    non-positive, the webhook is REJECTED with a visible error and the raw
    payload is retained for inspection. Nothing is invented.
  * Price geometry is validated: BUY requires sl < entry < tp; SELL requires
    tp < entry < sl. A geometry violation is flagged (and rejected) — again
    with the raw payload retained.
  * The indicator ``version`` is preserved on every trade for version
    partitioning / analytics.
  * The full raw payload plus all parsed lane-specific fields are stored.
"""
import json
import logging
from datetime import datetime, timezone, timedelta

from src.database import get_pip_size

logger = logging.getLogger(__name__)


# ============================================================================
# The 10 live execution alert names -> canonical setup type
# ============================================================================

MB_ALERT_TYPES = {
    "MB_EXECUTE_LONG":    "WITH_TREND",
    "MB_EXECUTE_SHORT":   "WITH_TREND",
    "MB_CONTINUE_LONG":   "CONTINUATION",
    "MB_CONTINUE_SHORT":  "CONTINUATION",
    "MB_CT_LONG":         "COUNTER_TREND",
    "MB_CT_SHORT":        "COUNTER_TREND",
    "MB_MACRO_LONG":      "WITH_TREND",
    "MB_MACRO_SHORT":     "WITH_TREND",
    "MB_REENTRY_LONG":    "RE_ENTRY",
    "MB_REENTRY_SHORT":   "RE_ENTRY",
    "MB_VREVERSAL_LONG":  "V_REVERSAL",
    "MB_VREVERSAL_SHORT": "V_REVERSAL",
}

# Alerts whose price levels are already final entry prices (carry entry_price).
_ENTRY_PRICE_LANES = {"RE_ENTRY", "V_REVERSAL"}


# ============================================================================
# Helpers
# ============================================================================

def _to_float(val, default=None):
    """Parse a webhook value (string or number) to float, or ``default``."""
    if val is None:
        return default
    try:
        f = float(val)
    except (ValueError, TypeError):
        return default
    return f


def _to_int(val, default=0):
    if val is None:
        return default
    try:
        return int(float(str(val)))
    except (ValueError, TypeError):
        return default


def is_mb_payload(data: dict) -> bool:
    """Detect a v17.85.x Market Brief live execution alert.

    Matches on the ``alert`` name being one of the 10 known MB_* execution
    alerts. (MB_SETUP_READY and other informational MB alerts are intentionally
    NOT matched — only tradeable execution alerts create trades.)
    """
    if not isinstance(data, dict):
        return False
    alert = str(data.get("alert", "")).upper().strip()
    return alert in MB_ALERT_TYPES


def _calc_pips(a: float, b: float, symbol: str) -> float:
    pip_size = get_pip_size(symbol)
    if not pip_size or pip_size <= 0:
        pip_size = 0.01 if any(x in symbol.upper() for x in ("JPY", "XAU")) else 0.0001
    return round(abs(a - b) / pip_size, 1)


# ============================================================================
# Normalizer
# ============================================================================

def normalize_mb_payload(data: dict):
    """Normalize an MB_* execution payload into a signals-table record.

    Returns a tuple ``(record, error)``:
      * On success: ``(record_dict, None)``.
      * On rejection: ``(None, error_message)`` — the caller should return a
        visible error and retain the raw payload. Nothing is invented.
    """
    alert_name = str(data.get("alert", "")).upper().strip()
    if alert_name not in MB_ALERT_TYPES:
        return None, f"Unknown MB alert name: {alert_name!r}"

    setup_type = MB_ALERT_TYPES[alert_name]

    # --- Direction strictly from the payload (BUY/SELL), never from the name ---
    raw_dir = str(data.get("direction", "")).upper().strip()
    if raw_dir in ("BUY", "LONG", "L"):
        direction = "LONG"
    elif raw_dir in ("SELL", "SHORT", "S"):
        direction = "SHORT"
    else:
        return None, (f"Missing/invalid 'direction' (got {raw_dir!r}); "
                      "expected BUY or SELL")

    symbol = str(data.get("symbol") or data.get("ticker") or "UNKNOWN").upper().strip()

    # --- Entry price selection rule ---------------------------------------
    # Use entry_price when present & valid (RE_ENTRY / V_REVERSAL); otherwise
    # use price (WITH_TREND / CONTINUATION / COUNTER_TREND). The 'entry' field
    # is a STRING entry-mode label and is never parsed as a price.
    entry_price = None
    entry_source = None
    if setup_type in _ENTRY_PRICE_LANES:
        entry_price = _to_float(data.get("entry_price"))
        entry_source = "entry_price"
        # Defensive fallback: if the entry-price lane somehow lacked it, fall
        # back to price rather than silently failing — but flag the source.
        if entry_price is None:
            entry_price = _to_float(data.get("price"))
            entry_source = "price"
    else:
        entry_price = _to_float(data.get("price"))
        entry_source = "price"

    sl_price = _to_float(data.get("sl"))
    tp_price = _to_float(data.get("tp"))

    # --- Required-price validation (reject, never invent) -----------------
    missing = []
    if entry_price is None or entry_price <= 0:
        missing.append(f"entry ({entry_source})")
    if sl_price is None or sl_price <= 0:
        missing.append("sl")
    if tp_price is None or tp_price <= 0:
        missing.append("tp")
    if missing:
        return None, ("Missing/invalid required price field(s): "
                      + ", ".join(missing)
                      + ". SL/TP must be supplied by the indicator; "
                      "the tracker does not invent them.")

    # --- Price geometry validation ----------------------------------------
    # BUY: sl < entry < tp ; SELL: tp < entry < sl
    if direction == "LONG":
        geometry_valid = (sl_price < entry_price < tp_price)
    else:
        geometry_valid = (tp_price < entry_price < sl_price)

    if not geometry_valid:
        return None, (f"Invalid price geometry for {direction}: "
                      f"entry={entry_price} sl={sl_price} tp={tp_price}. "
                      f"Expected {'sl < entry < tp' if direction == 'LONG' else 'tp < entry < sl'}.")

    # --- Risk / reward metrics (from the indicator's own SL/TP) -----------
    risk_pips = _calc_pips(entry_price, sl_price, symbol)
    reward_pips = _calc_pips(tp_price, entry_price, symbol)
    rr = round(reward_pips / risk_pips, 2) if risk_pips > 0 else 0.0

    # --- Timestamps -------------------------------------------------------
    now = datetime.now(timezone.utc)
    sig_ts = str(data.get("time") or now.isoformat())
    hour_utc = hour_est = dow = None
    try:
        dt = datetime.fromisoformat(sig_ts.replace("Z", "+00:00"))
        hour_utc = dt.hour
        hour_est = (dt - timedelta(hours=4)).hour
        dow = dt.weekday()
    except Exception:
        pass

    # --- Lane-specific / analytics fields ---------------------------------
    macro_express = 1 if _to_int(data.get("macro_express"), 0) == 1 else 0
    fast_lane = 1 if _to_int(data.get("fast_lane"), 0) == 1 else 0
    re_entry = 1 if _to_int(data.get("re_entry"), 0) == 1 else 0
    confidence = _to_int(data.get("confidence"), 0)
    sequence = _to_int(data.get("sequence"), 0)
    displacement_value = _to_float(data.get("displacement"), 0.0) or 0.0
    poi_score = _to_int(data.get("poi"), 0)

    # Session comes as a kill-zone string (e.g. "London", "NY AM"). Preserve
    # it verbatim as session_kz and normalise a coarse session_tag for filters.
    session_kz = str(data.get("session", "") or "").strip()
    _kz_upper = session_kz.upper()
    if "LONDON" in _kz_upper:
        session_tag = "LONDON"
    elif "NY" in _kz_upper or "NEW YORK" in _kz_upper:
        session_tag = "NY"
    elif "ASIA" in _kz_upper:
        session_tag = "ASIAN"
    else:
        session_tag = "NY"

    version = str(data.get("version", "") or "unknown")

    # Deterministic-ish unique signal id (symbol + timestamp + alert).
    ts_compact = now.strftime("%Y%m%d_%H%M%S_%f")
    signal_id = f"{symbol}_{ts_compact}_{alert_name}"

    # Optional test-batch label for isolating paper-test batches.
    test_batch = data.get("test_batch") or data.get("batch") or None

    record = {
        # --- core identity ---
        "signal_id": signal_id,
        "pair": symbol,
        "direction": direction,
        # map to the constrained signal_type column (STANDARD/COUNTER_TREND)
        "signal_type": "COUNTER_TREND" if setup_type == "COUNTER_TREND" else "STANDARD",
        # --- prices (exactly as received) ---
        "entry_price": entry_price,
        "stop_loss": sl_price,
        "take_profit": tp_price,
        "sl_distance_pips": risk_pips,
        "tp_distance_pips": reward_pips,
        "target_rr": rr if rr > 0 else 3.0,
        # --- timestamps / session ---
        "signal_timestamp": sig_ts,
        "server_timestamp": now.isoformat(),
        "signal_hour_utc": hour_utc,
        "signal_hour_est": hour_est,
        "signal_day_of_week": dow,
        "session": session_tag.title() if session_tag != "NY" else "New York",
        "session_tag": session_tag,
        "kill_zone": session_kz or None,
        # --- status / version ---
        "status": "ACTIVE",
        "mode": "EXECUTION",
        "valid": 1,
        "indicator_version": version,
        "timeframe": str(data.get("timeframe", "") or ""),
        "poi_score": poi_score if 0 <= poi_score <= 7 else None,
        # --- MB lane-specific fields (persisted via migration) ---
        "alert_name": alert_name,
        "mb_type": setup_type,
        "entry_mode": str(data.get("entry", "") or ""),
        "entry_source": entry_source,
        "confidence": confidence,
        "macro_express": macro_express,
        "fast_lane": fast_lane,
        "re_entry": re_entry,
        "displacement_value": displacement_value,
        "trigger_text": str(data.get("trigger", "") or ""),
        "narrative": str(data.get("narrative", "") or ""),
        "location": str(data.get("location", "") or ""),
        "bias": str(data.get("bias", "") or ""),
        "mb_action": str(data.get("action", "") or ""),
        "geometry_valid": 1 if geometry_valid else 0,
        "test_batch": test_batch,
        # reuse existing persisted sequence_state column for the sequence value
        "sequence_state": sequence,
        # --- full raw payload retention ---
        "raw_payload": json.dumps(data, default=str),
        "rr_ratio": rr,
    }
    return record, None
