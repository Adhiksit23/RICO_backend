"""
Auth API router — handles signup, login, logout, user management, and invite links.
All auth endpoints are prefixed with /api/auth.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, field_validator

from services.auth_service import (
    create_access_token,
    create_invite_token,
    create_user,
    decode_token,
    get_user_by_email,
    get_user_by_id,
    get_users_by_plant,
    mark_invite_used,
    toggle_user_active,
    validate_invite_token,
    verify_password,
    _row_to_user,
)
from services.config import ACCESS_TOKEN_EXPIRE_MINUTES, COOKIE_NAME

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ─── Pydantic Models ─────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    plant_name: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v

    @field_validator("full_name", "plant_name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("This field cannot be empty.")
        return v.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class InviteRequest(BaseModel):
    email: Optional[EmailStr] = None


class RegisterViaInviteRequest(BaseModel):
    token: str
    email: EmailStr
    password: str
    full_name: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v

    @field_validator("full_name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Full name cannot be empty.")
        return v.strip()


# ─── Auth Dependencies ───────────────────────────────────────────────

def get_current_user(request: Request) -> dict:
    """Dependency: reads cookie or Authorization header, decodes JWT, returns the active user dict."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please sign in.",
        )
    payload = decode_token(token)
    user_id_raw = payload.get("sub")
    if not user_id_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
        )
    user = get_user_by_id(int(user_id_raw))
    if not user or not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account is deactivated.",
        )
    return user


def require_plant_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Dependency: ensures the current user is a Plant Admin."""
    if current_user["role"] != "plant_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Plant Admin role required.",
        )
    return current_user


def _set_auth_cookie(response: Response, token: str) -> None:
    """Helper: set the HTTP-only auth cookie on a response."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,          # Set to True in production with HTTPS
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


# ─── Endpoints ───────────────────────────────────────────────────────

@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, response: Response):
    """
    Plant Admin self-registration.
    Creates a new plant_admin account and returns a JWT cookie & token.
    """
    plant_id = payload.plant_name.lower().replace(" ", "_").replace("-", "_")

    try:
        user = create_user(
            email=str(payload.email),
            password=payload.password,
            full_name=payload.full_name,
            role="plant_admin",
            plant_id=plant_id,
            plant_name=payload.plant_name,
            created_by=None,
        )
    except HTTPException:
        raise  # already formatted — let it through
    except Exception as exc:
        logger.exception("[/signup] Unexpected error creating account for %s", payload.email)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create account. Please try again later.",
        ) from exc

    try:
        token = create_access_token({"sub": str(user["id"]), "role": user["role"]})
        _set_auth_cookie(response, token)
    except Exception as exc:
        logger.exception("[/signup] Token generation failed for user id=%s", user.get("id"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account created but login failed. Please sign in manually.",
        ) from exc

    logger.info("New Plant Admin registered: %s (plant: %s)", user["email"], plant_id)
    return {"user": _row_to_user(user), "token": token, "message": "Account created successfully."}


@router.post("/login")
def login(payload: LoginRequest, response: Response):
    """
    Login with email and password.
    Returns user info, token, and sets HTTP-only JWT cookie.
    """
    user = get_user_by_email(str(payload.email))
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Contact your Plant Admin.",
        )

    token = create_access_token({"sub": str(user["id"]), "role": user["role"]})
    _set_auth_cookie(response, token)

    logger.info("User logged in: %s", user["email"])
    return {"user": _row_to_user(user), "token": token, "message": "Signed in successfully."}



@router.post("/logout")
def logout(response: Response):
    """Clear the auth cookie and log the user out."""
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"message": "Signed out successfully."}


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return _row_to_user(current_user)


@router.post("/invite", status_code=status.HTTP_201_CREATED)
def invite_user(
    payload: InviteRequest,
    current_user: dict = Depends(require_plant_admin),
):
    """
    Plant Admin generates a one-time invite link for a new user.
    The link is valid for 7 days and can only be used once.
    """
    try:
        invite = create_invite_token(
            invited_by_id=current_user["id"],
            plant_id=current_user["plant_id"],
            email=str(payload.email) if payload.email else None,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "[/invite] Failed to create invite for admin %s in plant %s",
            current_user["email"], current_user["plant_id"],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate invite link. Please try again.",
        ) from exc

    logger.info(
        "Invite created by %s for plant %s",
        current_user["email"],
        current_user["plant_id"],
    )
    return invite


@router.post("/register-via-invite", status_code=status.HTTP_201_CREATED)
def register_via_invite(payload: RegisterViaInviteRequest, response: Response):
    """
    Complete user registration using an invite token.
    Validates the token, creates the user, and returns an auth cookie.
    """
    try:
        invite = validate_invite_token(payload.token)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("[/register-via-invite] Token validation error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate invite link. Please try again.",
        ) from exc

    # If the invite pre-filled an email, the registering user must use it
    if invite["email"] and str(payload.email).lower() != invite["email"].lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invite was sent for a different email address.",
        )

    try:
        user = create_user(
            email=str(payload.email),
            password=payload.password,
            full_name=payload.full_name,
            role="user",
            plant_id=invite["plant_id"],
            plant_name=None,
            created_by=invite["invited_by"],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("[/register-via-invite] Failed to create user %s", payload.email)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create your account. Please try again.",
        ) from exc

    mark_invite_used(payload.token)

    try:
        token = create_access_token({"sub": str(user["id"]), "role": user["role"]})
        _set_auth_cookie(response, token)
    except Exception as exc:
        logger.exception("[/register-via-invite] Token generation failed for user id=%s", user.get("id"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account created but auto-login failed. Please sign in manually.",
        ) from exc

    logger.info("New user registered via invite: %s", user["email"])
    return {"user": _row_to_user(user), "message": "Account created successfully."}


@router.get("/users")
def list_users(current_user: dict = Depends(require_plant_admin)):
    """
    Plant Admin: list all users in their plant.
    """
    try:
        users = get_users_by_plant(current_user["plant_id"])
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "[/users] Failed to fetch users for plant %s", current_user["plant_id"]
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user list. Please try again.",
        ) from exc
    return [_row_to_user(u) for u in users]


@router.patch("/users/{user_id}")
def toggle_user(
    user_id: int,
    current_user: dict = Depends(require_plant_admin),
):
    """
    Plant Admin: toggle a user's active status.
    Plant Admins cannot deactivate themselves.
    """
    if user_id == current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account.",
        )

    # Ensure the target user belongs to the same plant
    target = get_user_by_id(user_id)
    if not target or target.get("plant_id") != current_user["plant_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in your plant.",
        )

    updated = toggle_user_active(user_id)
    return _row_to_user(updated)
