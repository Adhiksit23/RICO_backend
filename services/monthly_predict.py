"""Backfill quality predictions for historical parts.

Run AFTER the traceability refill (monthly_update_shot) and the PLC gap fill
(monthly_update_plc), because it reads operating_parameter.

Rules:
  * calibration is as-of-shot: newest die_calibration with
    calibration_date <= production_date. When a shot predates every
    calibration for its die, the earliest calibration is used instead.
  * model is as-of-shot: per-die models are used only when the shot date is on
    or after the model date; parts before that use the older global models.
  * a part missing any parameter required by its models is skipped entirely.
  * predictions are overwritten (upsert on (id_part, defect_type)).

Usage:
    python -m services.monthly_predict --date 2026-11-03
    python -m services.monthly_predict --from 2026-06-27 --to 2026-11-16
"""
from __future__ import annotations

import pickle
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import psycopg2
from psycopg2.extras import execute_values

from services.config import DB_CONFIG
from services.predictor import PARAM_MAPPING, TARGET_DEFECTS

DIE_LIST = ["S14", "S16", "S17", "S18"]
MODEL_ROOT = Path(__file__).resolve().parent.parent / "models"

# S16 calibration only uses the long names; the per-die tables use short names.
EXTRA_PARAM_MAPPING = {
    "DIE-CLOSE CORE IN TIME": "die_close_core_in_time",
}

_MODEL_DATE_RE = re.compile(r"_(\d{8})_voting\.pkl$")
_MODEL_CACHE: dict[str, dict] = {}
_CALIBRATION_CACHE: dict[int, dict] = {}


def _canonical_param(name: str) -> str:
    name = str(name).strip()
    if name in PARAM_MAPPING:
        return PARAM_MAPPING[name]
    if name in EXTRA_PARAM_MAPPING:
        return EXTRA_PARAM_MAPPING[name]
    return name


def _model_date(path: Path) -> Optional[date]:
    match = _MODEL_DATE_RE.search(path.name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d").date()
    except ValueError:
        return None


def model_path_asof(die: str, defect: str, production_date: date) -> Optional[Path]:
    tag = defect.replace(" ", "_")

    if die != "S16":
        candidates = []
        for path in (MODEL_ROOT / die).glob(f"{die}_{tag}_*_voting.pkl"):
            stamp = _model_date(path)
            if stamp is not None and stamp <= production_date:
                candidates.append((stamp, path))
        if candidates:
            return max(candidates, key=lambda item: (item[0], item[1].name))[1]

    global_candidates = []
    for path in MODEL_ROOT.glob(f"{tag}_*_voting.pkl"):
        stamp = _model_date(path)
        if stamp is not None:
            global_candidates.append((stamp, path))

    eligible = [item for item in global_candidates if item[0] <= production_date]
    if eligible:
        return max(eligible, key=lambda item: item[0])[1]

    if global_candidates:
        return min(global_candidates, key=lambda item: item[0])[1]

    return None


def _load_model(path: Path) -> dict:
    key = str(path)
    if key not in _MODEL_CACHE:
        with open(path, "rb") as handle:
            _MODEL_CACHE[key] = pickle.load(handle)
    return _MODEL_CACHE[key]


def _feature_specs(model: dict) -> list[tuple[str, int]]:
    specs = []
    for feature in model["scaler"].feature_names_in_:
        if feature.endswith("_inrange"):
            base, kind = feature[: -len("_inrange")], 0
        elif feature.endswith("_pctdev"):
            base, kind = feature[: -len("_pctdev")], 1
        else:
            raise ValueError(f"Unexpected model feature: {feature}")
        specs.append((_canonical_param(base), kind))
    return specs


def _calibration_for(cur, die: str, day: date) -> tuple[Optional[int], bool]:
    """Return (calibration_id, used_earliest_fallback)."""
    cur.execute(
        """
        SELECT id_calibration
        FROM rico.die_calibration
        WHERE id_die = %s
          AND calibration_date IS NOT NULL
          AND calibration_date <= %s
        ORDER BY calibration_date DESC, id_calibration DESC
        LIMIT 1
        """,
        (die, day),
    )
    row = cur.fetchone()
    if row:
        return row[0], False

    cur.execute(
        """
        SELECT id_calibration
        FROM rico.die_calibration
        WHERE id_die = %s
        ORDER BY calibration_date ASC NULLS LAST, id_calibration ASC
        LIMIT 1
        """,
        (die,),
    )
    row = cur.fetchone()
    if row:
        return row[0], True

    return None, False


def _load_calibration(cur, calibration_id: int) -> dict:
    if calibration_id in _CALIBRATION_CACHE:
        return _CALIBRATION_CACHE[calibration_id]

    cur.execute(
        """
        SELECT parameter_name, baseline, lower_tolerance, upper_tolerance
        FROM rico.calibration_parameter
        WHERE id_calibration = %s
        """,
        (calibration_id,),
    )
    values = {}
    for name, baseline, lower, upper in cur.fetchall():
        values[_canonical_param(name)] = (baseline, lower, upper)

    _CALIBRATION_CACHE[calibration_id] = values
    return values


def _predict_day(cur, conn, die: str, day: date, totals: dict) -> None:
    calibration_id, used_earliest_fallback = _calibration_for(cur, die, day)
    if calibration_id is None:
        totals["days_no_calibration"] += 1
        print(f"[SKIP] {day} {die}: no calibration exists")
        return

    if used_earliest_fallback:
        totals["days_earliest_calibration"] += 1
        if die not in totals["_fallback_dies"]:
            totals["_fallback_dies"].add(die)
            print(
                f"[FALLBACK] {die}: shots predate every calibration; "
                f"using earliest calibration {calibration_id}"
            )

    calibration = _load_calibration(cur, calibration_id)

    cur.execute(
        """
        SELECT id_part, id_die, id_machine, id_client, production_date, manufactored_on
        FROM rico.part
        WHERE production_date = %s AND id_die = %s
        """,
        (day, die),
    )
    parts = cur.fetchall()
    if not parts:
        return

    model_paths = {
        defect: model_path_asof(die, defect, day) for defect in TARGET_DEFECTS
    }
    missing_models = [d for d, p in model_paths.items() if p is None]
    if missing_models:
        totals["days_no_model"] += 1
        print(f"[SKIP] {day} {die}: no model for {missing_models}")
        return

    models = {defect: _load_model(path) for defect, path in model_paths.items()}
    specs = {defect: _feature_specs(model) for defect, model in models.items()}
    required = {param for spec in specs.values() for param, _ in spec}

    model_dates = sorted({str(_model_date(path)) for path in model_paths.values()})
    missing_in_calibration = sorted(required - set(calibration))
    if missing_in_calibration:
        print(
            f"[WARN] {day} {die}: calibration {calibration_id} missing "
            f"{missing_in_calibration}"
        )

    part_ids = [row[0] for row in parts]
    cur.execute(
        """
        SELECT id_part, parameter_name, value
        FROM rico.operating_parameter
        WHERE id_part = ANY(%s)
        """,
        (part_ids,),
    )
    params: dict[str, dict] = {}
    for part_id, name, value in cur.fetchall():
        params.setdefault(part_id, {})[name] = value

    kept = []
    canonical_rows = []
    for row in parts:
        part_values = params.get(row[0], {})
        canonical = {}

        for param, (baseline, lower, upper) in calibration.items():
            value = part_values.get(param)
            if value is None:
                continue
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            if baseline is None or lower is None or upper is None:
                continue

            inrange = 1.0 if lower <= value <= upper else 0.0
            pctdev = (value - baseline) / baseline if baseline else 0.0
            canonical[param] = (inrange, float(np.clip(pctdev, -0.30, 0.30)))

        if not required.issubset(canonical):
            continue

        kept.append(row)
        canonical_rows.append(canonical)

    skipped_missing = len(parts) - len(kept)
    totals["parts"] += len(parts)
    totals["skipped_missing"] += skipped_missing

    if not kept:
        print(
            f"{day} {die}: parts={len(parts)} scored=0 "
            f"skipped_missing={skipped_missing} calib={calibration_id} "
            f"models={model_dates}"
        )
        return

    now = datetime.now()
    today = date.today()
    output_rows = []

    for defect in TARGET_DEFECTS:
        model = models[defect]
        spec = specs[defect]
        matrix = np.empty((len(kept), len(spec)), dtype=float)
        for i, canonical in enumerate(canonical_rows):
            for j, (param, kind) in enumerate(spec):
                matrix[i, j] = canonical[param][kind]

        scaled = model["scaler"].transform(matrix)
        pca = model["pca"].transform(scaled)
        cca = model["cca"].transform(pca)
        probabilities = model["model"].predict_proba(cca)[:, 1]

        for i, row in enumerate(kept):
            part_id, id_die, id_machine, id_client, _pdate, manufactored_on = row
            output_rows.append(
                (
                    part_id,
                    id_die,
                    int(id_client) if id_client is not None else None,
                    id_machine,
                    manufactored_on,
                    defect,
                    float(probabilities[i]),
                    now,
                    today,
                )
            )

    execute_values(
        cur,
        """
        INSERT INTO rico.part_quality_prediction (
            id_part, id_die, id_client, id_machine, manufactored_on,
            defect_type, defect_probability, created_at, updated_at
        )
        VALUES %s
        ON CONFLICT (id_part, defect_type) DO UPDATE SET
            id_die = EXCLUDED.id_die,
            id_client = EXCLUDED.id_client,
            id_machine = EXCLUDED.id_machine,
            manufactored_on = EXCLUDED.manufactored_on,
            defect_probability = EXCLUDED.defect_probability,
            updated_at = EXCLUDED.updated_at
        """,
        output_rows,
        page_size=500,
    )
    conn.commit()

    totals["scored"] += len(kept)
    totals["rows"] += len(output_rows)
    print(
        f"{day} {die}: parts={len(parts)} scored={len(kept)} "
        f"skipped_missing={skipped_missing} calib={calibration_id} "
        f"models={model_dates} rows={len(output_rows)}"
    )


def predict_date_range(
    start_date: str,
    end_date: str,
    dies: Optional[list[str]] = None,
) -> dict:
    first = date.fromisoformat(start_date)
    last = date.fromisoformat(end_date)
    if first > last:
        raise ValueError("start_date cannot be after end_date")

    dies = dies or DIE_LIST

    print("\n" + "=" * 80)
    print("QUALITY PREDICTION BACKFILL")
    print("=" * 80)
    print(f"From: {first}")
    print(f"To:   {last}")
    print(f"Dies: {', '.join(dies)}")

    print("\nConnecting to PostgreSQL...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    print("Database connection successful.")

    totals = {
        "parts": 0,
        "scored": 0,
        "skipped_missing": 0,
        "rows": 0,
        "days_no_calibration": 0,
        "days_earliest_calibration": 0,
        "days_no_model": 0,
        "_fallback_dies": set(),
    }

    try:
        current = first
        while current <= last:
            for die in dies:
                _predict_day(cur, conn, die, current, totals)
            current += timedelta(days=1)
    finally:
        cur.close()
        conn.close()
        print("\nDatabase connection closed.")

    print("\n" + "=" * 80)
    print("PREDICTION BACKFILL COMPLETE")
    print("=" * 80)
    print(f"Parts seen:            {totals['parts']}")
    print(f"Parts scored:          {totals['scored']}")
    print(f"Parts skipped (params):{totals['skipped_missing']}")
    print(f"Prediction rows:       {totals['rows']}")
    print(f"Days without calib:    {totals['days_no_calibration']}")
    print(f"Days earliest cal:     {totals['days_earliest_calibration']}")
    print(f"Days without model:    {totals['days_no_model']}")
    print("=" * 80)

    return totals


if __name__ == "__main__":
    args = sys.argv[1:]
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
        raise SystemExit(
            "usage:\n"
            "  python -m services.monthly_predict --from YYYY-MM-DD --to YYYY-MM-DD\n"
            "  python -m services.monthly_predict --date YYYY-MM-DD"
        )

    predict_date_range(start, end or start)
