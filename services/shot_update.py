import psycopg2
from datetime import datetime, date, timedelta, timezone
import requests

BASE_URL = "http://192.168.100.136:9090/api"
AUTH_PATH = "/auth/login"
 
USERNAME = "sanjeev"
PASSWORD = "Sanjeev@rico123"

TOKEN_JSON_PATH = "token"

#Database configurations for access
DB_CONFIG = {
    "host":     "aws-1-ap-southeast-2.pooler.supabase.com",
    "dbname":   "postgres",
    "user":     "postgres.nnflwohgewhkqqjfvote",
    "password": "Datamgnt25!#",
    "options":  "-c search_path=rico"
    
}

DIE_LIST = ["S14", "S16", "S17"]

SHIFT_CODE = "ALL"
LIMIT = "200"
PAGE = "1"
SHOT_RESULT = "ALL"
PAGE_SIZE = "200"
IP = "192.168.117.201"


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

def update_date_path_shot() -> str:
    #Connect to database
    # Fall back to a default if the table is empty
   
    date_from = date.today().strftime("%Y-%m-%dT00:00:00")
    date_to = (date.today() + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")

    # date_from = "2026-07-16T00:00:00"
    # date_to = "2026-07-16T12:00:00"
    data_path = f"/plc-monitor/readings/history?ip={IP}&from={date_from}&to={date_to}&limit={LIMIT}&page={PAGE}&pageSize={PAGE_SIZE}&shift={SHIFT_CODE}l&shotResult={SHOT_RESULT}"
    return data_path



def get_auth_token_shot() -> str:
    """Step 1: POST credentials, pull the token out of the JSON response."""
    url = f"{BASE_URL}{"/v1"}{AUTH_PATH}"
    payload = {"username": USERNAME, "password": PASSWORD}
 
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    body = resp.json()
 
    token = body
    for key in TOKEN_JSON_PATH.split("."):
        token = token[key]
 
    if not isinstance(token, str):
        raise ValueError(f"Expected a string token at '{TOKEN_JSON_PATH}', got: {token!r}")
    return token

def get_iot_data_shot(token: str, data_path):
    """Step 2: GET the data endpoint using the token from step 1."""
    url = f"{"http://192.168.100.136/api"}{data_path}"
    print(url)
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, timeout=15)
    # time_taken = resp.elapsed.total_seconds()
    # print(f"Time taken: {time_taken} seconds")
    resp.raise_for_status()
    data = resp.json()
    #print(data)
    if len(data['data']) != 0:
        print(len(data['data']))
        last_record = data['data'][0]
        #print(last_record)
        process_data_shot(last_record)
    
    return

def date_processing(date):
    naive = datetime.fromisoformat(date.replace("Z", ""))
    ist = timezone(timedelta(hours=5, minutes=30))
    correct_dt = naive.replace(tzinfo=ist)  # now correctly IST-aware
    return correct_dt


def process_data_shot(data):

    id_die = data['part_name'][-3:]
    print(id_die)
    if id_die not in DIE_LIST:
        return
    
    part_id = data['shot_month'] + data['shot_day'] + data['shot_hour'] + data['shot_minute'] + data['machine_name'][-1:] + str(data['shot_number'])
    print("Getting part id: " + part_id)

    machine_id = data['machine_name']
    if(machine_id[-1:] != "2"):
        print("Not Ube 850T-02")
        return
        
    
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
    # print(id_machine)
    
    recorded_stamp = data['recorded_at']
    date_ist = date_processing(date=recorded_stamp)
    

    cur.execute("""
        INSERT INTO part (id_part, id_die, id_client, id_machine, manufactored_on, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (id_part) DO UPDATE SET
            id_die = EXCLUDED.id_die,
            id_client = EXCLUDED.id_client,
            id_machine = EXCLUDED.id_machine,
            manufactored_on = EXCLUDED.manufactored_on
""", (part_id, id_die, id_client, id_machine, date_ist, datetime.now()))

    for param, val in data.items():
        if(param not in PARAM_MAP):
            continue
        param_name = names_UOM[param][0]
        param_lower_tolerance = data.get(f"{param}_lower_limit") or 0
        param_upper_tolerance = data.get(f"{param}_upper_limit") or 0
            # print(param_upper_tolerance)
        
        uom = names_UOM[param][1]
        cur.execute("""
                INSERT INTO operating_parameter (id_part, id_die, id_client, id_machine, parameter_name, "UOM", value, recomended_lower_tolerance, recomended_upper_tolerance, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s,  %s,  %s, %s)
                ON CONFLICT (id_part, parameter_name) DO UPDATE SET
                    id_die = EXCLUDED.id_die,
                    id_client = EXCLUDED.id_client,
                    id_machine = EXCLUDED.id_machine,
                    value = EXCLUDED.value,
                    updated_at = EXCLUDED.updated_at
        """, (part_id, id_die, id_client, id_machine, param_name, uom, val, param_lower_tolerance, param_upper_tolerance, date_ist, datetime.now()))

    conn.commit()
    cur.close()
    conn.close()
    return
