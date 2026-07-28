import logging
import pandas as pd
import psycopg2
from . import calibrate_params

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host":     "aws-1-ap-southeast-2.pooler.supabase.com",
    "dbname":   "postgres",
    "user":     "postgres.nnflwohgewhkqqjfvote",
    "password": "Datamgnt25!#",
    "options":  "-c search_path=rico"
}

def get_latest_parameters(machine: str = None, die: str = None):
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur  = conn.cursor()

        # print(die)
        # print(machine)
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
        # print(df)
        # Return a clean dictionary of { "Param Name": baseline_value }
        result = {
            row["parameter_name"]: {
            
            "baseline": float(row["baseline"]),
            "min_range": float(row["lower_tolerance"]),
            "max_range": float(row["upper_tolerance"])
            } for _, row in df.iterrows()
        }
    
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
):
    try:
        baselines, num_samples = calibrate_params.main(machine, die=die)
    except Exception as exc:
        logger.exception("compute_calibration_ranges failed for machine=%s die=%s", machine, die)
        raise

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
    # vals["ACCEL. POINT"]["baseline"] = 0
    #print(vals["ACCEL. POINT"])
    
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