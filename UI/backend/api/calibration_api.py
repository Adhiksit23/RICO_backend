# from fastapi import APIRouter
# from pydantic import BaseModel

# from services.calibration_service import (
#     get_latest_parameters,
#     compute_calibration_ranges,
#     update_parameters
# )

# router = APIRouter(
#     prefix="/api/calibration",
#     tags=["Calibration"]
# )


# class ParameterUpdate(BaseModel):

#     cooling_time: float
#     spray_time: float
#     metal_pressure: float
#     metal_temperature: float


# @router.get("/latest")

# def latest_parameters():

#     return get_latest_parameters()


# @router.get("/ranges")

# def calibration_ranges():

#     return compute_calibration_ranges()


# @router.post("/update")

# def update_calibration(data: ParameterUpdate):

#     return update_parameters(data.dict())

# @router.post("/apply")

# def apply_new_calibration(data: ParameterUpdate):

#     return apply_calibration(data.dict())


# from fastapi import APIRouter
# from pydantic import BaseModel

# from services.calibration_service import (
#     get_latest_parameters,
#     compute_calibration_ranges,
#     update_parameters,
#     apply_calibration
# )

# router = APIRouter(
#     prefix="/api/calibration",
#     tags=["Calibration"]
# )


# class ParameterUpdate(BaseModel):

#     pouring_time: float
#     shot_forward_time: float
#     cooling_time: float
#     die_open_core_out_time: float
#     ejector_time: float
#     extraction_time: float
#     spray_time: float

#     speed_1: float
#     speed_2: float
#     speed_3: float
#     speed_4: float

#     metal_pressure: float
#     metal_temperature: float


# @router.get("/latest")
# def latest_parameters():

#     return get_latest_parameters()


# @router.get("/ranges")
# def calibration_ranges():

#     return compute_calibration_ranges()


# @router.post("/update")
# def update_calibration(data: ParameterUpdate):

#     return update_parameters(data.dict())


# @router.post("/apply")
# def apply_new_calibration(data: ParameterUpdate):

#     return apply_calibration(data.dict())


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
    return get_latest_parameters()

@router.get("/ranges")
def calibration_ranges(
    machine: str | None = None,
    die: str | None = "S14"
):
    return compute_calibration_ranges(die)

@router.post("/update")
def update_calibration(data: ParameterUpdate):
    return update_parameters(data.dict())

@router.post("/apply")
def apply_new_calibration(
    data: dict[str, float],  # Accepts any key-value pair of floats
    machine: str | None = None,
    die: str | None = "S14"
):
    # Notice we don't use .dict() anymore because 'data' is already a dictionary
    return apply_calibration(data, die)