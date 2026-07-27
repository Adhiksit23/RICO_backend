"""
Auth service — core business logic for authentication.
Handles password hashing, JWT generation, user CRUD, and invite tokens.
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import psycopg2
import psycopg2.extras
from fastapi import HTTPException, status
from jose import JWTError, jwt

from services.config import (
    DB_CONFIG,
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    FRONTEND_URL,
    COOKIE_NAME,
)

logger = logging.getLogger(__name__)

# ─── Password Hashing ────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ─── Database Connection ─────────────────────────────────────────────
def get_db_connection():
    """Return a new psycopg2 connection using the centralized DB config."""
    return psycopg2.connect(**DB_CONFIG)


# ─── JWT Tokens ──────────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.
    Raises HTTPException(401) on invalid or expired token.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ─── User Operations ─────────────────────────────────────────────────
def _row_to_user(row: dict) -> dict:
    """Convert a DB row dict to a safe user dict (no password_hash)."""
    return {
        "id":         row["id"],
        "email":      row["email"],
        "full_name":  row["full_name"],
        "role":       row["role"],
        "plant_id":   row["plant_id"],
        "plant_name": row["plant_name"],
        "is_active":  row["is_active"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "created_by": row["created_by"],
    }


def get_user_by_email(email: str) -> Optional[dict]:
    """Fetch a user row by email. Returns None if not found."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM app_user WHERE email = %s",
                (email.lower().strip(),),
            )
            row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Fetch a user row by ID. Returns None if not found."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM app_user WHERE id = %s", (user_id,))
            row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_user(
    email: str,
    password: str,
    full_name: str,
    role: str,
    plant_id: Optional[str],
    plant_name: Optional[str],
    created_by: Optional[int] = None,
) -> dict:
    """
    Create a new user in the database.
    Raises HTTPException(400) if email already exists.
    """
    email = email.lower().strip()
    if get_user_by_email(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    password_hash = hash_password(password)
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO app_user (email, password_hash, full_name, role, plant_id, plant_name, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, email, full_name, role, plant_id, plant_name, is_active, created_at, created_by
                """,
                (email, password_hash, full_name.strip(), role, plant_id, plant_name, created_by),
            )
            row = cur.fetchone()
        conn.commit()
        return dict(row)
    except Exception as exc:
        conn.rollback()
        logger.error("Failed to create user: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account. Please try again.",
        ) from exc
    finally:
        conn.close()


def get_users_by_plant(plant_id: str) -> list:
    """Fetch all users belonging to a plant."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, email, full_name, role, plant_id, plant_name,
                       is_active, created_at, created_by
                FROM app_user
                WHERE plant_id = %s
                ORDER BY created_at DESC
                """,
                (plant_id,),
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def toggle_user_active(user_id: int) -> dict:
    """Toggle a user's is_active status. Returns updated user."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE app_user
                SET is_active = NOT is_active, updated_at = NOW()
                WHERE id = %s
                RETURNING id, email, full_name, role, plant_id, plant_name,
                          is_active, created_at, created_by
                """,
                (user_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found.",
                )
        conn.commit()
        return dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        logger.error("Failed to toggle user active: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user status.",
        ) from exc
    finally:
        conn.close()


# ─── Invite Tokens ───────────────────────────────────────────────────
def create_invite_token(
    invited_by_id: int,
    plant_id: str,
    email: Optional[str] = None,
) -> dict:
    """
    Generate a secure one-time invite token valid for 7 days.
    Returns dict with token string and invite URL.
    """
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO invite_token (token, email, invited_by, plant_id, expires_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (token, email.lower().strip() if email else None, invited_by_id, plant_id, expires_at),
            )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error("Failed to create invite token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate invite link.",
        ) from exc
    finally:
        conn.close()

    invite_url = f"{FRONTEND_URL}/invite/{token}"
    return {
        "token": token,
        "invite_url": invite_url,
        "expires_at": expires_at.isoformat(),
    }


def validate_invite_token(token: str) -> dict:
    """
    Validate an invite token.
    Raises HTTPException(400) if token is invalid, used, or expired.
    Returns the invite row dict.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM invite_token WHERE token = %s",
                (token,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invite link. Please request a new one.",
        )

    row = dict(row)

    if row["used"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invite link has already been used.",
        )

    expires_at = row["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invite link has expired. Please request a new one.",
        )

    return row


def mark_invite_used(token: str) -> None:
    """Mark an invite token as used."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE invite_token SET used = TRUE WHERE token = %s",
                (token,),
            )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error("Failed to mark invite used: %s", exc)
    finally:
        conn.close()
