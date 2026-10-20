import pandas as pd
import numpy as np
import json
import psycopg2
import sys
import re

from services.config import (
    DB_CONFIG
)

PARAM_MAPPING = {
    "cycletime_value_sec": "cycle_time",
    "DIE-CLOSE CORE IN TIME": "die_close_core_in_time",
    "POURING_step_value_sec": "pouring_time",
    "SHOT_FWD_step_value_sec": "shot_fwd_time",
    "COOLING_step_value_sec": "curing_time",
    "DIE_OPEN_CORE_OUT_step_value_sec": "die_open_core_out_time",
    "EJECTOR_step_value_sec": "ejector_time",
    "EXTRACTOR_step_value_sec": "extract_time",
    "SPRAY_step_value_sec": "spray_time",
    "SPEED_1_m_sec_value": "v1_speed",
    "SPEED_2_m_sec_value": "v2_speed",
    "SPEED_3_m_sec_value": "v3_speed",
    "SPEED_4_m_sec_value": "v4_speed",
    "ACC_POSITION_1_mm_value": "accel_point",
    "DEACC_POSITION_1_mm_value": "deaccel_point",
    "INTESIFICAITON_TIME_msec_value": "intensification_time",
    "MATEL_PRESSURE_Mpa_value": "metal_pressure",
    "BISCUIT_THICKNESS_mm_value": "biscuit_thickness",
    "CLAMP_FORCE__value": "clamp_force_pct",
    "CLAMP_TONNAGE_MN_value": "clamp_tonnage",
    "SHOT_ACC_PRESSURE_value": "shot_acc_pressure",
    "INTESIFICAITON_ACC_PRESSUREvalue": "intensification_acc_pressure",
    "METAL_TEMP_value": "furnace_metal_temp",
}

names_UOM = {
    'accel_point': 'mm',
    'biscuit_thickness': 'mm',
    'clamp_force_pct': '%',
    'clamp_tonnage': 'Mn',
    'curing_time': 'sec',
    'deaccel_point': 'mm',
    'die_open_core_out_time': 'sec',
    'die_close_core_in_time': 'sec',
    'ejector_time': 'sec',
    'extract_time': 'sec',
    'furnace_metal_temp': 'C',
    'intensification_time': 'msec',
    'intensification_acc_pressure': 'mPa',
    'metal_pressure': 'mPa',
    'pouring_time': 'sec',
    'shot_acc_pressure': 'Mpa',
    'shot_fwd_time': 'sec',
    'spray_time': 'sec',
    'v1_speed': 'm/sec',
    'v2_speed': 'm/sec',
    'v3_speed': 'm/sec',
    'v4_speed': 'm/sec',
    'cycle_time': 'sec',
}
TARGET_DEFECTS = ["Blow Hole","Crack","Non filling","Porosity","Shrinkage","Chipoff"]
def safe_cn(col):
        return re.sub(r"[^a-zA-Z0-9]","_",str(col)).strip("_").replace("__","_")


def main(machine_id, die, start_date=None, end_date=None):
   
    print(f"[calibrate_params] die={die}, machine={machine_id}, start_date={start_date}, end_date={end_date}")
    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()

    num_samples = 0

    # Filter parts for specific die, machine, and optional date range
    part_clauses = ["id_die = %s", "id_machine = %s"]
    part_params = [die, machine_id]

    if start_date:
        part_clauses.append("manufactored_on >= %s::date")
        part_params.append(start_date.strip())
    if end_date:
        part_clauses.append("manufactored_on < (%s::date + INTERVAL '1 day')")
        part_params.append(end_date.strip())

    part_where = " AND ".join(part_clauses)

    query = f"""
        SELECT c.*
        FROM operating_parameter c
        WHERE id_part IN (
            SELECT id_part FROM part
            WHERE {part_where}
        );
    """
    df_raw = pd.read_sql(query, conn, params=tuple(part_params))
    if df_raw.empty:
        conn.close()
        print("[calibrate_params] No operating parameters found for selected filter criteria.")
        return [{}, 0]

    # part_ids = df_raw["id_part"].unique().tolist()
    # print("Part Ids seen: ", part_ids)
    print("Recieved parts for calculation")
    df = df_raw.pivot(index=["id_part", "id_die"], columns="parameter_name", values="value")
    param_names = [col for col in df.columns if col not in ["id_part", "id_die"]]
    df.columns.name = None
    df = df.reset_index()   

    cur.execute("SELECT id_part FROM part_quality WHERE id_die = %s", (die,)) 
    existing_ids = {row[0] for row in cur.fetchall()}

    conn.close()

    mask = ~df["id_part"].isin(existing_ids)
    df = df[mask]

    print("Removed defective parts from list")

    bl_params = {}
    sub = df[df["id_die"] == die].drop(columns=["id_die"]).reset_index(drop=True)
    for param in param_names:
        if param not in sub.columns:
            continue
        vals = sub[param]
        if(num_samples == 0):   
            num_samples = len(vals)
        avg = vals.mean()
        tol = max((vals - avg).abs().mean(), 1e-9)
        if param in bl_params:
            prev_avg, prev_tol, _, _, _= bl_params[param]
            new_avg = (prev_avg + avg) / 2
            new_tol = max((prev_tol + tol) / 2, 1e-9)
        else:
            new_avg = avg
            new_tol = tol

        # if die == 'S16':
        #     uom = names_UOM.get(PARAM_MAPPING[param], "")
        # else:
        uom = names_UOM.get(param, "")  
        
        bl_params[param] = (new_avg, new_tol, max(0, new_avg - new_tol), new_avg + new_tol, uom)
    print("Ranges calculated: ", bl_params)
    print("Number of samples used for calculation: ", num_samples) 
    return [bl_params, num_samples]

if __name__ == "__main__":
    main()