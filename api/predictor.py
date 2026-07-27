from fastapi import APIRouter, HTTPException
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
    monitor_data
)

@router.get("/predict")
def predict(die: str):
    try:
        prediction = predictions(die)
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
    try:
        data, die_id = monitor_data(die)
        ranges = get_latest_calibration(die)
    except Exception as exc:
        logger.exception("[/monitor] Failed to fetch monitor data for die=%s", die)
        raise HTTPException(
            status_code=500,
            detail=f"Monitor data fetch failed for die '{die}': {str(exc)}",
        ) from exc

    return [data, ranges]


@router.get("/update")
def update():
    # data_path = update_date_path()
    # print(data_path)
    
    # print("Authenticating...")
    # token = get_auth_token()
    # #print(token)

    # print("Fetching data...")
    # get_iot_data(token, data_path)
    # print("Recieved Data")
    return