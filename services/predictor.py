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

    # date_from = "2026-10-01T06:00:00"
    # date_to = "2026-10-12T06:00:00"
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
    baselines = df_baselines.set_index('parameter_name').to_dict(orient='index')
  
    cur.close()
    conn.close()
    
    return baselines

def monitor_data(die):
    #Connect to database
    conn = psycopg2.connect(**DB_CONFIG)
    print("In monitor data, DB_Config used: ", DB_CONFIG)
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
    last_params = df_raw.set_index("parameter_name")["value"].to_dict()
    # print(last_params)
        
    
    last_params["part_id"] = part_id
    timestamp = df_raw["created_at"].iloc[0]      
    ist = timezone(timedelta(hours=5, minutes=30))
    formatted = timestamp.tz_convert(ist).strftime("%Y-%m-%dT%H:%M:%S")
       
    last_params["timestamp"] = formatted
    
    return last_params

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

    df_raw = pd.read_sql(query, conn, params=(die,))
    df = df_raw.pivot(index=["id_part", "id_die"], columns="parameter_name", values="value")
    df.columns = df.columns.str.strip()
   
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