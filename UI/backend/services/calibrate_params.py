import pandas as pd
import numpy as np
import json
import psycopg2
import sys
import re

DB_CONFIG = {
    "host":     "aws-1-ap-southeast-2.pooler.supabase.com",
    "dbname":   "postgres",
    "user":     "postgres.nnflwohgewhkqqjfvote",
    "password": "Datamgnt25!#",
    "options":  "-c search_path=rico"
}

names_UOM = {
    'ACCEL. POINT mm ': ['ACCEL. POINT', 'mm'], 'BISCUIT THICKNESS mm ': ['BISCUIT THICKNESS', 'mm'], 'CLAMP FORCE (%) ': ['CLAMP FORCE', '%'], 
    'CLAMP TONNAGE (T) ': ['CLAMP TONNAGE', 'T'], 'CLAMP TONNAGE(HE.LOW) % ': ['CLAMP TONNAGE(HE.LOW)', '%'], 'CLAMP TONNAGE(HE.LOW) MN ': ['CLAMP TONNAGE(HE.LOW)', 'MN'], 
    'CLAMP TONNAGE(HE.UP) % ': ['CLAMP TONNAGE(HE.UP)', '%'], 'CLAMP TONNAGE(OP.LOW) % ': ['CLAMP TONNAGE(OP.LOW)', '%'], 'CLAMP TONNAGE(OP.UP) % ': ['CLAMP TONNAGE(OP.UP)', '%'], 
    'COOLING WATER FLOW RATE(MOV.) L/min ': ['COOLING WATER FLOW RATE(MOV.)', 'L/min'], 'COOLING WATER FLOW RATE(STA.) L/min ': ['COOLING WATER FLOW RATE(STA.)', 'L/min'], 
    'CURING TIME sec ': ['CURING TIME', 'sec'], 'DEACEL. POINT mm ': ['DEACEL. POINT',  'mm'], 'DIE OPEN CORE OUT TIME sec ': ['DIE OPEN CORE OUT TIME', 'sec'], 
    'DIE-CLOSE CORE IN TIME sec ': ['DIE-CLOSE CORE IN TIME', 'sec'], 'EJECTOR TIME sec ': ['EJECTOR TIME', 'sec'], 'EXTRACT TIME sec ': ['EXTRACT TIME', 'sec'], 
    'FIXED DIE TEMP (F-1) C ': ['FIXED DIE TEMP (F-1)', 'C'], 'FIXED DIE TEMP (F-2) C ': ['FIXED DIE TEMP (F-2)', 'C'], 'FURNACE METAL TEMP. C ': ['FURNACE METAL TEMP.', 'C'], 
    'HIGH SHOT COUNT ': ['HIGH SHOT COUNT', ' '], 'INTEN. TIME msec ': ['INTEN. TIME', 'msec'], 'INTENSIFICATION ACC. PRESSURE MPa ': ['INTENSIFICATION ACC. PRESSURE', 'mPa'], 
    'JET COOLING PRESSURE kgf/cm2 ': ['JET COOLING PRESSURE', 'kgf/cm2'], 'METAL PRESS. Mpa ': ['METAL PRESS.', 'mPa'], 'MOVING DIE TEMP (M-1) C ': ['MOVING DIE TEMP (M-1)', 'C'],
    'MOVING DIE TEMP (M-2) C ': ['MOVING DIE TEMP (M-2)', 'C'], 'NG COUNTER ': ['NG COUNTER', ' '], 'POURING TIME sec ': ['POURING TIME', 'sec'], 'SHOT ACC. PRESSURE MPa ': ['SHOT ACC. PRESSURE', 'Mpa'], 
    'SHOT FWD TIME sec ': ['SHOT FWD TIME', 'sec'], 'SLIDE TEMP-1 (S-1) C ': ['SLIDE TEMP-1 (S-1)', 'C'], 'SPRAY TIME sec ': ['SPRAY TIME', 'sec'], 
    'V1 m/sec ': ['V1', 'm/sec'], 'V2 m/sec) ': ['V2', 'm/sec'], 'V3 m/sec ': ['V3', 'm/sec'], 'V4 m/sec ': ['V4', 'm/sec'], 
    'VACUUM PRESSURE mbar ': ['VACUUM PRESSURE', 'mbar']
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

    cur.execute("SELECT id_part FROM part_quality")
    existing_ids = {row[0] for row in cur.fetchall()}

    conn.close()

    mask = ~df["id_part"].isin(existing_ids)
    df = df[mask]
    

    # groups = {value: group_df.drop(columns=["id_die"]).reset_index(drop=True)
    #         for value, group_df in df.groupby("id_die")}
    # print(groups.keys())
    # baselines = {}


    bl_params = {}
    # sub = groups[die]
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

        uom = names_UOM.get(param, ["Unknown", ""])[1]
        
        bl_params[param] = (new_avg, new_tol, new_avg - new_tol, new_avg + new_tol, uom)
             
    print(num_samples) 
    return [bl_params, num_samples]

if __name__ == "__main__":
    main()