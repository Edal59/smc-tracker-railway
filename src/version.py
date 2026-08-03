"""
TradeX Tracker — Backend Version (Single Source of Truth)

All backend modules should import VERSION / FEATURES from here so the
reported version stays consistent across the health endpoint, logs,
payload defaults, and database records.
"""

# Single source of truth for the backend version.
VERSION = "v17.85.34"

# Feature flags advertised by the /health endpoint.
FEATURES = [
    "dual_mode",
    "session_analytics",
    "zombie_prevention",
    "invalid_classification",
    "amd_context_awareness",
    "hud_sync",
    "daily_counters",
    "guardian_htf_gating",
    "pdh_pdl_liquidity",  # NEW in v17.57
    "bos_anchored_ranges",  # NEW in v17.58
    "sequence_state_machine",  # NEW in v17.58
    "trend_override_logic",  # NEW in v17.59 (emergency fix)
    "amd_velocity_detection",  # NEW in v17.59 (emergency fix)
    "mb_execution_alerts",  # NEW in v17.85.34 (10 live MB_* execution alerts)
    "indicator_supplied_sl_tp",  # NEW in v17.85.34 (SL/TP used as received, never recalculated)
    "entry_price_lane_selection",  # NEW in v17.85.34 (entry_price for RE_ENTRY/V_REVERSAL, price otherwise)
    "geometry_validation",  # NEW in v17.85.34 (BUY sl<entry<tp / SELL tp<entry<sl)
    "same_candle_conflict_setting",  # NEW in v17.85.34 (visible SL-first default)
    "mb_analytics_filters",  # NEW in v17.85.34 (alert/type/lane/version/test-batch filters)
]

# Valid AMD (Accumulation-Manipulation-Distribution) market states.
# v17.56.8 HUD sync introduces MARKUP / MARKDOWN in addition to the
# classic Wyckoff phases.
VALID_AMD_STATES = [
    "ACCUMULATION",
    "MANIPULATION",
    "DISTRIBUTION",
    "MARKUP",
    "MARKDOWN",
]

DEFAULT_AMD_STATE = "ACCUMULATION"


def get_version() -> str:
    """Return the current backend version string."""
    return VERSION


def get_features() -> list:
    """Return the list of advertised backend features."""
    return list(FEATURES)


def normalize_amd_state(value, default: str = DEFAULT_AMD_STATE) -> str:
    """Validate/normalize an AMD state string. Falls back to default if invalid."""
    if value is None:
        return default
    state = str(value).upper().strip()
    return state if state in VALID_AMD_STATES else default


# Guardian HTF-gating risk levels (v17.56.9):
#   0 = low    (Guardian aligned with HTF bias)
#   1 = medium (minor HTF mismatch)
#   2 = high   (counter-trend — HTF COUNTER / STANDBY)
VALID_GUARDIAN_RISK = (0, 1, 2)
DEFAULT_GUARDIAN_RISK = 0


def normalize_guardian_risk(value, default: int = DEFAULT_GUARDIAN_RISK) -> int:
    """Validate/normalize a guardian_risk value to one of {0, 1, 2}.

    Accepts ints or numeric strings; anything out of range or non-numeric
    falls back to the default (0 = low risk).
    """
    if isinstance(value, bool):
        # Guard against bool being treated as int (True == 1).
        return default
    try:
        risk = int(value)
    except (TypeError, ValueError):
        return default
    return risk if risk in VALID_GUARDIAN_RISK else default


# ============================================================
# v17.58: Sequence State Machine & BOS-Anchored Ranges
# ------------------------------------------------------------
# The indicator now drives a 5-state institutional sequence:
#   0 = idle / no sequence
#   1 = LOCATION      (price in HTF Premium/Discount zone)
#   2 = LIQUIDITY     (liquidity swept)
#   3 = DISPLACEMENT  (LTF shift / displacement detected)
#   4 = MITIGATION    (price returns to mitigation zone)
#   5 = EXECUTION     (entry trigger / sequence complete)
# BOS-anchored ranges describe the active Break-of-Structure swing range
# (high / low / equilibrium) and its directional trend (1=bull, -1=bear, 0=none).
# ============================================================
VALID_SEQUENCE_STATES = (0, 1, 2, 3, 4, 5)
DEFAULT_SEQUENCE_STATE = 0

VALID_BOS_TRENDS = (1, -1, 0)
DEFAULT_BOS_TREND = 0


def normalize_sequence_state(value, default: int = DEFAULT_SEQUENCE_STATE) -> int:
    """Validate/normalize a sequence_state value to one of {0,1,2,3,4,5}.

    Accepts ints or numeric strings; anything out of range or non-numeric
    falls back to the default (0 = idle / no sequence).
    """
    if isinstance(value, bool):
        return default
    try:
        state = int(value)
    except (TypeError, ValueError):
        return default
    return state if state in VALID_SEQUENCE_STATES else default


def normalize_bos_trend(value, default: int = DEFAULT_BOS_TREND) -> int:
    """Validate/normalize a bos_trend value to one of {1, -1, 0}.

    Accepts ints or numeric strings; anything out of range or non-numeric
    falls back to the default (0 = no trend).
    """
    if isinstance(value, bool):
        return default
    try:
        trend = int(value)
    except (TypeError, ValueError):
        return default
    return trend if trend in VALID_BOS_TRENDS else default


# ============================================================
# v17.59: Trend Override Logic & AMD Velocity (EMERGENCY FIX)
# ------------------------------------------------------------
# Emergency fix for inverted entry logic during strong directional
# trends. The indicator now reports HTF/LTF trend-override state and
# an AMD velocity reading (as a % of ATR) so the backend can surface
# a "strong trend mode" context. These fields are IN-MEMORY ONLY:
# they are echoed on the API/latest snapshot but NOT persisted to the
# database (no schema migration required).
#   strong_trend_mode: BEARISH | BULLISH | NONE
# ============================================================
VALID_STRONG_TREND_MODES = ("BEARISH", "BULLISH", "NONE")
DEFAULT_STRONG_TREND_MODE = "NONE"


def normalize_strong_trend_mode(value, default: str = DEFAULT_STRONG_TREND_MODE) -> str:
    """Validate/normalize a strong_trend_mode string to {BEARISH, BULLISH, NONE}.

    Anything unrecognised or missing falls back to the default (NONE).
    """
    if value is None:
        return default
    mode = str(value).upper().strip()
    return mode if mode in VALID_STRONG_TREND_MODES else default
