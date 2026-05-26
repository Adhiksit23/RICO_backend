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



latest_parameters = {

    "pouring_time": 4.52,
    "shot_forward_time": 2.02,
    "cooling_time": 13.78,
    "die_open_core_out_time": 5.31,
    "ejector_time": 4.91,
    "extraction_time": 12.92,
    "spray_time": 14.74,

    "speed_1": 0.29,
    "speed_2": 0.30,
    "speed_3": 3.29,
    "speed_4": 3.36,

    "metal_pressure": 120.00,
    "metal_temperature": 690.00
}


def get_latest_parameters():

    return latest_parameters


def compute_calibration_ranges():

    return {

        "Pouring Time": {
            "baseline": 4.52,
            "tolerance": 0.09,
            "min_range": 4.23,
            "max_range": 4.81
        },

        "Shot Forward Time": {
            "baseline": 2.02,
            "tolerance": 0.04,
            "min_range": 1.89,
            "max_range": 2.16
        },

        "Cooling Time": {
            "baseline": 13.78,
            "tolerance": 0.03,
            "min_range": 13.66,
            "max_range": 13.90
        },

        "Die Open/Core Out Time": {
            "baseline": 5.31,
            "tolerance": 0.02,
            "min_range": 5.24,
            "max_range": 5.38
        },

        "Ejector Time": {
            "baseline": 4.91,
            "tolerance": 0.03,
            "min_range": 4.80,
            "max_range": 5.02
        },

        "Extraction Time": {
            "baseline": 12.92,
            "tolerance": 0.04,
            "min_range": 12.80,
            "max_range": 13.04
        },

        "Spray Time": {
            "baseline": 14.74,
            "tolerance": 0.09,
            "min_range": 14.47,
            "max_range": 15.02
        },

        "Speed 1": {
            "baseline": 0.29,
            "tolerance": 0.002,
            "min_range": 0.285,
            "max_range": 0.296
        },

        "Speed 2": {
            "baseline": 0.30,
            "tolerance": 0.002,
            "min_range": 0.302,
            "max_range": 0.316
        },

        "Speed 3": {
            "baseline": 3.29,
            "tolerance": 0.004,
            "min_range": 3.285,
            "max_range": 3.307
        },

        "Speed 4": {
            "baseline": 3.36,
            "tolerance": 0.004,
            "min_range": 3.356,
            "max_range": 3.379
        },

        "Metal Pressure": {
            "baseline": 120.0,
            "tolerance": 5.0,
            "min_range": 115.0,
            "max_range": 125.0
        },

        "Metal Temperature": {
            "baseline": 690.0,
            "tolerance": 10.0,
            "min_range": 680.0,
            "max_range": 700.0
        }
    }


def update_parameters(data):

    global latest_parameters

    latest_parameters.update(data)

    return {
        "message": "Parameters Updated Successfully"
    }


def apply_calibration(data):

    global latest_parameters

    latest_parameters.update(data)

    return {
        "message": "Calibration Applied Successfully"
    }
