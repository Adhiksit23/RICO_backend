"""
Prediction + monitor refresh scheduler.

Independent of the IoT shot sync scheduler: every PREDICT_MONITOR_INTERVAL_SECONDS
it calls the base prediction and monitor functions for each configured die.

No part-level targeting yet — the base functions decide which part they read.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from services.config import (
    PREDICT_MONITOR_ENABLED,
    PREDICT_MONITOR_INTERVAL_SECONDS,
)

logger = logging.getLogger(__name__)

JOB_ID = "rico_predict_monitor"

_scheduler: Optional[BackgroundScheduler] = None
_cycle_lock = threading.Lock()

_die_locks: dict[str, threading.Lock] = {}
_die_locks_guard = threading.Lock()

_last_run_at: Optional[str] = None
_last_result: Optional[dict[str, Any]] = None
_last_by_die: dict[str, dict[str, Any]] = {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_predict_monitor_cycle(trigger: str = "scheduler") -> dict[str, Any]:
    """
    Call predictions(die) and monitor_data(die) for every die once.
    Never raises — each die/function failure is recorded and logged.
    """
    global _last_run_at, _last_result

    if not _cycle_lock.acquire(blocking=False):
        logger.info("[predict-monitor] Skipped (%s) — previous cycle still running", trigger)
        return {
            "status": "skipped",
            "reason": "already_running",
            "trigger": trigger,
            "finished_at": _utc_now_iso(),
        }

    try:
        from services.predictor import predictions, monitor_data
        from services.shot_update import DIE_LIST

        result: dict[str, Any] = {
            "status": "ok",
            "trigger": trigger,
            "dies": {},
            "finished_at": None,
        }

        for die in DIE_LIST:
            entry: dict[str, Any] = {}

            try:
                prediction = predictions(die)

                entry["prediction"] = "ok"
                logger.info("[predict-monitor] die=%s prediction=%s", die, prediction)
            except Exception as exc:
                entry["prediction"] = "error"
                entry["prediction_error"] = str(exc)
                logger.exception("[predict-monitor] die=%s prediction failed: %s", die, exc)

            try:
                monitor_data(die)
                entry["monitor"] = "ok"
                logger.info("[predict-monitor] die=%s monitor=ok", die)
            except Exception as exc:
                entry["monitor"] = "error"
                entry["monitor_error"] = str(exc)
                logger.exception("[predict-monitor] die=%s monitor failed: %s", die, exc)

            result["dies"][die] = entry

        result["finished_at"] = _utc_now_iso()
        _last_run_at = result["finished_at"]
        _last_result = result
        return result
    finally:
        _cycle_lock.release()


def _get_die_lock(die: str) -> threading.Lock:
    with _die_locks_guard:
        lock = _die_locks.get(die)
        if lock is None:
            lock = threading.Lock()
            _die_locks[die] = lock
        return lock


def run_predict_monitor_for_die(
    die: str,
    part_id: Optional[str] = None,
    trigger: str = "shot_sync",
) -> dict[str, Any]:
    """
    Run prediction + monitor for the part just saved by shot sync. Never raises.

    ``part_id`` is passed through to predictions() so inference uses the saved
    part's operating parameters rather than the latest part for the die.
    """
    lock = _get_die_lock(die)
    if not lock.acquire(blocking=False):
        logger.info(
            "[predict-monitor] Skipped die=%s part=%s (%s) — previous run still active",
            die, part_id, trigger,
        )
        return {
            "status": "skipped",
            "reason": "already_running",
            "die": die,
            "part_id": part_id,
            "trigger": trigger,
        }

    result: dict[str, Any] = {
        "status": "ok",
        "die": die,
        "part_id": part_id,
        "trigger": trigger,
        "finished_at": None,
    }
    try:
        try:
            from services.predictor import predictions, monitor_data
        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)
            logger.exception("[predict-monitor] die=%s import failed: %s", die, exc)
            return result

        try:
            prediction = predictions(die, part_id=part_id)
            result["prediction"] = "ok"
            result["probabilities"] = [round(float(p), 6) for p in prediction]
            logger.info(
                "[predict-monitor] die=%s part=%s prediction=%s",
                die, part_id, result["probabilities"],
            )
        except Exception as exc:
            result["prediction"] = "error"
            result["prediction_error"] = str(exc)
            logger.exception("[predict-monitor] die=%s prediction failed: %s", die, exc)

        try:
            monitor_data(die)
            result["monitor"] = "ok"
            logger.info("[predict-monitor] die=%s part=%s monitor=ok", die, part_id)
        except Exception as exc:
            result["monitor"] = "error"
            result["monitor_error"] = str(exc)
            logger.exception("[predict-monitor] die=%s monitor failed: %s", die, exc)

        return result
    finally:
        result["finished_at"] = _utc_now_iso()
        _last_by_die[die] = result
        lock.release()


def _ensure_scheduler_instance() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        _scheduler = BackgroundScheduler(timezone="UTC")
        _scheduler.start()
    return _scheduler


def is_predict_monitor_running() -> bool:
    return (
        _scheduler is not None
        and _scheduler.running
        and _scheduler.get_job(JOB_ID) is not None
    )


def _next_run_iso() -> Optional[str]:
    if not is_predict_monitor_running() or _scheduler is None:
        return None
    job = _scheduler.get_job(JOB_ID)
    if not job or not job.next_run_time:
        return None
    return job.next_run_time.astimezone(timezone.utc).isoformat()


def get_predict_monitor_status() -> dict[str, Any]:
    return {
        "running": is_predict_monitor_running(),
        "enabled": PREDICT_MONITOR_ENABLED,
        "interval_seconds": PREDICT_MONITOR_INTERVAL_SECONDS,
        "last_run_at": _last_run_at,
        "last_result": _last_result,
        "last_by_die": _last_by_die,
        "next_run_at": _next_run_iso(),
    }


def start_predict_monitor_scheduler() -> dict[str, Any]:
    if not PREDICT_MONITOR_ENABLED:
        logger.info("[predict-monitor] Disabled (PREDICT_MONITOR_ENABLED=false)")
        return get_predict_monitor_status()

    if is_predict_monitor_running():
        logger.info("[predict-monitor] Scheduler already running")
        return get_predict_monitor_status()

    scheduler = _ensure_scheduler_instance()
    scheduler.add_job(
        run_predict_monitor_cycle,
        trigger=IntervalTrigger(seconds=PREDICT_MONITOR_INTERVAL_SECONDS),
        id=JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=PREDICT_MONITOR_INTERVAL_SECONDS,
        kwargs={"trigger": "scheduler"},
    )
    logger.info(
        "[predict-monitor] Scheduler started — every %ss",
        PREDICT_MONITOR_INTERVAL_SECONDS,
    )
    return get_predict_monitor_status()


def stop_predict_monitor_scheduler(*, shutdown: bool = False) -> dict[str, Any]:
    global _scheduler

    if shutdown:
        if _scheduler is not None:
            try:
                if _scheduler.running:
                    _scheduler.shutdown(wait=False)
                    logger.info("[predict-monitor] Scheduler shut down (app exit)")
            except Exception:
                logger.exception("[predict-monitor] Error while shutting down scheduler")
            finally:
                _scheduler = None
        return get_predict_monitor_status()

    if _scheduler is not None and _scheduler.running:
        try:
            if _scheduler.get_job(JOB_ID):
                _scheduler.remove_job(JOB_ID)
        except Exception:
            logger.exception("[predict-monitor] Error removing job")

    logger.info("[predict-monitor] Scheduler stopped")
    return get_predict_monitor_status()


def start_predict_monitor_scheduler_on_boot() -> None:
    """Called from FastAPI lifespan."""
    start_predict_monitor_scheduler()


def shutdown_predict_monitor_scheduler() -> None:
    """App lifespan shutdown."""
    stop_predict_monitor_scheduler(shutdown=True)
