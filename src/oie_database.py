"""
TradeX Tracker — OIE Database Operations
CRUD operations for the Opportunity Intelligence Engine tables.
"""
import json
import logging
from datetime import datetime, timezone

from src.database import get_connection, dict_from_row

logger = logging.getLogger(__name__)


# ============================================================================
# Opportunity CRUD
# ============================================================================

def insert_opportunity(opp: dict, db_path=None) -> int:
    """
    Insert a normalized opportunity record.
    Returns the new opportunity ID.
    """
    sql = """INSERT INTO opportunities
        (pair, setup_type, setup_id, h4_bias, pd_zone, kill_zone, guardian,
         entry_price, sl_price, tp_price, risk_pips, reward_pips, rr_ratio,
         quality_score, poi_score, confluence, dt_stage,
         status, identified_at, raw_payload, version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

    values = (
        opp.get("pair"),
        opp.get("setup_type"),
        opp.get("setup_id", "dynamic"),
        opp.get("h4_bias", "Unknown"),
        opp.get("pd_zone", "Unknown"),
        opp.get("kill_zone", "Unknown"),
        opp.get("guardian", "Unknown"),
        opp.get("entry_price"),
        opp.get("sl_price"),
        opp.get("tp_price"),
        opp.get("risk_pips"),
        opp.get("reward_pips"),
        opp.get("rr_ratio"),
        opp.get("quality_score"),
        opp.get("poi_score"),
        opp.get("confluence"),
        opp.get("dt_stage"),
        opp.get("status", "identified"),
        opp.get("identified_at", datetime.now(timezone.utc).isoformat()),
        opp.get("raw_payload"),
        opp.get("version", "v17.20"),
    )

    with get_connection(db_path) as conn:
        cursor = conn.execute(sql, values)
        opp_id = cursor.lastrowid
        logger.info(f"Inserted opportunity #{opp_id}: {opp.get('setup_type')} {opp.get('pair')}")
        return opp_id


def get_opportunity(opp_id: int, db_path=None) -> dict:
    """Get a single opportunity by ID."""
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opp_id,)).fetchone()
    return dict_from_row(row)


def get_opportunities(pair=None, status=None, setup_type=None, kill_zone=None,
                      limit=100, offset=0, db_path=None) -> list:
    """Get opportunities with optional filters."""
    conditions = []
    params = []
    if pair:
        conditions.append("pair = ?")
        params.append(pair)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if setup_type:
        conditions.append("setup_type = ?")
        params.append(setup_type)
    if kill_zone:
        conditions.append("kill_zone = ?")
        params.append(kill_zone)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM opportunities {where} ORDER BY identified_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with get_connection(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict_from_row(r) for r in rows]


def count_opportunities(pair=None, status=None, db_path=None) -> int:
    """Count opportunities with optional filters."""
    conditions = []
    params = []
    if pair:
        conditions.append("pair = ?")
        params.append(pair)
    if status:
        conditions.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT COUNT(*) FROM opportunities {where}"
    with get_connection(db_path) as conn:
        return conn.execute(sql, params).fetchone()[0]


def update_opportunity(opp_id: int, updates: dict, db_path=None):
    """Update an opportunity record."""
    if not updates:
        return
    set_parts = [f"{k} = ?" for k in updates]
    vals = list(updates.values()) + [opp_id]
    sql = f"UPDATE opportunities SET {', '.join(set_parts)} WHERE id = ?"
    with get_connection(db_path) as conn:
        conn.execute(sql, vals)
    logger.debug(f"Updated opportunity #{opp_id}: {list(updates.keys())}")


# ============================================================================
# Outcome CRUD
# ============================================================================

def insert_outcome(opportunity_id: int, outcome_type: str, price=None,
                   pips_captured=None, notes=None, db_path=None) -> int:
    """Insert an opportunity outcome."""
    sql = """INSERT INTO opportunity_outcomes
        (opportunity_id, outcome_type, price, pips_captured, notes)
        VALUES (?, ?, ?, ?, ?)"""
    with get_connection(db_path) as conn:
        cursor = conn.execute(sql, (opportunity_id, outcome_type, price, pips_captured, notes))
        return cursor.lastrowid


def get_outcomes(opportunity_id: int, db_path=None) -> list:
    """Get all outcomes for an opportunity."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM opportunity_outcomes WHERE opportunity_id = ? ORDER BY timestamp",
            (opportunity_id,)
        ).fetchall()
    return [dict_from_row(r) for r in rows]


# ============================================================================
# Analytics
# ============================================================================

def get_oie_summary(pair=None, days=None, db_path=None) -> dict:
    """Get OIE performance summary."""
    conditions = []
    params = []
    if pair and pair != 'ALL':
        conditions.append("pair = ?")
        params.append(pair)
    if days:
        conditions.append(f"identified_at >= datetime('now', '-{int(days)} days')")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    sql = f"""
    SELECT
        COUNT(*) as total,
        SUM(CASE WHEN status = 'identified' THEN 1 ELSE 0 END) as identified,
        SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
        SUM(CASE WHEN status = 'tp_hit' THEN 1 ELSE 0 END) as tp_hits,
        SUM(CASE WHEN status = 'sl_hit' THEN 1 ELSE 0 END) as sl_hits,
        SUM(CASE WHEN status = 'expired' THEN 1 ELSE 0 END) as expired,
        SUM(CASE WHEN status = 'invalidated' THEN 1 ELSE 0 END) as invalidated,
        AVG(rr_ratio) as avg_rr,
        AVG(risk_pips) as avg_risk_pips,
        AVG(reward_pips) as avg_reward_pips,
        AVG(CASE WHEN setup_type LIKE '%sniper%' THEN poi_score ELSE NULL END) as avg_sniper_poi,
        COUNT(CASE WHEN setup_type LIKE '%sniper%' THEN 1 END) as sniper_count,
        COUNT(CASE WHEN setup_type LIKE '%retrace%' THEN 1 END) as retrace_count
    FROM opportunities {where}
    """
    with get_connection(db_path) as conn:
        row = conn.execute(sql, params).fetchone()
    if not row:
        return {"total": 0}

    result = dict_from_row(row)
    tp = result.get("tp_hits") or 0
    sl = result.get("sl_hits") or 0
    result["win_rate"] = round(tp / (tp + sl) * 100, 1) if (tp + sl) > 0 else 0.0
    return result
