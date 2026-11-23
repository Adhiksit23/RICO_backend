"""
Service module for querying pivoted/wide operating parameters.
Uses the optimized PostgreSQL views (rico.vw_part_operating_parameters_wide / mv_part_operating_parameters_wide)
or in-memory indexed fallback.
"""
from __future__ import annotations

import logging
from typing import Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

from services.config import DB_CONFIG

logger = logging.getLogger(__name__)

CORE_PARAMETERS = [
    "cycle_time",
    "die_close_core_in_time",
    "pouring_time",
    "shot_fwd_time",
    "curing_time",
    "die_open_core_out_time",
    "ejector_time",
    "extract_time",
    "spray_time",
    "v1_speed",
    "v2_speed",
    "v3_speed",
    "v4_speed",
    "accel_point",
    "deaccel_point",
    "intensification_time",
    "metal_pressure",
    "biscuit_thickness",
    "clamp_force_pct",
    "clamp_tonnage",
    "shot_acc_pressure",
    "intensification_acc_pressure",
    "furnace_metal_temp",
]


def get_part_parameters_wide(
    part_id: str,
    use_materialized: bool = False,
    conn: Optional[Any] = None,
) -> Optional[dict[str, Any]]:
    """
    Fetch all operating parameters as dedicated columns for a single part ID.
    Returns a dictionary of part metadata + every parameter value.
    """
    table_name = "rico.mv_part_operating_parameters_wide" if use_materialized else "rico.vw_part_operating_parameters_wide"
    should_close = False

    if conn is None:
        conn = psycopg2.connect(**DB_CONFIG)
        should_close = True

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT *
                FROM {table_name}
                WHERE id_part = %s
                LIMIT 1
                """,
                (part_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        if should_close:
            conn.close()


def get_parts_parameters_wide_batch(
    part_ids: Optional[list[str]] = None,
    die: Optional[str] = None,
    machine: Optional[str] = None,
    production_date: Optional[str] = None,
    limit: Optional[int] = 100,
    use_materialized: bool = True,
    conn: Optional[Any] = None,
) -> list[dict[str, Any]]:
    """
    Fetch operating parameters as columns for multiple parts with filtering.
    """
    table_name = "rico.mv_part_operating_parameters_wide" if use_materialized else "rico.vw_part_operating_parameters_wide"
    should_close = False

    if conn is None:
        conn = psycopg2.connect(**DB_CONFIG)
        should_close = True

    conditions = []
    params: list[Any] = []

    if part_ids:
        conditions.append("id_part = ANY(%s)")
        params.append(part_ids)
    if die and die != "All":
        conditions.append("id_die = %s")
        params.append(die)
    if machine and machine != "All":
        conditions.append("id_machine = %s")
        params.append(machine)
    if production_date:
        conditions.append("production_date = %s")
        params.append(production_date)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    limit_clause = f"LIMIT {int(limit)}" if limit else ""

    sql = f"""
        SELECT *
        FROM {table_name}
        {where_clause}
        ORDER BY manufactored_on DESC NULLS LAST
        {limit_clause}
    """

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, tuple(params))
            return [dict(r) for r in cur.fetchall()]
    finally:
        if should_close:
            conn.close()


def refresh_materialized_parameters(conn: Optional[Any] = None) -> bool:
    """
    Refresh the materialized view concurrently without blocking reader queries.
    """
    should_close = False
    if conn is None:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        should_close = True

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT rico.refresh_part_parameters_wide();")
        logger.info("Successfully refreshed rico.mv_part_operating_parameters_wide")
        return True
    except Exception as exc:
        logger.exception("Failed to refresh materialized parameters view: %s", exc)
        return False
    finally:
        if should_close:
            conn.close()
