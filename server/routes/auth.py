"""Authentication routes, session handling, and security dependencies."""

from __future__ import annotations

import os
import secrets
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.database import get_db
from server.models import User

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
    """Dependency that resolves the authenticated User from the active session."""
    token = get_token_from_request(request)
    if not token or token not in ACTIVE_SESSIONS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    user_id = ACTIVE_SESSIONS[token]
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        # Purge stale session mapping
        ACTIVE_SESSIONS.pop(token, None)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


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
