"""
SMC Performance Tracker — API Routes
All webhook and REST API endpoints.
v17.59: EMERGENCY FIX — Trend Override Logic (htf_override_active / ltf_override_active / htf_trend_final / ltf_trend_final) + Range Debug (range_anchor_time / range_force_expanded) + AMD Velocity (amd_velocity) + Strong Trend Mode (strong_trend_mode) — in-memory only (NO DB migration), exposed via /latest and POST /signal echo
v17.58: Sequence State Machine (sequence_state / sequence_step / missing_step / sequence_complete + 5 state flags) + BOS-Anchored Ranges (bos_range_high / bos_range_low / bos_equilibrium / bos_trend) + liquidity/shift detection flags — PERSISTED, exposed via /signals and /sequence-analytics
v17.57: PDH/PDL Institutional Liquidity Levels (pdh / pdl / near_pdh / near_pdl / pdh_swept / pdl_swept) — in-memory only, exposed via /latest
v17.56.9: Guardian HTF-Gating (guardian_label / guardian_risk) + HTF-counter Standby awareness
v17.56.8: HUD Sync (amd_state) + AMD Context Awareness + Daily Counters (sniper_today / execution_today)
v17.56.7: Dual Mode Alert System + Session Analytics + Zombie Trade Prevention
"""
import logging
from datetime import datetime, timezone
from functools import wraps
from flask import Blueprint, request, jsonify

from src.version import VERSION, get_features

from src.config import config
from src.webhook_server.validators import validate_alert
from src.tracker.processor import process_alert
from src.oie_processor import is_oie_payload, normalize_oie_payload, oie_to_legacy_compact, normalize_v17_54_payload
from src.oie_database import (
    insert_opportunity, get_opportunity, get_opportunities,
    count_opportunities, get_oie_summary
)
from src.database import (
    get_signal, get_signals, get_active_signals, count_signals,
    get_events, log_system, get_performance_summary_filtered,
    get_signals_for_analysis
)
from src.analytics.metrics import get_full_metrics, get_cumulative_pnl, get_rolling_win_rate
from src.analytics.reports import generate_json_report, generate_csv_signals

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


# ============================================================
# v17.57: In-memory PDH/PDL liquidity cache
# ------------------------------------------------------------
# The PDH/PDL institutional liquidity levels are ephemeral daily
# reference values and are deliberately NOT persisted to the database.
# We keep only the most recent signal's curated snapshot in memory so it
# can be surfaced via GET /latest. This resets on every process restart.
# ============================================================

_LATEST_SIGNAL = {}


def _update_latest_signal(opp_record: dict) -> None:
    """Cache a curated snapshot of the most recent OIE signal in memory.

    Includes the v17.57 PDH/PDL liquidity fields. The raw payload is
    intentionally excluded to keep the snapshot small and JSON-safe.
    """
    global _LATEST_SIGNAL
    try:
        _LATEST_SIGNAL = {
            'pair': opp_record.get('pair'),
            'direction': opp_record.get('direction'),
            'setup_type': opp_record.get('setup_type'),
            'mode': opp_record.get('mode'),
            'session': opp_record.get('session_tag'),
            'poi_score': opp_record.get('poi_score'),
            'poi_max': opp_record.get('poi_max', 6),
            # v17.57 PDH/PDL institutional liquidity levels (in-memory only)
            'pdh': opp_record.get('pdh', 0.0),
            'pdl': opp_record.get('pdl', 0.0),
            'near_pdh': bool(opp_record.get('near_pdh', False)),
            'near_pdl': bool(opp_record.get('near_pdl', False)),
            'pdh_swept': bool(opp_record.get('pdh_swept', False)),
            'pdl_swept': bool(opp_record.get('pdl_swept', False)),
            # v17.58 sequence state machine + BOS-anchored ranges (persisted)
            'sequence_state': opp_record.get('sequence_state', 0),
            'sequence_step': opp_record.get('sequence_step'),
            'missing_step': opp_record.get('missing_step'),
            'sequence_complete': bool(opp_record.get('sequence_complete', False)),
            'bos_range_high': opp_record.get('bos_range_high', 0.0),
            'bos_range_low': opp_record.get('bos_range_low', 0.0),
            'bos_equilibrium': opp_record.get('bos_equilibrium', 0.0),
            'bos_trend': opp_record.get('bos_trend', 0),
            'state1_location': bool(opp_record.get('state1_location', False)),
            'state2_liquidity': bool(opp_record.get('state2_liquidity', False)),
            'state3_displacement': bool(opp_record.get('state3_displacement', False)),
            'state4_mitigation': bool(opp_record.get('state4_mitigation', False)),
            'state5_execution': bool(opp_record.get('state5_execution', False)),
            'liquidity_swept': bool(opp_record.get('liquidity_swept', False)),
            'ltf_shift_detected': bool(opp_record.get('ltf_shift_detected', False)),
            'displacement_detected': bool(opp_record.get('displacement_detected', False)),
            'mitigation_zone': bool(opp_record.get('mitigation_zone', False)),
            # v17.59 trend override + AMD velocity (EMERGENCY FIX, in-memory only)
            'htf_override_active': bool(opp_record.get('htf_override_active', False)),
            'ltf_override_active': bool(opp_record.get('ltf_override_active', False)),
            'htf_trend_final': opp_record.get('htf_trend_final', 0),
            'ltf_trend_final': opp_record.get('ltf_trend_final', 0),
            'range_anchor_time': opp_record.get('range_anchor_time', ''),
            'range_force_expanded': bool(opp_record.get('range_force_expanded', False)),
            'amd_velocity': opp_record.get('amd_velocity', 0.0),
            'strong_trend_mode': opp_record.get('strong_trend_mode', 'NONE'),
            'received_at': datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:  # never let caching break the webhook path
        logger.warning(f"[v17.57] Failed to update latest-signal cache: {e}")


# ============================================================
# Auth Middleware
# ============================================================

def require_api_key(f):
    """Decorator to require API key authentication.
    v17.56.6: Extended to check query params and Authorization Bearer header.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not config.require_auth:
            return f(*args, **kwargs)

        # Check for API key in multiple sources
        api_key = ''
        # Source 1: JSON body
        try:
            body = request.get_json(silent=True)
            if body and isinstance(body, dict):
                api_key = body.get('api_key', '')
        except Exception:
            pass
        # Source 2: Query parameter
        if not api_key:
            api_key = request.args.get('api_key', '')
        # Source 3: X-API-Key header
        if not api_key:
            api_key = request.headers.get('X-API-Key', '')
        # Source 4: Authorization Bearer header
        if not api_key:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                api_key = auth_header[7:].strip()

        expected = config.api_key

        if not expected or api_key == expected:
            return f(*args, **kwargs)

        logger.warning(f"Unauthorized request from {request.remote_addr}")
        return jsonify({'error': 'Unauthorized'}), 401

    return decorated


# ============================================================
# Health Check
# ============================================================

@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'service': 'SMC Performance Tracker',
        'version': VERSION,
        'features': get_features(),
    })


# ============================================================
# Ultra-Simple Format Converter
# ============================================================

def _expand_simple_format(data: dict) -> dict:
    """
    Convert an ultra-simple TradingView webhook payload into compact format.

    Input (ultra-simple):
        {"k": "API_KEY", "p": "GBPJPY", "d": "LONG", "pr": "214.100"}

    Output (compact format for existing processor):
        {"api_key": "...", "e": "ENTRY", "id": "GBPJPY_20260412_183000",
         "p": "GBPJPY", "d": "L", "ep": 214.1, "sl": 0, "tp": 0, "t": "..."}
    """
    pair = str(data.get('p', '')).upper().strip()
    direction = str(data.get('d', 'LONG')).upper().strip()
    price_str = str(data.get('pr', '0')).strip()

    try:
        entry_price = float(price_str)
    except (ValueError, TypeError):
        entry_price = 0.0

    now = datetime.now(timezone.utc)
    ts_str = now.strftime('%Y%m%d_%H%M%S')
    signal_id = f"{pair}_{ts_str}"

    # Map direction to compact key
    is_long = direction in ('LONG', 'BUY', 'L')
    d_compact = 'L' if is_long else 'S'

    # Estimate SL/TP from entry price so distance calcs aren't nonsensical
    # Use a small pip-based offset (30 pips SL, 90 pips TP for 1:3 R:R)
    pip_mult = 0.01 if 'JPY' in pair else 0.0001
    sl_dist = 30 * pip_mult
    tp_dist = 90 * pip_mult
    if is_long:
        sl = round(entry_price - sl_dist, 5)
        tp = round(entry_price + tp_dist, 5)
    else:
        sl = round(entry_price + sl_dist, 5)
        tp = round(entry_price - tp_dist, 5)

    return {
        'api_key': data.get('k', ''),
        'e': 'ENTRY',
        'id': signal_id,
        'p': pair,
        'd': d_compact,
        'ep': entry_price,
        'sl': sl,
        'tp': tp,
        't': now.isoformat(),
        'ps': 0,
        'rr': 3.0,
        '_simple_format': True,  # Internal flag
    }


# ============================================================
# Signal Webhook (Main Endpoint)
# ============================================================

@api_bp.route('/signal', methods=['GET', 'POST'])
def receive_signal():
    """Receive a signal alert from TradingView.
    
    GET:  Returns 200 OK for webhook validation/health checks (no auth required).
    POST: Processes actual signal data (auth required).
    """
    # GET requests: return 200 OK for TradingView webhook validation
    if request.method == 'GET':
        logger.info("GET /signal - webhook validation/health check")
        return jsonify({
            "status": "ok",
            "message": "SMC Performance Tracker Webhook Endpoint",
            "version": VERSION,
            "accepts": "POST",
            "endpoint": "/api/v1/signal"
        }), 200

    # POST requests: check API key authentication
    # v17.56.6: Extended auth sources — TradingView webhooks can't send custom headers,
    # so we support: (1) JSON body api_key/k, (2) query param ?api_key=, (3) X-API-Key header,
    # (4) Authorization: Bearer header. This fixes 401 errors for TradingView webhooks.
    if config.require_auth:
        api_key = ''
        # Source 1: JSON body (standard and ultra-simple formats)
        try:
            body = request.get_json(silent=True)
            if body and isinstance(body, dict):
                api_key = body.get('api_key', '') or body.get('k', '')
        except Exception:
            pass
        # Source 2: Query parameter (recommended for TradingView webhooks)
        if not api_key:
            api_key = request.args.get('api_key', '')
        # Source 3: X-API-Key header
        if not api_key:
            api_key = request.headers.get('X-API-Key', '')
        # Source 4: Authorization Bearer header
        if not api_key:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                api_key = auth_header[7:].strip()
        expected = config.api_key
        if expected and api_key != expected:
            logger.warning(f"Unauthorized POST /signal from {request.remote_addr} "
                           f"(checked body/query/header, none matched)")
            return jsonify({'error': 'Unauthorized', 'hint': 'Send api_key in JSON body, '
                           '?api_key= query param, X-API-Key header, or Authorization: Bearer header'}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid JSON payload'}), 400

    # ── v17.54.x / v17.25 / v17.56.7 OIE format detection ──
    if is_oie_payload(data):
        try:
            # 1. Normalize into opportunity record
            opp_record = normalize_oie_payload(data)

            # ── v17.56.7: Zombie Trade Prevention ──
            # If valid == False, log as informational event only, don't create trade
            if not opp_record.get('valid', True):
                logger.info(
                    f"[OIE] ⛔ INVALID signal ignored (zombie prevention): "
                    f"{opp_record['setup_type']} {opp_record['pair']} "
                    f"| mode={opp_record.get('mode', 'DATA')} "
                    f"| session={opp_record.get('session_tag', 'NY')}"
                )
                log_system('INFO', 'webhook',
                           f"Zombie prevention: ignored invalid {opp_record['setup_type']} "
                           f"{opp_record['pair']}",
                           {'reason': 'valid=false', 'payload': str(data)[:500]})
                return jsonify({
                    'status': 'ignored',
                    'reason': 'invalid signal (valid=false)',
                    'pair': opp_record['pair'],
                    'setup_type': opp_record['setup_type'],
                }), 200

            opp_id = insert_opportunity(opp_record)

            # v17.57: cache the curated snapshot (incl. PDH/PDL liquidity) in
            # memory so GET /latest can surface the ephemeral, non-persisted levels.
            _update_latest_signal(opp_record)

            # 2. Also feed into legacy signals pipeline for backward compat
            legacy_data = oie_to_legacy_compact(data)
            try:
                legacy_signal_id = process_alert(legacy_data)
                logger.info(f"OIE: Legacy bridge signal created: {legacy_signal_id}")
            except Exception as le:
                logger.warning(f"OIE: Legacy bridge failed (non-critical): {le}")
                legacy_signal_id = None

            log_system('INFO', 'webhook',
                       f"OIE opportunity #{opp_id}: {opp_record['setup_type']} "
                       f"{opp_record['pair']} | {opp_record['kill_zone']} | "
                       f"RR {opp_record['rr_ratio']}:1 | "
                       f"mode={opp_record.get('mode', 'DATA')} | "
                       f"session={opp_record.get('session_tag', 'NY')}",
                       {'opportunity_id': opp_id, 'legacy_signal': legacy_signal_id})

            # v17.56.6+: Include OTE bonus in log
            ote_tag = " (OTE)" if opp_record.get('has_ote') else ""
            mode_tag = f" [{opp_record.get('mode', 'DATA')}]"
            session_tag = f" {opp_record.get('session_tag', 'NY')}"
            logger.info(
                f"[OIE] ✅{mode_tag}{session_tag} {opp_record['setup_type']} on {opp_record['pair']} "
                f"| {opp_record.get('direction', '?')} "
                f"| {opp_record['kill_zone']} session | {opp_record['h4_bias']} bias "
                f"| RR {opp_record['rr_ratio']}:1 | POI {opp_record['poi_score']}"
                f"/{opp_record.get('poi_max', 6)}{ote_tag}"
            )

            return jsonify({
                'status': 'ok',
                'pipeline': 'oie',
                'opportunity_id': opp_id,
                'setup_type': opp_record['setup_type'],
                'pair': opp_record['pair'],
                'direction': opp_record.get('direction', ''),
                'kill_zone': opp_record['kill_zone'],
                'rr_ratio': opp_record['rr_ratio'],
                'poi_score': opp_record['poi_score'],
                'poi_max': opp_record.get('poi_max', 6),
                'has_ote': opp_record.get('has_ote', False),
                'mode': opp_record.get('mode', 'DATA'),
                'session': opp_record.get('session_tag', 'NY'),
                # v17.57: PDH/PDL institutional liquidity levels (in-memory only)
                'pdh': opp_record.get('pdh', 0.0),
                'pdl': opp_record.get('pdl', 0.0),
                'near_pdh': bool(opp_record.get('near_pdh', False)),
                'near_pdl': bool(opp_record.get('near_pdl', False)),
                'pdh_swept': bool(opp_record.get('pdh_swept', False)),
                'pdl_swept': bool(opp_record.get('pdl_swept', False)),
                # v17.58: Sequence state machine + BOS-anchored ranges (persisted)
                'sequence_state': opp_record.get('sequence_state', 0),
                'sequence_step': opp_record.get('sequence_step'),
                'missing_step': opp_record.get('missing_step'),
                'sequence_complete': bool(opp_record.get('sequence_complete', False)),
                'bos_range_high': opp_record.get('bos_range_high', 0.0),
                'bos_range_low': opp_record.get('bos_range_low', 0.0),
                'bos_equilibrium': opp_record.get('bos_equilibrium', 0.0),
                'bos_trend': opp_record.get('bos_trend', 0),
                # v17.59: Trend override + AMD velocity (EMERGENCY FIX, in-memory only)
                'htf_override_active': bool(opp_record.get('htf_override_active', False)),
                'ltf_override_active': bool(opp_record.get('ltf_override_active', False)),
                'htf_trend_final': opp_record.get('htf_trend_final', 0),
                'ltf_trend_final': opp_record.get('ltf_trend_final', 0),
                'range_anchor_time': opp_record.get('range_anchor_time', ''),
                'range_force_expanded': bool(opp_record.get('range_force_expanded', False)),
                'amd_velocity': opp_record.get('amd_velocity', 0.0),
                'strong_trend_mode': opp_record.get('strong_trend_mode', 'NONE'),
                'legacy_signal_id': legacy_signal_id,
            }), 200

        except Exception as e:
            logger.error(f"OIE processing error: {e}", exc_info=True)
            log_system('ERROR', 'webhook', f"OIE error: {str(e)}", {'data': str(data)[:500]})
            return jsonify({'error': 'OIE processing failed', 'message': str(e)}), 500

    # ── Ultra-simple format detection ──
    # TradingView alert message: {"k":"API_KEY","p":"GBPJPY","d":"LONG","pr":"214.100"}
    # Convert to compact format the existing processor understands.
    if 'k' in data and 'p' in data and 'd' in data and 'event' not in data and 'e' not in data:
        data = _expand_simple_format(data)
        logger.info(f"Converted ultra-simple webhook to compact format: {data.get('id')}")

    # Validate
    is_valid, error_msg = validate_alert(data)
    if not is_valid:
        logger.warning(f"Invalid alert: {error_msg}")
        log_system('WARNING', 'webhook', f"Invalid alert: {error_msg}", {'data': str(data)[:500]})
        return jsonify({'error': 'Validation failed', 'message': error_msg}), 400

    # Process
    try:
        signal_id = process_alert(data)
        event = data.get('event') or data.get('e', 'unknown')
        log_system('INFO', 'webhook', f"Processed {event} for {signal_id}")
        return jsonify({
            'status': 'ok',
            'signal_id': signal_id,
            'event': event,
        }), 200
    except Exception as e:
        logger.error(f"Error processing alert: {e}", exc_info=True)
        log_system('ERROR', 'webhook', f"Processing error: {str(e)}")
        return jsonify({'error': 'Processing failed', 'message': str(e)}), 500


# ============================================================
# Signal Queries
# ============================================================

@api_bp.route('/latest', methods=['GET'])
@require_api_key
def latest_signal():
    """Return the most recent signal's in-memory snapshot.

    v17.57: This is the canonical way to read the ephemeral PDH/PDL
    institutional liquidity levels (pdh / pdl / near_pdh / near_pdl /
    pdh_swept / pdl_swept). Those fields are NOT persisted to the database,
    so the /signals endpoint (which reads from the DB) will not contain them.
    Returns ``{'signal': null}`` until the first OIE signal is received, and
    resets on process restart.
    """
    return jsonify({
        'signal': _LATEST_SIGNAL or None,
        'version': VERSION,
    })


@api_bp.route('/signals', methods=['GET'])
@require_api_key
def list_signals():
    """List signals with optional filters.
    v17.56.7: Supports ?mode=EXECUTION&session=NY filters.
    v17.56.9: Supports ?guardian_risk=2 filter (0=low | 1=medium | 2=high).
    v17.58: Supports ?sequence_state=5 and ?sequence_complete=1 filters.
    """
    pair = request.args.get('pair')
    status = request.args.get('status')
    mode = request.args.get('mode')
    session_tag = request.args.get('session')
    amd_state = request.args.get('amd_state')
    guardian_risk = request.args.get('guardian_risk', type=int)
    sequence_state = request.args.get('sequence_state', type=int)
    sequence_complete = request.args.get('sequence_complete', type=int)
    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))

    signals = get_signals(pair=pair, status=status, mode=mode,
                          session_tag=session_tag, amd_state=amd_state,
                          guardian_risk=guardian_risk,
                          sequence_state=sequence_state,
                          sequence_complete=sequence_complete,
                          limit=limit, offset=offset)
    total = count_signals(pair=pair, status=status, mode=mode,
                          session_tag=session_tag, amd_state=amd_state,
                          guardian_risk=guardian_risk,
                          sequence_state=sequence_state,
                          sequence_complete=sequence_complete)

    return jsonify({
        'signals': signals,
        'total': total,
        'limit': limit,
        'offset': offset,
        'filters': {
            'pair': pair, 'status': status,
            'mode': mode, 'session': session_tag,
            'amd_state': amd_state,
            'guardian_risk': guardian_risk,
            'sequence_state': sequence_state,
            'sequence_complete': sequence_complete,
        }
    })


@api_bp.route('/sequence-analytics', methods=['GET'])
@require_api_key
def sequence_analytics():
    """v17.58: Sequence State Machine analytics.

    Returns the distribution of persisted signals across the 5-state
    institutional sequence (0=idle .. 5=execution), the completion rate, and
    a breakdown of the individual state-completion / detection flags. Supports
    an optional ?pair= filter.
    """
    pair = request.args.get('pair')

    state_labels = {
        0: 'idle',
        1: 'location',
        2: 'liquidity',
        3: 'displacement',
        4: 'mitigation',
        5: 'execution',
    }

    total = count_signals(pair=pair)
    completed = count_signals(pair=pair, sequence_complete=1)

    state_distribution = {}
    for state, label in state_labels.items():
        state_distribution[str(state)] = {
            'label': label,
            'count': count_signals(pair=pair, sequence_state=state),
        }

    completion_rate = round((completed / total) * 100, 2) if total else 0.0

    return jsonify({
        'version': VERSION,
        'pair': pair,
        'total_signals': total,
        'sequence_complete': completed,
        'completion_rate_pct': completion_rate,
        'state_distribution': state_distribution,
    })


@api_bp.route('/signals/active', methods=['GET'])
@require_api_key
def active_signals():
    """Get all active signals."""
    signals = get_active_signals()
    return jsonify({'signals': signals, 'count': len(signals)})


@api_bp.route('/signals/<signal_id>', methods=['GET'])
@require_api_key
def get_signal_detail(signal_id):
    """Get signal detail with events."""
    signal = get_signal(signal_id)
    if not signal:
        return jsonify({'error': 'Signal not found'}), 404

    events = get_events(signal_id)
    signal['events'] = events
    return jsonify(signal)


# ============================================================
# Metrics & Analytics
# ============================================================

@api_bp.route('/metrics', methods=['GET'])
@require_api_key
def get_metrics():
    """Get aggregated performance metrics."""
    pair = request.args.get('pair')
    days = request.args.get('days', type=int)

    metrics = get_full_metrics(pair=pair, days=days)
    return jsonify(metrics)


@api_bp.route('/metrics/<pair>', methods=['GET'])
@require_api_key
def get_pair_metrics(pair):
    """Get pair-specific metrics."""
    days = request.args.get('days', type=int)
    metrics = get_full_metrics(pair=pair, days=days)
    return jsonify(metrics)


@api_bp.route('/pnl', methods=['GET'])
@require_api_key
def get_pnl_curve():
    """Get cumulative P&L curve data."""
    pair = request.args.get('pair')
    days = request.args.get('days', type=int)
    data = get_cumulative_pnl(pair=pair, days=days)
    return jsonify({'data': data})


@api_bp.route('/report', methods=['GET'])
@require_api_key
def get_report():
    """Get comprehensive JSON report."""
    pair = request.args.get('pair')
    days = request.args.get('days', type=int)
    report = generate_json_report(pair=pair, days=days)
    return jsonify(report)


@api_bp.route('/export/csv', methods=['GET'])
@require_api_key
def export_csv():
    """Export signals as CSV."""
    pair = request.args.get('pair')
    days = request.args.get('days', type=int)
    csv_data = generate_csv_signals(pair=pair, days=days)

    from flask import Response
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=signals_export.csv'}
    )


# ============================================================
# Backfill (Manual Signal Entry)
# ============================================================

@api_bp.route('/backfill', methods=['POST'])
@require_api_key
def backfill_signal():
    """Manually add a signal (for backfilling historical data)."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    try:
        signal_id = process_alert(data)
        return jsonify({'status': 'ok', 'signal_id': signal_id}), 201
    except Exception as e:
        logger.error(f"Backfill error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ============================================================
# OIE — Opportunity Intelligence Engine Endpoints
# ============================================================

@api_bp.route('/opportunities', methods=['GET'])
@require_api_key
def list_opportunities():
    """List opportunities with optional filters."""
    pair = request.args.get('pair')
    status = request.args.get('status')
    setup_type = request.args.get('setup_type')
    kill_zone = request.args.get('kill_zone')
    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))

    opps = get_opportunities(pair=pair, status=status, setup_type=setup_type,
                             kill_zone=kill_zone, limit=limit, offset=offset)
    total = count_opportunities(pair=pair, status=status)
    return jsonify({
        'opportunities': opps,
        'total': total,
        'limit': limit,
        'offset': offset,
    })


@api_bp.route('/opportunities/<int:opp_id>', methods=['GET'])
@require_api_key
def get_opportunity_detail(opp_id):
    """Get opportunity detail with outcomes."""
    from src.oie_database import get_outcomes
    opp = get_opportunity(opp_id)
    if not opp:
        return jsonify({'error': 'Opportunity not found'}), 404
    opp['outcomes'] = get_outcomes(opp_id)
    return jsonify(opp)


@api_bp.route('/opportunities/summary', methods=['GET'])
@require_api_key
def opportunities_summary():
    """Get OIE performance summary."""
    pair = request.args.get('pair')
    days = request.args.get('days', type=int)
    summary = get_oie_summary(pair=pair, days=days)
    return jsonify(summary)


# ============================================================
# v17.56.7: Session-Based Performance Analytics
# ============================================================

@api_bp.route('/session-performance', methods=['GET'])
@require_api_key
def session_performance():
    """
    v17.56.7: Get London vs NY session performance comparison.
    Only includes EXECUTION mode trades for accurate performance tracking.
    
    Query params:
        pair: Filter by pair (optional)
        days: Filter by recent N days (optional)
    """
    pair = request.args.get('pair')
    days = request.args.get('days', type=int)

    london_stats = get_performance_summary_filtered(
        pair=pair, days=days, mode='EXECUTION', session_tag='LONDON'
    )
    ny_stats = get_performance_summary_filtered(
        pair=pair, days=days, mode='EXECUTION', session_tag='NY'
    )
    overall_exec = get_performance_summary_filtered(
        pair=pair, days=days, mode='EXECUTION'
    )

    return jsonify({
        'london': london_stats,
        'ny': ny_stats,
        'overall_execution': overall_exec,
        'filters': {'pair': pair, 'days': days, 'mode': 'EXECUTION'},
    })


@api_bp.route('/stats', methods=['GET'])
@require_api_key
def execution_stats():
    """
    v17.56.7: Get performance stats filtered by mode.
    Defaults to EXECUTION-only trades for real performance tracking.
    
    Query params:
        mode: "EXECUTION" (default) or "DATA" or "ALL"
        session: "LONDON" or "NY" (optional)
        pair: Filter by pair (optional)
        days: Filter by recent N days (optional)
    """
    mode = request.args.get('mode', 'EXECUTION').upper()
    session_tag = request.args.get('session')
    pair = request.args.get('pair')
    days = request.args.get('days', type=int)

    # "ALL" means no mode filter
    mode_filter = None if mode == 'ALL' else mode

    stats = get_performance_summary_filtered(
        pair=pair, days=days, mode=mode_filter, session_tag=session_tag
    )

    return jsonify({
        'stats': stats,
        'filters': {
            'mode': mode,
            'session': session_tag,
            'pair': pair,
            'days': days,
        }
    })
