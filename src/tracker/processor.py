"""
SMC Performance Tracker — Signal Processor
Parses incoming alert data (compact & full format) and creates signal records.
"""
import logging
from datetime import datetime, timezone, timedelta

from src.database import insert_signal, insert_event, update_signal, get_signal, get_pip_size

logger = logging.getLogger(__name__)

# ============================================================
# Compact-to-Full Field Mapping
# ============================================================

EVENT_MAP = {
    'ENTRY': 'SIGNAL_ENTRY', 'TP': 'SIGNAL_EXIT_TP', 'SL': 'SIGNAL_EXIT_SL',
    'TO': 'SIGNAL_EXIT_TIMEOUT', 'GO': 'SIGNAL_GET_OUT', 'UPD': 'SIGNAL_UPDATE',
}

DIRECTION_MAP = {'L': 'LONG', 'S': 'SHORT'}
TYPE_MAP = {'STD': 'STANDARD', 'CT': 'COUNTER_TREND'}
STRUCTURE_MAP = {'BU': 'BULLISH', 'BE': 'BEARISH'}
ZONE_MAP = {'P': 'PREMIUM', 'D': 'DISCOUNT', 'E': 'EQUILIBRIUM'}
RISK_MAP = {'L': 'Low', 'M': 'Medium', 'H': 'High'}

KILL_ZONE_NAMES = {
    0: 'Outside KZ', 1: 'London KZ', 2: 'NY AM KZ', 3: 'NY PM KZ', 4: 'Asian KZ'
}

ENTRY_MODEL_NAMES = {
    0: None, 1: 'Disp. Trap', 2: 'Refined OB', 3: 'Breaker Blk', 4: 'Flip Zone', 5: 'Confluence'
}

AMD_PHASE_NAMES = {
    0: None, 1: 'ACCUMULATION', 2: 'MANIPULATION', 3: 'DISTRIBUTION', 4: 'TRANSITION'
}

FIB_ZONE_NAMES = {
    0: None, 618: 'Fib 61.8%', 786: 'Fib 78.6%', 886: 'Fib 88.6%', 900: 'Fib 90%+ EXTREME'
}

FIB_BONUS = {0: 0.0, 618: 0.5, 786: 1.0, 886: 1.5, 900: 2.0}

M15_MAP = {'SC': 'Sweep Confirmed', 'W': 'Waiting', 'OB': 'In OB Zone'}
M5_MAP = {'EC': 'Entry Confirmed', 'WM': 'Waiting for M15'}


def is_compact_format(data: dict) -> bool:
    """Detect if payload uses compact single-char keys."""
    return 'e' in data and 'id' in data


def expand_compact_entry(data: dict) -> dict:
    """Expand compact entry payload to full format."""
    direction = DIRECTION_MAP.get(data.get('d', ''), data.get('d', 'LONG'))
    signal_type = TYPE_MAP.get(data.get('st', 'STD'), 'STANDARD')

    # Parse timestamp
    ts = data.get('t')
    if isinstance(ts, (int, float)):
        signal_ts = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    else:
        signal_ts = str(ts)

    kz_id = int(data.get('kz', 0))
    em_id = int(data.get('em', 0))
    amd_id = int(data.get('amd', 0))
    fz_id = int(data.get('fz', 0))

    pair = data.get('p', '')
    entry_price = float(data.get('ep', 0))
    sl = float(data.get('sl', 0))
    tp = float(data.get('tp', 0))
    pip_size = get_pip_size(pair)

    sl_dist = abs(entry_price - sl) / pip_size
    tp_dist = abs(tp - entry_price) / pip_size

    # Determine session from kill zone
    session = _get_session(kz_id)

    # Parse UTC hour if we have a proper timestamp
    hour_utc = None
    hour_est = None
    dow = None
    if isinstance(ts, (int, float)):
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        hour_utc = dt.hour
        est_dt = dt - timedelta(hours=4)  # Approx EST
        hour_est = est_dt.hour
        dow = dt.weekday()

    return {
        'signal_id': data.get('id', ''),
        'pair': pair,
        'direction': direction,
        'signal_type': signal_type,
        'entry_price': entry_price,
        'stop_loss': sl,
        'take_profit': tp,
        'sl_distance_pips': round(sl_dist, 1),
        'tp_distance_pips': round(tp_dist, 1),
        'structure': STRUCTURE_MAP.get(data.get('str', ''), data.get('str')),
        'h4_bias': STRUCTURE_MAP.get(data.get('h4', ''), data.get('h4')),
        'zone': ZONE_MAP.get(data.get('z', ''), data.get('z')),
        'poi_status': 'IN POI' if data.get('poi', 0) else 'No POI',
        'liquidity': 'SWEPT' if data.get('liq', 0) else 'Not Swept',
        'poi_score': int(data.get('ps', 0)),
        'm15_status': M15_MAP.get(data.get('m15', ''), data.get('m15')),
        'm5_status': M5_MAP.get(data.get('m5', ''), data.get('m5')),
        'reversal_risk': RISK_MAP.get(data.get('rsk', ''), data.get('rsk')),
        'kill_zone': KILL_ZONE_NAMES.get(kz_id, 'Outside KZ'),
        'kill_zone_id': kz_id,
        'pattern_aligned': int(data.get('pat', 0)),
        'amd_phase': AMD_PHASE_NAMES.get(amd_id),
        'amd_phase_id': amd_id,
        'entry_model': ENTRY_MODEL_NAMES.get(em_id),
        'entry_model_id': em_id,
        'target_rr': float(data.get('rr', 3.0)),
        'fib_zone': FIB_ZONE_NAMES.get(fz_id),
        'fib_zone_id': fz_id,
        'fib_poi_bonus': FIB_BONUS.get(fz_id, 0.0),
        'signal_timestamp': signal_ts,
        'server_timestamp': datetime.now(timezone.utc).isoformat(),
        'signal_hour_utc': hour_utc,
        'signal_hour_est': hour_est,
        'signal_day_of_week': dow,
        'session': session,
        'status': 'ACTIVE',
        'indicator_version': f"v{data.get('v', '13.4')}",
    }


def expand_full_entry(data: dict) -> dict:
    """Process full-format SIGNAL_ENTRY payload."""
    sig = data.get('signal', {})
    hud = data.get('hud', {})
    fib = data.get('fib', {})

    pair = sig.get('pair', '')
    entry_price = float(sig.get('entry_price', 0))
    sl = float(sig.get('stop_loss', 0))
    tp = float(sig.get('take_profit', 0))
    pip_size = get_pip_size(pair)

    kz_id = int(hud.get('kill_zone_id', 0))
    em_id = int(hud.get('entry_model_id', 0))
    amd_id = int(hud.get('amd_phase_id', 0))
    fz_id = int(fib.get('zone_id', 0))

    ts_str = data.get('timestamp', '')
    hour_utc = None
    hour_est = None
    dow = None
    try:
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        hour_utc = dt.hour
        est_dt = dt - timedelta(hours=4)
        hour_est = est_dt.hour
        dow = dt.weekday()
    except Exception:
        pass

    return {
        'signal_id': data.get('signal_id', ''),
        'pair': pair,
        'direction': sig.get('direction', 'LONG'),
        'signal_type': sig.get('type', 'STANDARD'),
        'entry_price': entry_price,
        'stop_loss': sl,
        'take_profit': tp,
        'sl_distance_pips': round(float(sig.get('sl_distance_pips', abs(entry_price - sl) / pip_size)), 1),
        'tp_distance_pips': round(float(sig.get('tp_distance_pips', abs(tp - entry_price) / pip_size)), 1),
        'structure': hud.get('structure'),
        'h4_bias': hud.get('h4_bias'),
        'zone': hud.get('zone'),
        'poi_status': hud.get('poi_status'),
        'liquidity': hud.get('liquidity'),
        'poi_score': int(hud.get('poi_score', 0)),
        'm15_status': hud.get('m15_status'),
        'm5_status': hud.get('m5_status'),
        'reversal_risk': hud.get('reversal_risk'),
        'kill_zone': hud.get('kill_zone'),
        'kill_zone_id': kz_id,
        'pattern': hud.get('pattern'),
        'pattern_aligned': int(hud.get('pattern_aligned', 0)),
        'amd_phase': hud.get('amd_phase'),
        'amd_phase_id': amd_id,
        'entry_model': hud.get('entry_model'),
        'entry_model_id': em_id,
        'target_rr': float(sig.get('target_rr', 3.0)),
        'workflow_step': hud.get('workflow'),
        'fib_zone': fib.get('zone'),
        'fib_zone_id': fz_id,
        'fib_poi_bonus': float(fib.get('poi_bonus', FIB_BONUS.get(fz_id, 0.0))),
        'signal_timestamp': ts_str,
        'server_timestamp': datetime.now(timezone.utc).isoformat(),
        'signal_hour_utc': hour_utc,
        'signal_hour_est': hour_est,
        'signal_day_of_week': dow,
        'session': _get_session(kz_id),
        'status': 'ACTIVE',
        'indicator_version': data.get('version', 'v13.4'),
    }


def process_entry(data: dict) -> str:
    """Process a SIGNAL_ENTRY alert. Returns signal_id."""
    if is_compact_format(data):
        record = expand_compact_entry(data)
    else:
        record = expand_full_entry(data)

    # Validate prices
    ep = record['entry_price']
    sl = record['stop_loss']
    tp = record['take_profit']
    direction = record['direction']

    if direction == 'LONG':
        if not (sl < ep < tp):
            logger.warning(f"Price inconsistency for LONG: SL={sl} EP={ep} TP={tp}")
    elif direction == 'SHORT':
        if not (tp < ep < sl):
            logger.warning(f"Price inconsistency for SHORT: TP={tp} EP={ep} SL={sl}")

    # Insert signal
    signal_id = insert_signal(record)

    # Log ENTRY event
    insert_event(signal_id, 'ENTRY', event_data={
        'entry_price': ep, 'stop_loss': sl, 'take_profit': tp,
        'direction': direction, 'poi_score': record['poi_score']
    }, price_at_event=ep)

    logger.info(f"Processed ENTRY signal: {signal_id} ({direction} {record['pair']} @ {ep})")
    return signal_id


def process_exit(data: dict, event_type: str) -> str:
    """Process exit events (TP_HIT, SL_HIT, TIMEOUT, GET_OUT)."""
    signal_id = data.get('signal_id') or data.get('id', '')
    if is_compact_format(data):
        signal_id = data.get('id', signal_id)

    # Check signal exists
    existing = get_signal(signal_id)
    if not existing:
        logger.warning(f"Exit event for unknown signal: {signal_id}")
        return signal_id

    outcome = data.get('outcome', {})
    warning = data.get('warning', {})

    status_map = {
        'SIGNAL_EXIT_TP': 'WON',
        'SIGNAL_EXIT_SL': 'LOST',
        'SIGNAL_EXIT_TIMEOUT': 'TIMEOUT',
        'SIGNAL_GET_OUT': 'GET_OUT',
    }
    new_status = outcome.get('status', status_map.get(event_type, 'LOST'))

    updates = {
        'status': new_status,
        'outcome_timestamp': data.get('timestamp', datetime.now(timezone.utc).isoformat()),
    }

    if outcome:
        updates.update({
            'outcome_price': outcome.get('exit_price'),
            'pips_gained': outcome.get('pips_gained'),
            'actual_rr': outcome.get('actual_rr'),
            'bars_to_outcome': outcome.get('bars_to_outcome'),
            'time_to_outcome_min': outcome.get('time_to_outcome_min'),
            'mfe_pips': outcome.get('mfe_pips'),
            'mfe_rr': outcome.get('mfe_rr'),
            'mae_pips': outcome.get('mae_pips'),
            'mae_rr': outcome.get('mae_rr'),
        })
    elif warning:  # GET_OUT
        updates.update({
            'outcome_price': warning.get('price_at_warning'),
            'pips_gained': warning.get('unrealized_pips'),
            'actual_rr': warning.get('unrealized_rr'),
        })

    # Remove None values
    updates = {k: v for k, v in updates.items() if v is not None}
    update_signal(signal_id, updates)

    # Log event
    db_event_type = {
        'SIGNAL_EXIT_TP': 'TP_HIT',
        'SIGNAL_EXIT_SL': 'SL_HIT',
        'SIGNAL_EXIT_TIMEOUT': 'TIMEOUT',
        'SIGNAL_GET_OUT': 'GET_OUT',
    }.get(event_type, event_type)

    insert_event(signal_id, db_event_type,
                 event_data=outcome or warning,
                 price_at_event=outcome.get('exit_price') or warning.get('price_at_warning'))

    logger.info(f"Processed {db_event_type} for {signal_id}: status={new_status}")
    return signal_id


def process_update(data: dict) -> str:
    """Process periodic price update for an active signal."""
    signal_id = data.get('signal_id') or data.get('id', '')
    update = data.get('update', {})

    existing = get_signal(signal_id)
    if not existing:
        logger.warning(f"Update for unknown signal: {signal_id}")
        return signal_id

    if existing['status'] != 'ACTIVE':
        logger.debug(f"Ignoring update for resolved signal: {signal_id}")
        return signal_id

    updates = {}
    current_mfe = update.get('current_mfe_pips')
    current_mae = update.get('current_mae_pips')

    # Update MFE if new high
    if current_mfe and (existing.get('mfe_pips') is None or current_mfe > (existing.get('mfe_pips') or 0)):
        updates['mfe_pips'] = current_mfe

    # Update MAE if new low
    if current_mae and (existing.get('mae_pips') is None or current_mae > (existing.get('mae_pips') or 0)):
        updates['mae_pips'] = current_mae

    if updates:
        update_signal(signal_id, updates)

    # Log update event
    insert_event(signal_id, 'UPDATE',
                 event_data=update,
                 price_at_event=update.get('current_price'))

    return signal_id


def process_alert(data: dict) -> str:
    """Main entry point: route alert to appropriate handler."""
    # Determine event type
    event = data.get('event') or data.get('e', '')

    # Map compact events
    if event in EVENT_MAP:
        event = EVENT_MAP[event]

    logger.info(f"Processing alert: event={event}, signal_id={data.get('signal_id') or data.get('id')}")

    if event == 'SIGNAL_ENTRY':
        return process_entry(data)
    elif event in ('SIGNAL_EXIT_TP', 'SIGNAL_EXIT_SL', 'SIGNAL_EXIT_TIMEOUT', 'SIGNAL_GET_OUT'):
        return process_exit(data, event)
    elif event == 'SIGNAL_UPDATE':
        return process_update(data)
    else:
        logger.warning(f"Unknown event type: {event}")
        return ''


def _get_session(kz_id: int) -> str:
    """Determine trading session from kill zone ID."""
    mapping = {
        1: 'London', 2: 'New York', 3: 'New York', 4: 'Asian'
    }
    return mapping.get(kz_id, 'Other')
