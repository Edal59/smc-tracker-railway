"""
SMC Performance Tracker — Report Generation
Export analytics data as JSON or CSV.
"""
import csv
import io
import json
import logging

from src.database import get_signals_for_analysis
from src.analytics.metrics import get_full_metrics, get_cumulative_pnl

logger = logging.getLogger(__name__)


def generate_json_report(pair=None, days=None) -> dict:
    """Generate a comprehensive JSON report."""
    metrics = get_full_metrics(pair=pair, days=days)
    pnl_curve = get_cumulative_pnl(pair=pair, days=days)
    return {
        'generated_at': __import__('datetime').datetime.now().isoformat(),
        'filters': {'pair': pair or 'ALL', 'days': days or 'all-time'},
        'metrics': metrics,
        'pnl_curve': pnl_curve,
    }


def generate_csv_signals(pair=None, days=None) -> str:
    """Generate CSV export of all signals."""
    signals = get_signals_for_analysis(pair=pair, days=days)
    if not signals:
        return ''

    output = io.StringIO()
    fields = [
        'signal_id', 'pair', 'direction', 'signal_type', 'entry_price',
        'stop_loss', 'take_profit', 'sl_distance_pips', 'tp_distance_pips',
        'poi_score', 'kill_zone', 'entry_model', 'amd_phase', 'pattern',
        'zone', 'structure', 'h4_bias', 'reversal_risk', 'fib_zone',
        'signal_timestamp', 'status', 'outcome_timestamp',
        'outcome_price', 'actual_rr', 'pips_gained',
        'mfe_pips', 'mfe_rr', 'mae_pips', 'mae_rr',
        'bars_to_outcome', 'time_to_outcome_min',
        'session', 'kill_zone_id', 'entry_model_id', 'target_rr',
    ]

    writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    for s in signals:
        writer.writerow(s)

    return output.getvalue()
