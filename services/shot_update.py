"""
PLC shot IoT sync — auth + fetch + upsert into rico.part / operating_parameter.
Credentials and base URLs come from services.config (env).
"""
from __future__ import annotations

import logging
from datetime import datetime, date, timedelta, timezone
from urllib.parse import urlencode

import psycopg2
import requests

from services.config import (
    DB_CONFIG,
    IOT_AUTH_TIMEOUT,
    IOT_BASE_URL,
    IOT_DATA_BASE_URL,
    IOT_DATA_TIMEOUT,
    IOT_MACHINE_IP,
    IOT_PASSWORD,
    IOT_USERNAME,
)

logger = logging.getLogger(__name__)

AUTH_PATH = "/v1/auth/login"
TOKEN_JSON_PATH = "token"

DIE_LIST = ["S14", "S16", "S17", "S18"]

SHIFT_CODE = "all"
LIMIT = "2000"
PAGE = "1"
SHOT_RESULT = "all"
PAGE_SIZE = "200"

names_UOM = {
    "accel_point": ["ACCEL. POINT", "mm"],
    "biscuit_thickness": ["BISCUIT THICKNESS", "mm"],
    "clamp_force_pct": ["CLAMP FORCE", "%"],
    "clamp_tonnage": ["CLAMP TONNAGE", "Mn"],
    "curing_time": ["CURING TIME", "sec"],
    "deaccel_point": ["DEACEL. POINT", "mm"],
    "die_open_core_out_time": ["DIE OPEN CORE OUT TIME", "sec"],
    "die_close_core_in_time": ["DIE-CLOSE CORE IN TIME", "sec"],
    "ejector_time": ["EJECTOR TIME", "sec"],
    "extract_time": ["EXTRACT TIME", "sec"],
    "furnace_metal_temp": ["FURNACE METAL TEMP.", "C"],
    "intensification_time": ["INTEN. TIME", "msec"],
    "intensification_acc_pressure": ["INTENSIFICATION ACC. PRESSURE", "mPa"],
    "metal_pressure": ["METAL PRESS.", "mPa"],
    "pouring_time": ["POURING TIME", "sec"],
    "shot_acc_pressure": ["SHOT ACC. PRESSURE", "Mpa"],
    "shot_fwd_time": ["SHOT FWD TIME", "sec"],
    "spray_time": ["SPRAY TIME", "sec"],
    "v1_speed": ["V1", "m/sec"],
    "v2_speed": ["V2", "m/sec"],
    "v3_speed": ["V3", "m/sec"],
    "v4_speed": ["V4", "m/sec"],
    "cycle_time": ["cycletime value (sec)", "sec"],
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


def update_date_path_shot() -> str:
    """Build PLC history query path for today's shots."""
    date_from =  date.today().strftime("%Y-%m-%dT00:00:00")
    date_to = (date.today() + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")

    query = urlencode(
        {
            "ip": IOT_MACHINE_IP,
            "from": date_from,
            "to": date_to,
            "limit": LIMIT,
            "shift": SHIFT_CODE,
            "shotResult": SHOT_RESULT,
        }
    )
    return f"/plc-monitor/readings/history?{query}"


def get_auth_token_shot() -> str:
    """POST credentials, return Bearer token string."""
    if not IOT_USERNAME or not IOT_PASSWORD:
        raise ValueError(
            "IOT_USERNAME / IOT_PASSWORD are not set. Add them to the backend .env file."
        )

    url = f"{IOT_BASE_URL}{AUTH_PATH}"
    payload = {"username": IOT_USERNAME, "password": IOT_PASSWORD}

    resp = requests.post(url, json=payload, timeout=IOT_AUTH_TIMEOUT)
    resp.raise_for_status()
    body = resp.json()

    token = body
    for key in TOKEN_JSON_PATH.split("."):
        token = token[key]

    if not isinstance(token, str):
        raise ValueError(f"Expected a string token at '{TOKEN_JSON_PATH}', got: {token!r}")
    return token


def get_iot_data_shot(token: str, data_path: str) -> None:
    """GET latest PLC readings and persist the newest applicable shot."""
    url = f"{IOT_DATA_BASE_URL}{data_path}"
    logger.info("[shot_update] Fetching %s", url)
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, timeout=IOT_DATA_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    rows = data.get("data") or []
    row = rows[0]
    if not rows:
        logger.info("[shot_update] No shot rows returned")
        return

    target_shot = 6671
    # print(rows[0].get("shot_number") == 8754)
    # print(type(rows[0].get("shot_number")))
    # row = next((r for r in rows if r.get("shot_number") == target_shot), None)
    # if row is None:
    #     logger.info("[shot_update] No row with shot_number=%s", target_shot)
    #     return
    process_data_shot(row)


def date_processing(raw_date: str) -> datetime:
    naive = datetime.fromisoformat(raw_date.replace("Z", ""))
    ist = timezone(timedelta(hours=5, minutes=30))
    return naive.replace(tzinfo=ist)


def process_data_shot(data: dict) -> None:
    id_die = data.get("die_name")
    logger.info("[shot_update] die_name=%s", id_die)
    if id_die not in DIE_LIST:
        return

    part_id = (
        data["shot_month"]
        + data["shot_day"]
        + data["shot_hour"]
        + data["shot_minute"]
        + data["machine_name"][-1:]
        + str(data["shot_number"])
    )
    logger.info("[shot_update] part_id=%s", part_id)

    machine_id = data["machine_name"]
    if machine_id[-1:] != "2":
        logger.info("[shot_update] Skipping machine %s (not UBE 850T-02)", machine_id)
        return

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id_client FROM client WHERE name = %s", ("Suzuki",))
        client_row = cur.fetchone()
        if not client_row:
            raise RuntimeError("Client 'Suzuki' not found in rico.client")
        id_client = client_row[0]

        cur.execute("SELECT id_machine FROM machine WHERE id_client = %s", ("1",))
        machine_row = cur.fetchone()
        if not machine_row:
            raise RuntimeError("No machine found for id_client=1")
        id_machine = machine_row[0]

        date_ist = date_processing(data["recorded_at"])

        cur.execute(
            """
            INSERT INTO part (id_part, id_die, id_client, id_machine, manufactored_on, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id_part) DO UPDATE SET
                id_die = EXCLUDED.id_die,
                id_client = EXCLUDED.id_client,
                id_machine = EXCLUDED.id_machine,
                manufactored_on = EXCLUDED.manufactored_on
            """,
            (part_id, id_die, id_client, id_machine, date_ist, datetime.now()),
        )

        for param, val in data.items():
            if param not in PARAM_MAP:
                continue
            param_name = names_UOM[param][0]
            param_lower_tolerance = data.get(f"{param}_lower_limit") or 0
            param_upper_tolerance = data.get(f"{param}_upper_limit") or 0
            uom = names_UOM[param][1]
            cur.execute(
                """
                INSERT INTO operating_parameter (
                    id_part, id_die, id_client, id_machine, parameter_name, "UOM", value,
                    recomended_lower_tolerance, recomended_upper_tolerance, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id_part, parameter_name) DO UPDATE SET
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
                    param_lower_tolerance,
                    param_upper_tolerance,
                    date_ist,
                    datetime.now(),
                ),
            )

        conn.commit()
        logger.info("[shot_update] Saved part %s", part_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
