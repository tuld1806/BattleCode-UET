"""Authentication routes, session handling, and security dependencies."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
import secrets
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.database import get_db
from server.models import ApiKey, Badge, User, UserBadge

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory session store mapping active token string to user ID
ACTIVE_SESSIONS: Dict[str, int] = {}


class RegisterRequest(BaseModel):
    """Pydantic schema for user account registration."""
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


def get_token_from_request(request: Request) -> str | None:
    """Extract session token from Authorization header or HTTP cookies."""
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return request.cookies.get("session_token")


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Dependency that resolves the authenticated User from the active session or API Key."""
    token = get_token_from_request(request)
    if token and token in ACTIVE_SESSIONS:
        user_id = ACTIVE_SESSIONS[token]
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return user
        # Purge stale session mapping
        ACTIVE_SESSIONS.pop(token, None)

    # Fallback to API Key resolution (X-API-Key header or Authorization: Bearer bcuet_...)
    raw_api_key = request.headers.get("x-api-key")
    if not raw_api_key and token and token.startswith("bcuet_"):
        raw_api_key = token

    if raw_api_key:
        candidate_key = raw_api_key.strip()
        key_hash = hashlib.sha256(candidate_key.encode("utf-8")).hexdigest()
        api_key = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
        if api_key and api_key.user:
            api_key.last_used_at = datetime.now(timezone.utc)
            db.commit()
            return api_key.user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


get_current_user_or_api_key = get_current_user



def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency that ensures the authenticated User has admin privileges."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )
    return current_user


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Register a new user account with unique username and hashed password."""
    username = payload.username.strip()
    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot be empty",
        )

    target_admin = os.getenv("ADMIN_USERNAME", "admin").strip().lower()
    if username.lower() == target_admin or username.lower() == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is reserved for administrator",
        )

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    user = User(username=username, elo=1200)
    user.set_password(payload.password)
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "username": user.username,
        "elo": user.elo,
        "is_admin": user.is_admin,
    }


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Authenticate user credentials from JSON or form data, issuing a session token."""
    content_type = request.headers.get("content-type", "")
    username: str | None = None
    password: str | None = None

    if "application/json" in content_type:
        try:
            body = await request.json()
            username = body.get("username")
            password = body.get("password")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Malformed JSON body",
            )
    else:
        try:
            form = await request.form()
            username = form.get("username")
            password = form.get("password")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Malformed form data",
            )

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both username and password are required",
        )

    user = db.query(User).filter(User.username == username).first()
    if not user or not user.verify_password(password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = secrets.token_hex(24)
    ACTIVE_SESSIONS[token] = user.id
    response.set_cookie(key="session_token", value=token, httponly=True, path="/")

    return {
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "elo": user.elo,
            "is_admin": user.is_admin,
        },
    }


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
) -> Dict[str, str]:
    """Terminate the active session and clear session cookie."""
    token = get_token_from_request(request)
    if token and token in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[token]

    response.delete_cookie(key="session_token", path="/")
    return {"message": "Logged out successfully"}


@router.get("/me")
def get_me(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve profile and statistics for the currently authenticated user."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "elo": current_user.elo,
        "is_admin": current_user.is_admin,
        "wins": current_user.wins,
        "losses": current_user.losses,
        "draws": current_user.draws,
    }


class CreateApiKeyRequest(BaseModel):
    name: str = Field("CLI Bot Upload", max_length=64)


@router.post("/api-keys", status_code=status.HTTP_201_CREATED)
def create_api_key(
    payload: CreateApiKeyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Generate a new personal API Key for headless CLI bot uploads."""
    raw_token = "bcuet_" + secrets.token_hex(24)
    key_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    api_key = ApiKey(
        user_id=current_user.id,
        name=payload.name.strip(),
        key_hash=key_hash,
        key_prefix=raw_token[:12],
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return {
        "id": api_key.id,
        "name": api_key.name,
        "token": raw_token,
        "prefix": api_key.key_prefix,
        "created_at": api_key.created_at.isoformat() if api_key.created_at else None,
    }


@router.get("/api-keys")
def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List all registered personal API keys for the authenticated user."""
    keys = (
        db.query(ApiKey)
        .filter(ApiKey.user_id == current_user.id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )
    return [
        {
            "id": k.id,
            "name": k.name,
            "prefix": k.key_prefix,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        }
        for k in keys
    ]


@router.delete("/api-keys/{key_id}")
def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Revoke and delete a personal API key."""
    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.id == key_id, ApiKey.user_id == current_user.id)
        .first()
    )
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key with id {key_id} not found.",
        )
    db.delete(api_key)
    db.commit()
    return {"message": "API key revoked successfully."}


profile_router = APIRouter(prefix="/profile", tags=["profile"])


@profile_router.get("/badges")
def get_user_badges(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Retrieve all unlocked achievement badges for the authenticated user."""
    user_badges = (
        db.query(UserBadge)
        .filter(UserBadge.user_id == current_user.id)
        .order_by(UserBadge.earned_at.desc())
        .all()
    )
    results = []
    for ub in user_badges:
        b = ub.badge
        if b:
            results.append({
                "id": b.id,
                "slug": b.slug,
                "name": b.name,
                "description": b.description,
                "icon": b.icon,
                "earned_at": ub.earned_at.isoformat() if ub.earned_at else None,
            })
    return results
