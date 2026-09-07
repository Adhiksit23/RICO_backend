"""
Server-side IoT sync scheduler.

- Runs inside the FastAPI process (survives browser logout/close).
- Can be started/stopped at runtime via /api/iot/* (plant admin UI).
- Desired on/off state is persisted so it survives backend restarts.
- Boot default: persisted state if present, else IOT_SYNC_ENABLED from .env.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from services.config import (
    IOT_SYNC_ENABLED,
    IOT_SYNC_INCLUDE_LEGACY,
    IOT_SYNC_INTERVAL_SECONDS,
)

logger = logging.getLogger(__name__)

JOB_ID = "rico_iot_sync"
STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "iot_scheduler_state.json"

_scheduler: Optional[BackgroundScheduler] = None
_sync_lock = threading.Lock()
_state_lock = threading.Lock()

_last_run_at: Optional[str] = None
_last_result: Optional[dict[str, Any]] = None
_desired_running: bool = False
_updated_by: Optional[str] = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_state_dir() -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_persisted_state() -> Optional[dict[str, Any]]:
    try:
        if not STATE_FILE.exists():
            return None
        with STATE_FILE.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        logger.exception("[iot-sync] Failed to read state file %s", STATE_FILE)
        return None


def _persist_desired_state(desired: bool, updated_by: Optional[str] = None) -> None:
    global _desired_running, _updated_by
    _desired_running = desired
    if updated_by is not None:
        _updated_by = updated_by
    payload = {
        "desired_running": desired,
        "updated_at": _utc_now_iso(),
        "updated_by": _updated_by,
        "interval_seconds": IOT_SYNC_INTERVAL_SECONDS,
    }
    try:
        _ensure_state_dir()
        with STATE_FILE.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
    except Exception:
        logger.exception("[iot-sync] Failed to persist state file %s", STATE_FILE)


def is_scheduler_running() -> bool:
    return _scheduler is not None and _scheduler.running and _scheduler.get_job(JOB_ID) is not None


def _next_run_iso() -> Optional[str]:
    if not is_scheduler_running() or _scheduler is None:
        return None
    job = _scheduler.get_job(JOB_ID)
    if not job or not job.next_run_time:
        return None
    return job.next_run_time.astimezone(timezone.utc).isoformat()


def get_iot_status() -> dict[str, Any]:
    return {
        "running": is_scheduler_running(),
        "desired_running": _desired_running,
        "interval_seconds": IOT_SYNC_INTERVAL_SECONDS,
        "include_legacy": IOT_SYNC_INCLUDE_LEGACY,
        "boot_env_enabled": IOT_SYNC_ENABLED,
        "last_run_at": _last_run_at,
        "last_result": _last_result,
        "next_run_at": _next_run_iso(),
        "updated_by": _updated_by,
    }


def run_iot_sync(trigger: str = "scheduler") -> dict[str, Any]:
    """
    Run the PLC shot sync (and optional legacy historical sync).
    Never raises — safe for APScheduler and HTTP wrappers.
    """
    global _last_run_at, _last_result

    if not _sync_lock.acquire(blocking=False):
        logger.info("[iot-sync] Skipped (%s) — previous run still in progress", trigger)
        skipped = {
            "status": "skipped",
            "reason": "already_running",
            "trigger": trigger,
            "finished_at": _utc_now_iso(),
        }
        return skipped

    result: dict[str, Any] = {
        "status": "ok",
        "trigger": trigger,
        "shot_sync": None,
        "legacy_sync": None,
        "finished_at": None,
    }
    try:
        from services.shot_update import (
            get_auth_token_shot,
            get_iot_data_shot,
            update_date_path_shot,
        )

        data_path = update_date_path_shot()
        token = get_auth_token_shot()
        get_iot_data_shot(token, data_path)
        result["shot_sync"] = "ok"
        logger.info("[iot-sync] Shot sync completed (%s)", trigger)

        if IOT_SYNC_INCLUDE_LEGACY:
            from services.predictor import get_auth_token, get_iot_data, update_date_path

            legacy_path = update_date_path()
            legacy_token = get_auth_token()
            get_iot_data(legacy_token, legacy_path)
            result["legacy_sync"] = "ok"
            logger.info("[iot-sync] Legacy sync completed (%s)", trigger)

        return result
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        logger.exception("[iot-sync] Failed (%s): %s", trigger, exc)
        return result
    finally:
        result["finished_at"] = _utc_now_iso()
        _last_run_at = result["finished_at"]
        _last_result = {
            "status": result.get("status"),
            "trigger": trigger,
            "error": result.get("error"),
            "shot_sync": result.get("shot_sync"),
            "legacy_sync": result.get("legacy_sync"),
            "finished_at": result["finished_at"],
        }
        _sync_lock.release()


def _ensure_scheduler_instance() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        _scheduler = BackgroundScheduler(timezone="UTC")
        _scheduler.start()
    return _scheduler


def _queue_interval_job(run_immediately: bool = True) -> None:
    scheduler = _ensure_scheduler_instance()
    scheduler.add_job(
        run_iot_sync,
        trigger=IntervalTrigger(seconds=IOT_SYNC_INTERVAL_SECONDS),
        id=JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=IOT_SYNC_INTERVAL_SECONDS,
        kwargs={"trigger": "scheduler"},
    )
    if run_immediately:
        try:
            scheduler.add_job(
                run_iot_sync,
                id="rico_iot_sync_once",
                replace_existing=True,
                kwargs={"trigger": "startup"},
            )
        except Exception:
            logger.exception("[iot-sync] Failed to queue immediate sync")


def start_iot_scheduler(
    *,
    updated_by: Optional[str] = None,
    persist: bool = True,
    run_immediately: bool = True,
) -> dict[str, Any]:
    """Start (or resume) the interval IoT sync job."""
    with _state_lock:
        if is_scheduler_running():
            if persist:
                _persist_desired_state(True, updated_by=updated_by)
            logger.info("[iot-sync] Scheduler already running")
            return get_iot_status()

        _queue_interval_job(run_immediately=run_immediately)
        if persist:
            _persist_desired_state(True, updated_by=updated_by)
        else:
            global _desired_running
            _desired_running = True
            if updated_by is not None:
                global _updated_by
                _updated_by = updated_by

        logger.info(
            "[iot-sync] Scheduler started — every %ss (by=%s)",
            IOT_SYNC_INTERVAL_SECONDS,
            updated_by or "system",
        )
        return get_iot_status()


def stop_iot_scheduler(
    *,
    updated_by: Optional[str] = None,
    persist: bool = True,
    shutdown: bool = False,
) -> dict[str, Any]:
    """
    Stop the interval job (UI stop) or fully shut down on app exit.

    UI stop: remove job, keep process alive, persist desired_running=false.
    App shutdown: shutdown APScheduler entirely (persist=False).
    """
    global _scheduler

    with _state_lock:
        if shutdown:
            if _scheduler is not None:
                try:
                    if _scheduler.running:
                        _scheduler.shutdown(wait=False)
                        logger.info("[iot-sync] Scheduler shut down (app exit)")
                except Exception:
                    logger.exception("[iot-sync] Error while shutting down scheduler")
                finally:
                    _scheduler = None
            return get_iot_status()

        if _scheduler is not None and _scheduler.running:
            try:
                if _scheduler.get_job(JOB_ID):
                    _scheduler.remove_job(JOB_ID)
                once = _scheduler.get_job("rico_iot_sync_once")
                if once:
                    _scheduler.remove_job("rico_iot_sync_once")
            except Exception:
                logger.exception("[iot-sync] Error removing jobs")

        if persist:
            _persist_desired_state(False, updated_by=updated_by)
        else:
            global _desired_running
            _desired_running = False

        logger.info("[iot-sync] Scheduler stopped (by=%s)", updated_by or "system")
        return get_iot_status()


def start_iot_scheduler_on_boot() -> None:
    """
    Called from FastAPI lifespan.
    Preference order: persisted UI state → IOT_SYNC_ENABLED env.
    """
    global _desired_running, _updated_by

    persisted = _load_persisted_state()
    if persisted is not None and "desired_running" in persisted:
        want = bool(persisted.get("desired_running"))
        _desired_running = want
        _updated_by = persisted.get("updated_by")
        logger.info(
            "[iot-sync] Boot from persisted state desired_running=%s (by=%s)",
            want,
            _updated_by,
        )
    else:
        want = IOT_SYNC_ENABLED
        _desired_running = want
        _updated_by = "env:IOT_SYNC_ENABLED"
        logger.info("[iot-sync] Boot from env IOT_SYNC_ENABLED=%s", want)

    if want:
        start_iot_scheduler(
            updated_by=_updated_by,
            persist=False,
            run_immediately=True,
        )
    else:
        logger.info(
            "[iot-sync] Not auto-starting. Plant admin can start from UI (/api/iot/start)."
        )


def shutdown_iot_scheduler() -> None:
    """App lifespan shutdown — do not change persisted desired state."""
    stop_iot_scheduler(persist=False, shutdown=True)
