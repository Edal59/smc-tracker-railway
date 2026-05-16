"""
SMC Performance Tracker — API Routes
All webhook and REST API endpoints.
"""
import logging
from datetime import datetime, timezone
from functools import wraps
from flask import Blueprint, request, jsonify

from src.config import config
from src.webhook_server.validators import validate_alert
from src.tracker.processor import process_alert
from src.oie_processor import is_oie_payload, normalize_oie_payload, oie_to_legacy_compact
from src.oie_database import (
    insert_opportunity, get_opportunity, get_opportunities,
    count_opportunities, get_oie_summary
)
from src.database import (
    get_signal, get_signals, get_active_signals, count_signals,
    get_events, log_system
)
from src.analytics.metrics import get_full_metrics, get_cumulative_pnl, get_rolling_win_rate
from src.analytics.reports import generate_json_report, generate_csv_signals

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


# ============================================================
# Auth Middleware
# ============================================================

def require_api_key(f):
    """Decorator to require API key authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not config.require_auth:
            return f(*args, **kwargs)

        # Check for API key in request body first (for TradingView webhooks)
        api_key = ''
        try:
            body = request.get_json(silent=True)
            if body and isinstance(body, dict):
                api_key = body.get('api_key', '')
        except Exception:
            pass

        # Fall back to X-API-Key header if not found in body
        if not api_key:
            api_key = request.headers.get('X-API-Key', '')

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
        'version': 'v17.17',
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
            "version": "v17.17",
            "accepts": "POST",
            "endpoint": "/api/v1/signal"
        }), 200

    # POST requests: check API key authentication
    if config.require_auth:
        api_key = ''
        try:
            body = request.get_json(silent=True)
            if body and isinstance(body, dict):
                # Support both 'api_key' (standard) and 'k' (ultra-simple format)
                api_key = body.get('api_key', '') or body.get('k', '')
        except Exception:
            pass
        if not api_key:
            api_key = request.headers.get('X-API-Key', '')
        expected = config.api_key
        if expected and api_key != expected:
            logger.warning(f"Unauthorized POST /signal from {request.remote_addr}")
            return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid JSON payload'}), 400

    # ── v17.17 OIE format detection ──
    # OIE payloads have type: "sniper_long"|"sniper_short"|"retrace_long"|"retrace_short"
    # and version starting with "v17.14"
    if is_oie_payload(data):
        try:
            # 1. Normalize into opportunity record
            opp_record = normalize_oie_payload(data)
            opp_id = insert_opportunity(opp_record)

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
                       f"RR {opp_record['rr_ratio']}:1",
                       {'opportunity_id': opp_id, 'legacy_signal': legacy_signal_id})

            logger.info(
                f"[OIE] ✅ {opp_record['setup_type']} on {opp_record['pair']} "
                f"| {opp_record['kill_zone']} session | {opp_record['h4_bias']} bias "
                f"| RR {opp_record['rr_ratio']}:1 | POI {opp_record['poi_score']}"
            )

            return jsonify({
                'status': 'ok',
                'pipeline': 'oie',
                'opportunity_id': opp_id,
                'setup_type': opp_record['setup_type'],
                'pair': opp_record['pair'],
                'kill_zone': opp_record['kill_zone'],
                'rr_ratio': opp_record['rr_ratio'],
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

@api_bp.route('/signals', methods=['GET'])
@require_api_key
def list_signals():
    """List signals with optional filters."""
    pair = request.args.get('pair')
    status = request.args.get('status')
    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))

    signals = get_signals(pair=pair, status=status, limit=limit, offset=offset)
    total = count_signals(pair=pair, status=status)

    return jsonify({
        'signals': signals,
        'total': total,
        'limit': limit,
        'offset': offset,
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
