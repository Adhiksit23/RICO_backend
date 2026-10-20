import logging
import pandas as pd
import psycopg2
from . import calibrate_params

logger = logging.getLogger(__name__)

from services.config import (
    DB_CONFIG
)

PARAM_MAPPING = {
    "cycletime_value_sec": "cycle_time",
    "DIE-CLOSE CORE IN TIME": "die_close_core_in_time",
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

def get_latest_parameters(machine: str = None, die: str = None):
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur  = conn.cursor()

        query = """
            SELECT c.*
            FROM calibration_parameter c
            WHERE c.id_calibration = (
                SELECT id_calibration FROM die_calibration
                WHERE id_die = %s and id_machine = %s
                ORDER BY id_calibration DESC
                LIMIT 1
            );
        """
        df = pd.read_sql(query, conn, params=(die, machine))
            
        cur.close()
        conn.close()
        
        result = {
            row["parameter_name"]: {
            
            "baseline": float(row["baseline"]),
            "min_range": float(row["lower_tolerance"]),
            "max_range": float(row["upper_tolerance"]),
            "unit": names_UOM[PARAM_MAPPING[row["parameter_name"]]] if die == "S16" else names_UOM[row["parameter_name"]],
            } for _, row in df.iterrows()
        }
        # print("Result of latest in calibration page: ", result )
    except Exception as exc:
        logger.exception("get_latest_parameters failed for die=%s", die)
        raise
    finally:
        if conn:
            conn.close()

    return result
   


def compute_calibration_ranges(
    machine: str | None = None,
    die: str | None = "S14",
    start_date: str | None = None,
    end_date: str | None = None,
):
    try:
        baselines, num_samples = calibrate_params.main(
            machine, die=die, start_date=start_date, end_date=end_date
        )
    except Exception as exc:
        logger.exception("compute_calibration_ranges failed for machine=%s die=%s", machine, die)
        raise

    print("Calculated vals recieved")
    vals = {
        name: {
            # Wrap everything in float() to strip away NumPy np.float64 types
            "baseline":  float(baselines[name][0]),
            "tolerance": float(baselines[name][1]),
            "min_range": float(baselines[name][2]),
            "max_range": float(baselines[name][3]),
        }
        for name in baselines
    }
    
    print("Calculated vals sent")
    return {
        "ranges": vals,
        # Cast num_samples to standard int
        "samples_analyzed": int(num_samples),
    }


def apply_calibration(data: dict, id_machine: str, die: str):
    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()
    try:
        # 1. Get IDs
        cur.execute("SELECT id_client FROM client WHERE name = %s", ('Suzuki',))
        id_client = cur.fetchone()[0]
        
        id_die = die
        
        # 2. Create the parent calibration record
        cur.execute("""
            INSERT INTO die_calibration (id_die, id_client, id_machine, enabled)
            VALUES (%s, %s, %s, %s)
            RETURNING id_calibration
        """, (id_die, id_client, id_machine, 'true'))
        id_calibration = cur.fetchone()[0]

        # 3. Fetch the tolerances dynamically based on the current die
        ranges_data = data

        # 4. Insert each parameter
        for col, v in data.items():
            if col not in ranges_data:
                print(f"Warning: {col} not found in computed ranges. Skipping.")
                continue
            # Safely cast to float
            baseline = v['baseline']
            lower_tolerance = v['min_range']
            upper_tolerance = v['max_range']

            cur.execute("""
                INSERT INTO calibration_parameter 
                (id_calibration, id_die, id_client, id_machine, parameter_name, baseline, lower_tolerance, upper_tolerance)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (id_calibration, id_die, id_client, id_machine, col, baseline, lower_tolerance, upper_tolerance))
            
        conn.commit()

        return {
            "message": "Parameters applied successfully",
            "updated_values": data
        }

    except Exception as e:
        conn.rollback()  # Undo the insert if anything crashes
        logger.exception("Database error during apply_calibration for die=%s", die)
        raise  # re-raise so the API layer can convert to HTTPException

    finally:
        cur.close()
        conn.close()