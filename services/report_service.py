"""
Service layer for generating Quality and Prescription Reports.
Handles database querying for calibration ranges, part defects, predictions,
and generates multi-sheet Excel (.xlsx) workbooks matching RICO specifications.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta, date
import io
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from pydantic import BaseModel, Field
import psycopg2

from services.config import DB_CONFIG

logger = logging.getLogger(__name__)


# ─── Pydantic Schemas for Report Generation ──────────────────────────
class ParameterMinMeanMax(BaseModel):
    min: Union[float, int, str] = "-"
    mean: Union[float, int, str] = "-"
    max: Union[float, int, str] = "-"


class PrescribedParameterRow(BaseModel):
    machine_id: str
    die_id: str
    prescription_id: str
    date_provided: str
    parameters: Dict[str, ParameterMinMeanMax] = Field(default_factory=dict)


class DefectPredictionMap(BaseModel):
    ok: str = "OK"
    blow_hole: str = "0"
    non_filling: str = "0"
    porosity: str = "0"
    shrinkage: str = "0"
    chip_off: str = "0"
    crack: str = "0"


class DefectRecordedMap(BaseModel):
    ok: str = "OK"
    blow_hole: str = "0"
    non_filling: str = "0"
    porosity: str = "0"
    shrinkage: str = "0"
    chip_off: str = "0"
    crack: str = "0"
    other: str = "0"


class PartDefectComparisonRow(BaseModel):
    source: str = "Neuriot labs"
    today_date: str
    machine_id: str
    die_id: str
    manufactured_date: str
    manufactured_time: str
    part_serial: str
    customer_qr: str
    status: str = ""                   # traceability status from rico.part.status
    prescription_id: str
    predicted: DefectPredictionMap
    recorded: DefectRecordedMap
    # OOR (out-of-range parameter) data from rico.part_quality
    monitor_verdict: str = ""          # e.g. "PASS" / "FAIL" from monitor_verdict column
    params_out_of_range: int = 0       # number of parameters outside calibrated range
    params_compared: int = 0           # number of parameters actually compared
    params_total: int = 0              # total parameters in the shot
    parameters: Dict[str, Any] = Field(default_factory=dict) # Core 23 process parameters


class ReportSummary(BaseModel):
    total_prescriptions: int
    total_parts: int
    die: str
    machine: str
    period: str


class DefectAccuracyItem(BaseModel):
    defect_type: str
    predicted_count: int
    gains: int
    losses: int
    accuracy_pct: float


class AccuracyPartAuditRow(BaseModel):
    part_serial: str
    customer_qr: str
    status: str = ""                   # traceability status from rico.part.status
    prescription_id: str
    machine_id: str
    die_id: str
    manufactured_date: str
    manufactured_time: str
    defect_type: str
    predicted_label: str
    recorded_label: str
    outcome: str  # "GAIN" | "LOSS"


class PredictionAccuracyReport(BaseModel):
    sample_size: int
    total_gains: int
    total_losses: int
    overall_accuracy_pct: float
    breakdown: List[DefectAccuracyItem] = Field(default_factory=list)
    audit_rows: List[AccuracyPartAuditRow] = Field(default_factory=list)


class ReportPreviewResponse(BaseModel):
    prescribed_parameters: List[PrescribedParameterRow]
    part_defect_records: List[PartDefectComparisonRow]
    prediction_accuracy: PredictionAccuracyReport
    summary: ReportSummary


# Single source of truth for the 23 standard process parameters in exact order
REPORT_PARAMETERS: List[Tuple[str, List[str]]] = [
    ("Acc Position 1", ["accel_point", "ACC_POSITION_1_mm_value", "acc_position_1"]),
    ("Biscuit Thickness", ["biscuit_thickness", "BISCUIT_THICKNESS_mm_value"]),
    ("Clamp Force %", ["clamp_force_pct", "CLAMP_FORCE__value", "clamp_force"]),
    ("Clamp Tonnage", ["clamp_tonnage", "CLAMP_TONNAGE_MN_value"]),
    ("Cooling Step", ["curing_time", "COOLING_step_value_sec", "cooling_step"]),
    ("Deacc Position", ["deaccel_point", "DEACC_POSITION_1_mm_value", "deacc_position"]),
    (
        "Die Close Core In Time",
        ["die_close_core_in_time", "DIE-CLOSE CORE IN TIME", "DIE_CLOSE_CORE_IN_step_value_sec"],
    ),
    (
        "Die Open Core Out Time",
        ["die_open_core_out_time", "DIE_OPEN_CORE_OUT_step_value_sec"],
    ),
    ("Ejecter Step Time", ["ejector_time", "EJECTOR_step_value_sec", "ejecter_step_time"]),
    ("Extractor Step Time", ["extract_time", "EXTRACTOR_step_value_sec", "extractor_step_time"]),
    (
        "Intensification Pressure",
        ["intensification_acc_pressure", "INTESIFICAITON_ACC_PRESSUREvalue", "intensification_pressure"],
    ),
    (
        "Intensification Time",
        ["intensification_time", "INTESIFICAITON_TIME_msec_value"],
    ),
    ("Metal Pressure", ["metal_pressure", "MATEL_PRESSURE_Mpa_value"]),
    ("Metal Temp", ["furnace_metal_temp", "METAL_TEMP_value", "metal_temp"]),
    ("Poring Step Time", ["pouring_time", "POURING_step_value_sec", "poring_step_time"]),
    ("Shot Acc Pressure", ["shot_acc_pressure", "SHOT_ACC_PRESSURE_value"]),
    ("Shot Fwd Step Time", ["shot_fwd_time", "SHOT_FWD_step_value_sec", "shot_fwd_step_time"]),
    ("Speed 1", ["v1_speed", "SPEED_1_m_sec_value", "speed_1"]),
    ("Speed 2", ["v2_speed", "SPEED_2_m_sec_value", "speed_2"]),
    ("Speed 3", ["v3_speed", "SPEED_3_m_sec_value", "speed_3"]),
    ("Speed 4", ["v4_speed", "SPEED_4_m_sec_value", "speed_4"]),
    ("Spray Time", ["spray_time", "SPRAY_step_value_sec"]),
    ("Total Cycle Time", ["cycle_time", "cycletime_value_sec", "total_cycle_time"]),
]

TARGET_DEFECT_KEYS = ["Blow_Hole", "Non_filling", "Porosity", "Shrinkage", "Chipoff", "Crack"]

# India Standard Time (no DST) — report timestamps and production days are IST based.
IST = timezone(timedelta(hours=5, minutes=30), "IST")
PRODUCTION_DAY_START_HOUR = 6


def _to_ist(value):
    """Convert a DB timestamp (timestamptz) to IST for display."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(IST)
    return value


def _production_day(now_ist: datetime) -> date:
    """Production day is 06:00 -> 06:00 IST; before 06:00 it is still the previous day."""
    return (now_ist - timedelta(hours=PRODUCTION_DAY_START_HOUR)).date()


def _production_day_start(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, PRODUCTION_DAY_START_HOUR, tzinfo=IST)



def _get_db_conn():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as exc:
        logger.warning("Could not connect to PostgreSQL for reports: %s", exc)
        return None


def fetch_prescribed_parameters(
    die: Optional[str] = None,
    machine: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[PrescribedParameterRow]:
    """
    Retrieve timestamped prescribed parameter calibrations from database.
    Falls back gracefully if database connection is unreachable.
    """
    conn = _get_db_conn()
    records: List[PrescribedParameterRow] = []

    if conn:
        try:
            cur = conn.cursor()
            conditions = []
            params: List[Any] = []

            if die and die != "All":
                conditions.append("dc.id_die = %s")
                params.append(die)
            if machine and machine != "All":
                conditions.append("dc.id_machine = %s")
                params.append(machine)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            limit_clause = f"LIMIT {int(limit) * 30}" if limit is not None else ""

            query = f"""
                SELECT 
                    dc.id_calibration,
                    dc.id_die,
                    COALESCE(m.name, dc.id_machine::text, 'UBE 850T-02') as machine_name,
                    COALESCE(dc.created_at, NOW()) as date_provided,
                    cp.parameter_name,
                    cp.baseline,
                    cp.lower_tolerance,
                    cp.upper_tolerance
                FROM die_calibration dc
                LEFT JOIN machine m ON dc.id_machine::text = m.id_machine::text
                LEFT JOIN calibration_parameter cp ON dc.id_calibration = cp.id_calibration
                {where_clause}
                ORDER BY dc.id_calibration DESC, cp.parameter_name
                {limit_clause};
            """
            cur.execute(query, tuple(params))
            rows = cur.fetchall()

            # Group rows by id_calibration
            grouped: Dict[int, Dict[str, Any]] = {}
            for row in rows:
                calib_id, die_id, machine_name, date_prov, param_name, baseline, lower_tol, upper_tol = row
                if calib_id not in grouped:
                    presc_id = str(calib_id)
                    grouped[calib_id] = {
                        "machine_id": machine_name or "UBE 850T-2",
                        "die_id": die_id or "S18",
                        "prescription_id": presc_id,
                        "date_provided": date_prov.strftime("%Y-%m-%d %H:%M") if hasattr(date_prov, "strftime") else str(date_prov),
                        "raw_params": {},
                    }
                if param_name:
                    grouped[calib_id]["raw_params"][param_name.strip().lower()] = {
                        "min": round(float(lower_tol), 2) if lower_tol is not None else "-",
                        "mean": round(float(baseline), 2) if baseline is not None else "-",
                        "max": round(float(upper_tol), 2) if upper_tol is not None else "-",
                    }

            for calib_id, item in grouped.items():
                param_dict: Dict[str, ParameterMinMeanMax] = {}
                for display_name, aliases in REPORT_PARAMETERS:
                    val_obj = None
                    for alias in aliases:
                        if alias.lower() in item["raw_params"]:
                            val_obj = item["raw_params"][alias.lower()]
                            break
                    if val_obj:
                        param_dict[display_name] = ParameterMinMeanMax(
                            min=val_obj["min"],
                            mean=val_obj["mean"],
                            max=val_obj["max"],
                        )
                    else:
                        param_dict[display_name] = ParameterMinMeanMax()

                records.append(
                    PrescribedParameterRow(
                        machine_id=item["machine_id"],
                        die_id=item["die_id"],
                        prescription_id=item["prescription_id"],
                        date_provided=item["date_provided"],
                        parameters=param_dict,
                    )
                )
            cur.close()
            conn.close()
        except Exception as exc:
            logger.warning("Error fetching calibration parameters from DB: %s", exc)
            if conn:
                conn.close()

    # Fallback default calibration sample if database has no rows yet
    if not records:
        target_dies = [die] if die and die != "All" else ["S18", "S17"]
        for d in target_dies:
            p_dict: Dict[str, ParameterMinMeanMax] = {}
            for name, _ in REPORT_PARAMETERS:
                p_dict[name] = ParameterMinMeanMax(min=10.0, mean=12.5, max=15.0)
            records.append(
                PrescribedParameterRow(
                    machine_id=str(machine) if machine and machine != "All" else "UBE 850T-2",
                    die_id=str(d),
                    prescription_id="75",
                    date_provided=datetime.now(IST).strftime("%Y-%m-%d 08:30"),
                    parameters=p_dict,
                )
            )

    return records


def fetch_part_defect_comparisons(
    die: Optional[str] = None,
    machine: Optional[str] = None,
    client: Optional[str] = None,
    period: str = "all",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[PartDefectComparisonRow]:
    """
    Fetch parts with their predicted defect probabilities and actual recorded defects.
    """
    conn = _get_db_conn()
    records: List[PartDefectComparisonRow] = []

    if conn:
        try:
            cur = conn.cursor()
            conditions = ["p.id_part IS NOT NULL"]
            params: List[Any] = []

            if die and die != "All":
                conditions.append("p.id_die = %s")
                params.append(die)
            if machine and machine != "All":
                conditions.append("(p.id_machine::text = %s OR m.name = %s)")
                params.extend([machine, machine])
            if client and client != "All":
                conditions.append("c.name = %s")
                params.append(client)

            # Date Period filtering (production day = 06:00 -> 06:00 IST)
            now_ist = datetime.now(IST)
            anchor = _production_day(now_ist)
            if period == "today":
                conditions.append("p.manufactored_on >= %s")
                params.append(_production_day_start(anchor))
            elif period == "last_7_days":
                conditions.append("p.manufactored_on >= %s")
                params.append(_production_day_start(anchor - timedelta(days=7)))
            elif period == "last_month":
                conditions.append("p.manufactored_on >= %s")
                params.append(_production_day_start(anchor - timedelta(days=30)))
            elif period == "ytd":
                conditions.append("p.manufactored_on >= %s")
                params.append(_production_day_start(date(anchor.year, 1, 1)))
            elif period == "custom" and (start_date or end_date):
                if start_date and end_date:
                    start_d = date.fromisoformat(str(start_date)[:10])
                    end_d = date.fromisoformat(str(end_date)[:10])
                    # Strict IST calendar range: 00:00:00 on start date to 23:59:59.999999 on end date
                    start_dt = datetime(start_d.year, start_d.month, start_d.day, 0, 0, 0, tzinfo=IST)
                    end_dt = datetime(end_d.year, end_d.month, end_d.day, 23, 59, 59, 999999, tzinfo=IST)
                    conditions.append("p.manufactored_on >= %s AND p.manufactored_on <= %s")
                    params.extend([start_dt, end_dt])
                elif start_date:
                    start_d = date.fromisoformat(str(start_date)[:10])
                    start_dt = datetime(start_d.year, start_d.month, start_d.day, 0, 0, 0, tzinfo=IST)
                    conditions.append("p.manufactored_on >= %s")
                    params.append(start_dt)
                elif end_date:
                    end_d = date.fromisoformat(str(end_date)[:10])
                    end_dt = datetime(end_d.year, end_d.month, end_d.day, 23, 59, 59, 999999, tzinfo=IST)
                    conditions.append("p.manufactored_on <= %s")
                    params.append(end_dt)

            where_str = f"WHERE {' AND '.join(conditions)}"
            limit_str = f"LIMIT {int(limit)}" if limit is not None else ""

            # Check available columns in rico.part safely (without altering DB)
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'rico' AND table_name = 'part';"
            )
            part_col_names = {row[0].lower() for row in cur.fetchall()}
            customer_qr_expr = "p.customer_qr" if "customer_qr" in part_col_names else "NULL as customer_qr"
            status_expr = "p.status" if "status" in part_col_names else "NULL as status"

            query = f"""
                SELECT 
                    p.id_part,
                    p.id_die,
                    COALESCE(m.name, p.id_machine::text, 'UBE 850T-2') as machine_name,
                    p.manufactored_on,
                    {customer_qr_expr},
                    p.id_calibration_used,
                    {status_expr}
                FROM rico.part p
                LEFT JOIN rico.machine m ON p.id_machine::text = m.id_machine::text
                LEFT JOIN rico.client c ON p.id_client = c.id_client
                {where_str}
                ORDER BY p.manufactored_on DESC
                {limit_str};
            """
            cur.execute(query, tuple(params))
            parts = cur.fetchall()

            if parts:
                part_ids = [r[0] for r in parts]

                # 1. Fetch actual recorded shop-floor defects from rico.part_quality
                cur.execute(
                    """
                    SELECT id_part, defect_type
                    FROM rico.part_quality
                    WHERE id_part = ANY(%s);
                    """,
                    (part_ids,),
                )
                actual_defects_map: Dict[str, List[str]] = {}
                for pid, dtype in cur.fetchall():
                    actual_defects_map.setdefault(pid, []).append((dtype or "").lower())

                # 2. Fetch AI defect predictions AND Parameter Health columns from rico.part_quality_prediction
                cur.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'rico' AND table_name = 'part_quality_prediction';"
                )
                pqp_col_names = {row[0].lower() for row in cur.fetchall()}

                pqp_mv_expr = "monitor_verdict" if "monitor_verdict" in pqp_col_names else "NULL as monitor_verdict"
                pqp_oor_expr = "params_out_of_range" if "params_out_of_range" in pqp_col_names else "0 as params_out_of_range"
                pqp_pc_expr = "params_compared" if "params_compared" in pqp_col_names else "0 as params_compared"
                pqp_pt_expr = "params_total" if "params_total" in pqp_col_names else "0 as params_total"

                cur.execute(
                    f"""
                    SELECT
                        id_part,
                        defect_type,
                        defect_probability,
                        {pqp_mv_expr},
                        {pqp_oor_expr},
                        {pqp_pc_expr},
                        {pqp_pt_expr}
                    FROM rico.part_quality_prediction 
                    WHERE id_part = ANY(%s);
                    """,
                    (part_ids,),
                )
                pred_map: Dict[str, Dict[str, float]] = {}
                pqp_oor_map: Dict[str, Dict[str, Any]] = {}
                for row in cur.fetchall():
                    pid = row[0]
                    dtype = (row[1] or "").lower()
                    prob = float(row[2]) if row[2] is not None else 0.0
                    mv_val = str(row[3] or "").strip().upper()
                    oor_val = int(row[4] or 0)
                    compared_val = int(row[5] or 0)
                    total_val = int(row[6] or 0)

                    if pid not in pred_map:
                        pred_map[pid] = {}
                    pred_map[pid][dtype] = prob

                    if pid not in pqp_oor_map:
                        pqp_oor_map[pid] = {
                            "monitor_verdict": mv_val,
                            "params_out_of_range": oor_val,
                            "params_compared": compared_val,
                            "params_total": total_val,
                        }
                    else:
                        if mv_val and not pqp_oor_map[pid]["monitor_verdict"]:
                            pqp_oor_map[pid]["monitor_verdict"] = mv_val
                        if oor_val and not pqp_oor_map[pid]["params_out_of_range"]:
                            pqp_oor_map[pid]["params_out_of_range"] = oor_val
                        if compared_val and not pqp_oor_map[pid]["params_compared"]:
                            pqp_oor_map[pid]["params_compared"] = compared_val
                        if total_val and not pqp_oor_map[pid]["params_total"]:
                            pqp_oor_map[pid]["params_total"] = total_val

                # 3. Fetch all 23 actual parameters for parts
                part_params_map: Dict[str, Dict[str, Any]] = {}
                try:
                    cur.execute(
                        """
                        SELECT *
                        FROM rico.vw_part_operating_parameters_wide
                        WHERE id_part = ANY(%s);
                        """,
                        (part_ids,),
                    )
                    col_names = [desc[0].lower() for desc in cur.description]
                    for r in cur.fetchall():
                        r_dict = dict(zip(col_names, r))
                        pid = str(r_dict.get("id_part"))
                        part_params_map[pid] = {}
                        for p_name, aliases in REPORT_PARAMETERS:
                            val = None
                            for alias in aliases:
                                c_name = alias.lower().replace(" ", "_")
                                if c_name in r_dict and r_dict[c_name] is not None:
                                    try:
                                        val = round(float(r_dict[c_name]), 2)
                                    except (TypeError, ValueError):
                                        val = r_dict[c_name]
                                    break
                            part_params_map[pid][p_name] = val
                except Exception:
                    # Fallback if view is not yet created in the DB: query raw operating_parameter
                    if conn and hasattr(conn, "rollback"):
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                    try:
                        cur.execute(
                            """
                            SELECT id_part, parameter_name, value
                            FROM rico.operating_parameter
                            WHERE id_part = ANY(%s);
                            """,
                            (part_ids,),
                        )
                        alias_to_display = {}
                        for p_name, aliases in REPORT_PARAMETERS:
                            for a in aliases:
                                alias_to_display[a.lower()] = p_name
                                alias_to_display[a.lower().replace(" ", "_")] = p_name

                        for pid, pname, val in cur.fetchall():
                            pid_str = str(pid)
                            if pid_str not in part_params_map:
                                part_params_map[pid_str] = {}
                            clean_pname = (pname or "").lower().strip()
                            disp = alias_to_display.get(clean_pname) or alias_to_display.get(clean_pname.replace(" ", "_"))
                            if disp and val is not None:
                                try:
                                    part_params_map[pid_str][disp] = round(float(val), 2)
                                except (TypeError, ValueError):
                                    part_params_map[pid_str][disp] = val
                    except Exception as e_fallback:
                        logger.warning("Could not fetch parameter fallback: %s", e_fallback)

                today_str = datetime.now(IST).strftime("%Y-%m-%d")

                for part_id, die_id, machine_name, mfg_on, cust_qr, calib_used, part_st in parts:
                    mfg_on = _to_ist(mfg_on)
                    mfg_date = mfg_on.strftime("%Y-%m-%d") if hasattr(mfg_on, "strftime") else str(mfg_on)[:10]
                    mfg_time = mfg_on.strftime("%H:%M:%S") if hasattr(mfg_on, "strftime") else "00:00:00"

                    # Map actual recorded defects from rico.part_quality
                    act_list = actual_defects_map.get(part_id, [])
                    has_actual_defect = len(act_list) > 0

                    def check_actual(name: str) -> str:
                        target = name.lower().replace("_", "")
                        return "1" if any(target in a.replace("-", "").replace("_", "") for a in act_list) else "0"

                    recorded_data = DefectRecordedMap(
                        ok="DEFECT" if has_actual_defect else "OK",
                        blow_hole=check_actual("blow_hole"),
                        non_filling=check_actual("non_filling"),
                        porosity=check_actual("porosity"),
                        shrinkage=check_actual("shrinkage"),
                        chip_off=check_actual("chipoff"),
                        crack=check_actual("crack"),
                        other="0",
                    )

                    # --- Parameter Health & Out-of-Range values from rico.part_quality_prediction ---
                    pqp_info = pqp_oor_map.get(part_id, {})
                    part_oor = int(pqp_info.get("params_out_of_range") or 0)
                    part_compared = int(pqp_info.get("params_compared") or 0)
                    part_total = int(pqp_info.get("params_total") or 0)
                    part_mv = str(pqp_info.get("monitor_verdict") or "").strip().upper()

                    # --- Predicted defect logic ---
                    # Threshold: 60% probability AND >= 4 parameters out of range
                    # Both conditions must be met for the overall part to be called DEFECT.
                    DEFECT_PROB_THRESHOLD = 0.60
                    OOR_GATE = 4

                    preds = pred_map.get(part_id, {})
                    any_high_prob = any(p > DEFECT_PROB_THRESHOLD for p in preds.values())
                    gates_passed = any_high_prob and (part_oor >= OOR_GATE)

                    def format_pred(name: str) -> str:
                        """Always show probability; 1/0 reflects the probability threshold,
                        while the overall DEFECT verdict uses the dual gate."""
                        p_val = preds.get(name.lower(), 0.0)
                        flag = "1" if p_val > DEFECT_PROB_THRESHOLD else "0"
                        return f"{flag} ({int(p_val * 100)}%)"

                    predicted_data = DefectPredictionMap(
                        # Overall verdict requires BOTH: prob > 60% AND params_oor >= 4
                        ok="DEFECT" if gates_passed else "OK",
                        blow_hole=format_pred("blow_hole"),
                        non_filling=format_pred("non_filling"),
                        porosity=format_pred("porosity"),
                        shrinkage=format_pred("shrinkage"),
                        chip_off=format_pred("chipoff"),
                        crack=format_pred("crack"),
                    )

                    customer_qr_val = str(cust_qr).strip() if cust_qr else ""
                    status_val = str(part_st).strip() if part_st is not None else ""
                    prescription_id_val = str(calib_used).strip() if calib_used is not None else ""

                    records.append(
                        PartDefectComparisonRow(
                            source="Neuriot labs",
                            today_date=today_str,
                            machine_id=machine_name or "UBE 850T-2",
                            die_id=die_id or "S18",
                            manufactured_date=mfg_date,
                            manufactured_time=mfg_time,
                            part_serial=str(part_id),
                            customer_qr=customer_qr_val,
                            status=status_val,
                            prescription_id=prescription_id_val,
                            predicted=predicted_data,
                            recorded=recorded_data,
                            monitor_verdict=part_mv,
                            params_out_of_range=part_oor,
                            params_compared=part_compared,
                            params_total=part_total,
                            parameters=part_params_map.get(str(part_id), {}),
                        )
                    )

            cur.close()
            conn.close()
        except Exception as exc:
            logger.warning("Error fetching defect comparison records from DB: %s", exc)
            if conn:
                conn.close()

    # Fallback sample rows if DB is empty / offline — reflects new dual-gate logic (60% + >=4 OOR)
    if not records:
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        now_time = datetime.now(IST)
        # (serial, pred_type, rec_type, monitor_verdict, params_oor)
        # Dual gate: predicted DEFECT only when pred_type set AND params_oor >= 4
        sample_configs = [
            ("1104135924619", None,          None,          "PASS", 1),   # OK — low OOR
            ("1104135824618", "blow_hole",    "blow_hole",   "FAIL", 5),   # GAIN — both gates pass
            ("1104135724617", None,          None,          "PASS", 2),   # OK — low OOR
            ("1104135524616", "non_filling", "non_filling", "FAIL", 6),   # GAIN — both gates pass
            ("1104135424615", None,          None,          "PASS", 3),   # OK — below OOR threshold
            ("1104135324614", "porosity",    None,          "PASS", 2),   # LOSS — high prob but OOR < 4, so not flagged DEFECT
        ]
        for i, (serial, pred_type, rec_type, mv, oor) in enumerate(sample_configs):
            # Dual gate: overall DEFECT only when both prob > 60% AND params_oor >= 4
            is_def_predicted = pred_type is not None and oor >= 4

            pred_map_fb = DefectPredictionMap(ok="DEFECT" if is_def_predicted else "OK")
            rec_map_fb = DefectRecordedMap(ok="DEFECT" if rec_type else "OK")

            if pred_type == "blow_hole":
                pred_map_fb.blow_hole = "1 (82%)"
            elif pred_type == "non_filling":
                pred_map_fb.non_filling = "1 (74%)"
            elif pred_type == "porosity":
                pred_map_fb.porosity = "1 (68%)"

            if rec_type == "blow_hole":
                rec_map_fb.blow_hole = "1"
            elif rec_type == "non_filling":
                rec_map_fb.non_filling = "1"

            records.append(
                PartDefectComparisonRow(
                    source="Neuriot labs",
                    today_date=today_str,
                    machine_id=machine if machine and machine != "All" else "UBE 850T-2",
                    die_id=die if die and die != "All" else "S18",
                    manufactured_date=today_str,
                    manufactured_time=(now_time - timedelta(minutes=i * 2)).strftime("%H:%M:%S"),
                    part_serial=serial,
                    customer_qr="",
                    status="Received",
                    prescription_id="75",
                    predicted=pred_map_fb,
                    recorded=rec_map_fb,
                    monitor_verdict=mv,
                    params_out_of_range=oor,
                    params_compared=23,
                    params_total=23,
                    parameters={p_name: 0.0 for p_name, _ in REPORT_PARAMETERS},
                )
            )

    return records


def compute_prediction_accuracy(
    part_defect_records: List[PartDefectComparisonRow],
) -> PredictionAccuracyReport:
    """
    Calculate prediction accuracy across the target 6 defect types.

    A per-defect prediction only counts toward the sample when the OVERALL part
    was flagged DEFECT — i.e. the dual gate was satisfied (prob > 60% AND
    params_out_of_range >= 4).  This keeps the accuracy metric consistent with
    the defect verdict shown in the UI.

      - GAIN: overall verdict == DEFECT AND defect of type T was recorded.
      - LOSS: overall verdict == DEFECT AND defect of type T was NOT recorded.
      - IGNORED: overall verdict == OK (dual gate not met), regardless of recording.
    """
    defect_fields = [
        ("blow_hole", "Blow Hole"),
        ("crack", "Crack"),
        ("non_filling", "Non-filling"),
        ("porosity", "Porosity"),
        ("shrinkage", "Shrinkage"),
        ("chip_off", "Chip-off"),
    ]

    counts: Dict[str, Dict[str, int]] = {
        label: {"predicted": 0, "gains": 0, "losses": 0}
        for _, label in defect_fields
    }
    audit_rows: List[AccuracyPartAuditRow] = []

    for r in part_defect_records:
        # Only consider this part if the dual gate was passed (overall == DEFECT)
        if str(r.predicted.ok).strip().upper() != "DEFECT":
            continue

        for field, label in defect_fields:
            p_val = getattr(r.predicted, field, "0")
            r_val = getattr(r.recorded, field, "0")

            p_str = str(p_val).strip()
            r_str = str(r_val).strip()

            # Count this defect type if it was individually flagged (prob > 60%)
            if p_str.startswith("1"):
                counts[label]["predicted"] += 1
                is_gain = r_str.startswith("1")
                if is_gain:
                    counts[label]["gains"] += 1
                    outcome = "GAIN"
                else:
                    counts[label]["losses"] += 1
                    outcome = "LOSS"

                audit_rows.append(
                    AccuracyPartAuditRow(
                        part_serial=r.part_serial,
                        customer_qr=r.customer_qr,
                        status=r.status,
                        prescription_id=r.prescription_id,
                        machine_id=r.machine_id,
                        die_id=r.die_id,
                        manufactured_date=r.manufactured_date,
                        manufactured_time=r.manufactured_time,
                        defect_type=label,
                        predicted_label=p_str,
                        recorded_label=r_str,
                        outcome=outcome,
                    )
                )

    breakdown: List[DefectAccuracyItem] = []
    total_predicted = 0
    total_gains = 0
    total_losses = 0

    for _, label in defect_fields:
        c = counts[label]
        p_cnt = c["predicted"]
        g_cnt = c["gains"]
        l_cnt = c["losses"]
        acc = round((g_cnt / p_cnt) * 100, 1) if p_cnt > 0 else 0.0
        breakdown.append(
            DefectAccuracyItem(
                defect_type=label,
                predicted_count=p_cnt,
                gains=g_cnt,
                losses=l_cnt,
                accuracy_pct=acc,
            )
        )
        total_predicted += p_cnt
        total_gains += g_cnt
        total_losses += l_cnt

    overall_acc = round((total_gains / total_predicted) * 100, 1) if total_predicted > 0 else 0.0

    return PredictionAccuracyReport(
        sample_size=total_predicted,
        total_gains=total_gains,
        total_losses=total_losses,
        overall_accuracy_pct=overall_acc,
        breakdown=breakdown,
        audit_rows=audit_rows,
    )


def get_report_preview_data(
    client: Optional[str] = "All",
    machine: Optional[str] = "All",
    die: Optional[str] = "All",
    period: str = "all",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None,
) -> ReportPreviewResponse:
    """
    Get compiled JSON preview data for frontend UI viewing.
    """
    prescribed = fetch_prescribed_parameters(die=die, machine=machine)
    defect_records = fetch_part_defect_comparisons(
        die=die,
        machine=machine,
        client=client,
        period=period,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    accuracy = compute_prediction_accuracy(defect_records)

    return ReportPreviewResponse(
        prescribed_parameters=prescribed,
        part_defect_records=defect_records,
        prediction_accuracy=accuracy,
        summary=ReportSummary(
            total_prescriptions=len(prescribed),
            total_parts=len(defect_records),
            die=die or "All",
            machine=machine or "All",
            period=period or "all",
        ),
    )


def generate_report_excel_workbook(
    client: Optional[str] = "All",
    machine: Optional[str] = "All",
    die: Optional[str] = "All",
    period: str = "all",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None,
) -> io.BytesIO:
    """
    Generate the Excel workbook with EXACTLY the 3 requested sheets:
      1. Prescription history
      2. Predicted vs Actual
      3. Prediction Accuracy
    Styled professionally matching RICO specifications.
    """
    prescribed_rows = fetch_prescribed_parameters(die=die, machine=machine)
    defect_comparison_rows = fetch_part_defect_comparisons(
        die=die,
        machine=machine,
        client=client,
        period=period,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )

    wb = openpyxl.Workbook()

    # Reusable Styles
    font_family = "Segoe UI"
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )
    header_border = Border(
        left=Side(style="thin", color="B0B0B0"),
        right=Side(style="thin", color="B0B0B0"),
        top=Side(style="thin", color="B0B0B0"),
        bottom=Side(style="thin", color="B0B0B0"),
    )

    fill_id_header = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid") # Dark Navy Blue
    fill_presc_header = PatternFill(start_color="2E75B6", end_color="2E75B6", fill_type="solid") # Blue Accent
    fill_oor_header = PatternFill(start_color="B25900", end_color="B25900", fill_type="solid") # Amber / Orange Accent
    fill_pred_header = PatternFill(start_color="7030A0", end_color="7030A0", fill_type="solid") # Purple Accent
    fill_rec_header = PatternFill(start_color="C65911", end_color="C65911", fill_type="solid") # Rust / Amber
    fill_param_header = PatternFill(start_color="117A65", end_color="117A65", fill_type="solid") # Dark Teal (IoT Actual Parameters)
    fill_zebra = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")

    font_top_header = Font(name=font_family, size=11, bold=True, color="FFFFFF")
    font_sub_header = Font(name=font_family, size=9, bold=True, color="FFFFFF")
    font_data = Font(name=font_family, size=9)
    font_data_bold = Font(name=font_family, size=9, bold=True)
    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center")

    # =========================================================================
    # SHEET 1: Prescription history
    # =========================================================================
    ws1 = wb.active
    ws1.title = "Prescription history"
    ws1.views.sheetView[0].showGridLines = True

    # Tier 1 Header: Groupings
    ws1.merge_cells("A1:D1")
    ws1["A1"] = "Identification"
    ws1["A1"].fill = fill_id_header
    ws1["A1"].font = font_top_header
    ws1["A1"].alignment = align_center

    total_param_cols = len(REPORT_PARAMETERS) * 3
    end_col_letter = get_column_letter(4 + total_param_cols)
    ws1.merge_cells(f"E1:{end_col_letter}1")
    ws1["E1"] = "Prescribed Parameters"
    ws1["E1"].fill = fill_presc_header
    ws1["E1"].font = font_top_header
    ws1["E1"].alignment = align_center

    # Tier 2 Header: Column Names
    headers_tier2 = ["Machine ID", "Die ID", "Prescription ID", "Date Provided"]
    for p_name, _ in REPORT_PARAMETERS:
        headers_tier2.extend([f"{p_name} - Min", f"{p_name} - Mean", f"{p_name} - Max"])

    for col_idx, h_text in enumerate(headers_tier2, 1):
        cell = ws1.cell(row=2, column=col_idx, value=h_text)
        cell.font = font_sub_header
        cell.fill = fill_id_header if col_idx <= 4 else fill_presc_header
        cell.alignment = align_center
        cell.border = header_border

    # Data Rows
    current_row = 3
    for r in prescribed_rows:
        row_values = [r.machine_id, r.die_id, r.prescription_id, r.date_provided]
        for p_name, _ in REPORT_PARAMETERS:
            p_val = r.parameters.get(p_name, ParameterMinMeanMax())
            row_values.extend([p_val.min, p_val.mean, p_val.max])

        for col_idx, val in enumerate(row_values, 1):
            cell = ws1.cell(row=current_row, column=col_idx, value=val)
            cell.font = font_data_bold if col_idx in [1, 2, 3] else font_data
            cell.alignment = align_left if col_idx <= 4 else align_center
            cell.border = thin_border
            if current_row % 2 == 0:
                cell.fill = fill_zebra
        current_row += 1

    # Footnote
    fn_cell = ws1.cell(row=current_row + 1, column=1, value="Responsible: Neuriot labs")
    fn_cell.font = Font(name=font_family, size=9, italic=True, bold=True, color="555555")

    # Column Widths
    for c_idx in range(1, len(headers_tier2) + 1):
        col_letter = get_column_letter(c_idx)
        ws1.column_dimensions[col_letter].width = 18 if c_idx <= 4 else 14

    # =========================================================================
    # SHEET 2: Predicted vs Actual
    # =========================================================================
    ws2 = wb.create_sheet(title="Predicted vs Actual")
    ws2.views.sheetView[0].showGridLines = True

    # Tier 1 Header
    ws2.merge_cells("A1:J1")
    ws2["A1"] = "Identification"
    ws2["A1"].fill = fill_id_header
    ws2["A1"].font = font_top_header
    ws2["A1"].alignment = align_center

    ws2.merge_cells("K1:M1")
    ws2["K1"] = "Parameter Health (OOR)"
    ws2["K1"].fill = fill_oor_header
    ws2["K1"].font = font_top_header
    ws2["K1"].alignment = align_center

    ws2.merge_cells("N1:T1")
    ws2["N1"] = "Predicted (Defects)"
    ws2["N1"].fill = fill_pred_header
    ws2["N1"].font = font_top_header
    ws2["N1"].alignment = align_center

    ws2.merge_cells("U1:AB1")
    ws2["U1"] = "Recorded (Defects)"
    ws2["U1"].fill = fill_rec_header
    ws2["U1"].font = font_top_header
    ws2["U1"].alignment = align_center

    # Actual 23 Operating Parameters
    total_param_len = len(REPORT_PARAMETERS)
    param_start_col = 29
    param_end_col = param_start_col + total_param_len - 1
    param_start_letter = get_column_letter(param_start_col)
    param_end_letter = get_column_letter(param_end_col)
    ws2.merge_cells(f"{param_start_letter}1:{param_end_letter}1")
    ws2[f"{param_start_letter}1"] = "Actual Operating Parameters (Recorded in IoT)"
    ws2[f"{param_start_letter}1"].fill = fill_param_header
    ws2[f"{param_start_letter}1"].font = font_top_header
    ws2[f"{param_start_letter}1"].alignment = align_center

    # Tier 2 Header
    headers_defect_comparison = [
        "Source",
        "Today's Date",
        "Machine ID",
        "Die ID",
        "Manufactured Date",
        "Manufactured Time",
        "Part Serial",
        "Customer QR",
        "Status",
        "Prescription ID",
        # Parameter Health (OOR)
        "Monitor Verdict",
        "OOR / Compared",
        "OOR Status (≥4 Rule)",
        # Predicted
        "OK",
        "Blow Hole",
        "Non-filling",
        "Porosity",
        "Shrinkage",
        "Chip-off",
        "Crack",
        # Recorded
        "OK",
        "Blow Hole",
        "Non-filling",
        "Porosity",
        "Shrinkage",
        "Chip-off",
        "Crack",
        "Other",
        # Actual 23 Operating Parameters
        *[p_name for p_name, _ in REPORT_PARAMETERS],
    ]

    for col_idx, h_text in enumerate(headers_defect_comparison, 1):
        cell = ws2.cell(row=2, column=col_idx, value=h_text)
        cell.font = font_sub_header
        if col_idx <= 10:
            cell.fill = fill_id_header
        elif col_idx <= 13:
            cell.fill = fill_oor_header
        elif col_idx <= 20:
            cell.fill = fill_pred_header
        elif col_idx <= 28:
            cell.fill = fill_rec_header
        else:
            cell.fill = fill_param_header
        cell.alignment = align_center
        cell.border = header_border

    # Data Rows
    current_row = 3
    for b in defect_comparison_rows:
        oor_status_str = (
            f"≥4 OOR ({b.params_out_of_range} out of range)"
            if (b.params_out_of_range or 0) >= 4
            else f"<4 OOR ({b.params_out_of_range} out of range)"
        )
        row_vals = [
            b.source,
            b.today_date,
            b.machine_id,
            b.die_id,
            b.manufactured_date,
            b.manufactured_time,
            b.part_serial,
            b.customer_qr,
            b.status or "-",
            b.prescription_id,
            # Parameter Health
            b.monitor_verdict or "-",
            f"{b.params_out_of_range} / {b.params_compared}" if b.params_compared else str(b.params_out_of_range),
            oor_status_str,
            # Predicted
            b.predicted.ok,
            b.predicted.blow_hole,
            b.predicted.non_filling,
            b.predicted.porosity,
            b.predicted.shrinkage,
            b.predicted.chip_off,
            b.predicted.crack,
            # Recorded
            b.recorded.ok,
            b.recorded.blow_hole,
            b.recorded.non_filling,
            b.recorded.porosity,
            b.recorded.shrinkage,
            b.recorded.chip_off,
            b.recorded.crack,
            b.recorded.other,
            # Actual 23 Operating Parameters
            *[b.parameters.get(p_name, "-") for p_name, _ in REPORT_PARAMETERS],
        ]

        for col_idx, val in enumerate(row_vals, 1):
            cell = ws2.cell(row=current_row, column=col_idx, value=val)
            cell.font = font_data_bold if col_idx in [4, 7, 9, 11, 14, 21] else font_data
            cell.alignment = align_center
            cell.border = thin_border
            if current_row % 2 == 0:
                cell.fill = fill_zebra
        current_row += 1

    # Footnote
    fn_cell2 = ws2.cell(row=current_row + 1, column=1, value="Responsible: Neuriot labs")
    fn_cell2.font = Font(name=font_family, size=9, italic=True, bold=True, color="555555")

    # Column Widths for Sheet 2 (Predicted vs Actual)
    col_widths_s2 = {
        1: 16,   # Source ("Neuriot labs")
        2: 14,   # Today's Date
        3: 16,   # Machine ID
        4: 10,   # Die ID
        5: 18,   # Manufactured Date
        6: 16,   # Manufactured Time
        7: 20,   # Part Serial
        8: 24,   # Customer QR
        9: 16,   # Status (Traceability)
        10: 18,  # Prescription ID
        11: 16,  # Monitor Verdict
        12: 18,  # OOR / Compared
        13: 26,  # OOR Status (≥4 Rule)
        14: 12,  # OK (Predicted)
        15: 14,  # Blow Hole
        16: 14,  # Non-filling
        17: 14,  # Porosity
        18: 14,  # Shrinkage
        19: 14,  # Chip-off
        20: 14,  # Crack
        21: 12,  # OK (Recorded)
        22: 14,  # Blow Hole
        23: 14,  # Non-filling
        24: 14,  # Porosity
        25: 14,  # Shrinkage
        26: 14,  # Chip-off
        27: 14,  # Crack
        28: 12,  # Other
    }
    # Add widths for all 23 Operating Parameters (columns 29 to 51)
    for c_idx in range(29, 29 + len(REPORT_PARAMETERS)):
        col_widths_s2[c_idx] = 16

    for c_idx, w in col_widths_s2.items():
        ws2.column_dimensions[get_column_letter(c_idx)].width = w

    # =========================================================================
    # SHEET 3: Prediction Accuracy
    # =========================================================================
    ws3 = wb.create_sheet(title="Prediction Accuracy")
    ws3.views.sheetView[0].showGridLines = True

    accuracy_report = compute_prediction_accuracy(defect_comparison_rows)

    fill_gain = PatternFill(start_color="E2F0D9", end_color="E2F0D9", fill_type="solid")  # Soft green
    font_gain = Font(name=font_family, size=9, bold=True, color="385723")
    fill_loss = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")  # Soft orange/red
    font_loss = Font(name=font_family, size=9, bold=True, color="C65911")
    fill_metric_kpi = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    font_kpi_val = Font(name=font_family, size=11, bold=True, color="1F4E79")

    # Banner Title
    ws3.merge_cells("A1:L1")
    ws3["A1"] = "NEURIOT LABS - PREDICTION ACCURACY REPORT"
    ws3["A1"].fill = fill_id_header
    ws3["A1"].font = font_top_header
    ws3["A1"].alignment = align_center

    ws3.merge_cells("A2:L2")
    ws3["A2"] = (
        f"Die: {die or 'All'} | Machine: {machine or 'All'} | Period: {period.upper()} | "
        f"Target: 6 Defect Types (Dual Gate: Prob > 60% & OOR >= 4 | Evaluated after 3 days)"
    )
    ws3["A2"].fill = PatternFill(start_color="203764", end_color="203764", fill_type="solid")
    ws3["A2"].font = Font(name=font_family, size=9, italic=True, color="D9E1F2")
    ws3["A2"].alignment = align_center

    # KPI Summary Cards Block (Rows 4-5) - spans all 12 columns (3 cols each)
    kpis = [
        ("Overall Prediction Accuracy", f"{accuracy_report.overall_accuracy_pct}%", "A4:C4", "A5:C5"),
        ("Total Sample (Predicted Defects)", str(accuracy_report.sample_size), "D4:F4", "D5:F5"),
        ("Confirmed Defects (Gains)", str(accuracy_report.total_gains), "G4:I4", "G5:I5"),
        ("False Alarms (Losses)", str(accuracy_report.total_losses), "J4:L4", "J5:L5"),
    ]
    for label, val, lbl_range, val_range in kpis:
        ws3.merge_cells(lbl_range)
        ws3.merge_cells(val_range)
        top_cell = ws3[lbl_range.split(":")[0]]
        top_cell.value = label
        top_cell.font = font_sub_header
        top_cell.fill = fill_presc_header
        top_cell.alignment = align_center
        top_cell.border = header_border

        v_cell = ws3[val_range.split(":")[0]]
        v_cell.value = val
        v_cell.font = font_kpi_val
        v_cell.fill = fill_metric_kpi
        v_cell.alignment = align_center
        v_cell.border = thin_border

    # Table 1: Defect Category Breakdown
    ws3.merge_cells("A7:E7")
    ws3["A7"] = "Defect Type Breakdown (Target 6 Defects)"
    ws3["A7"].fill = fill_presc_header
    ws3["A7"].font = font_top_header
    ws3["A7"].alignment = align_center

    breakdown_headers = [
        "Defect Type",
        "Predicted Sample",
        "Confirmed (Gains)",
        "False Alarms (Losses)",
        "Accuracy Rate (%)",
    ]
    for col_idx, h in enumerate(breakdown_headers, 1):
        cell = ws3.cell(row=8, column=col_idx, value=h)
        cell.font = font_sub_header
        cell.fill = fill_id_header
        cell.alignment = align_center
        cell.border = header_border

    r_idx = 9
    for item in accuracy_report.breakdown:
        ws3.cell(row=r_idx, column=1, value=item.defect_type).alignment = align_left
        ws3.cell(row=r_idx, column=2, value=item.predicted_count).alignment = align_center
        ws3.cell(row=r_idx, column=3, value=item.gains).alignment = align_center
        ws3.cell(row=r_idx, column=4, value=item.losses).alignment = align_center
        ws3.cell(row=r_idx, column=5, value=f"{item.accuracy_pct}%").alignment = align_center

        for c in range(1, 6):
            cell = ws3.cell(row=r_idx, column=c)
            cell.font = font_data_bold if c in [1, 5] else font_data
            cell.border = thin_border
            if r_idx % 2 == 0:
                cell.fill = fill_zebra
        r_idx += 1

    # Total row for Breakdown
    ws3.cell(row=r_idx, column=1, value="Total / Overall").alignment = align_left
    ws3.cell(row=r_idx, column=2, value=accuracy_report.sample_size).alignment = align_center
    ws3.cell(row=r_idx, column=3, value=accuracy_report.total_gains).alignment = align_center
    ws3.cell(row=r_idx, column=4, value=accuracy_report.total_losses).alignment = align_center
    ws3.cell(row=r_idx, column=5, value=f"{accuracy_report.overall_accuracy_pct}%").alignment = align_center
    for c in range(1, 6):
        cell = ws3.cell(row=r_idx, column=c)
        cell.font = font_data_bold
        cell.fill = fill_metric_kpi
        cell.border = header_border
    r_idx += 2

    # Table 2: Part-Level Gain / Loss Audit Log
    ws3.merge_cells(f"A{r_idx}:L{r_idx}")
    ws3[f"A{r_idx}"] = "Predicted Defects Audit Log (Gains & Losses Detail)"
    ws3[f"A{r_idx}"].fill = fill_pred_header
    ws3[f"A{r_idx}"].font = font_top_header
    ws3[f"A{r_idx}"].alignment = align_center
    r_idx += 1

    audit_headers = [
        "Part Serial",
        "Customer QR",
        "Status",
        "Prescription ID",
        "Machine ID",
        "Die ID",
        "Manufactured Date",
        "Manufactured Time",
        "Defect Type",
        "Predicted Flag",
        "Actual Recorded",
        "Outcome",
    ]
    for col_idx, h in enumerate(audit_headers, 1):
        cell = ws3.cell(row=r_idx, column=col_idx, value=h)
        cell.font = font_sub_header
        cell.fill = fill_id_header
        cell.alignment = align_center
        cell.border = header_border
    r_idx += 1

    for row_item in accuracy_report.audit_rows:
        ws3.cell(row=r_idx, column=1, value=row_item.part_serial).alignment = align_center
        ws3.cell(row=r_idx, column=2, value=row_item.customer_qr).alignment = align_center
        ws3.cell(row=r_idx, column=3, value=row_item.status or "-").alignment = align_center
        ws3.cell(row=r_idx, column=4, value=row_item.prescription_id).alignment = align_center
        ws3.cell(row=r_idx, column=5, value=row_item.machine_id).alignment = align_center
        ws3.cell(row=r_idx, column=6, value=row_item.die_id).alignment = align_center
        ws3.cell(row=r_idx, column=7, value=row_item.manufactured_date).alignment = align_center
        ws3.cell(row=r_idx, column=8, value=row_item.manufactured_time).alignment = align_center
        ws3.cell(row=r_idx, column=9, value=row_item.defect_type).alignment = align_left
        ws3.cell(row=r_idx, column=10, value=row_item.predicted_label).alignment = align_center
        ws3.cell(row=r_idx, column=11, value=row_item.recorded_label).alignment = align_center

        outcome_cell = ws3.cell(row=r_idx, column=12, value=row_item.outcome)
        outcome_cell.alignment = align_center
        if row_item.outcome == "GAIN":
            outcome_cell.fill = fill_gain
            outcome_cell.font = font_gain
        else:
            outcome_cell.fill = fill_loss
            outcome_cell.font = font_loss

        for c in range(1, 12):
            cell = ws3.cell(row=r_idx, column=c)
            cell.font = font_data_bold if c in [1, 9] else font_data
            cell.border = thin_border
            if r_idx % 2 == 0:
                cell.fill = fill_zebra
        outcome_cell.border = thin_border
        r_idx += 1

    # Footnote
    fn_cell3 = ws3.cell(row=r_idx + 1, column=1, value="Responsible: Neuriot labs")
    fn_cell3.font = Font(name=font_family, size=9, italic=True, bold=True, color="555555")
    fn_note = ws3.cell(
        row=r_idx + 2,
        column=1,
        value="Domain note: Total sample includes predicted defects across 6 categories. Non-defects that became defects are omitted. Parts evaluated after 3 days of shop floor inspection.",
    )
    fn_note.font = Font(name=font_family, size=8, italic=True, color="777777")

    # Column Widths for Sheet 3 (Prediction Accuracy)
    col_widths_s3 = {
        1: 20,   # Part Serial
        2: 24,   # Customer QR
        3: 16,   # Status (Traceability)
        4: 18,   # Prescription ID
        5: 16,   # Machine ID
        6: 12,   # Die ID
        7: 18,   # Manufactured Date
        8: 16,   # Manufactured Time
        9: 18,   # Defect Type
        10: 18,  # Predicted Flag
        11: 18,  # Actual Recorded
        12: 16,  # Outcome (GAIN / LOSS)
    }
    for c_idx, w in col_widths_s3.items():
        ws3.column_dimensions[get_column_letter(c_idx)].width = w

    # Output to in-memory bytes stream
    excel_stream = io.BytesIO()
    wb.save(excel_stream)
    excel_stream.seek(0)
    return excel_stream

