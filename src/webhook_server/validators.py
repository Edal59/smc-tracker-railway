"""
SMC Performance Tracker — Payload Validators
Validate incoming webhook alert payloads.
"""
import logging

logger = logging.getLogger(__name__)

# Valid event types (full and compact)
VALID_EVENTS_FULL = {
    'SIGNAL_ENTRY', 'SIGNAL_EXIT_TP', 'SIGNAL_EXIT_SL',
    'SIGNAL_EXIT_TIMEOUT', 'SIGNAL_GET_OUT', 'SIGNAL_UPDATE'
}
VALID_EVENTS_COMPACT = {'ENTRY', 'TP', 'SL', 'TO', 'GO', 'UPD'}


def validate_alert(data: dict) -> tuple:
    """
    Validate an incoming alert payload.
    Returns: (is_valid: bool, error_message: str)
    """
    if not data or not isinstance(data, dict):
        return False, "Empty or invalid payload"

    # Determine format
    event = data.get('event') or data.get('e')
    if not event:
        return False, "Missing event type ('event' or 'e' field)"

    if event not in VALID_EVENTS_FULL and event not in VALID_EVENTS_COMPACT:
        return False, f"Invalid event type: {event}"

    # Check signal_id
    signal_id = data.get('signal_id') or data.get('id')
    if not signal_id:
        return False, "Missing signal_id ('signal_id' or 'id' field)"

    # Format-specific validation
    is_compact = 'e' in data

    if event in ('SIGNAL_ENTRY', 'ENTRY'):
        return _validate_entry(data, is_compact)
    elif event in ('SIGNAL_EXIT_TP', 'SIGNAL_EXIT_SL', 'SIGNAL_EXIT_TIMEOUT', 'TP', 'SL', 'TO'):
        return _validate_exit(data, is_compact)
    elif event in ('SIGNAL_GET_OUT', 'GO'):
        return True, ""
    elif event in ('SIGNAL_UPDATE', 'UPD'):
        return True, ""

    return True, ""


def _validate_entry(data: dict, compact: bool) -> tuple:
    """Validate entry payload."""
    if compact:
        required = ['p', 'd', 'ep', 'sl', 'tp']
        for field in required:
            if field not in data:
                return False, f"Missing required field for entry: {field}"
        # Validate numeric fields
        try:
            float(data['ep'])
            float(data['sl'])
            float(data['tp'])
        except (ValueError, TypeError):
            return False, "Entry/SL/TP must be numeric"
    else:
        sig = data.get('signal', {})
        if not sig:
            return False, "Missing 'signal' object in entry payload"
        required = ['pair', 'direction', 'entry_price', 'stop_loss', 'take_profit']
        for field in required:
            if field not in sig:
                return False, f"Missing required signal field: {field}"
        try:
            float(sig['entry_price'])
            float(sig['stop_loss'])
            float(sig['take_profit'])
        except (ValueError, TypeError):
            return False, "Entry/SL/TP must be numeric"

    return True, ""


def _validate_exit(data: dict, compact: bool) -> tuple:
    """Validate exit payload."""
    if not compact:
        outcome = data.get('outcome', {})
        if not outcome:
            return False, "Missing 'outcome' object in exit payload"
    return True, ""
