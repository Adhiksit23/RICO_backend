"""
Calibration API router — handles latest parameters, calibration ranges, and apply.
All endpoints are prefixed with /api/calibration.
"""
import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from services.calibration_service import (
    get_latest_parameters,
    compute_calibration_ranges,
    apply_calibration,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/calibration",
    tags=["Calibration"],
)


class RangeData(BaseModel):
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


# ─── GET /api/calibration/latest ────────────────────────────────────────────

@router.get("/latest")
def latest_parameters(
    machine: str | None = None,
    die: str | None = None,
):
    """Return the latest calibration parameters for a given die."""
    if not die:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter 'die' is required (e.g. ?die=S14).",
        )
    try:
        result = get_latest_parameters(machine = machine, die=die)
    except HTTPException:
        raise  # re-raise already-formatted errors
    except Exception as exc:
        logger.exception("[/calibration/latest] Failed to fetch parameters for die=%s", die)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load calibration parameters for die '{die}': {str(exc)}",
        ) from exc

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No calibration parameters found for die '{die}'. "
                   "Please run a calibration first.",
        )
    return result


# ─── GET /api/calibration/ranges ─────────────────────────────────────────────

@router.get("/ranges")
def calibration_ranges(
    machine: str | None = None,
    die: str | None = "S14",
):
    """Compute and return calibration tolerance ranges for a given die."""
    try:
        ranges = compute_calibration_ranges(machine, die)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "[/calibration/ranges] Failed to compute ranges for machine=%s die=%s",
            machine, die,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute calibration ranges for die '{die}': {str(exc)}",
        ) from exc

    return ranges


# ─── POST /api/calibration/apply ─────────────────────────────────────────────

@router.post("/apply")
def apply_new_calibration(
    data: dict[str, dict],
    machine: str | None = None,
    die: str | None = "S14",
):
    """Apply (save) new calibration parameter values to the database."""
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No calibration data provided in request body.",
        )
    try:
        result = apply_calibration(data, machine, die)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "[/calibration/apply] Failed to apply calibration for machine=%s die=%s",
            machine, die,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save calibration data for die '{die}': {str(exc)}",
        ) from exc

    return result