from fastapi import APIRouter
from pydantic import BaseModel

from services.calibration_service import (
    get_latest_parameters,
    compute_calibration_ranges,
    # update_parameters,
    apply_calibration
)

router = APIRouter(
    prefix="/api/calibration",
    tags=["Calibration"]
)

class RangeData (BaseModel):
    baseline: float
    tolerance: float
    min_range: float
    max_range: float
    unit: str | None = None

    
class ParameterUpdate(BaseModel):
    pouring_time: float
    shot_forward_time: float
    cooling_time: float
    die_open_core_out_time: float
    ejector_time: float
    extraction_time: float
    spray_time: float

    speed_1: float
    speed_2: float
    speed_3: float
    speed_4: float

    metal_pressure: float
    metal_temperature: float

@router.get("/latest")
def latest_parameters(
    machine: str | None = None,
    die: str | None = None
):
    return get_latest_parameters(machine = machine, die = die)

@router.get("/ranges")
def calibration_ranges(
    machine: str | None = None,
    die: str | None = "S14"
):
    #print(machine)
    ranges = compute_calibration_ranges(machine, die)
    # print(ranges)
    return ranges

@router.post("/apply")
def apply_new_calibration(
    data: dict[str, dict],  # Accepts any key-value pair of floats
    machine: str | None = None,
    die: str | None = "S14"
):
    # print("Test")
    print(data)
    return apply_calibration(data, machine, die)