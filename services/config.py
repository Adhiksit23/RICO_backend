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
