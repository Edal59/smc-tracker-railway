"""
TradeX Tracker — Backend Version (Single Source of Truth)

All backend modules should import VERSION / FEATURES from here so the
reported version stays consistent across the health endpoint, logs,
payload defaults, and database records.
"""

# Single source of truth for the backend version.
VERSION = "v17.56.8"

# Feature flags advertised by the /health endpoint.
FEATURES = [
    "dual_mode",
    "session_analytics",
    "zombie_prevention",
    "invalid_classification",
    "amd_context_awareness",
    "hud_sync",
    "daily_counters",
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
