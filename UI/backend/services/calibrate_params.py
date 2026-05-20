
import pandas as pd
import numpy as np
import json
import psycopg2
import sys

import warnings, re, os
import matplotlib.pyplot as plt
try:
    from lightgbm import LGBMClassifier
except: os.system("pip install lightgbm -q"); from lightgbm import LGBMClassifier
try:
    from xgboost import XGBClassifier
except: os.system("pip install xgboost -q"); from xgboost import XGBClassifier
warnings.filterwarnings("ignore")


def main():

    #Database configurations for access
    DB_CONFIG = {
        "host":     "localhost",
        "port":     5432,
        "dbname":   "Oil Pan Dataset",
        "user":     "postgres",
        "password": "Datamgnt25!#"
    }
    
    names_UOM = {'ACCEL. POINT mm ': ['ACCEL. POINT', 'mm'], 'BISCUIT THICKNESS mm ': ['BISCUIT THICKNESS', 'mm'], 'CLAMP FORCE (%) ': ['CLAMP FORCE', '%'], 
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
            'VACUUM PRESSURE mbar ': ['VACUUM PRESSURE', 'mbar']}

    #Connect to database
    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()

    #The target outputs
    TARGET_DEFECTS = ["Blow Hole","Crack","Non filling","Porosity","Shrinkage","Chipoff"]
    REPORT_LINES = []
    def rprint(*args):
        line = " ".join(str(a) for a in args)
        REPORT_LINES.append(line)
        print(line)

    def safe_cn(col):
        return re.sub(r"[^a-zA-Z0-9]","_",str(col)).strip("_").replace("__","_")

    #Will add such that it takes data from part_quality data for defect
    query = """
        SELECT id_part, parameter_name, value, id_die, id_machine
        FROM operating_parameter
        ORDER BY id_part
    """

    df_raw = pd.read_sql(query, conn)
    conn.close()


    # Pivot: each unique 'name' becomes a column, parent_id becomes the index
    df = df_raw.pivot(index=["id_part", "id_die"], columns="parameter_name", values="value")
    param_names = [col for col in df.columns if col not in ["id_part", "id_die"]]
    # Optional: flatten the column index
    df.columns.name = None
    df = df.reset_index()

    #Temporarily add data to simulate no defects for testing
    for col in TARGET_DEFECTS:
        df[col] = 0

    groups = {value: group_df.drop(columns=["id_die"]).reset_index(drop=True)
            for value, group_df in df.groupby("id_die")}



    baselines = {}

    for die in groups:
        bl_params = {}
        for defect in TARGET_DEFECTS:
            sub = groups[die][(groups[die][defect]==0)]
            for param in param_names:
                if param not in sub.columns:
                    continue
                vals = sub[param]
                avg = vals.mean()
                tol = max((vals - avg).abs().mean(), 1e-9)
                if param in bl_params:
                    prev_avg, prev_tol, _, _, _= bl_params[param]
                    new_avg = (prev_avg + avg) / 2
                    new_tol = max((prev_tol + tol) / 2, 1e-9)
                else:
                    new_avg = avg
                    new_tol = tol

                bl_params[param] = (new_avg, new_tol, new_avg - new_tol, new_avg + new_tol,names_UOM[param][1] )
        baselines[die] = bl_params
                

    return baselines["S14"]

if __name__ == "__main__":
    main()