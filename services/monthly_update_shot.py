import requests
import psycopg2

from datetime import date, datetime, timezone, timedelta

from services.config import (
    DB_CONFIG,
    IOT_AUTH_TIMEOUT,
    IOT_BASE_URL,
    IOT_DATA_BASE_URL,
    IOT_DATA_TIMEOUT,
    IOT_PASSWORD,
    IOT_USERNAME,
)


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL =  f"{IOT_BASE_URL}/v1"

USERNAME = IOT_USERNAME
PASSWORD = IOT_PASSWORD

# KEEP THESE THE SAME AS YOUR EXISTING WORKING SCRIPT
AUTH_PATH = "/auth/login"
TOKEN_JSON_PATH = "token"

# Historical API pagination
PAGE_SIZE = 100
START_PAGE = 1


# ============================================================
# PARAMETER CONFIGURATION
# ============================================================
names_UOM = {
    'accel_point': ['ACCEL. POINT', 'mm'],
    'biscuit_thickness': ['BISCUIT THICKNESS', 'mm'],
    'clamp_force_pct': ['CLAMP FORCE', '%'],
    'clamp_tonnage': ['CLAMP TONNAGE', 'Mn'],
    'curing_time': ['CURING TIME', 'sec'],
    'deaccel_point': ['DEACEL. POINT', 'mm'],
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
    'cycle_time': ['cycletime value (sec)', 'sec'],
}


PARAM_MAP = {
    "cycle_time": "cycletime value (sec)",
    "die_close_core_in_time": "DIE CLOSE/CORE IN Parameter (sec)value",
    "pouring_time": "POURING-step value (sec)",
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

MACHINE_IDS = [
    "UBE 850T-1",
    "UBE 850T-2",
    "UBE 850T-3",
]


DIE_LIST = [
    "S14",
    "S16",
    "S17",
    "S18",
]


# ============================================================
# API FUNCTIONS
# ============================================================

def get_auth_token() -> str:
    """
    Authenticate with the IoT API once and return the bearer token.
    """

    url = f"{BASE_URL}{AUTH_PATH}"

    payload = {
        "username": USERNAME,
        "password": PASSWORD,
    }

    resp = requests.post(
        url,
        json=payload,
        timeout=IOT_AUTH_TIMEOUT,
    )

    resp.raise_for_status()

    body = resp.json()

    token = body

    for key in TOKEN_JSON_PATH.split("."):
        token = token[key]

    if not isinstance(token, str):
        raise ValueError(
            f"Expected string token at "
            f"'{TOKEN_JSON_PATH}', got: {token!r}"
        )

    return token


def build_data_path(
    current_date: date,
    page: int,
) -> str:
    """
    Build historical report URL for a single day.

    Example:
        Aug 01 06:00 -> Aug 02 06:00
    """

    next_date = current_date + timedelta(days=1)

    date_from = current_date.strftime(
        "%Y-%m-%dT06:00:00"
    )

    date_to = next_date.strftime(
        "%Y-%m-%dT06:00:00"
    )

    return (
        "/reports/report/historical"
        f"?dateFrom={date_from}"
        f"&dateTo={date_to}"
        f"&page={page}"
        f"&pageSize={PAGE_SIZE}"
        "&partCategory=HPDC"
        "&clean=1"
    )

def get_iot_page(
    token: str,
    data_path: str,
):
    url = f"{BASE_URL}{data_path}"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    print(f"\nGET {url}")

    resp = requests.get(
        url,
        headers=headers,
        timeout=IOT_DATA_TIMEOUT,
    )

    print(f"Status code: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('Content-Type')}")
    print(
        f"API request time: "
        f"{resp.elapsed.total_seconds():.2f}s"
    )

    # ========================================================
    # TOKEN EXPIRED → REAUTHENTICATE AND RETRY ONCE
    # ========================================================

    if resp.status_code == 401:

        print(
            "[AUTH] Token expired or unauthorized."
        )

        print(
            "[AUTH] Getting a new token..."
        )

        token = get_auth_token()

        headers = {
            "Authorization": f"Bearer {token}"
        }

        print(
            "[AUTH] Retrying request with new token..."
        )

        resp = requests.get(
            url,
            headers=headers,
            timeout=IOT_DATA_TIMEOUT,
        )

        print(
            f"Retry status code: {resp.status_code}"
        )

    # If retry also failed, raise normally
    resp.raise_for_status()

    if not resp.text.strip():
        print("[API ERROR] Empty response")
        return [], token

    try:
        data = resp.json()

    except requests.exceptions.JSONDecodeError:

        print(
            "[API ERROR] Response was not valid JSON"
        )

        print(
            f"Response body: {resp.text[:1000]}"
        )

        raise

    rows = data.get("records") or []

    return rows, token
# ============================================================
# DATE PROCESSING
# ============================================================

def date_processing(date_string):
    """
    Convert IoT timestamp into IST-aware datetime.
    """

    naive = datetime.fromisoformat(
        date_string.replace("Z", "")
    )

    ist = timezone(
        timedelta(hours=5, minutes=30)
    )

    return naive.replace(tzinfo=ist)


# ============================================================
# DATABASE STORAGE
# ============================================================

def store_defect(
    cur,
    row,
    id_client,
    id_machine,
):
    """
    Insert/update defect information for a part.
    """

    rejection = row.get("rejection") or {}

    defect = rejection.get("reason")
    category = rejection.get("category")
    zone = rejection.get("zone")
    sub_zone = rejection.get("subZone")
    view = rejection.get("view")

    part_id = row["part"]["id"]
    id_die = row["part"]["die"]

    cur.execute(
        """
        INSERT INTO part_quality (
            id_part,
            id_die,
            id_client,
            updated_at,
            category,
            zone,
            sub_zone,
            view,
            id_machine,
            defect_type
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s
        )

        ON CONFLICT (id_part)
        DO UPDATE SET
            id_die = EXCLUDED.id_die,
            id_client = EXCLUDED.id_client,
            updated_at = EXCLUDED.updated_at,
            category = EXCLUDED.category,
            zone = EXCLUDED.zone,
            sub_zone = EXCLUDED.sub_zone,
            view = EXCLUDED.view,
            id_machine = EXCLUDED.id_machine,
            defect_type = EXCLUDED.defect_type
        """,
        (
            part_id,
            id_die,
            id_client,
            datetime.now(),
            category,
            zone,
            sub_zone,
            view,
            id_machine,
            defect,
        )
    )


def process_data(
    data,
    cur,
    id_client,
    id_machine,
):
    """
    Process ONE IoT record.

    Important:
        This function does NOT open/close a database connection
        and does NOT commit.

        The monthly backfill controls the connection and commits.
    """

    shot = data.get("shot") or {}
    part = data.get("part") or {}

    parameters = shot.get("parameters")

    if parameters is None:
        return False

    part_id = part.get("id")

    if not part_id:
        print("[SKIP] Missing part ID")
        return False

    client_code = "R437111511"

    print(f"Getting part id: {part_id}")

    if client_code in part_id:
        print(
            f"[SKIP] Problematic API part ID: "
            f"{part_id}"
        )
        return False

    id_die = part.get("die")

    if id_die not in DIE_LIST:
        print(
            f"[SKIP] Die {id_die} not in DIE_LIST"
        )
        return False

    recorded_stamp = shot.get("recordedAt")

    if not recorded_stamp:
        print(
            f"[SKIP] No recordedAt for {part_id}"
        )
        return False

    date_ist = date_processing(
        recorded_stamp
    )

    # --------------------------------------------------------
    # PART
    # --------------------------------------------------------

    cur.execute(
        """
        INSERT INTO part (
            id_part,
            id_die,
            id_client,
            id_machine,
            manufactored_on,
            created_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s
        )

        ON CONFLICT (id_part)
        DO UPDATE SET
            id_die = EXCLUDED.id_die,
            id_client = EXCLUDED.id_client,
            id_machine = EXCLUDED.id_machine,
            manufactored_on = EXCLUDED.manufactored_on
        """,
        (
            part_id,
            id_die,
            id_client,
            id_machine,
            date_ist,
            datetime.now(),
        )
    )

    # --------------------------------------------------------
    # OPERATING PARAMETERS
    # --------------------------------------------------------

    for param, val in parameters.items():

        if param not in PARAM_MAP:
            # print(param)
            continue

        if param not in names_UOM:
            print(
                f"[WARNING] No UOM mapping for {param}"
            )
            continue

        param_name = names_UOM[param][0]
        # print(param_name)
        uom = names_UOM[param][1]

        cur.execute(
            """
            INSERT INTO operating_parameter (
                id_part,
                id_die,
                id_client,
                id_machine,
                parameter_name,
                "UOM",
                value,
                created_at,
                updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )

            ON CONFLICT (
                id_part,
                parameter_name
            )
            DO UPDATE SET
                id_die = EXCLUDED.id_die,
                id_client = EXCLUDED.id_client,
                id_machine = EXCLUDED.id_machine,
                value = EXCLUDED.value,
                updated_at = EXCLUDED.updated_at
            """,
            (
                part_id,
                id_die,
                id_client,
                id_machine,
                param_name,
                uom,
                val,
                date_ist,
                datetime.now(),
            )
        )

    # --------------------------------------------------------
    # DEFECT
    # --------------------------------------------------------

    rejection = data.get("rejection") or {}

    if rejection.get("reason") is not None:

        print(
            f"Defect: {rejection.get('reason')}"
        )

        store_defect(
            cur,
            data,
            id_client,
            id_machine,
        )

    return True


# ============================================================
# PROCESS ONE DAY
# ============================================================
def process_one_day(
    token,
    current_date,
    conn,
    cur,
    id_client,
    id_machine,
):
    """
    Process every API page and every record for one day.

    Commits every 10 successfully stored records.
    """

    print("\n" + "=" * 80)
    print(f"PROCESSING DATE: {current_date}")
    print("=" * 80)

    page = START_PAGE

    total_received = 0
    total_processed = 0
    total_failed = 0

    # ========================================================
    # COMMIT SETTINGS
    # ========================================================

    COMMIT_EVERY = 10
    entries_since_commit = 0

    while True:

        data_path = build_data_path(
            current_date=current_date,
            page=page,
        )

        rows = get_iot_page(
            token=token,
            data_path=data_path,
        )

        print(f"rows type: {type(rows)}")
        print(rows.get("pagination"))
        print(rows[0])
        if not rows:
            print(
                f"No records returned on page {page}."
            )
            break

        print(
            f"Date: {current_date} | "
            f"Page: {page} | "
            f"Records: {len(rows)}"
        )

        total_received += len(rows)

        # ====================================================
        # PROCESS EVERY ROW
        # ====================================================

        for row_number, row in enumerate(
            rows,
            start=1,
        ):

            shot = row.get("shot") or {}
            part = row.get("part") or {}

            shot_number = shot.get("number")
            part_id = part.get("id")

            print(
                f"[{current_date}] "
                f"Page={page} "
                f"Row={row_number}/{len(rows)} "
                f"Shot={shot_number} "
                f"Part={part_id}"
            )

            # ------------------------------------------------
            # Savepoint for this individual row
            # ------------------------------------------------

            cur.execute(
                "SAVEPOINT process_row"
            )

            try:

                stored = process_data(
                    data=row,
                    cur=cur,
                    id_client=id_client,
                    id_machine=id_machine,
                )

                cur.execute(
                    "RELEASE SAVEPOINT process_row"
                )

                if stored:

                    total_processed += 1
                    entries_since_commit += 1

                    # ========================================
                    # COMMIT EVERY 10 STORED ROWS
                    # ========================================

                    if entries_since_commit >= COMMIT_EVERY:

                        conn.commit()

                        print(
                            "\n"
                            + "-" * 60
                        )

                        print(
                            f"[BATCH COMMIT] "
                            f"{COMMIT_EVERY} records committed"
                        )

                        print(
                            f"Date: {current_date}"
                        )

                        print(
                            f"Page: {page}"
                        )

                        print(
                            f"Total processed so far: "
                            f"{total_processed}"
                        )

                        print(
                            "-" * 60
                            + "\n"
                        )

                        entries_since_commit = 0

            except Exception as e:

                total_failed += 1

                cur.execute(
                    "ROLLBACK TO SAVEPOINT process_row"
                )

                cur.execute(
                    "RELEASE SAVEPOINT process_row"
                )

                print(
                    f"[ROW ERROR] "
                    f"Date={current_date} "
                    f"Page={page} "
                    f"Row={row_number} "
                    f"Shot={shot_number} "
                    f"Part={part_id}"
                )

                print(
                    f"Error: {e}"
                )

                continue

        # ====================================================
        # PAGINATION
        # ====================================================

        if len(rows) < PAGE_SIZE:

            print(
                f"Final page reached: {page}"
            )

            break

        page += 1

    # ========================================================
    # COMMIT REMAINING RECORDS
    #
    # Example:
    #   Last batch only has 27 records.
    #   We still need to commit those 27.
    # ========================================================

    if entries_since_commit > 0:

        conn.commit()

        print(
            f"\n[FINAL BATCH COMMIT] "
            f"{entries_since_commit} remaining records "
            f"committed for {current_date}"
        )

        entries_since_commit = 0

    print("-" * 80)

    print(
        f"Finished {current_date}: "
        f"{total_received} received, "
        f"{total_processed} processed, "
        f"{total_failed} failed"
    )

    return {
        "received": total_received,
        "processed": total_processed,
        "failed": total_failed,
        "token": token,
    }

# ============================================================
# MONTHLY BACKFILL
# ============================================================

def update_month(
    year: int,
    month: int,
):
    """
    Backfill an entire calendar month.

    Example:
        update_month(2026, 8)

    Processes:

        Aug 01 06:00 -> Aug 02 06:00
        Aug 02 06:00 -> Aug 03 06:00
        ...
        Aug 31 06:00 -> Sep 01 06:00

    Database connection is opened ONCE.

    Each successfully completed day is committed separately.
    """

    first_day = date(
        year,
        month,
        1,
    )

    if month == 12:

        next_month = date(
            year + 1,
            1,
            1,
        )

    else:

        next_month = date(
            year,
            month + 1,
            1,
        )

    last_day = (
        next_month
        - timedelta(days=1)
    )

    print("\n")
    print("=" * 80)
    print("MONTHLY IoT BACKFILL")
    print("=" * 80)

    print(
        f"From: {first_day}"
    )

    print(
        f"To:   {last_day}"
    )

    # --------------------------------------------------------
    # AUTHENTICATE ONCE
    # --------------------------------------------------------

    print("\nAuthenticating with IoT API...")

    token = get_auth_token()

    print("Authentication successful.")

    # --------------------------------------------------------
    # DATABASE CONNECTION OPENED ONCE
    # --------------------------------------------------------

    print("\nConnecting to PostgreSQL...")

    conn = psycopg2.connect(
        **DB_CONFIG
    )

    cur = conn.cursor()

    print("Database connection successful.")

    # --------------------------------------------------------
    # FETCH STATIC IDs ONCE
    # --------------------------------------------------------

    cur.execute(
        """
        SELECT id_client
        FROM client
        WHERE name = %s
        """,
        ("Suzuki",)
    )

    client_result = cur.fetchone()

    if client_result is None:
        raise ValueError(
            "Could not find client 'Suzuki'"
        )

    id_client = client_result[0]

    # This preserves the behavior of your old code.
    #
    # It currently selects the first machine belonging
    # to this client.
    #
    # Later, this should ideally map:
    # data['shot']['machine']
    # to the correct DB machine.
    cur.execute(
        """
        SELECT id_machine
        FROM machine
        WHERE id_client = %s
        LIMIT 1
        """,
        (id_client,)
    )

    machine_result = cur.fetchone()

    if machine_result is None:
        raise ValueError(
            f"No machine found for client "
            f"{id_client}"
        )

    id_machine = machine_result[0]

    print(
        f"Client ID: {id_client}"
    )

    print(
        f"Machine ID: {id_machine}"
    )

    # --------------------------------------------------------
    # MONTH TOTALS
    # --------------------------------------------------------

    month_received = 0
    month_processed = 0
    month_failed = 0

    successful_days = 0
    failed_days = 0

    current_date = first_day

    try:

        # ====================================================
        # DAY LOOP
        # ====================================================

        while current_date < next_month:

            try:

                result = process_one_day(
                    token=token,
                    current_date=current_date,
                    conn=conn,
                    cur=cur,
                    id_client=id_client,
                    id_machine=id_machine,
                )

                token = result["token"]
                # --------------------------------------------
                # COMMIT ONCE PER DAY
                # --------------------------------------------

             
                successful_days += 1

                month_received += (
                    result["received"]
                )

                month_processed += (
                    result["processed"]
                )

                month_failed += (
                    result["failed"]
                )

                print(
                    f"COMMITTED {current_date}"
                )


            except Exception as e:

                # --------------------------------------------
                # Roll back only this day's transaction
                # --------------------------------------------

                conn.rollback()

                failed_days += 1

                print(
                    f"\n[DAY ERROR] "
                    f"{current_date}"
                )

                print(
                    f"Error: {e}"
                )

                print(
                    f"Rolled back {current_date}"
                )

            # -----------------------------------------------
            # NEXT DAY
            # -----------------------------------------------

            current_date += timedelta(days=1)

    finally:

        # ====================================================
        # CLOSE DATABASE ONLY AFTER MONTH IS COMPLETE
        # ====================================================

        cur.close()
        conn.close()

        print(
            "\nDatabase connection closed."
        )

    # --------------------------------------------------------
    # FINAL SUMMARY
    # --------------------------------------------------------

    print("\n")
    print("=" * 80)
    print("MONTHLY BACKFILL COMPLETE")
    print("=" * 80)

    print(
        f"Period: "
        f"{first_day} -> {last_day}"
    )

    print(
        f"Successful days: {successful_days}"
    )

    print(
        f"Failed days: {failed_days}"
    )

    print(
        f"Records received: {month_received}"
    )

    print(
        f"Records processed: {month_processed}"
    )

    print(
        f"Records failed: {month_failed}"
    )

    print("=" * 80)


# ============================================================
# QUALITY PREDICTIONS
# ============================================================

def store_quality_pred(
    predictions,
    part,
    TARGET_DEFECTS,
    cur,
):
    id_part = part["id_part"].iloc[0]
    id_die = part["id_die"].iloc[0]
    id_machine = part["id_machine"].iloc[0]
    id_client = part["id_client"].iloc[0]

    for i in range(
        len(TARGET_DEFECTS)
    ):

        cur.execute(
            """
            INSERT INTO part_quality_prediction (
                id_part,
                id_die,
                id_client,
                id_machine,
                defect_type,
                defect_probability,
                created_at,
                updated_at
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )

            ON CONFLICT (
                id_part,
                defect_type
            )
            DO UPDATE SET
                defect_probability =
                    EXCLUDED.defect_probability,
                updated_at =
                    EXCLUDED.updated_at
            """,
            (
                id_part,
                id_die,
                int(id_client),
                id_machine,
                TARGET_DEFECTS[i],
                predictions[i],
                datetime.now(),
                datetime.now(),
            )
        )

def update_date_range(
    start_date: str,
    end_date: str,
):
    """
    Backfill a specific inclusive date range.

    Example:
        update_date_range(
            "2026-08-12",
            "2026-08-15"
        )

    Processes:
        Aug 12 06:00 -> Aug 13 06:00
        Aug 13 06:00 -> Aug 14 06:00
        Aug 14 06:00 -> Aug 15 06:00
        Aug 15 06:00 -> Aug 16 06:00
    """

    first_day = datetime.strptime(
        start_date,
        "%Y-%m-%d"
    ).date()

    last_day = datetime.strptime(
        end_date,
        "%Y-%m-%d"
    ).date()

    if first_day > last_day:
        raise ValueError(
            "start_date cannot be after end_date"
        )

    print("\n" + "=" * 80)
    print("DATE RANGE IoT BACKFILL")
    print("=" * 80)
    print(f"From: {first_day}")
    print(f"To:   {last_day}")

    # --------------------------------------------------------
    # Authenticate ONCE
    # --------------------------------------------------------

    print("\nAuthenticating with IoT API...")

    token = get_auth_token()

    print("Authentication successful.")

    # --------------------------------------------------------
    # Open DB connection ONCE
    # --------------------------------------------------------

    print("\nConnecting to PostgreSQL...")

    conn = psycopg2.connect(
        **DB_CONFIG
    )

    cur = conn.cursor()

    print("Database connection successful.")

    try:

        # ----------------------------------------------------
        # Get client ID once
        # ----------------------------------------------------

        cur.execute(
            """
            SELECT id_client
            FROM client
            WHERE name = %s
            """,
            ("Suzuki",)
        )

        client_result = cur.fetchone()

        if client_result is None:
            raise ValueError(
                "Could not find client 'Suzuki'"
            )

        id_client = client_result[0]

        # ----------------------------------------------------
        # Get machine ID once
        # ----------------------------------------------------

        cur.execute(
            """
            SELECT id_machine
            FROM machine
            WHERE id_client = %s
            LIMIT 1
            """,
            (id_client,)
        )

        machine_result = cur.fetchone()

        if machine_result is None:
            raise ValueError(
                f"No machine found for client {id_client}"
            )

        id_machine = machine_result[0]

        print(f"Client ID: {id_client}")
        print(f"Machine ID: {id_machine}")

        current_date = first_day

        total_received = 0
        total_processed = 0
        total_failed = 0

        # ====================================================
        # PROCESS ONLY REQUESTED DAYS
        # ====================================================

        while current_date <= last_day:

            try:

                result = process_one_day(
                    token=token,
                    current_date=current_date,
                    conn=conn,
                    cur=cur,
                    id_client=id_client,
                    id_machine=id_machine,
                )

                # Commit every successfully completed day
                conn.commit()

                total_received += result["received"]
                total_processed += result["processed"]
                total_failed += result["failed"]

                print(
                    f"\nCOMMITTED {current_date}"
                )

            except Exception as e:

                conn.rollback()

                print(
                    f"\n[DAY ERROR] {current_date}"
                )

                print(
                    f"Error: {e}"
                )

                print(
                    f"Rolled back {current_date}"
                )

            current_date += timedelta(days=1)

    finally:

        cur.close()
        conn.close()

        print(
            "\nDatabase connection closed."
        )

    print("\n" + "=" * 80)
    print("DATE RANGE BACKFILL COMPLETE")
    print("=" * 80)

    print(
        f"Records received: {total_received}"
    )

    print(
        f"Records processed: {total_processed}"
    )

    print(
        f"Records failed: {total_failed}"
    )

    print("=" * 80)
# ============================================================
# RUN SCRIPT
# ============================================================

if __name__ == "__main__":

    # Example:
    # Backfill all of August 2026

    # update_month(
    #     year=2026,
    #     month=8,
    # )
    update_date_range(
        start_date="2026-08-06",
        end_date="2026-08-31",
    )