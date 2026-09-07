"""
Centralized configuration module for RICO backend.
Loads all environment variables from .env file.
"""
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ─── Database Configuration ──────────────────────────────────────────
DB_CONFIG = {
    "host":     os.environ.get("DB_HOST", "aws-1-ap-southeast-2.pooler.supabase.com"),
    "dbname":   os.environ.get("DB_NAME", "postgres"),
    "user":     os.environ.get("DB_USER", ""),
    "password": os.environ.get("DB_PASSWORD", ""),
    "options":  f"-c search_path={os.environ.get('DB_SCHEMA', 'rico')}",
}

# ─── JWT Configuration ───────────────────────────────────────────────
JWT_SECRET_KEY              = os.environ.get("JWT_SECRET_KEY", "fallback-secret-change-in-production")
JWT_ALGORITHM               = os.environ.get("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

# ─── App Configuration ───────────────────────────────────────────────
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
COOKIE_NAME  = "rico_access_token"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        logger.warning("Invalid int for %s=%r — using default %s", name, raw, default)
        return default


# ─── IoT Sync (plant PLC / vendor API) ────────────────────────────────
# Auth base includes "/api" (no trailing slash). Example:
#   http://14.195.222.243:9090/api
IOT_BASE_URL = os.environ.get("IOT_BASE_URL", "http://14.195.222.243:9090/api").rstrip("/")
# Data fetch base. Defaults to same host without :9090 to match current plant routing.
# Override to IOT_BASE_URL if both auth + data are on :9090.
IOT_DATA_BASE_URL = os.environ.get(
    "IOT_DATA_BASE_URL",
    "http://14.195.222.243/api",
).rstrip("/")
IOT_USERNAME = os.environ.get("IOT_USERNAME", "")
IOT_PASSWORD = os.environ.get("IOT_PASSWORD", "")
IOT_MACHINE_IP = os.environ.get("IOT_MACHINE_IP", "192.168.117.201")
IOT_AUTH_TIMEOUT = _env_int("IOT_AUTH_TIMEOUT", 15)
IOT_DATA_TIMEOUT = _env_int("IOT_DATA_TIMEOUT", 30)

# Backend scheduler (replaces frontend BackgroundUpdater)
# Keep false on laptop/dev when plant IoT is unreachable.
IOT_SYNC_ENABLED = _env_bool("IOT_SYNC_ENABLED", False)
IOT_SYNC_INTERVAL_SECONDS = max(30, _env_int("IOT_SYNC_INTERVAL_SECONDS", 60))
# Also run legacy /reports historical sync from predictor.py
IOT_SYNC_INCLUDE_LEGACY = _env_bool("IOT_SYNC_INCLUDE_LEGACY", False)
