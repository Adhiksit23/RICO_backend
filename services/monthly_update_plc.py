"""Backfill PLC shot history into rico.part / operating_parameter.

Intended flow after emptying part data:

    TRUNCATE rico.part CASCADE;
    python -m services.monthly_update_shot <month> <year>
    python -m services.monthly_update_plc YYYY-MM-DD YYYY-MM-DD

The reports/traceability refill runs first and owns customer_qr and defect
data. This script then inserts only the shots that refill did not cover,
keyed by (id_die, shot_number, production_date). It is idempotent: rerunning
or overlapping date ranges skips parts that already exist.

Requires migrations/002_part_shot_identity.sql (shot_number, production_date).
Quality predictions and monitor results are produced by the live schedulers
and are not written by this backfill.

Dedupe is by (id_die, shot_number, production_date). id_part is only a
surrogate: the reports API stamps part.id from the shot-start minute while the
PLC API exposes the read minute, so the two can differ by one minute. Never
match parts by id_part string; use the numeric key. Run the reports refill
before this script so shots it owns are skipped rather than duplicated.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

import psycopg2
import requests

from services.config import (
    DB_CONFIG,
    IOT_AUTH_PATH_SHOT,
    IOT_AUTH_TIMEOUT,
    IOT_DATA_BASE_URL,
    IOT_DATA_TIMEOUT,
    IOT_MACHINE_IP,
    IOT_SHOT_PASSWORD,
    IOT_SHOT_USERNAME,
)

DIE_LIST = ["S14", "S16", "S17", "S18"]
TARGET_MACHINE_SUFFIX = "2"
PAGE_SIZE = 100
COMMIT_EVERY = 10
SHIFT_CODE = "all"
SHOT_RESULT = "all"
TOKEN_JSON_PATH = "token"
IST = timezone(timedelta(hours=5, minutes=30))
PRODUCTION_DAY_OFFSET = timedelta(hours=6)

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


def get_auth_token() -> str:
    if not IOT_SHOT_USERNAME or not IOT_SHOT_PASSWORD:
        raise ValueError("IOT_SHOT_USERNAME / IOT_SHOT_PASSWORD are not set")

    url = f"{IOT_DATA_BASE_URL}{IOT_AUTH_PATH_SHOT}"
    resp = requests.post(
        url,
        json={"username": IOT_SHOT_USERNAME, "password": IOT_SHOT_PASSWORD},
        timeout=IOT_AUTH_TIMEOUT,
    )
    resp.raise_for_status()

    token = resp.json()["data"]
    for key in TOKEN_JSON_PATH.split("."):
        token = token[key]

    if not isinstance(token, str):
        raise ValueError(f"Expected token string at '{TOKEN_JSON_PATH}'")
    return token


def build_history_path(design_date: date, page: int) -> str:
    query = urlencode(
        {
            "ip": IOT_MACHINE_IP,
            "from": design_date.strftime("%Y-%m-%dT00:00:00"),
            "to": (design_date + timedelta(days=2)).strftime("%Y-%m-%dT00:00:00"),
            "limit": PAGE_SIZE,
            "page": page,
            "shift": SHIFT_CODE,
            "shotResult": SHOT_RESULT,
        }
    )
    return f"/plc-monitor/readings/history?{query}"


def fetch_page(token: str, path: str):
    url = f"{IOT_DATA_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}

    print(f"\nGET {url}")

    resp = requests.get(url, headers=headers, timeout=IOT_DATA_TIMEOUT)

    print(f"Status code: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('Content-Type')}")
    print(f"API request time: {resp.elapsed.total_seconds():.2f}s")

    if resp.status_code == 401:
        print("[AUTH] Token expired or unauthorized.")
        print("[AUTH] Getting a new token...")

        token = get_auth_token()
        headers = {"Authorization": f"Bearer {token}"}

        print("[AUTH] Retrying request with new token...")

        resp = requests.get(url, headers=headers, timeout=IOT_DATA_TIMEOUT)

        print(f"Retry status code: {resp.status_code}")

    resp.raise_for_status()
    body = resp.json()

    rows = body.get("data") or []
    pagination = body.get("pagination") or {}

    print("Pagination section of data:", pagination)
    print(f"Number of records is {len(rows)}")

    return rows, pagination, token


def parse_api_time(raw: str) -> datetime:
    naive = datetime.fromisoformat(str(raw).replace("Z", ""))
    return naive.replace(tzinfo=IST)


def resolve_production_date(row: dict, recorded: datetime) -> date:
    raw = row.get("production_date") or row.get("shot_date")
    if raw:
        try:
            return date.fromisoformat(str(raw)[:10])
        except ValueError:
            pass
    return (recorded - PRODUCTION_DAY_OFFSET).date()


def build_part_id(row: dict, recorded: datetime) -> str:
    fields = ("shot_month", "shot_day", "shot_hour", "shot_minute")
    if all(row.get(field) not in (None, "") for field in fields):
        prefix = "".join(str(row[field]).zfill(2) for field in fields)
    else:
        prefix = recorded.strftime("%m%d%H%M")
    machine_digit = (row.get("machine_name") or "")[-1:]
    return f"{prefix}{machine_digit}{int(row['shot_number']):04d}"


def find_existing(cur, id_die: str, shot_number: int, production_date: date):
    cur.execute(
        """
        SELECT id_part
        FROM rico.part
        WHERE id_die = %s
          AND (
                (shot_number = %s AND production_date = %s)
             OR (substring(id_part FROM 10) ~ '^[0-9]+$'
                 AND substring(id_part FROM 10)::bigint = %s
                 AND ((manufactored_on AT TIME ZONE 'Asia/Kolkata')
                      - interval '6 hours')::date = %s)
          )
        LIMIT 1
        """,
        (id_die, shot_number, production_date, shot_number, production_date),
    )
    row = cur.fetchone()
    return row[0] if row else None


def store_shot(cur, row: dict, design_date: date, id_client, id_machine) -> str:
    id_die = row.get("die_name")
    if id_die not in DIE_LIST:
        print(f"[SKIP] Die {id_die} not in DIE_LIST")
        return "skip_die"

    if (row.get("machine_name") or "")[-1:] != TARGET_MACHINE_SUFFIX:
        print(
            f"[SKIP] Machine {row.get('machine_name')} does not end "
            f"with target suffix {TARGET_MACHINE_SUFFIX}"
        )
        return "skip_machine"

    if row.get("shot_number") is None or not row.get("recorded_at"):
        print(
            f"[SKIP] Incomplete row: shot={row.get('shot_number')} "
            f"recorded_at={row.get('recorded_at')}"
        )
        return "skip_incomplete"

    try:
        shot_number = int(row["shot_number"])
        recorded = parse_api_time(row["recorded_at"])
    except (TypeError, ValueError):
        print(
            f"[SKIP] Invalid shot/recorded_at: shot={row.get('shot_number')} "
            f"recorded_at={row.get('recorded_at')}"
        )
        return "skip_invalid"

    production_date = resolve_production_date(row, recorded)
    if production_date != design_date:
        print(
            f"[SKIP] Shot {shot_number} production_date={production_date} "
            f"!= design_date={design_date}"
        )
        return "skip_other_date"

    existing_part_id = find_existing(cur, id_die, shot_number, production_date)
    if existing_part_id:
        print(
            f"[EXISTS] Shot {shot_number} on {production_date} "
            f"already stored as {existing_part_id}"
        )
        return "exists"

    part_id = build_part_id(row, recorded)

    cur.execute(
        """
        INSERT INTO rico.part (
            id_part, id_die, id_client, id_machine,
            manufactored_on, created_at, shot_number, production_date, status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id_part) DO NOTHING
        """,
        (
            part_id,
            id_die,
            id_client,
            id_machine,
            recorded,
            datetime.now(IST),
            shot_number,
            production_date,
            "in_progress",
        ),
    )

    if cur.rowcount == 0:
        print(
            f"[EXISTS] Shot {shot_number} part={part_id} "
            f"insert skipped (id_part conflict)"
        )
        return "exists"

    param_count = 0

    for param in PARAM_LIST:
        value = row.get(param)
        if value is None:
            continue

        uom = names_UOM.get(param)
        if uom is None:
            print(f"[WARNING] No UOM mapping for {param}")
            continue

        cur.execute(
            """
            INSERT INTO rico.operating_parameter (
                id_part, id_die, id_client, id_machine, parameter_name, "UOM",
                value, recomended_lower_tolerance, recomended_upper_tolerance,
                created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id_part, parameter_name) DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = EXCLUDED.updated_at
            """,
            (
                part_id,
                id_die,
                id_client,
                id_machine,
                param,
                uom,
                value,
                row.get(f"{param}_lower_limit") or 0,
                row.get(f"{param}_upper_limit") or 0,
                recorded,
                datetime.now(IST),
            ),
        )
        param_count += 1

    print(
        f"[INSERT] Shot {shot_number} part={part_id} "
        f"production_date={production_date} params={param_count}"
    )

    return "inserted"


def process_day(token, design_date: date, conn, cur, id_client, id_machine):
    print("\n" + "=" * 80)
    print(f"PROCESSING DATE: {design_date}")
    print("=" * 80)

    page = 1
    pending = 0
    stats = {"received": 0, "inserted": 0, "exists": 0, "skipped": 0, "failed": 0}

    while True:
        rows, pagination, token = fetch_page(token, build_history_path(design_date, page))
        if not rows:
            print(f"No records returned on page {page}.")
            break

        stats["received"] += len(rows)

        print(
            f"Date: {design_date} | "
            f"Page: {page} | "
            f"Records: {len(rows)}"
        )

        for row_number, row in enumerate(rows, start=1):
            print(
                f"[{design_date}] "
                f"Page={page} "
                f"Row={row_number}/{len(rows)} "
                f"Shot={row.get('shot_number')} "
                f"Die={row.get('die_name')} "
                f"Machine={row.get('machine_name')}"
            )

            cur.execute("SAVEPOINT backfill_row")
            try:
                outcome = store_shot(cur, row, design_date, id_client, id_machine)
                cur.execute("RELEASE SAVEPOINT backfill_row")
            except Exception as exc:
                cur.execute("ROLLBACK TO SAVEPOINT backfill_row")
                cur.execute("RELEASE SAVEPOINT backfill_row")
                stats["failed"] += 1
                print(
                    f"[ROW ERROR] date={design_date} page={page} "
                    f"shot={row.get('shot_number')} die={row.get('die_name')}: {exc}"
                )
                continue

            if outcome == "inserted":
                stats["inserted"] += 1
                pending += 1
                if pending >= COMMIT_EVERY:
                    conn.commit()
                    print("\n" + "-" * 60)
                    print(f"[BATCH COMMIT] {COMMIT_EVERY} records committed")
                    print(f"Date: {design_date}")
                    print(f"Page: {page}")
                    print(f"Total inserted so far: {stats['inserted']}")
                    print("-" * 60 + "\n")
                    pending = 0
            elif outcome == "exists":
                stats["exists"] += 1
            else:
                stats["skipped"] += 1

        total_pages = pagination.get("totalPages") or pagination.get("total_pages")
        try:
            if total_pages and page >= int(total_pages):
                print(f"Final page reached: {page}")
                break
        except (TypeError, ValueError):
            pass

        if len(rows) < PAGE_SIZE:
            print(f"Final page reached: {page}")
            break
        page += 1

    if pending:
        conn.commit()
        print(
            f"\n[FINAL BATCH COMMIT] {pending} remaining records "
            f"committed for {design_date}"
        )

    print("-" * 80)
    print(
        f"Finished {design_date}: "
        f"{stats['received']} received, "
        f"{stats['inserted']} inserted, "
        f"{stats['exists']} existed, "
        f"{stats['skipped']} skipped, "
        f"{stats['failed']} failed"
    )

    return stats, token


def update_date_range(start_date: str, end_date: str) -> dict:
    first = date.fromisoformat(start_date)
    last = date.fromisoformat(end_date)
    if first > last:
        raise ValueError("start_date cannot be after end_date")

    print("\n" + "=" * 80)
    print("PLC DATE RANGE BACKFILL")
    print("=" * 80)
    print(f"From: {first}")
    print(f"To:   {last}")

    # --------------------------------------------------------
    # AUTHENTICATE ONCE
    # --------------------------------------------------------

    print("\nAuthenticating with PLC API...")

    token = get_auth_token()

    print("Authentication successful.")

    # --------------------------------------------------------
    # DATABASE CONNECTION OPENED ONCE
    # --------------------------------------------------------

    print("\nConnecting to PostgreSQL...")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    print("Database connection successful.")

    totals = {"received": 0, "inserted": 0, "exists": 0, "skipped": 0, "failed": 0}
    failed_days = 0

    try:
        cur.execute("SELECT id_client FROM rico.client WHERE name = %s", ("Suzuki",))
        client_row = cur.fetchone()
        if not client_row:
            raise RuntimeError("Client 'Suzuki' not found in rico.client")
        id_client = client_row[0]

        cur.execute(
            "SELECT id_machine FROM rico.machine WHERE id_client = %s LIMIT 1",
            (id_client,),
        )
        machine_row = cur.fetchone()
        if not machine_row:
            raise RuntimeError(f"No machine found for client {id_client}")
        id_machine = machine_row[0]

        print(f"Client ID: {id_client}")
        print(f"Machine ID: {id_machine}")

        print("\nChecking required schema columns...")

        cur.execute(
            """
            SELECT count(*) FROM information_schema.columns
            WHERE table_schema = 'rico' AND table_name = 'part'
              AND column_name IN ('shot_number', 'production_date', 'status')
            """
        )
        if cur.fetchone()[0] != 3:
            raise RuntimeError(
                "Run migrations/002_part_shot_identity.sql and "
                "003_part_status.sql before this script"
            )

        print("Schema check passed.")

        current = first
        while current <= last:
            try:
                stats, token = process_day(
                    token, current, conn, cur, id_client, id_machine
                )
                conn.commit()
                for key in totals:
                    totals[key] += stats[key]
                print(f"\nCOMMITTED {current}")
                print(
                    f"{current}: inserted={stats['inserted']} "
                    f"exists={stats['exists']} skipped={stats['skipped']} "
                    f"failed={stats['failed']}"
                )
            except Exception as exc:
                conn.rollback()
                failed_days += 1
                print(f"[DAY ERROR] {current}: {exc}")
            current += timedelta(days=1)
    finally:
        cur.close()
        conn.close()

        print("\nDatabase connection closed.")

    totals["failed_days"] = failed_days

    print("\n" + "=" * 80)
    print("PLC BACKFILL COMPLETE")
    print("=" * 80)
    print(f"Records received: {totals['received']}")
    print(f"Parts inserted:   {totals['inserted']}")
    print(f"Parts existed:    {totals['exists']}")
    print(f"Rows skipped:     {totals['skipped']}")
    print(f"Rows failed:      {totals['failed']}")
    print(f"Failed days:      {failed_days}")
    print("=" * 80)

    return totals


if __name__ == "__main__":
    args = sys.argv[1:]

    if args and args[0].startswith("--"):
        start = None
        end = None
        index = 0

        while index < len(args):
            flag = args[index]

            if flag == "--from":
                start = args[index + 1]
                index += 2
            elif flag == "--to":
                end = args[index + 1]
                index += 2
            elif flag == "--date":
                start = end = args[index + 1]
                index += 2
            else:
                raise SystemExit(f"unknown argument: {flag}")

        if start is None:
            raise SystemExit("--from or --date is required")

        update_date_range(start, end or start)

    else:
        if len(args) != 2:
            raise SystemExit(
                "usage:\n"
                "  python -m services.monthly_update_plc YYYY-MM-DD YYYY-MM-DD\n"
                "  python -m services.monthly_update_plc --from YYYY-MM-DD --to YYYY-MM-DD\n"
                "  python -m services.monthly_update_plc --date YYYY-MM-DD"
            )

        update_date_range(args[0], args[1])
