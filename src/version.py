"""
TradeX Tracker — Backend Version (Single Source of Truth)

All backend modules should import VERSION / FEATURES from here so the
reported version stays consistent across the health endpoint, logs,
payload defaults, and database records.
"""

# Single source of truth for the backend version.
VERSION = "v17.57"

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
