import pandas as pd
import numpy as np
import json
import psycopg2
import sys
import re

from services.config import (
    DB_CONFIG
)

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


def main(machine_id, die):
   
    print(die)
    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()

    num_samples = 0

    #Adjusts so that it takes for specific die and machine
    query = """
        SELECT c.*
        FROM operating_parameter c
        WHERE id_part IN (
            SELECT id_part FROM part
            WHERE id_die = %s and id_machine = %s
        );

    """
    df_raw = pd.read_sql(query, conn, params=(die, machine_id))
    df = df_raw.pivot(index=["id_part", "id_die"], columns="parameter_name", values="value")
    param_names = [col for col in df.columns if col not in ["id_part", "id_die"]]
    df.columns.name = None
    df = df.reset_index()   

    cur.execute("SELECT id_part FROM part_quality WHERE id_die = %s", (die,)) 
    existing_ids = {row[0] for row in cur.fetchall()}

    conn.close()

    mask = ~df["id_part"].isin(existing_ids)
    df = df[mask]


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

        uom = names_UOM[param]
        
        bl_params[param] = (new_avg, new_tol, max(0, new_avg - new_tol), new_avg + new_tol, uom)
    print("Ranges calculated: ", bl_params)
    print("Number of samples used for calculation: ", num_samples) 
    return [bl_params, num_samples]

if __name__ == "__main__":
    main()