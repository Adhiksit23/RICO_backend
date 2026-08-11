import psycopg2
import pickle
from datetime import date, timedelta, timezone
import requests
from .data_processing import process_data, store_quality_pred
import os

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
 
    part_id = data['shot_month'] + data['shot_day'] + data['shot_hour'] + data['shot_minute'] + data['machine_name'][-1:] + str(data['shot_number'])
    print("Getting part id: " + part_id)

    id_machine = data['shot']['machine']
    id_die = data['part']['die']
    print(id_die)
    if id_die not in DIE_LIST:
        return
    
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

    if(data['rejection']['category'] != "PRODUCTION"):
        print(data['reason'])
        store_defect(cur, data, id_client)

    conn.commit()
    cur.close()
    conn.close()
    return
