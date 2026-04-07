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
    get_performance_summary, get_signal, get_events
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
    limit = min(int(request.args.get('limit', 50)), 200)
    offset = int(request.args.get('offset', 0))
    signals = get_signals(pair=pair, status=status, limit=limit, offset=offset)
    total = count_signals(pair=pair, status=status)
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
