"""
SMC Performance Tracker — Web Dashboard Routes
Browser-based dashboard for viewing signals and performance.
"""
import os
import logging
from flask import Blueprint, render_template, request, jsonify

from src.config import config
from src.database import (
    get_signals, get_active_signals, count_signals,
    get_performance_summary, get_signal, get_events,
    get_signals_with_trade_status, count_signals_with_trade_status,
    mark_trade, get_trade_analytics, get_pip_size
)
from src.analytics.metrics import get_full_metrics, get_cumulative_pnl

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
def index():
    """Main dashboard page."""
    return render_template('dashboard.html', config=config)


@dashboard_bp.route('/trades')
def trades():
    """Trade log page."""
    return render_template('trades.html', config=config)


@dashboard_bp.route('/settings')
def settings():
    """Settings/info page."""
    webhook_url = request.host_url.rstrip('/') + '/api/v1/signal'
    return render_template('settings.html', config=config, webhook_url=webhook_url)


# ============================================================
# Dashboard API endpoints (for AJAX calls from templates)
# ============================================================

@dashboard_bp.route('/dash/api/summary')
def dash_summary():
    """Get dashboard summary data."""
    pair = request.args.get('pair')
    days = request.args.get('days', type=int)
    summary = get_performance_summary(pair=pair, days=days)
    active = get_active_signals()
    total = count_signals()
    return jsonify({
        'summary': summary,
        'active_count': len(active),
        'total_signals': total,
    })


@dashboard_bp.route('/dash/api/signals')
def dash_signals():
    """Get signals for trade log."""
    pair = request.args.get('pair')
    status = request.args.get('status')
    trade_status = request.args.get('trade_status')
    limit = min(int(request.args.get('limit', 50)), 200)
    offset = int(request.args.get('offset', 0))
    signals = get_signals_with_trade_status(
        pair=pair, status=status, trade_status=trade_status,
        limit=limit, offset=offset
    )
    total = count_signals_with_trade_status(
        pair=pair, status=status, trade_status=trade_status
    )
    return jsonify({'signals': signals, 'total': total, 'limit': limit, 'offset': offset})


@dashboard_bp.route('/dash/api/metrics')
def dash_metrics():
    """Get full metrics."""
    pair = request.args.get('pair')
    days = request.args.get('days', type=int)
    metrics = get_full_metrics(pair=pair, days=days)
    return jsonify(metrics)


@dashboard_bp.route('/dash/api/pnl')
def dash_pnl():
    """Get P&L curve data."""
    pair = request.args.get('pair')
    days = request.args.get('days', type=int)
    data = get_cumulative_pnl(pair=pair, days=days)
    return jsonify({'data': data})


@dashboard_bp.route('/dash/api/signal/<signal_id>')
def dash_signal_detail(signal_id):
    """Get signal detail."""
    signal = get_signal(signal_id)
    if not signal:
        return jsonify({'error': 'Not found'}), 404
    events = get_events(signal_id)
    signal['events'] = events
    return jsonify(signal)


@dashboard_bp.route('/dash/api/signal/<signal_id>/mark-trade', methods=['POST'])
def dash_mark_trade(signal_id):
    """Mark a signal as taken/missed/ignored with optional trade details."""
    signal = get_signal(signal_id)
    if not signal:
        return jsonify({'error': 'Signal not found'}), 404
    
    data = request.get_json(silent=True)
    if not data or 'trade_status' not in data:
        return jsonify({'error': 'trade_status is required'}), 400
    
    trade_status = data['trade_status']
    if trade_status not in ('taken', 'missed', 'ignored', 'pending'):
        return jsonify({'error': 'Invalid trade_status. Must be: taken, missed, ignored, or pending'}), 400
    
    trade_data = {}
    
    if trade_status == 'taken':
        # Extract trade details
        trade_data['actual_entry_price'] = data.get('actual_entry_price')
        trade_data['actual_exit_price'] = data.get('actual_exit_price')
        trade_data['actual_entry_time'] = data.get('actual_entry_time')
        trade_data['actual_exit_time'] = data.get('actual_exit_time')
        trade_data['trade_notes'] = data.get('trade_notes')
        
        # Calculate actual P&L in pips if entry and exit prices provided
        entry_p = trade_data.get('actual_entry_price') or signal.get('entry_price')
        exit_p = trade_data.get('actual_exit_price')
        if entry_p and exit_p:
            pip_size = get_pip_size(signal['pair'])
            direction = signal.get('direction', 'LONG')
            if direction == 'LONG':
                pnl_pips = (float(exit_p) - float(entry_p)) / pip_size
            else:
                pnl_pips = (float(entry_p) - float(exit_p)) / pip_size
            trade_data['actual_pnl'] = round(pnl_pips, 1)
        
        # Allow explicit pnl override
        if 'actual_pnl' in data and data['actual_pnl'] is not None:
            trade_data['actual_pnl'] = data['actual_pnl']
    elif trade_status in ('missed', 'ignored'):
        trade_data['trade_notes'] = data.get('trade_notes')
        # Clear trade-specific fields when marking as missed/ignored
        trade_data['actual_entry_price'] = None
        trade_data['actual_exit_price'] = None
        trade_data['actual_entry_time'] = None
        trade_data['actual_exit_time'] = None
        trade_data['actual_pnl'] = None
    elif trade_status == 'pending':
        # Reset everything
        trade_data['actual_entry_price'] = None
        trade_data['actual_exit_price'] = None
        trade_data['actual_entry_time'] = None
        trade_data['actual_exit_time'] = None
        trade_data['actual_pnl'] = None
        trade_data['trade_notes'] = None
    
    # Remove None values for non-reset operations
    trade_data = {k: v for k, v in trade_data.items() if v is not None or trade_status in ('pending', 'missed', 'ignored')}
    
    try:
        updated_signal = mark_trade(signal_id, trade_status, trade_data)
        logger.info(f"Marked signal {signal_id} as {trade_status}")
        return jsonify({'status': 'ok', 'signal': updated_signal})
    except Exception as e:
        logger.error(f"Error marking trade: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/dash/api/analytics')
def dash_analytics():
    """Get trade tracking analytics."""
    pair = request.args.get('pair')
    analytics = get_trade_analytics(pair=pair)
    return jsonify(analytics)
