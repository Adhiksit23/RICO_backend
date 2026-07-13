import psycopg2
import json
from datetime import date

DB_CONFIG = {
    "host":     "aws-1-ap-southeast-2.pooler.supabase.com",
    "dbname":   "postgres",
    "user":     "postgres.nnflwohgewhkqqjfvote",
    "password": "Datamgnt25!#",
    "options":  "-c search_path=rico"
    
}



names_UOM = {'accel_point': ['ACCEL. POINT', 'mm'], 
             'biscuit_thickness': ['BISCUIT THICKNESS', 'mm'], 
             'clamp_force_pct': ['CLAMP FORCE', '%'], 
            'clamp_tonnage': ['CLAMP TONNAGE', 'Mn'], 
            'curing_time': ['CURING TIME', 'sec'], 
            'deaccel_point': ['DEACEL. POINT',  'mm'], 
            'die_open_core_out_time': ['DIE OPEN CORE OUT TIME', 'sec'], 
            'die_close_core_in_time': ['DIE-CLOSE CORE IN TIME', 'sec'], 
            'ejector_time': ['EJECTOR TIME', 'sec'],
            'extract_time': ['EXTRACT TIME', 'sec'],  
            'furnace_metal_temp': ['FURNACE METAL TEMP.', 'C'], 
            'intensification_time': ['INTEN. TIME', 'msec'], 
            'intensification_acc_pressure': ['INTENSIFICATION ACC. PRESSURE', 'mPa'], 
            'metal_pressure': ['METAL PRESS.', 'mPa'],
            'pouring_time': ['POURING TIME', 'sec'], 
            'shot_acc_pressure': ['SHOT ACC. PRESSURE', 'Mpa'], 
            'shot_fwd_time': ['SHOT FWD TIME', 'sec'], 
            'spray_time': ['SPRAY TIME', 'sec'], 
            'v1_speed': ['V1', 'm/sec'], 
            'v2_speed': ['V2', 'm/sec'], 
            'v3_speed': ['V3', 'm/sec'], 
            'v4_speed': ['V4', 'm/sec'], 
            "cycle_time": ["cycletime value (sec)", "sec"]}

 

PARAM_MAP = {
    "cycle_time": "cycletime value (sec)",
    "die_close_core_in_time": "DIE CLOSE/CORE IN Parameter (sec)value",
    "pouring_time":"POURING-step value (sec)",
    "shot_fwd_time": "SHOT FWD-step value (sec)",
    "curing_time": "COOLING-step value (sec)",
    "die_open_core_out_time": "DIE OPEN/CORE OUT-step value (sec)",
    "ejector_time": "EJECTOR-step value (sec)",
    "extract_time": "EXTRACTOR-step value (sec)",
    "spray_time": "SPRAY-step value (sec)",
    "v1_speed": "SPEED 1 (m/sec)value",
    "v2_speed": "SPEED 2 (m/sec)value",
    "v3_speed": "SPEED 3 (m/sec)value",
    "v4_speed": "SPEED 4(m/sec)value",
    "accel_point": "ACC POSITION 1(mm)value",
    "deaccel_point": "DEACC POSITION 1(mm)value",
    "intensification_time": "INTESIFICAITON TIME(msec)value",
    "metal_pressure": "METAL PRESSURE(Mpa)value",
    "biscuit_thickness": "BISCUIT THICKNESS(mm)value",
    "clamp_force_pct": "CLAMP FORCE(%)value",
    "clamp_tonnage": "CLAMP TONNAGE(MN)value",
    "shot_acc_pressure": "SHOT ACC. PRESSURE value",
    "intensification_acc_pressure": "INTESIFICAITON ACC. PRESSUREvalue",
    "furnace_metal_temp": "METAL TEMP.value",

}
DIE_LIST = ["S14", "S16", "S17"]

def store_defect(cur, row, id_client):
    defect = row['rejection_reason']
    category = row['rejectionCategory']
    zone_sub_zone = row['rejection_zone']
    zone = zone_sub_zone[0]
    sub_zone = zone_sub_zone.split("Sub Zone ")[-1]
    view = row['rejectionView']
    part_id = row['part_id']
    id_die = row['plcReading']['part_name'][-3:]
    id_machine = row['plcReading']['machine_name']
    cur.execute("""
            INSERT INTO part_quality (id_part, id_die, id_client, category, zone, sub_zone, view, id_machine, defect_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (part_id, id_die, id_client, category, zone, sub_zone, view, id_machine, defect))

def update_date_path() -> str:
    #Connect to database
    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()

    cur.execute("SELECT MAX(created_at) FROM part")
    last_date = cur.fetchone()[0]
    # Fall back to a default if the table is empty
    if last_date is None:
        date_from = "2026-01-01"
    else:
        date_from = last_date.strftime("%Y-%m-%d")

    date_to = date.today().strftime("%Y-%m-%d")

    data_path = f"{{BASE_URL}}/reports/report/data?dateFrom={{date_from}}&dateTo={{date_to}}"
    return data_path

def process_data(data):
       
    if(data['plcReading'] == None):
        #0606125120955
        return

    #Start Enterring Data

    part_id = data['part_id']
    client_code = "R437111511"
    print(part_id)
    if(client_code in part_id):
        print("Shot data missing, getting part data from client")
        return
    
    id_machine = data['plcReading']['machine_name']
    id_die = data['plcReading']['part_name'][-3:]
    if id_die not in DIE_LIST:
        return
    print(id_die)
    date = data['plcReading']['shot_date']

    #Connect to database
    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()
    #Get client ID to match with  
    cur.execute(
    "SELECT id_client FROM client WHERE name = %s",
    ('Suzuki',)
    )
    id_client = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO part (id_part, id_die, id_client, id_machine, manufactored_on, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (id_part) DO UPDATE SET
            id_die = EXCLUDED.id_die,
            id_client = EXCLUDED.id_client,
            id_machine = EXCLUDED.id_machine,
            manufactored_on = EXCLUDED.manufactored_on
""", (part_id, id_die, id_client, id_machine, date, date))

    for param, val in data['plcReading'].items():
        if(param not in PARAM_MAP):
            continue
        param_name = names_UOM[param][0]
        
        uom = names_UOM[param][1]
        cur.execute("""
                INSERT INTO operating_parameter (id_part, id_die, id_client, id_machine, parameter_name, "UOM", value, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id_part, parameter_name) DO UPDATE SET
                    id_die = EXCLUDED.id_die,
                    id_client = EXCLUDED.id_client,
                    id_machine = EXCLUDED.id_machine,
                    value = EXCLUDED.value,
                    updated_at = EXCLUDED.updated_at
        """, (part_id, id_die, id_client, id_machine, param_name, uom, val, date, date))

    if(data['reason'] != "" and data['reason'] != "RECOVERY_PENDING_AFTER_BACKEND_RESTART"):
        print(data['reason'])
        store_defect(cur, data, id_client)

    conn.commit()
    cur.close()
    conn.close()
    return