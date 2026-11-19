import pandas as pd
import numpy as np
import warnings, re, os, glob
from sklearn.linear_model    import LogisticRegression
try:
    from lightgbm import LGBMClassifier
except: os.system("pip install lightgbm -q"); from lightgbm import LGBMClassifier
try:
    from xgboost import XGBClassifier
except: os.system("pip install xgboost -q"); from xgboost import XGBClassifier
warnings.filterwarnings("ignore")
import psycopg2
import pickle
from datetime import date, timedelta, timezone
import requests
from .data_processing import process_data, store_quality_pred
import os
from .config import DB_CONFIG, IOT_BASE_URL, IOT_USERNAME, IOT_PASSWORD, IOT_AUTH_TIMEOUT, IOT_DATA_TIMEOUT, IOT_AUTH_PATH

# Cache to track last read position for batch IoT data
_last_read_shot_number = None
_last_read_serial_no = None
_last_read_timestamp = None
_last_seen_page = 1
_last_seen_key = None

BASE_URL = f"{IOT_BASE_URL}"
 
USERNAME = IOT_USERNAME
PASSWORD = IOT_PASSWORD

TOKEN_JSON_PATH = "token"


#The target outputs
TARGET_DEFECTS = ["Blow_Hole","Crack","Non_filling","Porosity","Shrinkage","Chipoff"]

# Database configuration from centralized services.config (env)
SHIFT_CODE = "ALL"
LINE_NAME = "OIL PAN K-12"
PART_NAME = "OPK12"
DIE_CASTING_MACHINE = "UBE 850 T - 02"
PAGE = "1"
PAGE_SIZE = "100"

PARAM_MAPPING = {
    "cycletime_value_sec": "cycle_time",
    "DIE_CLOSE_CORE_IN_step_value_sec": "die_close_core_in_time",
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

def update_date_path() -> str:
    date_from =  date.today().strftime("%Y-%m-%dT06:00:00")
    date_to =  (date.today() + timedelta(days=1)).strftime("%Y-%m-%dT06:00:00")
    data_path = f"/v1/reports/report/historical?dateFrom={date_from}&dateTo={date_to}&page=1&pageSize={PAGE_SIZE}&partCategory=HPDC&clean=1"
    return data_path



def get_auth_token() -> str:
    """Step 1: POST credentials, pull the token out of the JSON response."""
    url = f"{BASE_URL}{IOT_AUTH_PATH}"
    payload = {"username": USERNAME, "password": PASSWORD}
 
    resp = requests.post(url, json=payload, timeout=IOT_AUTH_TIMEOUT)
    resp.raise_for_status()
    body = resp.json()
 
    token = body
    for key in TOKEN_JSON_PATH.split("."):
        token = token[key]
 
    if not isinstance(token, str):
        raise ValueError(f"Expected a string token at '{TOKEN_JSON_PATH}', got: {token!r}")
    return token

def _row_key(row):
    shot_num = row.get("shot", {}).get("number")
    serial_no = row.get("serialNo")
    ts = row.get("shot", {}).get("recordedAt") or row.get("__pr_final_scan_at") or row.get("__pr_first_scan_at")
    return (str(ts), str(serial_no), int(shot_num) if shot_num is not None else -1)


def _set_last_seen(key):
    global _last_seen_key, _last_read_shot_number, _last_read_serial_no, _last_read_timestamp, _last_seen_page
    _last_seen_key = key
    if key is not None:
        _last_read_timestamp, _last_read_serial_no, _last_read_shot_number = key
    _last_seen_page = 1


def get_iot_data(token: str, data_path):
    """GET traceability reports and process every row newer than the cursor.

    Rows are newest-first. Scans from page 1 until the last seen row is found,
    collecting all newer rows across page boundaries, then processes them
    oldest-to-newest.
    """
    headers = {"Authorization": f"Bearer {token}"}
    max_pages = 50

    import re as _re

    def fetch_page(page_num):
        page_path = _re.sub(r"page=\d+", f"page={page_num}", data_path) if _re.search(r"page=\d+", data_path) else (data_path + f"&page={page_num}")
        url = f"{BASE_URL}{page_path}"
        print(url)
        resp = requests.get(url, headers=headers, timeout=IOT_DATA_TIMEOUT)
        time_taken = resp.elapsed.total_seconds()
        print(f"Time taken: {time_taken} seconds")
        resp.raise_for_status()
        return resp.json()

    cursor = _last_seen_key
    new_rows = []
    seen = set()
    found = False
    total_pages = 1

    for page in range(1, max_pages + 1):
        try:
            data = fetch_page(page)
        except Exception as e:
            print(f"[defect_update] Error fetching page {page}: {e}")
            break

        if page == 1:
            pagination = data.get("pagination") or {}
            raw_total = pagination.get("totalPages") or pagination.get("total_pages") or pagination.get("lastPage") or 1
            try:
                total_pages = max(1, int(raw_total))
            except (TypeError, ValueError):
                total_pages = 1

        rows = data.get("records") or []
        for row in rows:
            key = _row_key(row)
            if cursor is not None and key == cursor:
                found = True
                break
            if key in seen:
                continue
            seen.add(key)
            new_rows.append(row)

        if found:
            break
        if page >= total_pages:
            break

    if cursor is not None and not found:
        print(f"[defect_update] Last seen row not found within {max_pages} pages; processed {len(new_rows)} rows")

    last_success_key = cursor
    for row in reversed(new_rows):
        key = _row_key(row)
        try:
            process_data(row)
            last_success_key = key
        except Exception as e:
            print(f"[defect_update] Error processing row: {e}")

    if last_success_key != cursor:
        _set_last_seen(last_success_key)

    if not new_rows:
        print("[defect_update] No new rows to process (all already seen)")


def get_latest_calibration(machine: str = None, die: str = None):
    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()

    query = """
        SELECT c.parameter_name, c.baseline, c.upper_tolerance, c.lower_tolerance
        FROM calibration_parameter c
        WHERE c.id_die = %s
        AND c.id_calibration = (
          SELECT MAX(id_calibration)
          FROM calibration_parameter
          WHERE id_die = %s
        ) """

    
    df_baselines = pd.read_sql(query, conn, params=(die,die))

    if die == 'S16':
        df_baselines["parameter_name"] = df_baselines["parameter_name"].replace(PARAM_MAPPING)

    baselines = df_baselines.set_index('parameter_name').to_dict(orient='index')
    
    cur.close()
    conn.close()
    
    return baselines

def monitor_data(die):
    #Connect to database
    conn = psycopg2.connect(**DB_CONFIG)
    # print("In monitor data, DB_Config used: ", DB_CONFIG)
    query = """
        SELECT c.*
        FROM operating_parameter c
        WHERE c.id_part = (
        SELECT id_part FROM part
        WHERE id_die = %s
        ORDER BY manufactored_on DESC
        LIMIT 1
    );

    """

    # print(die)
    df_raw = pd.read_sql(query, conn, params=(die,))
    df = df_raw.pivot(index=["id_part", "id_die"], columns="parameter_name", values="value")
    df.columns = df.columns.str.strip()
    part_id = df.index.get_level_values("id_part")[0]

    
    # print(last_params)
    if die == 'S16':
        df_raw["parameter_name"] = df_raw["parameter_name"].replace(PARAM_MAPPING)
    
    last_params = df_raw.set_index("parameter_name")["value"].to_dict()
    # print(last_params)

    ranges_df = df_raw.set_index("parameter_name")[["recomended_baseline", "recomended_lower_tolerance",  "recomended_upper_tolerance"]]
    set_ranges = ranges_df.fillna(0).to_dict(orient="index")
    
    last_params["part_id"] = part_id
    timestamp = df_raw["created_at"].iloc[0]      
    ist = timezone(timedelta(hours=5, minutes=30))
    formatted = timestamp.tz_convert(ist).strftime("%Y-%m-%dT%H:%M:%S")
       
    last_params["timestamp"] = formatted
   
    
    return last_params, set_ranges

def latest_model_path(die, defect):
    tag = defect.replace(" ", "_")
    if die != "S16":
        die_dir = os.path.join("models", die)
        matches = glob.glob(os.path.join(die_dir, f"{die}_{tag}_*_voting.pkl"))
        if not matches:
            return os.path.join("models", f"{tag}_20260605_voting.pkl")

        def _date(m):
            mm = re.search(r"_(\d{8})_voting\.pkl$", os.path.basename(m))
            return mm.group(1) if mm else "00000000"

        return max(matches, key=_date)
    return os.path.join("models", f"{tag}_20260605_voting.pkl")


def predictions(die, part_id=None):

    #Connect to database
    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()

    if part_id:
        query = """
            SELECT c.*
            FROM operating_parameter c
            WHERE c.id_part = %s
        """
        query_params = (part_id,)
    else:
        query = """
            SELECT c.*
            FROM operating_parameter c
            WHERE c.id_part = (
                SELECT id_part FROM part
                WHERE id_die = %s
                ORDER BY manufactored_on DESC
                LIMIT 1
            )
        """
        query_params = (die,)

    df_raw = pd.read_sql(query, conn, params=query_params)
    if df_raw.empty:
        cur.close()
        conn.close()
        return [0.0] * len(TARGET_DEFECTS)

    df = df_raw.pivot(index=["id_part", "id_die"], columns="parameter_name", values="value")
    df.columns = df.columns.str.strip()

    from services.monthly_predict import (
        _calibration_for, _load_calibration, _load_part_params, _monitor_counts,
    )

    id_part = df_raw["id_part"].iloc[0]
    cur.execute(
        "SELECT production_date, manufactored_on FROM rico.part WHERE id_part = %s",
        (id_part,),
    )
    part_row = cur.fetchone()
    if part_row and part_row[0] is not None:
        production_day = part_row[0]
    elif part_row and part_row[1] is not None:
        ist = timezone(timedelta(hours=5, minutes=30))
        production_day = (part_row[1].astimezone(ist) - timedelta(hours=6)).date()
    else:
        production_day = date.today()

    calibration_id, _ = _calibration_for(cur, die, production_day)
    if calibration_id is None:
        cur.execute(
            "SELECT MAX(id_calibration) FROM calibration_parameter WHERE id_die = %s",
            (die,),
        )
        calibration_id = cur.fetchone()[0]

    query = """
        SELECT c.parameter_name, c.baseline, c.upper_tolerance, c.lower_tolerance
        FROM calibration_parameter c
        WHERE c.id_die = %s AND c.id_calibration = %s
    """
    df_baselines = pd.read_sql(query, conn, params=(die, calibration_id))

    # Only S16 models do not include the DIE-CLOSE CORE IN TIME parameter;
    if die == "S16":
        df_baselines = df_baselines[df_baselines["parameter_name"] != "DIE-CLOSE CORE IN TIME"]

    baselines = df_baselines.set_index('parameter_name').to_dict(orient='index')
    
    feat_datasets = {}   # defect → feature DataFrame

    def safe_cn(col):
        return re.sub(r"[^a-zA-Z0-9]","_",str(col)).strip("_").replace("__","_")

    for defect in TARGET_DEFECTS:
        feat_rows = []
        for (_, _), row in df.iterrows():
            feats = {}
            for col, v in baselines.items():
                val = pd.to_numeric(row.get(col, np.nan), errors="coerce")
                avg = v["baseline"]
                min_r = v["lower_tolerance"]
                max_r = v["upper_tolerance"]
                if(die != 'S16'):
                    cn  = safe_cn(col)
                else:
                    cn = col

                #If value in range and within percetange deviation
                feats[f"{cn}_inrange"] = int(min_r <= val <= max_r)
                pct = (val - avg) / avg if avg != 0 else 0.0
                feats[f"{cn}_pctdev"] = float(np.clip(pct, -0.30, 0.30))
            feat_rows.append(feats)
        feat_df = pd.DataFrame(feat_rows, index=df.index)
        feat_datasets[defect] = feat_df
        # print(f"{defect}: {feat_df.T}")

    pred_results = []
    #print("Going to model")
    # Use latest model for each die (S14 only picks the newest trained model)
    for defect in TARGET_DEFECTS:
        model_path = latest_model_path(die, defect)
        if model_path is None:
            print(f"[predictions] No model found for defect={defect} and die={die}")
            pred_results.append(0.0)
            continue
        # print(model_path)
        model = pickle.load(open(model_path, 'rb'))
        # print("Scaler expects:", model['scaler'].feature_names_in_.tolist())
        # print("df_input has:", feat_datasets[defect].columns.tolist())
        
        df_input = feat_datasets[defect][model['scaler'].feature_names_in_]
        # nan_cols = df_input.columns[df_input.isnull().any()].tolist()
        # print("NaN columns:", nan_cols)
        X_scaled = model['scaler'].transform(df_input)
        X_pca    = model['pca'].transform(X_scaled)
        X_cca    = model['cca'].transform(X_pca)
        prob     = model['model'].predict_proba(X_cca)[:,1]
        pred_results.append(prob)

    predictions = [float(p[0]) for p in pred_results]
    calibration = _load_calibration(cur, calibration_id)
    part_values = _load_part_params(cur, [id_part]).get(id_part, {})
    monitor = _monitor_counts(part_values, calibration)
    store_quality_pred(predictions, df_raw, TARGET_DEFECTS, cur, monitor=monitor)
    
    conn.commit()
    cur.close()
    conn.close()

    return predictions


def last_predictions(die, N):
    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()

    query = """
        SELECT c.*
        FROM part_quality_prediction c
        WHERE c.id_part IN (
        SELECT id_part FROM part
        WHERE id_die = %s
        ORDER BY created_at DESC
        LIMIT %s
    );

    """
    df_raw = pd.read_sql(query, conn, params=(die, N))
    result = {}

    for _, row in df_raw.iterrows():
        id_part = row["id_part"]
        defect_type = row["defect_type"]
        probability = row["defect_probability"]

        if id_part not in result:
            result[id_part] = {}

        result[id_part][defect_type] = probability

    cur.close()
    conn.close()
    
    print(result)
    return result