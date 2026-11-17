"""Convert a shot (PLC) report JSON into an Excel workbook.

Usage:
    python scripts/shot_to_excel.py <shots.json> [output.xlsx]
    python scripts/shot_to_excel.py <shots.json> [output.xlsx] --traceability <trace.json>

The input can be any shot report whose top level is a bare list of records or
a dict with "data" / "records". Pagination metadata is read when present.

Output workbook:
    Summary     counts, date range, dies, machines, status totals
    Shots       one row per shot with identity, timestamps and status
    Parameters  one row per shot with every process parameter value

Timestamps are UTC. The API returns shot_datetime/recorded_at already in UTC
(they match the traceability report exactly); metal_injection_datetime uses
the same clock.

With --traceability, five comparison columns are added, joined on
(machine, shot number, production date):
    In Traceability, Trace Part ID, Trace Part Status, Trace Shot Status,
    Trace Time Match
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
except ImportError:
    sys.exit("openpyxl is required: pip install openpyxl")

SHOT_PARAMS = [
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
    "biscuit_thickness",
    "metal_pressure",
    "clamp_tonnage_he_low_pct",
    "clamp_tonnage_op_up_pct",
    "clamp_tonnage_op_low_pct",
    "clamp_tonnage_he_up_pct",
    "clamp_force_pct",
    "clamp_tonnage",
    "shot_acc_pressure",
    "intensification_acc_pressure",
    "jet_cooling_pressure",
    "vacuum_pressure",
    "cooling_water_mov",
    "cooling_water_sta",
    "furnace_metal_temp",
    "fixed_die_temp_f1",
    "fixed_die_temp_f2",
    "moving_die_temp_m1",
    "moving_die_temp_m2",
    "slide_temp_s1",
    "fix_1_flow",
    "fix_2_flow",
    "fix_3_flow",
    "mov_1_flow",
    "mov_2_flow",
    "mov_3_flow",
    "vacuum_pressure_mmhg",
    "average_die_clamp_tonnage_count",
    "time_for_stroke",
    "stroke",
]

STATUS_LABELS = {1: "OK", 3: "WARM", 5: "OFF"}

STATUS_FILLS = {
    "OK": PatternFill("solid", fgColor="C6EFCE"),
    "WARM": PatternFill("solid", fgColor="FFEB9C"),
    "OFF": PatternFill("solid", fgColor="FFC7CE"),
}

COLUMNS = [
    ("Shot Number", "shot", "0", 12),
    ("Production Date", "production_date", "@", 15),
    ("Shot DateTime (UTC)", "shot_datetime", "yyyy-mm-dd hh:mm:ss", 22),
    ("Recorded At (UTC)", "recorded_at", "yyyy-mm-dd hh:mm:ss", 22),
    ("Machine Name", "machine", "@", 18),
    ("Die", "die", "@", 8),
    ("Part Name", "part_name", "@", 12),
    ("Part Label", "part_label", "@", 14),
    ("Shot Status", "status", "0", 12),
    ("Shot Status Text", "status_text", "@", 15),
    ("Cycle Time (s)", "cycle_time", "0.00", 13),
    ("Parameter Count", "param_count", "0", 15),
    ("Metal Injection At (UTC)", "injection", "yyyy-mm-dd hh:mm:ss", 22),
    ("Reading ID", "reading_id", "@", 12),
]

TRACE_COLUMNS = [
    ("In Traceability", "in_trace", "@", 15),
    ("Trace Part ID", "trace_parts", "@", 20),
    ("Trace Part Status", "trace_part_status", "@", 18),
    ("Trace Shot Status", "trace_shot_status", "@", 17),
    ("Trace Time Match", "trace_time_match", "@", 16),
]


def parse_utc(raw):
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            value = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def load_document(path):
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict):
        records = data.get("data") or data.get("records") or []
        pagination = data.get("pagination") or {}
    elif isinstance(data, list):
        records, pagination = data, {}
    else:
        records, pagination = [], {}
    records = [record for record in records if isinstance(record, dict)]
    return records, pagination


def trace_index(path):
    records, _ = load_document(path)
    index = {}
    for record in records:
        shot = record.get("shot") or {}
        part = record.get("part") or {}
        number = to_int(shot.get("number"))
        machine = shot.get("machine")
        if number is None or not machine:
            continue
        key = (machine, number, shot.get("date"))
        entry = index.setdefault(
            key,
            {"parts": [], "part_status": [], "shot_status": [], "recorded": []},
        )
        part_id = part.get("id")
        if part_id and str(part_id) not in entry["parts"]:
            entry["parts"].append(str(part_id))
        if part.get("status") and part["status"] not in entry["part_status"]:
            entry["part_status"].append(part["status"])
        if shot.get("status") and shot["status"] not in entry["shot_status"]:
            entry["shot_status"].append(shot["status"])
        if shot.get("recordedAt"):
            entry["recorded"].append(parse_utc(shot["recordedAt"]))
    return index


def build_row(record):
    shot_number = to_int(record.get("shot_number"))
    status = to_int(record.get("shot_status"))
    param_count = sum(
        1
        for name in SHOT_PARAMS
        if record.get(name) not in (None, "")
    )
    return {
        "shot": shot_number,
        "production_date": str(record.get("production_date") or ""),
        "shot_datetime": parse_utc(record.get("shot_datetime")),
        "recorded_at": parse_utc(record.get("recorded_at")),
        "machine": record.get("machine_name") or "",
        "die": record.get("die_name") or "",
        "part_name": record.get("part_name") or "",
        "part_label": record.get("Part Name") or "",
        "status": status,
        "status_text": STATUS_LABELS.get(status, ""),
        "cycle_time": record.get("cycle_time"),
        "param_count": param_count,
        "injection": parse_utc(record.get("metal_injection_datetime")),
        "reading_id": str(record.get("id") or ""),
        "params": record,
    }


def augment_trace(row, index):
    key = (row["machine"], row["shot"], row["production_date"])
    entry = index.get(key)
    if not entry:
        row.update(
            in_trace="No",
            trace_parts="",
            trace_part_status="",
            trace_shot_status="",
            trace_time_match="",
        )
        return
    row["in_trace"] = "Yes"
    row["trace_parts"] = ", ".join(entry["parts"])
    row["trace_part_status"] = ", ".join(entry["part_status"])
    row["trace_shot_status"] = ", ".join(entry["shot_status"])
    times = [value for value in entry["recorded"] if value is not None]
    if row["recorded_at"] and times:
        row["trace_time_match"] = (
            "Yes" if any(value == row["recorded_at"] for value in times) else "No"
        )
    else:
        row["trace_time_match"] = ""


def style_header(worksheet, width_map):
    for cell in worksheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for index, width in enumerate(width_map, start=1):
        worksheet.column_dimensions[get_column_letter(index)].width = width
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = (
        f"A1:{get_column_letter(worksheet.max_column)}{worksheet.max_row}"
    )
    worksheet.sheet_view.zoomScale = 90


def write_shots(worksheet, rows, columns):
    worksheet.append([header for header, _, _, _ in columns])
    for row in rows:
        worksheet.append([row.get(key) for _, key, _, _ in columns])

    formats = {index: fmt for index, (_, _, fmt, _) in enumerate(columns, start=1)}
    status_index = next(
        (i for i, (_, key, _, _) in enumerate(columns, start=1) if key == "status_text"),
        None,
    )
    trace_index_column = next(
        (i for i, (_, key, _, _) in enumerate(columns, start=1) if key == "in_trace"),
        None,
    )
    match_index = next(
        (i for i, (_, key, _, _) in enumerate(columns, start=1) if key == "trace_time_match"),
        None,
    )
    for row_cells in worksheet.iter_rows(min_row=2):
        for index, fmt in formats.items():
            row_cells[index - 1].number_format = fmt
            if fmt == "yyyy-mm-dd hh:mm:ss":
                row_cells[index - 1].alignment = Alignment(horizontal="center")
        if status_index:
            fill = STATUS_FILLS.get(str(row_cells[status_index - 1].value))
            if fill:
                row_cells[status_index - 1].fill = fill
        if trace_index_column:
            cell = row_cells[trace_index_column - 1]
            if cell.value == "Yes":
                cell.fill = PatternFill("solid", fgColor="DDEBF7")
        if match_index:
            cell = row_cells[match_index - 1]
            if cell.value == "Yes":
                cell.fill = PatternFill("solid", fgColor="C6EFCE")
            elif cell.value == "No":
                cell.fill = PatternFill("solid", fgColor="FFC7CE")

    style_header(worksheet, [width for _, _, _, width in columns])


def write_parameters(worksheet, rows):
    headers = ["Shot Number", "Die", "Machine Name", "Recorded At (UTC)"] + SHOT_PARAMS
    worksheet.append(headers)
    for row in rows:
        source = row["params"]
        worksheet.append(
            [
                row["shot"],
                row["die"],
                row["machine"],
                row["recorded_at"],
            ]
            + [source.get(name) for name in SHOT_PARAMS]
        )
    for row_cells in worksheet.iter_rows(min_row=2):
        row_cells[0].number_format = "0"
        row_cells[3].number_format = "yyyy-mm-dd hh:mm:ss"
        for cell in row_cells[4:]:
            cell.number_format = "General"
    widths = [12, 8, 18, 22] + [13] * len(SHOT_PARAMS)
    for index in range(1, 4):
        worksheet.column_dimensions[get_column_letter(index)].width = widths[index - 1]
    style_header(worksheet, widths)
    worksheet.freeze_panes = "E2"


def add_summary(worksheet, rows, source, pagination, trace_path):
    records = len(rows)
    production_dates = sorted({row["production_date"] for row in rows if row["production_date"]})
    dies = sorted({row["die"] for row in rows if row["die"]})
    machines = sorted({row["machine"] for row in rows if row["machine"]})
    times = [row["recorded_at"] for row in rows if row["recorded_at"]]
    counts = {label: 0 for label in STATUS_LABELS.values()}
    for row in rows:
        if row["status_text"] in counts:
            counts[row["status_text"]] += 1
    param_counts = [row["param_count"] for row in rows] or [0]

    entries = [
        ("Input file", str(source)),
        ("Loaded records", records),
        ("Pagination total", pagination.get("total", "")),
        ("Pagination pages", pagination.get("totalPages", "")),
        ("Production dates", ", ".join(production_dates)),
        ("Dies", ", ".join(dies)),
        ("Machines", ", ".join(machines)),
        ("First recorded (UTC)", min(times) if times else ""),
        ("Last recorded (UTC)", max(times) if times else ""),
        ("Shot status OK", counts.get("OK", 0)),
        ("Shot status WARM", counts.get("WARM", 0)),
        ("Shot status OFF", counts.get("OFF", 0)),
        ("Parameters present", f"{min(param_counts)}-{max(param_counts)}"),
    ]
    if trace_path is not None:
        matched = sum(1 for row in rows if row.get("in_trace") == "Yes")
        entries.extend(
            [
                ("Traceability file", str(trace_path)),
                ("Matched in traceability", matched),
                ("Not in traceability", records - matched),
            ]
        )

    worksheet.append(["Metric", "Value"])
    for label, value in entries:
        worksheet.append([label, value])
    for cell in worksheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
    for row_cells in worksheet.iter_rows(min_row=2):
        row_cells[0].font = Font(bold=True)
        if isinstance(row_cells[1].value, datetime):
            row_cells[1].number_format = "yyyy-mm-dd hh:mm:ss"
    worksheet.column_dimensions["A"].width = 26
    worksheet.column_dimensions["B"].width = 60
    worksheet.freeze_panes = "A2"


def main():
    parser = argparse.ArgumentParser(
        description="Convert a shot (PLC) report JSON into an Excel workbook."
    )
    parser.add_argument("input", type=Path, help="shot report .json")
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        help="output .xlsx (default: same name as input, .xlsx)",
    )
    parser.add_argument(
        "--traceability",
        type=Path,
        help="traceability report .json to add cross-reference columns",
    )
    args = parser.parse_args()

    source = args.input
    if not source.is_file():
        sys.exit(f"Input not found: {source}")
    if args.traceability is not None and not args.traceability.is_file():
        sys.exit(f"Traceability not found: {args.traceability}")
    destination = args.output or source.with_suffix(".xlsx")

    records, pagination = load_document(source)
    rows = [build_row(record) for record in records]
    rows.sort(
        key=lambda row: (
            row["recorded_at"] is None,
            row["recorded_at"] or datetime.min,
            row["shot"] if row["shot"] is not None else -1,
        )
    )

    index = trace_index(args.traceability) if args.traceability else None
    if index is not None:
        for row in rows:
            augment_trace(row, index)

    columns = COLUMNS + (TRACE_COLUMNS if index is not None else [])

    workbook = Workbook()
    summary = workbook.active
    summary.title = "Summary"
    add_summary(summary, rows, source, pagination, args.traceability)

    shots_sheet = workbook.create_sheet("Shots")
    write_shots(shots_sheet, rows, columns)

    parameters_sheet = workbook.create_sheet("Parameters")
    write_parameters(parameters_sheet, rows)

    try:
        workbook.save(destination)
    except PermissionError:
        sys.exit(f"Cannot write {destination} - close it in Excel and retry")

    total = pagination.get("total")
    print(f"Input:  {source}")
    print(f"Output: {destination}")
    print(f"Shots:      {len(rows)} rows")
    if total not in (None, "") and int(total) != len(rows):
        print(f"WARNING:     pagination.total={total} but only {len(rows)} rows loaded")
    print(
        "Statuses:   "
        + ", ".join(
            f"{label}={sum(1 for row in rows if row['status_text'] == label)}"
            for label in ("OK", "WARM", "OFF")
        )
    )
    if index is not None:
        matched = sum(1 for row in rows if row.get("in_trace") == "Yes")
        print(f"Traceability: {matched} matched, {len(rows) - matched} not matched")
    print(f"Size:       {destination.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
