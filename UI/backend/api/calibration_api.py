from fastapi import APIRouter
from pydantic import BaseModel

from services.calibration_service import (
    get_latest_parameters,
    compute_calibration_ranges,
    update_parameters
)

router = APIRouter(
    prefix="/api/calibration",
    tags=["Calibration"]
)


class ParameterUpdate(BaseModel):

    cooling_time: float
    spray_time: float
    metal_pressure: float
    metal_temperature: float


@router.get("/latest")

def latest_parameters():

    return get_latest_parameters()


@router.get("/ranges")

def calibration_ranges():

    return compute_calibration_ranges()


@router.post("/update")

def update_calibration(data: ParameterUpdate):

    return update_parameters(data.dict())

@router.post("/apply")

def apply_new_calibration(data: ParameterUpdate):

    return apply_calibration(data.dict())