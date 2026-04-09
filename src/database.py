"""
SMC Performance Tracker — Database Module (Cloud)
SQLite database initialization and CRUD operations.
"""
import os
import json
import sqlite3
import logging
from datetime import datetime, timezone
from contextlib import contextmanager

from src.config import config, PROJECT_ROOT

logger = logging.getLogger(__name__)

SCHEMA_PATH = os.path.join(PROJECT_ROOT, 'schemas', 'schema.sql')
MIGRATION_PATH = os.path.join(PROJECT_ROOT, 'schemas', 'migrate_trade_tracking.sql')


def get_db_path():
    return config.db_path


def _run_migrations(conn):
    """Run migrations to add new columns to existing databases."""
    # Check if trade_status column exists
    cursor = conn.execute("PRAGMA table_info(signals)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'trade_status' not in columns:
        logger.info("Running trade tracking migration...")
        migration_columns = [
            ("trade_status", "TEXT DEFAULT 'pending'"),
            ("actual_entry_price", "REAL"),
            ("actual_exit_price", "REAL"),
            ("actual_entry_time", "TEXT"),
            ("actual_exit_time", "TEXT"),
            ("actual_pnl", "REAL"),
            ("trade_notes", "TEXT"),
        ]
        for col_name, col_def in migration_columns:
            if col_name not in columns:
                try:
                    conn.execute(f"ALTER TABLE signals ADD COLUMN {col_name} {col_def}")
                    logger.info(f"Added column: {col_name}")
                except Exception as e:
                    logger.warning(f"Column {col_name} may already exist: {e}")
        
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_trade_status ON signals(trade_status)")
        conn.commit()
        logger.info("Trade tracking migration complete")


def init_db(db_path=None):
    """Initialize database with schema."""
    path = db_path or get_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)

    conn = sqlite3.connect(path)
    try:
        with open(SCHEMA_PATH, 'r') as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)
        conn.commit()
        # Run migrations for existing databases
        _run_migrations(conn)
        logger.info(f"Database initialized at {path}")
    finally:
        conn.close()
    return path


@contextmanager
def get_connection(db_path=None):
    """Context manager for database connections."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def dict_from_row(row):
    if row is None:
        return None
    return dict(row)


# ============================================================
# Signal CRUD
# ============================================================

def insert_signal(signal_data: dict, db_path=None) -> str:
    known_columns = {
        'signal_id', 'pair', 'direction', 'signal_type',
        'entry_price', 'stop_loss', 'take_profit', 'sl_distance_pips', 'tp_distance_pips',
        'structure', 'h4_bias', 'zone', 'poi_status', 'liquidity',
        'poi_score', 'm15_status', 'm5_status', 'reversal_risk',
        'kill_zone', 'kill_zone_id', 'pattern', 'pattern_aligned',
        'amd_phase', 'amd_phase_id', 'entry_model', 'entry_model_id',
        'target_rr', 'workflow_step',
        'fib_zone', 'fib_zone_id', 'fib_poi_bonus',
        'signal_timestamp', 'server_timestamp',
        'signal_hour_utc', 'signal_hour_est', 'signal_day_of_week', 'session',
        'status', 'indicator_version', 'timeframe', 'notes',
        'mfe_price', 'mfe_pips', 'mfe_rr', 'mae_price', 'mae_pips', 'mae_rr',
        'outcome_timestamp', 'outcome_price', 'bars_to_outcome', 'time_to_outcome_min',
        'actual_rr', 'pips_gained',
        'trade_status', 'actual_entry_price', 'actual_exit_price',
        'actual_entry_time', 'actual_exit_time', 'actual_pnl', 'trade_notes',
    }

    cols = []
    vals = []
    for k, v in signal_data.items():
        if k in known_columns and v is not None:
            cols.append(k)
            vals.append(v)

    placeholders = ', '.join(['?'] * len(cols))
    col_str = ', '.join(cols)
    sql = f"INSERT OR IGNORE INTO signals ({col_str}) VALUES ({placeholders})"

    with get_connection(db_path) as conn:
        cursor = conn.execute(sql, vals)
        if cursor.rowcount == 0:
            logger.warning(f"Signal {signal_data.get('signal_id')} already exists (duplicate)")
        else:
            logger.info(f"Inserted signal: {signal_data.get('signal_id')}")

    return signal_data.get('signal_id', '')


def update_signal(signal_id: str, updates: dict, db_path=None):
    if not updates:
        return
    set_parts = []
    vals = []
    for k, v in updates.items():
        set_parts.append(f"{k} = ?")
        vals.append(v)
    vals.append(signal_id)
    sql = f"UPDATE signals SET {', '.join(set_parts)} WHERE signal_id = ?"
    with get_connection(db_path) as conn:
        conn.execute(sql, vals)
    logger.debug(f"Updated signal {signal_id}: {list(updates.keys())}")


def get_signal(signal_id: str, db_path=None) -> dict:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM signals WHERE signal_id = ?", (signal_id,)).fetchone()
    return dict_from_row(row)


def get_active_signals(db_path=None) -> list:
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM signals WHERE status = 'ACTIVE' ORDER BY signal_timestamp DESC").fetchall()
    return [dict_from_row(r) for r in rows]


def get_signals(pair=None, status=None, limit=100, offset=0, db_path=None) -> list:
    conditions = []
    params = []
    if pair:
        conditions.append("pair = ?")
        params.append(pair)
    if status:
        conditions.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM signals {where} ORDER BY signal_timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with get_connection(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict_from_row(r) for r in rows]


def count_signals(pair=None, status=None, db_path=None) -> int:
    conditions = []
    params = []
    if pair:
        conditions.append("pair = ?")
        params.append(pair)
    if status:
        conditions.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT COUNT(*) FROM signals {where}"
    with get_connection(db_path) as conn:
        return conn.execute(sql, params).fetchone()[0]


def insert_event(signal_id: str, event_type: str, event_data: dict = None,
                 price_at_event: float = None, db_path=None):
    sql = """INSERT INTO signal_events (signal_id, event_type, event_data, price_at_event)
             VALUES (?, ?, ?, ?)"""
    data_json = json.dumps(event_data) if event_data else None
    with get_connection(db_path) as conn:
        conn.execute(sql, (signal_id, event_type, data_json, price_at_event))
    logger.debug(f"Event {event_type} for {signal_id}")


def get_events(signal_id: str, db_path=None) -> list:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM signal_events WHERE signal_id = ? ORDER BY event_timestamp",
            (signal_id,)
        ).fetchall()
    return [dict_from_row(r) for r in rows]


def insert_price_tick(signal_id: str, pair: str, mid_price: float,
                      bid_price=None, ask_price=None,
                      is_mfe=False, is_mae=False, db_path=None):
    sql = """INSERT INTO price_ticks
             (signal_id, pair, mid_price, bid_price, ask_price, is_mfe_update, is_mae_update)
             VALUES (?, ?, ?, ?, ?, ?, ?)"""
    with get_connection(db_path) as conn:
        conn.execute(sql, (signal_id, pair, mid_price, bid_price, ask_price,
                           1 if is_mfe else 0, 1 if is_mae else 0))


def get_price_ticks(signal_id: str, db_path=None) -> list:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM price_ticks WHERE signal_id = ? ORDER BY timestamp",
            (signal_id,)
        ).fetchall()
    return [dict_from_row(r) for r in rows]


def cleanup_price_ticks(signal_id: str, db_path=None):
    with get_connection(db_path) as conn:
        conn.execute(
            "DELETE FROM price_ticks WHERE signal_id = ? AND is_mfe_update = 0 AND is_mae_update = 0",
            (signal_id,)
        )


def get_pip_size(pair: str, db_path=None) -> float:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT pip_size FROM pair_config WHERE pair = ?", (pair,)).fetchone()
    if row:
        return row['pip_size']
    return 0.01 if 'JPY' in pair or pair in ('XAUUSD', 'BTCUSD') else 0.0001


def get_all_pairs(db_path=None) -> list:
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM pair_config ORDER BY pair").fetchall()
    return [dict_from_row(r) for r in rows]


def upsert_daily_metrics(date_str: str, pair: str, metrics: dict, db_path=None):
    sql = """INSERT INTO daily_metrics (date, pair, total_signals, wins, losses, timeouts, get_outs,
             win_rate, avg_rr_achieved, avg_pips_won, avg_pips_lost, expectancy, profit_factor,
             by_poi_score, by_entry_model, by_kill_zone, by_amd_phase, by_pattern)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
             ON CONFLICT(date, pair) DO UPDATE SET
             total_signals=excluded.total_signals, wins=excluded.wins,
             losses=excluded.losses, timeouts=excluded.timeouts, get_outs=excluded.get_outs,
             win_rate=excluded.win_rate, avg_rr_achieved=excluded.avg_rr_achieved,
             avg_pips_won=excluded.avg_pips_won, avg_pips_lost=excluded.avg_pips_lost,
             expectancy=excluded.expectancy, profit_factor=excluded.profit_factor,
             by_poi_score=excluded.by_poi_score, by_entry_model=excluded.by_entry_model,
             by_kill_zone=excluded.by_kill_zone, by_amd_phase=excluded.by_amd_phase,
             by_pattern=excluded.by_pattern, computed_at=datetime('now')"""
    with get_connection(db_path) as conn:
        conn.execute(sql, (
            date_str, pair,
            metrics.get('total_signals', 0), metrics.get('wins', 0),
            metrics.get('losses', 0), metrics.get('timeouts', 0), metrics.get('get_outs', 0),
            metrics.get('win_rate', 0.0), metrics.get('avg_rr_achieved', 0.0),
            metrics.get('avg_pips_won', 0.0), metrics.get('avg_pips_lost', 0.0),
            metrics.get('expectancy', 0.0), metrics.get('profit_factor', 0.0),
            json.dumps(metrics.get('by_poi_score', {})),
            json.dumps(metrics.get('by_entry_model', {})),
            json.dumps(metrics.get('by_kill_zone', {})),
            json.dumps(metrics.get('by_amd_phase', {})),
            json.dumps(metrics.get('by_pattern', {})),
        ))


def get_daily_metrics(date_str=None, pair=None, db_path=None) -> list:
    conditions = []
    params = []
    if date_str:
        conditions.append("date = ?")
        params.append(date_str)
    if pair:
        conditions.append("pair = ?")
        params.append(pair)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM daily_metrics {where} ORDER BY date DESC"
    with get_connection(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict_from_row(r) for r in rows]


def log_system(level: str, component: str, message: str, details: dict = None, db_path=None):
    sql = """INSERT INTO system_log (level, component, message, details)
             VALUES (?, ?, ?, ?)"""
    try:
        with get_connection(db_path) as conn:
            conn.execute(sql, (level, component, message,
                               json.dumps(details) if details else None))
    except Exception as e:
        logger.error(f"Failed to write system log: {e}")


def get_performance_summary(pair=None, days=None, db_path=None) -> dict:
    conditions = ["status IN ('WON', 'LOST', 'TIMEOUT', 'GET_OUT')"]
    params = []
    if pair and pair != 'ALL':
        conditions.append("pair = ?")
        params.append(pair)
    if days:
        conditions.append(f"signal_timestamp >= datetime('now', '-{int(days)} days')")
    where = f"WHERE {' AND '.join(conditions)}"
    sql = f"""
    SELECT
        COUNT(*) as total_signals,
        SUM(CASE WHEN status = 'WON' THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN status = 'LOST' THEN 1 ELSE 0 END) as losses,
        SUM(CASE WHEN status = 'TIMEOUT' THEN 1 ELSE 0 END) as timeouts,
        SUM(CASE WHEN status = 'GET_OUT' THEN 1 ELSE 0 END) as get_outs,
        AVG(CASE WHEN status = 'WON' THEN actual_rr ELSE NULL END) as avg_rr_won,
        AVG(CASE WHEN status = 'LOST' THEN actual_rr ELSE NULL END) as avg_rr_lost,
        AVG(CASE WHEN status = 'WON' THEN pips_gained ELSE NULL END) as avg_pips_won,
        AVG(CASE WHEN status = 'LOST' THEN pips_gained ELSE NULL END) as avg_pips_lost,
        AVG(actual_rr) as avg_rr_overall,
        SUM(COALESCE(pips_gained, 0)) as total_pips,
        AVG(mfe_pips) as avg_mfe_pips,
        AVG(mae_pips) as avg_mae_pips,
        (SELECT COUNT(*) FROM signals WHERE status = 'ACTIVE') as active_signals
    FROM signals {where}
    """
    with get_connection(db_path) as conn:
        row = conn.execute(sql, params).fetchone()
    if not row or row['total_signals'] == 0:
        return {'total_signals': 0, 'wins': 0, 'losses': 0, 'win_rate': 0.0}
    result = dict_from_row(row)
    w = result['wins'] or 0
    l = result['losses'] or 0
    result['win_rate'] = (w / (w + l) * 100) if (w + l) > 0 else 0.0
    wr = w / (w + l) if (w + l) > 0 else 0
    avg_win = result['avg_rr_won'] or 0
    avg_loss = abs(result['avg_rr_lost'] or 0)
    result['expectancy'] = (wr * avg_win) - ((1 - wr) * avg_loss)
    gross_profit = (result['avg_pips_won'] or 0) * w
    gross_loss = abs(result['avg_pips_lost'] or 0) * l
    result['profit_factor'] = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0
    return result


def get_signals_with_trade_status(pair=None, status=None, trade_status=None,
                                   limit=100, offset=0, db_path=None) -> list:
    """Get signals with optional trade_status filter."""
    conditions = []
    params = []
    if pair:
        conditions.append("pair = ?")
        params.append(pair)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if trade_status:
        conditions.append("trade_status = ?")
        params.append(trade_status)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM signals {where} ORDER BY signal_timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with get_connection(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict_from_row(r) for r in rows]


def count_signals_with_trade_status(pair=None, status=None, trade_status=None, db_path=None) -> int:
    """Count signals with optional trade_status filter."""
    conditions = []
    params = []
    if pair:
        conditions.append("pair = ?")
        params.append(pair)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if trade_status:
        conditions.append("trade_status = ?")
        params.append(trade_status)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT COUNT(*) FROM signals {where}"
    with get_connection(db_path) as conn:
        return conn.execute(sql, params).fetchone()[0]


def mark_trade(signal_id: str, trade_status: str, trade_data: dict = None, db_path=None) -> dict:
    """Mark a signal with trade status and optional trade details."""
    if trade_status not in ('taken', 'missed', 'ignored', 'pending'):
        raise ValueError(f"Invalid trade_status: {trade_status}")
    
    updates = {'trade_status': trade_status}
    if trade_data:
        for key in ('actual_entry_price', 'actual_exit_price', 'actual_entry_time',
                     'actual_exit_time', 'actual_pnl', 'trade_notes'):
            if key in trade_data and trade_data[key] is not None:
                updates[key] = trade_data[key]
    
    update_signal(signal_id, updates, db_path)
    return get_signal(signal_id, db_path)


def get_trade_analytics(pair=None, db_path=None) -> dict:
    """Get trade tracking analytics comparing actual vs theoretical performance."""
    conditions = []
    params = []
    if pair and pair != 'ALL':
        conditions.append("pair = ?")
        params.append(pair)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    sql = f"""
    SELECT
        COUNT(*) as total_signals,
        SUM(CASE WHEN trade_status = 'taken' THEN 1 ELSE 0 END) as taken_count,
        SUM(CASE WHEN trade_status = 'missed' THEN 1 ELSE 0 END) as missed_count,
        SUM(CASE WHEN trade_status = 'ignored' THEN 1 ELSE 0 END) as ignored_count,
        SUM(CASE WHEN trade_status = 'pending' OR trade_status IS NULL THEN 1 ELSE 0 END) as pending_count,
        
        -- Actual performance (taken trades only)
        SUM(CASE WHEN trade_status = 'taken' AND actual_pnl > 0 THEN 1 ELSE 0 END) as actual_wins,
        SUM(CASE WHEN trade_status = 'taken' AND actual_pnl <= 0 THEN 1 ELSE 0 END) as actual_losses,
        SUM(CASE WHEN trade_status = 'taken' THEN COALESCE(actual_pnl, 0) ELSE 0 END) as actual_total_pnl,
        AVG(CASE WHEN trade_status = 'taken' AND actual_pnl IS NOT NULL THEN actual_pnl ELSE NULL END) as actual_avg_pnl,
        
        -- Theoretical performance (all resolved signals)
        SUM(CASE WHEN status = 'WON' THEN 1 ELSE 0 END) as theoretical_wins,
        SUM(CASE WHEN status = 'LOST' THEN 1 ELSE 0 END) as theoretical_losses,
        SUM(CASE WHEN status IN ('WON', 'LOST', 'TIMEOUT', 'GET_OUT') THEN COALESCE(pips_gained, 0) ELSE 0 END) as theoretical_total_pnl,
        AVG(CASE WHEN status IN ('WON', 'LOST', 'TIMEOUT', 'GET_OUT') THEN pips_gained ELSE NULL END) as theoretical_avg_pnl
    FROM signals {where}
    """
    
    with get_connection(db_path) as conn:
        row = conn.execute(sql, params).fetchone()
    
    if not row:
        return _empty_analytics()
    
    result = dict_from_row(row)
    
    # Calculate rates
    taken = result['taken_count'] or 0
    actual_wins = result['actual_wins'] or 0
    actual_losses = result['actual_losses'] or 0
    theo_wins = result['theoretical_wins'] or 0
    theo_losses = result['theoretical_losses'] or 0
    total = result['total_signals'] or 0
    
    result['taken_pct'] = round((taken / total * 100), 1) if total > 0 else 0
    result['missed_pct'] = round(((result['missed_count'] or 0) / total * 100), 1) if total > 0 else 0
    result['ignored_pct'] = round(((result['ignored_count'] or 0) / total * 100), 1) if total > 0 else 0
    result['pending_pct'] = round(((result['pending_count'] or 0) / total * 100), 1) if total > 0 else 0
    
    result['actual_win_rate'] = round((actual_wins / (actual_wins + actual_losses) * 100), 1) if (actual_wins + actual_losses) > 0 else 0
    result['theoretical_win_rate'] = round((theo_wins / (theo_wins + theo_losses) * 100), 1) if (theo_wins + theo_losses) > 0 else 0
    
    # Round numeric fields
    for key in ('actual_total_pnl', 'actual_avg_pnl', 'theoretical_total_pnl', 'theoretical_avg_pnl'):
        if result[key] is not None:
            result[key] = round(result[key], 2)
        else:
            result[key] = 0
    
    return result


def _empty_analytics():
    return {
        'total_signals': 0, 'taken_count': 0, 'missed_count': 0,
        'ignored_count': 0, 'pending_count': 0,
        'taken_pct': 0, 'missed_pct': 0, 'ignored_pct': 0, 'pending_pct': 0,
        'actual_wins': 0, 'actual_losses': 0,
        'actual_win_rate': 0, 'actual_total_pnl': 0, 'actual_avg_pnl': 0,
        'theoretical_wins': 0, 'theoretical_losses': 0,
        'theoretical_win_rate': 0, 'theoretical_total_pnl': 0, 'theoretical_avg_pnl': 0,
    }


def get_signals_for_analysis(pair=None, days=None, db_path=None) -> list:
    conditions = ["status IN ('WON', 'LOST', 'TIMEOUT', 'GET_OUT')"]
    params = []
    if pair and pair != 'ALL':
        conditions.append("pair = ?")
        params.append(pair)
    if days:
        conditions.append(f"signal_timestamp >= datetime('now', '-{int(days)} days')")
    where = f"WHERE {' AND '.join(conditions)}"
    sql = f"SELECT * FROM signals {where} ORDER BY signal_timestamp"
    with get_connection(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict_from_row(r) for r in rows]
