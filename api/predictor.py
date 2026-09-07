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


from services.shot_update import (
    update_date_path_shot,
    get_auth_token_shot,
    get_iot_data_shot,
)


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

    # try:
    #     last_predictions(die, 5)
    # except Exception as exc:
    #     # Non-fatal: log but don't fail the whole predict response
    #     logger.warning("[/predict] Could not store last predictions for die=%s: %s", die, exc)

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
        # print("Die for latest ranges is: ", die)
        ranges = get_latest_calibration(die = die)
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
    Trigger a manual IoT data fetch and update cycle.
    Currently disabled — returns status message.
    """
    # Uncomment below when IoT integration is re-enabled:
    data_path = update_date_path()
    token = get_auth_token()
    get_iot_data(token, data_path)
    return {"status": "update endpoint is currently disabled"}


@router.get("/update_IOT")
def update_IOT():
    """
    Trigger a manual IoT data fetch and update cycle.d
    Currently disabled — returns status message.
    """
    # Uncomment below when IoT integration is re-enabled:
    data_path = update_date_path_shot()
    token = get_auth_token_shot()
    get_iot_data_shot(token, data_path)
    return {"status": "update endpoint is currently disabled"}


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


scheduler = BackgroundScheduler()

@app.on_event("startup")
def start_scheduler():
    scheduler.add_job(update_iot_data, "interval", seconds=60)
    scheduler.start()

@app.on_event("shutdown")
def stop_scheduler():
    scheduler.shutdown()