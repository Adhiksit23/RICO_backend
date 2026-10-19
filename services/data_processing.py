import psycopg2
import json
from datetime import date, datetime, timezone, timedelta


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
 
MACHINE_IDS = ["UBE 850T-1", "UBE 850T-2", "UBE 850T-3"]

PARAM_LIST = [
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

DIE_LIST = ["S14", "S16", "S17", "S18"]

def store_defect(cur, row, date_ist, id_client, id_machine):
    defect = row['rejection']['reason']
    category = row['rejection']['category']
    zone = row['rejection']['zone']
    sub_zone = row['rejection']['subZone']
    view = row['rejection']['view']
    part_id = row['part']['id']
    id_die = row['part']['die']

    cur.execute("""
    INSERT INTO part_quality (id_part, id_die, id_client, updated_at, category, zone, sub_zone, view, id_machine, manufactored_on, defect_type)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (id_part) DO UPDATE SET
        id_die = EXCLUDED.id_die,
        id_client = EXCLUDED.id_client,
        category = EXCLUDED.category,
        zone = EXCLUDED.zone,
        sub_zone = EXCLUDED.sub_zone,
        view = EXCLUDED.view,
        id_machine = EXCLUDED.id_machine,
        defect_type = EXCLUDED.defect_type,
        manufactored_on = EXCLUDED.manufactored_on
""", (part_id, id_die, id_client, datetime.now(), category, zone, sub_zone, view, id_machine, date_ist, defect))

def date_processing(date):
    naive = datetime.fromisoformat(date.replace("Z", ""))
    ist = timezone(timedelta(hours=5, minutes=30))
    correct_dt = naive.replace(tzinfo=ist)  # now correctly IST-aware
    return correct_dt

def process_data(data):
       
    if(data['shot']['parameters'] == None):
        return


    part_id = data['part']['id']
    client_code = "R437111511"
    print("Getting part id: " + part_id)
    if(client_code in part_id):
        print("PROBLEM IN API")
        return
    
    id_machine = data['shot']['machine'] 
    id_die = data['part']['die']
    if id_die not in DIE_LIST:
        return

    
    recorded_stamp = data['shot']['recordedAt']
    date_ist = date_processing(date=recorded_stamp)

    #Connect to database
    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()
    #Get client ID to match with  
    cur.execute(
    "SELECT id_client FROM client WHERE name = %s",
    ('Suzuki',)
    )
    id_client = cur.fetchone()[0]

    cur.execute(
        "SELECT id_machine FROM machine WHERE id_client = %s",
        ('1',)
        )
    id_machine = cur.fetchone()[0]
    print(id_machine)

    #Start entering data
    cur.execute("""
        INSERT INTO part (id_part, id_die, id_client, id_machine, manufactored_on, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (id_part) DO UPDATE SET
            id_die = EXCLUDED.id_die,
            id_client = EXCLUDED.id_client,
            id_machine = EXCLUDED.id_machine,
            manufactored_on = EXCLUDED.manufactored_on
""", (part_id, id_die, id_client, id_machine, date_ist, datetime.now()))

    for param, val in data['shot']['parameters'].items():
        if(param not in PARAM_LIST):
            continue
        param_name = param
        uom = names_UOM[param]
        
        cur.execute("""
                INSERT INTO operating_parameter (id_part, id_die, id_client, id_machine, parameter_name, "UOM", value, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id_part, parameter_name) DO UPDATE SET
                    id_die = EXCLUDED.id_die,
                    id_client = EXCLUDED.id_client,
                    id_machine = EXCLUDED.id_machine,
                    value = EXCLUDED.value,
                    updated_at = EXCLUDED.updated_at
        """, (part_id, id_die, id_client, id_machine, param_name, uom, val, date_ist, datetime.now()))

    print("Defect seen is: ", data['rejection']['reason'])
    if(data['rejection']['reason'] != None):
        print("Defect being recored is: ", data['rejection']['reason'])
        store_defect(cur, data, date_ist, id_client, id_machine)

    conn.commit()
    cur.close()
    conn.close()
    return

def store_quality_pred(predictions, part, TARGET_DEFECTS, cur):
    id_part = part["id_part"].iloc[0]
    print("Storing predictions for: ", id_part)
    id_die = part["id_die"].iloc[0]
    id_machine = part["id_machine"].iloc[0]
    id_client = part["id_client"].iloc[0]
    for i in range(len(TARGET_DEFECTS)): 
        cur.execute("""
                INSERT INTO part_quality_prediction (id_part, id_die, id_client, id_machine, defect_type, defect_probability, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id_part, defect_type) DO UPDATE SET
                    defect_probability = EXCLUDED.defect_probability,
                    updated_at = EXCLUDED.updated_at
        """, (id_part, id_die, int(id_client), id_machine, TARGET_DEFECTS[i], predictions[i], datetime.now(), datetime.now()))
    return