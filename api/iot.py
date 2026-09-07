"""
IoT sync control API — status / start / stop / run-now.
Scheduler lives in the backend process so it keeps running after UI logout.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth import get_current_user, require_plant_admin
from services.iot_scheduler import (
    get_iot_status,
    run_iot_sync,
    start_iot_scheduler,
    stop_iot_scheduler,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/iot", tags=["IoT Sync"])


@router.get("/status")
def iot_status(current_user: dict = Depends(get_current_user)):
    """Any authenticated user can view sync status."""
    return get_iot_status()


@router.post("/start")
def iot_start(current_user: dict = Depends(require_plant_admin)):
    """Plant admin: start backend interval sync (survives UI session end)."""
    try:
        status_payload = start_iot_scheduler(
            updated_by=current_user.get("email"),
            persist=True,
            run_immediately=True,
        )
        return {"message": "IoT sync started", **status_payload}
    except Exception as exc:
        logger.exception("[/api/iot/start] Failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start IoT sync: {exc}",
        ) from exc


@router.post("/stop")
def iot_stop(current_user: dict = Depends(require_plant_admin)):
    """Plant admin: stop backend interval sync."""
    try:
        status_payload = stop_iot_scheduler(
            updated_by=current_user.get("email"),
            persist=True,
            shutdown=False,
        )
        return {"message": "IoT sync stopped", **status_payload}
    except Exception as exc:
        logger.exception("[/api/iot/stop] Failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop IoT sync: {exc}",
        ) from exc


@router.post("/run-now")
def iot_run_now(current_user: dict = Depends(require_plant_admin)):
    """Plant admin: run one sync cycle immediately (does not change on/off)."""
    result = run_iot_sync(trigger=f"manual:{current_user.get('email')}")
    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"IoT sync failed: {result.get('error', 'unknown error')}",
        )
    return {"message": "IoT sync finished", **result, **get_iot_status()}
