"""
SMC Performance Tracker — Analytics Metrics Engine
Core metric calculations and performance analysis.
"""
import logging
import statistics
from collections import defaultdict
from datetime import datetime

from src.database import (
    get_performance_summary, get_signals_for_analysis,
    get_active_signals, count_signals, get_connection
)

logger = logging.getLogger(__name__)


def calculate_win_rate(signals: list) -> float:
    """Calculate win rate from a list of signal dicts."""
    wins = sum(1 for s in signals if s.get('status') == 'WON')
    losses = sum(1 for s in signals if s.get('status') == 'LOST')
    total = wins + losses
    return (wins / total * 100) if total > 0 else 0.0


def calculate_expectancy(signals: list) -> float:
    """Calculate expectancy: (win_rate * avg_win) - (loss_rate * avg_loss)."""
    wins = [s for s in signals if s.get('status') == 'WON' and s.get('actual_rr') is not None]
    losses = [s for s in signals if s.get('status') == 'LOST' and s.get('actual_rr') is not None]

    if not wins and not losses:
        return 0.0

    total = len(wins) + len(losses)
    wr = len(wins) / total if total > 0 else 0
    avg_win = statistics.mean([s['actual_rr'] for s in wins]) if wins else 0
    avg_loss = abs(statistics.mean([s['actual_rr'] for s in losses])) if losses else 0

    return (wr * avg_win) - ((1 - wr) * avg_loss)


def calculate_profit_factor(signals: list) -> float:
    """Calculate profit factor: gross_profit / gross_loss."""
    gross_profit = sum(s.get('pips_gained', 0) for s in signals
                       if s.get('status') == 'WON' and s.get('pips_gained'))
    gross_loss = abs(sum(s.get('pips_gained', 0) for s in signals
                         if s.get('status') == 'LOST' and s.get('pips_gained')))
    if gross_loss == 0:
        return float('inf') if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def calculate_sharpe_ratio(signals: list) -> float:
    """Calculate Sharpe-like ratio: avg_rr / stddev(rr)."""
    rr_values = [s['actual_rr'] for s in signals if s.get('actual_rr') is not None]
    if len(rr_values) < 2:
        return 0.0
    avg = statistics.mean(rr_values)
    std = statistics.stdev(rr_values)
    return avg / std if std > 0 else 0.0


def calculate_max_drawdown(signals: list) -> float:
    """Calculate max drawdown in cumulative R:R."""
    if not signals:
        return 0.0
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for s in sorted(signals, key=lambda x: x.get('signal_timestamp', '')):
        rr = s.get('actual_rr', 0) or 0
        cumulative += rr
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd
    return max_dd


def calculate_streaks(signals: list) -> dict:
    """Calculate current and max win/loss streaks."""
    sorted_sigs = sorted(signals, key=lambda x: x.get('signal_timestamp', ''))
    current_streak = 0
    current_type = None
    max_win_streak = 0
    max_loss_streak = 0
    win_streak = 0
    loss_streak = 0

    for s in sorted_sigs:
        status = s.get('status')
        if status == 'WON':
            win_streak += 1
            loss_streak = 0
            max_win_streak = max(max_win_streak, win_streak)
        elif status == 'LOST':
            loss_streak += 1
            win_streak = 0
            max_loss_streak = max(max_loss_streak, loss_streak)
        else:
            continue

    # Current streak
    for s in reversed(sorted_sigs):
        status = s.get('status')
        if status == 'WON':
            if current_type is None:
                current_type = 'WIN'
            if current_type == 'WIN':
                current_streak += 1
            else:
                break
        elif status == 'LOST':
            if current_type is None:
                current_type = 'LOSS'
            if current_type == 'LOSS':
                current_streak += 1
            else:
                break

    return {
        'current_streak': current_streak,
        'current_streak_type': current_type or 'NONE',
        'max_win_streak': max_win_streak,
        'max_loss_streak': max_loss_streak,
    }


def get_breakdown(signals: list, dimension: str) -> dict:
    """
    Break down win rate by a dimension (column name).
    Returns: {value: {'wins': n, 'losses': n, 'total': n, 'win_rate': pct}}
    """
    groups = defaultdict(lambda: {'wins': 0, 'losses': 0, 'total': 0, 'timeouts': 0})

    for s in signals:
        key = s.get(dimension)
        if key is None:
            key = 'Unknown'
        groups[key]['total'] += 1
        if s['status'] == 'WON':
            groups[key]['wins'] += 1
        elif s['status'] == 'LOST':
            groups[key]['losses'] += 1
        elif s['status'] == 'TIMEOUT':
            groups[key]['timeouts'] += 1

    result = {}
    for key, v in groups.items():
        wl = v['wins'] + v['losses']
        v['win_rate'] = (v['wins'] / wl * 100) if wl > 0 else 0.0
        result[str(key)] = v
    return result


def get_full_metrics(pair=None, days=None) -> dict:
    """
    Compute comprehensive performance metrics.
    Returns a dict with all metrics and breakdowns.
    """
    signals = get_signals_for_analysis(pair=pair, days=days)
    summary = get_performance_summary(pair=pair, days=days)
    active = get_active_signals()

    if not signals:
        return {
            'summary': summary,
            'active_signals': len(active),
            'breakdowns': {},
            'streaks': {'current_streak': 0, 'current_streak_type': 'NONE',
                        'max_win_streak': 0, 'max_loss_streak': 0},
            'advanced': {},
        }

    # Advanced metrics
    sharpe = calculate_sharpe_ratio(signals)
    max_dd = calculate_max_drawdown(signals)
    streaks = calculate_streaks(signals)
    expectancy = calculate_expectancy(signals)
    profit_factor = calculate_profit_factor(signals)

    # Recovery factor
    total_rr = sum(s.get('actual_rr', 0) or 0 for s in signals)
    recovery = total_rr / max_dd if max_dd > 0 else 0.0

    # Breakdowns
    breakdowns = {
        'by_pair': get_breakdown(signals, 'pair'),
        'by_poi_score': get_breakdown(signals, 'poi_score'),
        'by_entry_model': get_breakdown(signals, 'entry_model'),
        'by_kill_zone': get_breakdown(signals, 'kill_zone'),
        'by_amd_phase': get_breakdown(signals, 'amd_phase'),
        'by_pattern': get_breakdown(signals, 'pattern'),
        'by_direction': get_breakdown(signals, 'direction'),
        'by_zone': get_breakdown(signals, 'zone'),
        'by_session': get_breakdown(signals, 'session'),
        'by_signal_type': get_breakdown(signals, 'signal_type'),
    }

    # Time analysis
    breakdowns['by_hour_utc'] = get_breakdown(signals, 'signal_hour_utc')
    breakdowns['by_day_of_week'] = get_breakdown(signals, 'signal_day_of_week')

    # Avg MFE/MAE
    mfe_values = [s['mfe_pips'] for s in signals if s.get('mfe_pips') is not None]
    mae_values = [s['mae_pips'] for s in signals if s.get('mae_pips') is not None]

    return {
        'summary': summary,
        'active_signals': len(active),
        'breakdowns': breakdowns,
        'streaks': streaks,
        'advanced': {
            'expectancy': round(expectancy, 3),
            'profit_factor': round(profit_factor, 2),
            'sharpe_ratio': round(sharpe, 3),
            'max_drawdown_rr': round(max_dd, 2),
            'recovery_factor': round(recovery, 2),
            'total_rr': round(total_rr, 2),
            'avg_mfe_pips': round(statistics.mean(mfe_values), 1) if mfe_values else 0,
            'avg_mae_pips': round(statistics.mean(mae_values), 1) if mae_values else 0,
        }
    }


def get_cumulative_pnl(pair=None, days=None) -> list:
    """Get cumulative P&L curve data (for charts)."""
    signals = get_signals_for_analysis(pair=pair, days=days)
    cumulative = 0.0
    data = []
    for s in signals:
        rr = s.get('actual_rr', 0) or 0
        cumulative += rr
        data.append({
            'signal_id': s['signal_id'],
            'timestamp': s.get('signal_timestamp', ''),
            'pair': s['pair'],
            'direction': s['direction'],
            'status': s['status'],
            'actual_rr': rr,
            'cumulative_rr': round(cumulative, 2),
            'pips_gained': s.get('pips_gained', 0),
        })
    return data


def get_rolling_win_rate(signals: list = None, window: int = 20, pair=None, days=None) -> list:
    """Calculate rolling win rate over N signals."""
    if signals is None:
        signals = get_signals_for_analysis(pair=pair, days=days)

    data = []
    for i, s in enumerate(signals):
        start = max(0, i - window + 1)
        batch = signals[start:i + 1]
        wr = calculate_win_rate(batch)
        data.append({
            'index': i,
            'signal_id': s['signal_id'],
            'timestamp': s.get('signal_timestamp', ''),
            'rolling_win_rate': round(wr, 1),
            'window_size': len(batch),
        })
    return data
