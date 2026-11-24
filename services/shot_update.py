"""
PLC shot IoT sync — auth + fetch + upsert into rico.part / operating_parameter.
Credentials and base URLs come from services.config (env).
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Optional
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
    IOT_SHOT_PASSWORD,
    IOT_SHOT_USERNAME,
    IOT_AUTH_PATH_SHOT
)

logger = logging.getLogger(__name__)


TOKEN_JSON_PATH = "token"

DIE_LIST = ["S14", "S16", "S17", "S18"]

SHIFT_CODE = "all"
LIMIT = "100"
PAGE = "1"
SHOT_RESULT = "all"
PAGE_SIZE = "100"
PRODUCTION_DAY_OFFSET = timedelta(hours=6)

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "shot_sync_state.json"
_last_synced_shot_key = None


def _load_last_synced_shot_key():
    global _last_synced_shot_key
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        raw = payload.get("last_synced_shot_key")
        if raw is not None:
            _last_synced_shot_key = int(raw)
    except (OSError, ValueError, TypeError):
        pass
    return _last_synced_shot_key


def _save_last_synced_shot_key(key):
    global _last_synced_shot_key
    if key is None:
        return
    _last_synced_shot_key = key
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(
            json.dumps({"last_synced_shot_key": str(key)}), encoding="utf-8"
        )
    except OSError:
        logger.exception("[shot_update] Could not persist last synced shot key")

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

PARAM_LIST = [
    "cycle_time",
    "die_close_core_in_time",
    "pouring_time",
    "shot_fwd_time",
    "curing_time",
    "die_open_core_out_time",
    "ejector_time",
    "extract_time",
    "spray_time",
    "v1_speed",
    "v2_speed",
    "v3_speed",
    "v4_speed",
    "accel_point",
    "deaccel_point",
    "intensification_time",
    "metal_pressure",
    "biscuit_thickness",
    "clamp_force_pct",
    "clamp_tonnage",
    "shot_acc_pressure",
    "intensification_acc_pressure",
    "furnace_metal_temp",
]

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
            "page": PAGE,
            "shift": SHIFT_CODE,
            "shotResult": SHOT_RESULT,
        }
    )
    return f"/plc-monitor/readings/history?{query}"


def get_auth_token_shot() -> str:
    """POST credentials, return Bearer token string."""
    if not IOT_SHOT_USERNAME or not IOT_SHOT_PASSWORD:
        raise ValueError(
            "IOT_USERNAME / IOT_PASSWORD are not set. Add them to the backend .env file."
        )

    url = f"{IOT_DATA_BASE_URL}{IOT_AUTH_PATH_SHOT}"
    payload = {"username": IOT_SHOT_USERNAME, "password": IOT_SHOT_PASSWORD}

    resp = requests.post(url, json=payload, timeout=IOT_AUTH_TIMEOUT)
    resp.raise_for_status()
    body = resp.json()

    token = body['data']
    for key in TOKEN_JSON_PATH.split("."):
        token = token[key]

    if not isinstance(token, str):
        raise ValueError(f"Expected a string token at '{TOKEN_JSON_PATH}', got: {token!r}")
    return token


def get_iot_data_shot(token: str, data_path: str) -> list[tuple[str, str]]:
    """GET PLC readings and persist every shot newer than the last synced shot.

    Rows are newest-first. Scans from page 1 until it reaches rows already
    synced, collecting all newer rows across page boundaries, then processes
    them oldest-to-newest.
    """
    logger.info("[shot_update] Fetching %s", f"{IOT_DATA_BASE_URL}{data_path}")
    headers = {"Authorization": f"Bearer {token}"}
    max_pages = 50

    def fetch_page(page_num):
        page_path = (
            re.sub(r"page=\d+", f"page={page_num}", data_path)
            if re.search(r"page=\d+", data_path)
            else data_path + f"&page={page_num}"
        )
        resp = requests.get(
            f"{IOT_DATA_BASE_URL}{page_path}",
            headers=headers,
            timeout=IOT_DATA_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    cursor = _load_last_synced_shot_key()
    new_rows = []
    seen = set()
    found = False

    for page in range(1, max_pages + 1):
        try:
            data = fetch_page(page)
        except Exception:
            logger.exception("[shot_update] Error fetching page %s", page)
            break

        rows = data.get("data") or []
        if not rows:
            break

        pagination = data.get("pagination") or data.get("meta") or {}
        has_next = pagination.get("hasNextPage")
        if has_next is None:
            has_next = pagination.get("has_next_page")
        raw_total = (
            pagination.get("totalPages")
            or pagination.get("total_pages")
            or pagination.get("lastPage")
        )
        try:
            total_pages = int(raw_total) if raw_total is not None else None
        except (TypeError, ValueError):
            total_pages = None

        for row in rows:
            try:
                key = int(build_part_id(row))
            except (KeyError, TypeError, ValueError):
                logger.warning("[shot_update] Skipping row without a usable shot id")
                continue
            if cursor is not None and key <= cursor:
                found = True
                break
            if key in seen:
                continue
            seen.add(key)
            new_rows.append((key, row))

        if found:
            break
        if has_next is False or (total_pages is not None and page >= total_pages):
            break

    if cursor is not None and not found:
        logger.warning(
            "[shot_update] Last synced shot not found within %s pages; processed %s rows",
            max_pages, len(new_rows),
        )

    saved = []
    last_success_key = cursor
    for key, row in reversed(new_rows):
        result = process_data_shot(row)
        if result:
            saved.append(result)
            if last_success_key is None or key > last_success_key:
                last_success_key = key

    if last_success_key != cursor:
        _save_last_synced_shot_key(last_success_key)

    logger.info(
        "[shot_update] Saved %s of %s newer shot rows (last key %s)",
        len(saved), len(new_rows), last_success_key,
    )
    return saved


def date_processing(raw_date: str) -> datetime:
    naive = datetime.fromisoformat(raw_date.replace("Z", ""))
    ist = timezone(timedelta(hours=5, minutes=30))
    return naive.replace(tzinfo=ist)


def derive_production_date(row: dict, date_ist: datetime) -> date:
    return (date_ist - PRODUCTION_DAY_OFFSET).date()


def build_part_id(row: dict) -> str:
    fields = ("shot_month", "shot_day", "shot_hour", "shot_minute")
    prefix = "".join(str(row[field]).zfill(2) for field in fields)
    machine_digit = (row.get("machine_name") or "")[-1:]
    return f"{prefix}{machine_digit}{int(row['shot_number']):04d}"


def process_data_shot(data: dict) -> Optional[tuple[str, str]]:
    """Upsert the shot part; return ``(id_die, id_part)`` when a part was saved."""
    id_die = data.get("die_name")
    logger.info("[shot_update] die_name=%s", id_die)
    if id_die not in DIE_LIST:
        return None

    machine_id = data["machine_name"]
    if machine_id[-1:] != "2":
        logger.info("[shot_update] Skipping machine %s (not UBE 850T-02)", machine_id)
        return None

    part_id = build_part_id(data)
    shot_number = int(data["shot_number"])
    date_ist = date_processing(data["recorded_at"])
    production_date = derive_production_date(data, date_ist)
    logger.info(
        "[shot_update] part_id=%s shot_number=%s production_date=%s",
        part_id, shot_number, production_date,
    )

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

        cur.execute(
            """
            INSERT INTO part (
                id_part, id_die, id_client, id_machine,
                manufactored_on, created_at, shot_number, production_date, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id_part) DO UPDATE SET
                id_die = EXCLUDED.id_die,
                id_client = EXCLUDED.id_client,
                id_machine = EXCLUDED.id_machine,
                manufactored_on = EXCLUDED.manufactored_on,
                shot_number = EXCLUDED.shot_number,
                production_date = EXCLUDED.production_date,
                status = EXCLUDED.status
            """,
            (
                part_id,
                id_die,
                id_client,
                id_machine,
                date_ist,
                datetime.now(),
                shot_number,
                production_date,
                "in_progress",
            ),
        )

        for param, val in data.items():
            if param not in PARAM_LIST:
                continue
            param_name = param
            param_lower_tolerance = data.get(f"{param}_lower_limit") or 0
            param_upper_tolerance = data.get(f"{param}_upper_limit") or 0
            uom = names_UOM[param]
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
        return id_die, part_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
