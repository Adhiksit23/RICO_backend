import pandas as pd
from . import calibrate_params
import psycopg2
DB_CONFIG = {
    "host":     "aws-1-ap-southeast-2.pooler.supabase.com",
    "dbname":   "postgres",
    "user":     "postgres.nnflwohgewhkqqjfvote",
    "password": "Datamgnt25!#",
    "options":  "-c search_path=rico"
    
}

# Temporary Excel source
# Later Adikshit can replace with SQL


def get_latest_parameters():


    param_names = ['ACCEL. POINT mm ', 'BISCUIT THICKNESS mm ', 'CLAMP FORCE (%) ', 'CLAMP TONNAGE (T) ', 'CLAMP TONNAGE(HE.LOW) % ', 
                   'CLAMP TONNAGE(HE.LOW) MN ', 'CLAMP TONNAGE(HE.UP) % ', 'CLAMP TONNAGE(OP.LOW) % ', 'CLAMP TONNAGE(OP.UP) % ', 
                   'COOLING WATER FLOW RATE(MOV.) L/min ', 'COOLING WATER FLOW RATE(STA.) L/min ', 'CURING TIME sec ', 'DEACEL. POINT mm ',
                     'DIE OPEN CORE OUT TIME sec ', 'DIE-CLOSE CORE IN TIME sec ', 'EJECTOR TIME sec ', 'EXTRACT TIME sec ', 
                     'FIXED DIE TEMP (F-1) C ', 'FIXED DIE TEMP (F-2) C ', 'FURNACE METAL TEMP. C ', 'HIGH SHOT COUNT ', 'INTEN. TIME msec ', 
                     'INTENSIFICATION ACC. PRESSURE MPa ', 'JET COOLING PRESSURE kgf/cm2 ', 'METAL PRESS. Mpa ', 'MOVING DIE TEMP (M-1) C ', 'MOVING DIE TEMP (M-2) C ', 'NG COUNTER ', 'POURING TIME sec ', 'SHOT ACC. PRESSURE MPa ', 'SHOT FWD TIME sec ', 'SLIDE TEMP-1 (S-1) C ', 'SPRAY TIME sec ', 'V1 m/sec ', 'V2 m/sec) ', 'V3 m/sec ', 'V4 m/sec ', 'VACUUM PRESSURE mbar ']
    dict_parms = {name: 0 for name in param_names}
    return dict_parms


def compute_calibration_ranges(): #Input should be machineID and DieID, which is entered by user when opening calibration page
    #For the time being no 
    baselines = calibrate_params.main()
    return {name: {"baseline": baselines[name][0], "tolerance": baselines[name][1], "min_range": baselines[name][2], "max_range": baselines[name][3]} for name, v in baselines.items()}

def update_parameters(data):

    #Assuming the data is same formate to the baseline data given earlier for compute_calibration_ranges
    #The data for calibration date will be the same as created_at date, unless already created, then changed to updated_date
    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()
    cur.execute(
    "SELECT id_client FROM client WHERE name = %s",
    ('Suzuki',)
    )
    id_client = cur.fetchone()[0]
    print(id_client)


    #Get machine ID to match with 
    cur.execute(
    "SELECT id_machine FROM machine WHERE id_client = %s",
    (id_client,)
    )
    id_machine = cur.fetchone()[0]
    print(id_machine)

    #Get die ID to match with 
    cur.execute(
    "SELECT id_die FROM die WHERE id_machine = %s",
    (id_machine,)
    )
    id_die = cur.fetchone()[0]

    #Add the DieCalibration data
    
    cur.execute("""
                    INSERT INTO die_calibration (id_die, id_client, id_machine, enabled)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id_calibration
            """, (id_die, id_client, id_machine, 'true'))
    id_calibration = cur.fetchone()[0]

    #Add the individual Param calibration data into Calibration Parameter
    for col, v in data.items():
        #Types need to be updated
        baseline = int( data[col][0])
        lower_tolerance = int(data[col][2])
        upper_tolerance = int(data[col][3])
        cur.execute("""
                    INSERT INTO calibration_parameter (id_calibration, id_die, id_client, id_machine, parameter_name, baseline, lower_tolerance, upper_tolerance)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id_calibration
            """, (id_calibration, id_die, id_client, id_machine, col, baseline, lower_tolerance, upper_tolerance))
        
    conn.commit()
    cur.close()
    conn.close()

    return {
        "message": "Parameters updated successfully",
        "updated_values": data
    }

def apply_calibration(data):

    # Adikshit can later save to SQL

    return {
        "message": "Calibration Applied Successfully",
        "applied_values": data
    }