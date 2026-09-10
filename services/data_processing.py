import psycopg2
import json
from datetime import date, datetime, timezone, timedelta


# DB_CONFIG = {
#     "host":     "aws-1-ap-southeast-2.pooler.supabase.com",
#     "dbname":   "postgres",
#     "user":     "postgres.nnflwohgewhkqqjfvote",
#     "password": "Datamgnt25!#",
#     "options":  "-c search_path=rico"    
    
# }


from services.config import (
    DB_CONFIG
)



names_UOM = {'accelPoint': ['ACCEL. POINT', 'mm'], 
             'biscuitThickness': ['BISCUIT THICKNESS', 'mm'], 
             'clampForcePercent': ['CLAMP FORCE', '%'], 
            'clampTonnage': ['CLAMP TONNAGE', 'Mn'], 
            'curingTime': ['CURING TIME', 'sec'], 
            'deaccelPoint': ['DEACEL. POINT',  'mm'], 
            'dieOpenCoreOutTime': ['DIE OPEN CORE OUT TIME', 'sec'], 
            'dieCloseCoreInTime': ['DIE-CLOSE CORE IN TIME', 'sec'], 
            'ejectorTime': ['EJECTOR TIME', 'sec'],
            'extractTime': ['EXTRACT TIME', 'sec'],  
            'furnaceMetalTemp': ['FURNACE METAL TEMP.', 'C'], 
            'intensificationTime': ['INTEN. TIME', 'msec'], 
            'intensificationAccPressure': ['INTENSIFICATION ACC. PRESSURE', 'mPa'], 
            'metalPressure': ['METAL PRESS.', 'mPa'],
            'pouringTime': ['POURING TIME', 'sec'], 
            'shotAccPressure': ['SHOT ACC. PRESSURE', 'Mpa'], 
            'shotForwardTime': ['SHOT FWD TIME', 'sec'], 
            'sprayTime': ['SPRAY TIME', 'sec'], 
            'v1Speed': ['V1', 'm/sec'], 
            'v2Speed': ['V2', 'm/sec'], 
            'v3Speed': ['V3', 'm/sec'], 
            'v4Speed': ['V4', 'm/sec'], 
            "cycleTime": ["cycletime value (sec)", "sec"]}

 
MACHINE_IDS = ["UBE 850T-1", "UBE 850T-2", "UBE 850T-3"]

PARAM_MAP = {
    "cycleTime": "cycletime value (sec)",
    "dieCloseCoreInTime": "DIE CLOSE/CORE IN Parameter (sec)value",
    "pouringTime":"POURING-step value (sec)",
    "shotForwardTime": "SHOT FWD-step value (sec)",
    "curingTime": "COOLING-step value (sec)",
    "dieOpenCoreOutTime": "DIE OPEN/CORE OUT-step value (sec)",
    "ejectorTime": "EJECTOR-step value (sec)",
    "extractTime": "EXTRACTOR-step value (sec)",
    "sprayTime": "SPRAY-step value (sec)",
    "v1Speed": "SPEED 1 (m/sec)value",
    "v2Speed": "SPEED 2 (m/sec)value",
    "v3Speed": "SPEED 3 (m/sec)value",
    "v4Speed": "SPEED 4(m/sec)value",
    "accelPoint": "ACC POSITION 1(mm)value",
    "deaccelPoint": "DEACC POSITION 1(mm)value",
    "intensificationTime": "INTESIFICAITON TIME(msec)value",
    "metalPressure": "METAL PRESSURE(Mpa)value",
    "biscuitThickness": "BISCUIT THICKNESS(mm)value",
    "clampForcePercent": "CLAMP FORCE(%)value",
    "clampTonnage": "CLAMP TONNAGE(MN)value",
    "shotAccPressure": "SHOT ACC. PRESSURE value",
    "intensificationAccPressure": "INTESIFICAITON ACC. PRESSUREvalue",
    "furnaceMetalTemp": "METAL TEMP.value",

}
DIE_LIST = ["S14", "S16", "S17", "S18"]

def store_defect(cur, row, id_client, id_machine):
    defect = row['rejection']['reason']
    category = row['rejection']['category']
    zone = row['rejection']['zone']
    sub_zone = row['rejection']['subZone']
    view = row['rejection']['view']
    part_id = row['part']['id']
    id_die = row['part']['die']
    # cur.execute("""
    #         INSERT INTO part_quality (id_part, id_die, id_client, category, zone, sub_zone, view, id_machine, defect_type)
    #         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    # """, (part_id, id_die, id_client, category, zone, sub_zone, view, id_machine, defect))

    cur.execute("""
    INSERT INTO part_quality (id_part, id_die, id_client, updated_at, category, zone, sub_zone, view, id_machine, defect_type)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (id_part) DO UPDATE SET
        id_die = EXCLUDED.id_die,
        id_client = EXCLUDED.id_client,
        category = EXCLUDED.category,
        zone = EXCLUDED.zone,
        sub_zone = EXCLUDED.sub_zone,
        view = EXCLUDED.view,
        id_machine = EXCLUDED.id_machine,
        defect_type = EXCLUDED.defect_type
""", (part_id, id_die, id_client, datetime.now(), category, zone, sub_zone, view, id_machine, defect))

def date_processing(date):
    naive = datetime.fromisoformat(date.replace("Z", ""))
    ist = timezone(timedelta(hours=5, minutes=30))
    correct_dt = naive.replace(tzinfo=ist)  # now correctly IST-aware
    return correct_dt

def process_data(data):
       
    if(data['shot']['parameters'] == None):
        return

    #Start Enterring Data

    part_id = data['part']['id']
    client_code = "R437111511"
    print("Getting part id: " + part_id)
    if(client_code in part_id):
        print("PROBLEM IN API")
        return
    
    # print("reason of defect:", data['rejection'])
    id_machine = data['shot']['machine'] #This needs to be updated to use stored machine id
    id_die = data['part']['die']
    # print(id_die)
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
        """, (part_id, id_die, id_client, id_machine, param_name, uom, val, date_ist, datetime.now()))

    print(data['rejection']['reason'])
    if(data['rejection']['reason'] != None):
        print(data['rejection']['reason'])
        store_defect(cur, data, id_client, id_machine)

    conn.commit()
    cur.close()
    conn.close()
    return

def store_quality_pred(predictions, part, TARGET_DEFECTS, cur):
    id_part = part["id_part"].iloc[0]
    print(id_part)
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