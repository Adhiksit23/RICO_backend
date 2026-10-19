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
            {"label": "Custom Range", "value": "custom"},
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


def build_filter_where_clause(
    client: Optional[str] = "All",
    machine: Optional[str] = "All",
    die: Optional[str] = "All",
    period: Optional[str] = "all",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """
    Build dynamic SQL WHERE clause and parameters for part queries.
    Supports preset periods or explicit start_date and end_date.
    """
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

    # 4. Period / Custom date filter
    p_val = (period or "all").lower().strip()
    period_label = "All Time"

    if p_val == "custom" or (start_date or end_date):
        if start_date and end_date:
            where_clauses.append("p.manufactored_on >= %s::date AND p.manufactored_on < (%s::date + INTERVAL '1 day')")
            params.extend([start_date.strip(), end_date.strip()])
            period_label = f"{start_date.strip()} to {end_date.strip()}"
        elif start_date:
            where_clauses.append("p.manufactored_on >= %s::date")
            params.append(start_date.strip())
            period_label = f"From {start_date.strip()}"
        elif end_date:
            where_clauses.append("p.manufactored_on < (%s::date + INTERVAL '1 day')")
            params.append(end_date.strip())
            period_label = f"Until {end_date.strip()}"
    elif p_val == "today":
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
    return where_sql, params, period_label, normalized_die, machine


def fetch_stats_from_cursor(
    cur,
    client: Optional[str] = "All",
    machine: Optional[str] = "All",
    die: Optional[str] = "All",
    period: Optional[str] = "all",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """
    Internal calculation helper that computes summary metrics, defect category breakdown,
    and pie chart slices using an active DB cursor.
    """
    where_sql, params, period_label, normalized_die, active_machine = build_filter_where_clause(
        client=client,
        machine=machine,
        die=die,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )

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
            "hex": meta["hex"],
            "width": f"{min(100, max(2, round(pct_defects)))}%",
        })

        chart_data.append({
            "name": cat_name,
            "value": cnt,
            "color": meta["hex"],
        })

    active_die_str = normalized_die if normalized_die != "All" else "All Dies"
    active_machine_str = active_machine.strip() if active_machine and active_machine != "All" else "All Machines"
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
        "category_counts": dict(category_counts),
    }


@router.get("/stats")
def get_stats(
    client: Optional[str] = "All",
    machine: Optional[str] = "All",
    die: Optional[str] = "All",
    period: Optional[str] = "all",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """
    Return comprehensive, 100% database-driven dashboard statistics:
    Summary metrics, Defect Breakdown table rows, and Pie Chart distribution.
    Supports preset periods or explicit start_date and end_date.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        stats = fetch_stats_from_cursor(
            cur=cur,
            client=client,
            machine=machine,
            die=die,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )

        return {
            "summary": stats["summary"],
            "defects_breakdown": stats["defects_breakdown"],
            "chart_data": stats["chart_data"],
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


@router.get("/compare")
def compare_periods(
    client: Optional[str] = "All",
    machine: Optional[str] = "All",
    die: Optional[str] = "All",
    # Period 1 (Baseline)
    p1_period: Optional[str] = "all",
    p1_start: Optional[str] = None,
    p1_end: Optional[str] = None,
    # Period 2 (Comparison)
    p2_period: Optional[str] = "custom",
    p2_start: Optional[str] = None,
    p2_end: Optional[str] = None,
):
    """
    Compare two distinct time periods to determine if defects have increased,
    decreased, or remained stable overall and per individual defect category.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        p1 = fetch_stats_from_cursor(
            cur=cur,
            client=client,
            machine=machine,
            die=die,
            period=p1_period,
            start_date=p1_start,
            end_date=p1_end,
        )

        p2 = fetch_stats_from_cursor(
            cur=cur,
            client=client,
            machine=machine,
            die=die,
            period=p2_period,
            start_date=p2_start,
            end_date=p2_end,
        )

        # Overall KPI deltas
        p1_rate = p1["summary"]["defect_rate"]
        p2_rate = p2["summary"]["defect_rate"]
        rate_diff = round(p2_rate - p1_rate, 2)

        relative_change = 0.0
        if p1_rate > 0:
            relative_change = round(((p2_rate - p1_rate) / p1_rate) * 100, 2)

        total_parts_diff = p2["summary"]["total_parts"] - p1["summary"]["total_parts"]
        defective_diff = p2["summary"]["defective_parts"] - p1["summary"]["defective_parts"]

        if rate_diff < 0:
            overall_status = "improved"
            status_text = f"Defect rate decreased by {abs(rate_diff):.2f}% ({abs(relative_change):.1f}% reduction)"
        elif rate_diff > 0:
            overall_status = "degraded"
            status_text = f"Defect rate increased by {rate_diff:.2f}% ({relative_change:.1f}% increase)"
        else:
            overall_status = "unchanged"
            status_text = "Defect rate remained identical across both periods"

        # Combine all defect categories from both periods
        all_categories = sorted(set(list(p1["category_counts"].keys()) + list(p2["category_counts"].keys())))
        defect_comparison = []

        p1_parts = p1["summary"]["total_parts"]
        p2_parts = p2["summary"]["total_parts"]

        for cat in all_categories:
            c1 = p1["category_counts"].get(cat, 0)
            c2 = p2["category_counts"].get(cat, 0)

            r1 = round((c1 / p1_parts * 100), 2) if p1_parts > 0 else 0.0
            r2 = round((c2 / p2_parts * 100), 2) if p2_parts > 0 else 0.0
            cat_rate_diff = round(r2 - r1, 2)
            cat_rel = round(((r2 - r1) / r1) * 100, 1) if r1 > 0 else 0.0

            if cat_rate_diff < 0:
                cat_status = "improved"
            elif cat_rate_diff > 0:
                cat_status = "degraded"
            else:
                cat_status = "unchanged"

            defect_comparison.append({
                "category": cat,
                "p1_count": c1,
                "p1_rate": r1,
                "p2_count": c2,
                "p2_rate": r2,
                "count_diff": c2 - c1,
                "rate_diff": cat_rate_diff,
                "relative_change": cat_rel,
                "status": cat_status,
            })

        # Sort by largest absolute rate change
        defect_comparison.sort(key=lambda x: abs(x["rate_diff"]), reverse=True)

        return {
            "period_1": p1["summary"],
            "period_2": p2["summary"],
            "delta": {
                "rate_diff": rate_diff,
                "relative_change": relative_change,
                "total_parts_diff": total_parts_diff,
                "defective_diff": defective_diff,
                "status": overall_status,
                "status_text": status_text,
            },
            "defect_comparison": defect_comparison,
        }
    except Exception as exc:
        logger.exception("[/api/dashboard/compare] Failed to compare periods")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute period comparison from database.",
        ) from exc
    finally:
        if conn:
            conn.close()


@router.get("/longitudinal")
def get_longitudinal_defects(
    client: Optional[str] = "All",
    machine: Optional[str] = "All",
    die: Optional[str] = "All",
    period: Optional[str] = "all",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    interval: Optional[str] = "day",
):
    """
    Time-series longitudinal defect analytics:
    Groups manufactured parts and defects by time intervals (day, week, month)
    to trace trend lines, quality fluctuations, and category progression over time.
    """
    valid_intervals = {"day": "day", "week": "week", "month": "month"}
    clean_interval = valid_intervals.get((interval or "day").lower().strip(), "day")

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        where_sql, params, period_label, normalized_die, active_machine = build_filter_where_clause(
            client=client,
            machine=machine,
            die=die,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )

        # 1. Total parts and defective parts per time bucket
        bucket_sql = f"""
            SELECT 
                DATE_TRUNC('{clean_interval}', p.manufactored_on)::date AS bucket_date,
                COUNT(DISTINCT p.id_part) AS total_parts,
                COUNT(DISTINCT pq.id_part) AS defective_parts
            FROM rico.part p
            LEFT JOIN rico.client c ON p.id_client = c.id_client
            LEFT JOIN rico.part_quality pq ON p.id_part = pq.id_part
            WHERE p.manufactored_on IS NOT NULL AND {where_sql}
            GROUP BY bucket_date
            ORDER BY bucket_date ASC;
        """
        cur.execute(bucket_sql, params)
        bucket_rows = cur.fetchall()

        # 2. Defect counts per bucket and defect type
        defect_bucket_sql = f"""
            SELECT 
                DATE_TRUNC('{clean_interval}', p.manufactored_on)::date AS bucket_date,
                pq.defect_type,
                COUNT(*) AS defect_count
            FROM rico.part_quality pq
            JOIN rico.part p ON pq.id_part = p.id_part
            LEFT JOIN rico.client c ON p.id_client = c.id_client
            WHERE p.manufactored_on IS NOT NULL AND {where_sql}
            GROUP BY bucket_date, pq.defect_type
            ORDER BY bucket_date ASC;
        """
        cur.execute(defect_bucket_sql, params)
        defect_bucket_rows = cur.fetchall()

        # Map defect counts by bucket and standardized category
        bucket_defects = defaultdict(lambda: defaultdict(int))
        all_categories = set()

        for b_date, raw_name, cnt in defect_bucket_rows:
            date_str = b_date.strftime("%Y-%m-%d") if hasattr(b_date, "strftime") else str(b_date)
            cat_name, _, _ = categorize_defect(raw_name)
            bucket_defects[date_str][cat_name] += cnt
            all_categories.add(cat_name)

        # Build timeline points
        timeline = []
        for b_date, total, defective in bucket_rows:
            date_str = b_date.strftime("%Y-%m-%d") if hasattr(b_date, "strftime") else str(b_date)
            total = total or 0
            defective = defective or 0
            rate = round((defective / total * 100), 2) if total > 0 else 0.0

            formatted_date = b_date.strftime("%d %b") if hasattr(b_date, "strftime") else date_str
            if clean_interval == "month":
                formatted_date = b_date.strftime("%b %Y") if hasattr(b_date, "strftime") else date_str

            point = {
                "date": date_str,
                "label": formatted_date,
                "total_parts": total,
                "defective_parts": defective,
                "defect_rate": rate,
                "defects": dict(bucket_defects.get(date_str, {})),
            }
            # Flatten top categories into point for convenient chart binding
            for cat in all_categories:
                point[cat] = bucket_defects.get(date_str, {}).get(cat, 0)

            timeline.append(point)

        return {
            "interval": clean_interval,
            "period_label": period_label,
            "categories": sorted(all_categories),
            "timeline": timeline,
            "total_buckets": len(timeline),
        }
    except Exception as exc:
        logger.exception("[/api/dashboard/longitudinal] Failed to compute longitudinal defect trends")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve longitudinal defect analytics.",
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
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """
    Backward-compatible summary endpoint.
    Delegates to get_stats and returns core summary fields.
    """
    stats_data = get_stats(
        client=client,
        machine=machine,
        die=die,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )
    return stats_data["summary"]