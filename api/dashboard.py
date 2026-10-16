"""
Dashboard API router — live, dynamic production quality overview & defect distribution.
Queries PostgreSQL rico.part and rico.part_quality.
"""
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
import psycopg2

from services.config import DB_CONFIG

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def normalize_die_name(die: Optional[str]) -> str:
    """Normalize 'S-14' -> 'S14' or 's14' -> 'S14'."""
    if not die:
        return "All"
    cleaned = die.strip().replace("-", "").upper()
    return cleaned if cleaned != "ALL" else "All"


def categorize_defect(raw_type: Optional[str]):
    """Map raw database defect strings into standardized categories and colors."""
    d = (raw_type or "").strip().lower()
    if not d:
        return "Others", "bg-gray-400", "#94A3B8"
    if "non-filling" in d or "pre filling" in d:
        return "Non-filling", "bg-cyan-400", "#22D3EE"
    if "blow hole" in d or "blowhole" in d:
        return "Blowhole", "bg-blue-400", "#3B82F6"
    if "porosity" in d:
        return "Porosity", "bg-yellow-400", "#FACC15"
    if "shrinkage" in d:
        return "Shrinkage", "bg-pink-500", "#EC4899"
    if "chip-off" in d or "chipoff" in d:
        return "Chip-off", "bg-green-400", "#34D399"
    if "crack" in d:
        return "Crack", "bg-red-500", "#EF4444"
    return "Others", "bg-gray-400", "#94A3B8"


@router.get("/filters")
def get_filters():
    """
    Return distinct filter options directly from the database
    (Clients, Machines, Dies) plus supported period options.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Clients
        cur.execute(
            """
            SELECT DISTINCT c.name 
            FROM rico.client c 
            JOIN rico.part p ON c.id_client = p.id_client 
            WHERE c.name IS NOT NULL
            ORDER BY c.name;
            """
        )
        clients = [r[0] for r in cur.fetchall()]
        if not clients:
            clients = ["Suzuki"]

        # Machines
        cur.execute(
            """
            SELECT DISTINCT p.id_machine 
            FROM rico.part p 
            WHERE p.id_machine IS NOT NULL 
            ORDER BY p.id_machine;
            """
        )
        machines = [r[0] for r in cur.fetchall()]
        if not machines:
            machines = ["UBE 850T-2"]

        # Dies
        cur.execute(
            """
            SELECT DISTINCT p.id_die 
            FROM rico.part p 
            WHERE p.id_die IS NOT NULL 
            ORDER BY p.id_die;
            """
        )
        dies = [r[0] for r in cur.fetchall()]
        if not dies:
            dies = ["S14", "S16", "S17", "S18"]

        periods = [
            {"label": "Today", "value": "today"},
            {"label": "Last 7 Days", "value": "last_7_days"},
            {"label": "Last Month", "value": "last_month"},
            {"label": "Year to Date", "value": "ytd"},
            {"label": "All Time", "value": "all"},
        ]

        return {
            "clients": ["All"] + clients,
            "machines": ["All"] + machines,
            "dies": ["All"] + dies,
            "periods": periods,
        }
    except Exception as exc:
        logger.exception("[/api/dashboard/filters] Failed to fetch filter options")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard filters from database.",
        ) from exc
    finally:
        if conn:
            conn.close()


@router.get("/stats")
def get_stats(
    client: Optional[str] = "All",
    machine: Optional[str] = "All",
    die: Optional[str] = "All",
    period: Optional[str] = "all",
):
    """
    Return comprehensive, 100% database-driven dashboard statistics:
    Summary metrics, Defect Breakdown table rows, and Pie Chart distribution.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Build dynamic WHERE clause
        where_clauses = ["1=1"]
        params = []

        # 1. Die filter (normalize S-14 -> S14, case insensitive)
        normalized_die = normalize_die_name(die)
        if normalized_die != "All":
            where_clauses.append("REPLACE(UPPER(p.id_die), '-', '') = %s")
            params.append(normalized_die)

        # 2. Machine filter
        if machine and machine != "All":
            where_clauses.append("p.id_machine = %s")
            params.append(machine.strip())

        # 3. Client filter
        if client and client != "All":
            where_clauses.append("c.name = %s")
            params.append(client.strip())

        # 4. Period filter
        p_val = (period or "all").lower().strip()
        period_label = "All Time"
        if p_val == "today":
            where_clauses.append("p.manufactored_on >= CURRENT_DATE")
            period_label = "Today"
        elif p_val in ("last_7_days", "7d"):
            where_clauses.append("p.manufactored_on >= CURRENT_DATE - INTERVAL '7 days'")
            period_label = "Last 7 Days"
        elif p_val in ("last_month", "30d", "last_30_days"):
            where_clauses.append("p.manufactored_on >= CURRENT_DATE - INTERVAL '30 days'")
            period_label = "Last Month"
        elif p_val in ("ytd", "year_to_date"):
            where_clauses.append("p.manufactored_on >= DATE_TRUNC('year', CURRENT_DATE)")
            period_label = "Year to Date"

        where_sql = " AND ".join(where_clauses)

        # Query 1: Total parts & Total defective parts
        count_sql = f"""
            SELECT 
                COUNT(DISTINCT p.id_part) AS total_parts,
                COUNT(DISTINCT pq.id_part) AS defective_parts
            FROM rico.part p
            LEFT JOIN rico.client c ON p.id_client = c.id_client
            LEFT JOIN rico.part_quality pq ON p.id_part = pq.id_part
            WHERE {where_sql};
        """
        cur.execute(count_sql, params)
        total_parts, defective_parts = cur.fetchone()
        total_parts = total_parts or 0
        defective_parts = defective_parts or 0

        defect_rate = round((defective_parts / total_parts * 100), 2) if total_parts > 0 else 0.0

        # Query 2: Defect category breakdown
        defect_sql = f"""
            SELECT 
                pq.defect_type,
                COUNT(*) AS count
            FROM rico.part_quality pq
            JOIN rico.part p ON pq.id_part = p.id_part
            LEFT JOIN rico.client c ON p.id_client = c.id_client
            WHERE {where_sql}
            GROUP BY pq.defect_type
            ORDER BY count DESC;
        """
        cur.execute(defect_sql, params)
        raw_defects = cur.fetchall()

        # Aggregate by standardized category
        category_counts = defaultdict(int)
        category_meta = {}

        for raw_name, cnt in raw_defects:
            cat_name, color, hex_color = categorize_defect(raw_name)
            category_counts[cat_name] += cnt
            if cat_name not in category_meta:
                category_meta[cat_name] = {"color": color, "hex": hex_color}

        # Sort categories by count descending
        sorted_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        total_defect_records = sum(category_counts.values()) or defective_parts

        defects_breakdown = []
        chart_data = []

        for cat_name, cnt in sorted_categories:
            pct_defects = round((cnt / total_defect_records * 100), 2) if total_defect_records > 0 else 0.0
            pct_rate = round((cnt / total_parts * 100), 2) if total_parts > 0 else 0.0
            meta = category_meta.get(cat_name, {"color": "bg-gray-400", "hex": "#94A3B8"})

            defects_breakdown.append({
                "name": cat_name,
                "count": cnt,
                "formatted_count": f"{cnt:,}",
                "percent": f"{pct_defects:.2f}%",
                "rate": f"{pct_rate:.2f}%",
                "color": meta["color"],
                "width": f"{min(100, max(2, round(pct_defects)))}%",
            })

            chart_data.append({
                "name": cat_name,
                "value": cnt,
                "color": meta["hex"],
            })

        # Dynamic subtitles
        active_die_str = normalized_die if normalized_die != "All" else "All Dies"
        active_machine_str = machine.strip() if machine and machine != "All" else "All Machines"
        subtitle_period = f"{period_label} • {active_die_str} • {active_machine_str}"
        subtitle_defects = f"{defective_parts:,} defective of {total_parts:,} parts"

        return {
            "summary": {
                "total_parts": total_parts,
                "defective_parts": defective_parts,
                "defect_rate": defect_rate,
                "period_label": period_label,
                "subtitle_period": subtitle_period,
                "subtitle_defects": subtitle_defects,
            },
            "defects_breakdown": defects_breakdown,
            "chart_data": chart_data,
        }
    except Exception as exc:
        logger.exception("[/api/dashboard/stats] Unexpected error generating dashboard statistics")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute dashboard statistics from database.",
        ) from exc
    finally:
        if conn:
            conn.close()


@router.get("/summary")
def get_summary(
    client: Optional[str] = "All",
    machine: Optional[str] = "All",
    die: Optional[str] = "All",
    period: Optional[str] = "all",
):
    """
    Backward-compatible summary endpoint.
    Delegates to get_stats and returns core summary fields.
    """
    stats_data = get_stats(client=client, machine=machine, die=die, period=period)
    return stats_data["summary"]