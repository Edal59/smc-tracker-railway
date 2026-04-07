"""
SMC Performance Tracker — API Routes
All webhook and REST API endpoints.
"""
import logging
from functools import wraps
from flask import Blueprint, request, jsonify

from src.config import config
from src.webhook_server.validators import validate_alert
from src.tracker.processor import process_alert
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
        'version': '1.0.0',
    })


# ============================================================
# Signal Webhook (Main Endpoint)
# ============================================================

@api_bp.route('/signal', methods=['POST'])
@require_api_key
def receive_signal():
    """Receive a signal alert from TradingView."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid JSON payload'}), 400

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
