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
from .config import DB_CONFIG, IOT_BASE_URL, IOT_USERNAME, IOT_PASSWORD, IOT_AUTH_TIMEOUT, IOT_DATA_TIMEOUT

BASE_URL = f"{IOT_BASE_URL}/v1"
AUTH_PATH = "/auth/login"
 
USERNAME = IOT_USERNAME
PASSWORD = IOT_PASSWORD

TOKEN_JSON_PATH = "token"

 
PARAM_COLS = [
    "cycletime value (sec)",
    "DIE CLOSE/CORE IN Parameter (sec)value",
    "POURING-step value (sec)",
    "SHOT FWD-step value (sec)",
    "COOLING-step value (sec)",
    "DIE OPEN/CORE OUT-step value (sec)",
    "EJECTOR-step value (sec)",
    "EXTRACTOR-step value (sec)",
    "SPRAY-step value (sec)",
    "SPEED 1 (m/sec)value",
    "SPEED 2 (m/sec)value",
    "SPEED 3 (m/sec)value",
    "SPEED 4(m/sec)value",
    "ACC POSITION 1(mm)value",
    "DEACC POSITION 1(mm)value",
    "INTESIFICAITON TIME(msec)value",
    "MATEL PRESSURE(Mpa)value",
    "BISCUIT THICKNESS(mm)value",
    "CLAMP FORCE(%)value",
    "CLAMP TONNAGE(MN)value",
    "SHOT ACC. PRESSURE value",
    "INTESIFICAITON ACC. PRESSUREvalue",
    "METAL TEMP.value",
]

PARAM_MAP = {
    "cycletime value (sec)": "cycletime value (sec)",
    "DIE CLOSE/CORE IN Parameter (sec)value": "DIE-CLOSE CORE IN TIME",
    "POURING-step value (sec)": "POURING TIME",
    "SHOT FWD-step value (sec)": "SHOT FWD TIME",
    "COOLING-step value (sec)": "CURING TIME",  # verify this one
    "DIE OPEN/CORE OUT-step value (sec)": "DIE OPEN CORE OUT TIME",
    "EJECTOR-step value (sec)": "EJECTOR TIME",
    "EXTRACTOR-step value (sec)": "EXTRACT TIME",
    "SPRAY-step value (sec)": "SPRAY TIME",
    "SPEED 1 (m/sec)value": "V1",
    "SPEED 2 (m/sec)value": "V2",
    "SPEED 3 (m/sec)value": "V3",
    "SPEED 4(m/sec)value": "V4",
    "ACC POSITION 1(mm)value": "ACCEL. POINT",
    "DEACC POSITION 1(mm)value": "DEACEL. POINT",
    "INTESIFICAITON TIME(msec)value": "INTEN. TIME",
    "MATEL PRESSURE(Mpa)value": "METAL PRESS.",
    "BISCUIT THICKNESS(mm)value": "BISCUIT THICKNESS",
    "CLAMP FORCE(%)value": "CLAMP FORCE",
    "CLAMP TONNAGE(MN)value": "CLAMP TONNAGE", 
    "SHOT ACC. PRESSURE value": "SHOT ACC. PRESSURE",
    "INTESIFICAITON ACC. PRESSUREvalue": "INTENSIFICATION ACC. PRESSURE",
    "METAL TEMP.value": "FURNACE METAL TEMP.",
}

PARAM_MAP_BL = {v: k for k, v in PARAM_MAP.items()}

RAW_TO_MODEL_ORDER = [
    "cycletime value (sec)",
    "POURING TIME sec",
    "SHOT FWD TIME sec",
    "CURING TIME",
    "DIE OPEN CORE OUT TIME",
    "EJECTOR TIME",
    "EXTRACT TIME",
    "SPRAY TIME",
    "V1",
    "V2",
    "V3",
    "V4",
    "ACCEL. POINT",
    "DEACEL. POINT",
    "INTEN. TIME",
    "METAL PRESS.",
    "BISCUIT THICKNESS",
    "CLAMP FORCE",
    "CLAMP TONNAGE",
    "SHOT ACC. PRESSURE MPa",
    "INTENSIFICATION ACC. PRESSURE",
    "FURNACE METAL TEMP.",
]


#The target outputs
TARGET_DEFECTS = ["Blow_Hole","Crack","Non_filling","Porosity","Shrinkage","Chipoff"]

# Database configuration from centralized services.config (env)
SHIFT_CODE = "ALL"
LINE_NAME = "OIL PAN K-12"
PART_NAME = "OPK12"
DIE_CASTING_MACHINE = "UBE 850 T - 02"
PAGE = "1"
PAGE_SIZE = "100"

def update_date_path() -> str:
    #Connect to database
    # Fall back to a default if the table is empty
   
    date_from =  date.today().strftime("%Y-%m-%dT06:00:00")
    date_to =  (date.today() + timedelta(days=1)).strftime("%Y-%m-%dT06:00:00")

    # date_from = "2026-07-16T00:00:00"
    # date_to = "2026-07-16T12:00:00"
    data_path = f"/reports/report/historical?dateFrom={date_from}&dateTo={date_to}&page={PAGE}&pageSize={PAGE_SIZE}&partCategory=HPDC&clean=1"
    return data_path



def get_auth_token() -> str:
    """Step 1: POST credentials, pull the token out of the JSON response."""
    url = f"{BASE_URL}{AUTH_PATH}"
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

def get_iot_data(token: str, data_path):
    """Step 2: GET the data endpoint using the token from step 1."""
    url = f"{BASE_URL}{data_path}"
    headers = {"Authorization": f"Bearer {token}"}
    print(url)
    resp = requests.get(url, headers=headers, timeout=IOT_DATA_TIMEOUT)
    time_taken = resp.elapsed.total_seconds()
    print(f"Time taken: {time_taken} seconds")
    resp.raise_for_status()
    data = resp.json()
    # print(data)

    rows = data.get("records") or []
    
    if not rows:
        print("[defect_update] No rows returned")
        return
    row = rows[0]
    # target_shot = 6671
    # row = next((r for r in rows if (r.get("shot").get("number")  == target_shot) and (r.get("rejection").get("reason") != None)), None)
    # if row is None:
    #     print(f"[shot_update] No row with shot_number=%s", target_shot)
    #     return
    
    process_data(row)
    
    return


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
    # print(die)
    # print(df_baselines)
    baselines = df_baselines.set_index('parameter_name').to_dict(orient='index')

    # baselines = {PARAM_MAP_BL[k]:v for k, v in baselines.items()}
    baselines = {k:v for k, v in baselines.items()}
    # print("From Latest")
    # print(baselines)
    conn.commit()
    cur.close()
    conn.close()
    
    return baselines

def monitor_data(die):
    #Connect to database
    conn = psycopg2.connect(**DB_CONFIG)

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

    # query = """
    #         SELECT c.*
    #         FROM operating_parameter c
    #         WHERE c.id_part = %s
    
    #     """
        
    df_raw = pd.read_sql(query, conn, params=(die,))
    # df_raw = pd.read_sql(query, conn, params=("0817235929978",))
    df = df_raw.pivot(index=["id_part", "id_die"], columns="parameter_name", values="value")
    df.columns = df.columns.str.strip()
    die_id = df.index.get_level_values("id_die")[0]
    part_id = df.index.get_level_values("id_part")[0]

    X = pd.DataFrame(index=df.index)
    for target_col in PARAM_COLS:
        source_col = PARAM_MAP[target_col]
        X[target_col] = df[source_col]

    parameters = X.iloc[0].to_dict()
    last_params = {PARAM_MAP[d]:v for d , v in parameters.items()}
    
    baselines = (df_raw.set_index("parameter_name")[["recomended_lower_tolerance", "recomended_upper_tolerance"]].apply(list, axis=1).to_dict())
    baselines_full = {
    param: {
        "baseline": 0,
        "lower_tolerance": values[0],
        "upper_tolerance": values[1],
    }
    for param, values in baselines.items()
}
    last_params["part_id"] = part_id
    timestamp = df_raw["created_at"].iloc[0]      
    ist = timezone(timedelta(hours=5, minutes=30))
    formatted = timestamp.tz_convert(ist).strftime("%Y-%m-%dT%H:%M:%S")
       
    last_params["timestamp"] = formatted
    # print(last_params.keys())
    # print("From monitor")
    # print(baselines)

    return [last_params, baselines_full]

def latest_model_path(die, defect):
    tag = defect.replace(" ", "_")
    if die == "S14" or die == "S17":
        die_dir = os.path.join("models", die)
        matches = glob.glob(os.path.join(die_dir, f"{die}_{tag}_*_voting.pkl"))
        if not matches:
            return os.path.join("models", f"{tag}_20260605_voting.pkl")

        def _date(m):
            mm = re.search(r"_(\d{8})_voting\.pkl$", os.path.basename(m))
            return mm.group(1) if mm else "00000000"

        return max(matches, key=_date)
    return os.path.join("models", f"{tag}_20260605_voting.pkl")


def predictions(die):

    #Connect to database
    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()

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
    
    # query = """
    #     SELECT c.*
    #     FROM operating_parameter c
    #     WHERE c.id_part = %s

    # """

    df_raw = pd.read_sql(query, conn, params=(die,))
    # df_raw = pd.read_sql(query, conn, params=("0817235929978",))
    # print(df_raw)
    df = df_raw.pivot(index=["id_part", "id_die"], columns="parameter_name", values="value")
    df.columns = df.columns.str.strip()
    # id_part = df.index.get_level_values("id_part")[0]
    #print(id_part)
    
    X = pd.DataFrame(index=df.index)
    for target_col in PARAM_COLS:
        source_col = PARAM_MAP[target_col]
        X[target_col] = df[source_col]

    query = """
        SELECT c.parameter_name, c.baseline, c.upper_tolerance, c.lower_tolerance
        FROM calibration_parameter c
        WHERE c.id_die = %s
        AND c.id_calibration = (
                  SELECT MAX(id_calibration)
                  FROM calibration_parameter
                  WHERE id_die = %s
                )

    """
    df_baselines = pd.read_sql(query, conn, params=(die,die))

    # Only S14 models include the DIE-CLOSE CORE IN TIME parameter;
    # other dies still run on the older models that omitted it.
    if die != "S14":
        df_baselines = df_baselines[df_baselines["parameter_name"] != "DIE-CLOSE CORE IN TIME"]

    baselines = df_baselines.set_index('parameter_name').to_dict(orient='index')
    
    feat_datasets = {}   # defect → feature DataFrame

    def safe_cn(col):
        return re.sub(r"[^a-zA-Z0-9]","_",str(col)).strip("_").replace("__","_")

    for defect in TARGET_DEFECTS:
        feat_rows = []
        for (_, _), row in X.iterrows():
            feats = {}
            for col, v in baselines.items():
                col = PARAM_MAP_BL[col]
                val = pd.to_numeric(row.get(col, np.nan), errors="coerce")
                avg = v["baseline"]
                min_r = v["lower_tolerance"]
                max_r = v["upper_tolerance"]
                cn  = safe_cn(col)
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
        df_input = feat_datasets[defect][model['scaler'].feature_names_in_]
        X_scaled = model['scaler'].transform(df_input)
        X_pca    = model['pca'].transform(X_scaled)
        X_cca    = model['cca'].transform(X_pca)
        prob     = model['model'].predict_proba(X_cca)[:,1]
        pred_results.append(prob)

    predictions = [float(p[0]) for p in pred_results]
    store_quality_pred(predictions, df_raw, TARGET_DEFECTS, cur)
    
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