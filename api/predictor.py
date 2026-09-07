from fastapi import APIRouter, HTTPException
from apscheduler.schedulers.background import BackgroundScheduler
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/predictor",
    tags=["Predictor"]
)

from services.predictor import (
    predictions,
    update_date_path,
    get_auth_token,
    get_iot_data,
    get_latest_calibration,
    last_predictions,
    monitor_data
)

from services.iot_scheduler import run_iot_sync


@router.get("/predict")
def predict(die: str):
    """
    Run defect probability prediction for a given die.
    Returns probabilities (0–100%) for each defect type.
    """
    try:
        prediction = predictions(die)  # single call — result reused below
    except Exception as exc:
        logger.exception("[/predict] Failed to generate prediction for die=%s", die)
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed for die '{die}': {str(exc)}",
        ) from exc

    return {
        "blowhole":    round(prediction[0] * 100, 2),
        "crack":       round(prediction[1] * 100, 2),
        "non_filling": round(prediction[2] * 100, 2),
        "porosity":    round(prediction[3] * 100, 2),
        "shrinkage":   round(prediction[4] * 100, 2),
        "chipoff":     round(prediction[5] * 100, 2),
    }


@router.get("/monitor")
def monitor(die: str):
    """
    Fetch latest operating parameters and calibration ranges for a given die.
    Returns [parameter_data, calibration_ranges].
    """
    try:
        data, _ = monitor_data(die)
    except Exception as exc:
        logger.exception("[/monitor] Failed to fetch monitor data for die=%s", die)
        raise HTTPException(
            status_code=500,
            detail=f"Could not fetch monitor data for die '{die}': {str(exc)}",
        ) from exc

    try:
        ranges = get_latest_calibration(die=die)
    except Exception as exc:
        logger.exception("[/monitor] Failed to fetch calibration ranges for die=%s", die)
        raise HTTPException(
            status_code=500,
            detail=f"Could not fetch calibration ranges for die '{die}': {str(exc)}",
        ) from exc

    return [data, ranges]


@router.get("/update")
def update():
    """
    Manual legacy historical IoT sync (reports API).
    Prefer server scheduler (IOT_SYNC_ENABLED) for production.
    """
    try:
        data_path = update_date_path()
        token = get_auth_token()
        get_iot_data(token, data_path)
        return {"status": "ok", "pipeline": "legacy_reports"}
    except Exception as exc:
        logger.exception("[/update] Legacy IoT sync failed")
        raise HTTPException(
            status_code=503,
            detail=f"IoT legacy sync failed (server unreachable or error): {exc}",
        ) from exc


@router.get("/update_IOT")
def update_IOT():
    """
    Manual PLC shot sync. Production should use the backend scheduler
    (IOT_SYNC_ENABLED=true) so sync continues when the browser is closed.
    """
    result = run_iot_sync(trigger="manual_api")
    if result.get("status") == "skipped":
        return result
    if result.get("status") == "error":
        raise HTTPException(
            status_code=503,
            detail=f"IoT shot sync failed: {result.get('error', 'unknown error')}",
        )
    return result


@router.get("/last_pred")
def last_pred(die: str, N: int):
    """
    Fetch the last N predictions for a given die.
    Returns a dict keyed by part_id with defect probabilities.
    """
    try:
        result = last_predictions(die, N)
    except Exception as exc:
        logger.exception("[/last_pred] Failed to fetch last predictions for die=%s N=%s", die, N)
        raise HTTPException(
            status_code=500,
            detail=f"Could not fetch last predictions for die '{die}': {str(exc)}",
        ) from exc

    return result
