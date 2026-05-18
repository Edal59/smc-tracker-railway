"""
SMC Performance Tracker — Analytics Aggregator
Time-window and dimension aggregations, daily metrics computation.
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from src.database import (
    get_signals_for_analysis, upsert_daily_metrics, get_connection
)
from src.analytics.metrics import (
    calculate_win_rate, calculate_expectancy, calculate_profit_factor,
    get_breakdown
)

logger = logging.getLogger(__name__)


def compute_daily_metrics(date_str: str = None):
    """
    Compute and store daily metrics for all pairs and aggregate.
    If date_str is None, computes for today.
    """
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    logger.info(f"Computing daily metrics for {date_str}")

    # Get all signals for this date
    sql = """SELECT * FROM signals
             WHERE DATE(signal_timestamp) = ?
             AND status IN ('WON', 'LOST', 'TIMEOUT', 'GET_OUT')
             ORDER BY signal_timestamp"""

    with get_connection() as conn:
        rows = conn.execute(sql, (date_str,)).fetchall()
    signals = [dict(r) for r in rows]

    if not signals:
        logger.info(f"No resolved signals for {date_str}")
        return

    # Compute per pair
    pair_groups = defaultdict(list)
    for s in signals:
        pair_groups[s['pair']].append(s)

    for pair, pair_signals in pair_groups.items():
        metrics = _compute_metrics_for_group(pair_signals)
        upsert_daily_metrics(date_str, pair, metrics)

    # Compute aggregate
    metrics = _compute_metrics_for_group(signals)
    upsert_daily_metrics(date_str, 'ALL', metrics)

    logger.info(f"Daily metrics computed for {date_str}: {len(signals)} signals, {len(pair_groups)} pairs")


def _compute_metrics_for_group(signals: list) -> dict:
    """Compute metric dict for a group of signals."""
    wins = [s for s in signals if s['status'] == 'WON']
    losses = [s for s in signals if s['status'] == 'LOST']
    timeouts = [s for s in signals if s['status'] == 'TIMEOUT']
    get_outs = [s for s in signals if s['status'] == 'GET_OUT']

    wl_total = len(wins) + len(losses)
    win_rate = (len(wins) / wl_total * 100) if wl_total > 0 else 0.0

    avg_rr_won = 0
    avg_pips_won = 0
    avg_pips_lost = 0
    if wins:
        rr_vals = [w.get('actual_rr', 0) or 0 for w in wins]
        pip_vals = [w.get('pips_gained', 0) or 0 for w in wins]
        avg_rr_won = sum(rr_vals) / len(rr_vals)
        avg_pips_won = sum(pip_vals) / len(pip_vals)
    if losses:
        pip_vals = [l.get('pips_gained', 0) or 0 for l in losses]
        avg_pips_lost = sum(pip_vals) / len(pip_vals)

    return {
        'total_signals': len(signals),
        'wins': len(wins),
        'losses': len(losses),
        'timeouts': len(timeouts),
        'get_outs': len(get_outs),
        'win_rate': round(win_rate, 1),
        'avg_rr_achieved': round(avg_rr_won, 2),
        'avg_pips_won': round(avg_pips_won, 1),
        'avg_pips_lost': round(avg_pips_lost, 1),
        'expectancy': round(calculate_expectancy(signals), 3),
        'profit_factor': round(calculate_profit_factor(signals), 2),
        'by_poi_score': get_breakdown(signals, 'poi_score'),
        'by_entry_model': get_breakdown(signals, 'entry_model'),
        'by_kill_zone': get_breakdown(signals, 'kill_zone'),
        'by_amd_phase': get_breakdown(signals, 'amd_phase'),
        'by_pattern': get_breakdown(signals, 'pattern'),
    }


def compute_metrics_backfill(days: int = 30):
    """Backfill daily metrics for the past N days."""
    today = datetime.now(timezone.utc).date()
    for i in range(days):
        d = today - timedelta(days=i)
        compute_daily_metrics(d.strftime('%Y-%m-%d'))
    logger.info(f"Backfilled {days} days of metrics")
