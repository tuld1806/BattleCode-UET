"""Database models for users, bots, matches, tournament settings, and bracket matches."""

from datetime import datetime, timezone
import hashlib
import hmac
import secrets
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.database import Base


def hash_password(password: str) -> str:
    """Hash a plaintext password using SHA-256 with a random salt.

    Args:
        password: Plaintext password string.

    Returns:
        Salted hash string in the format '{salt}${digest}'.
    """
    salt = secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def verify_password_hash(plain: str, stored_hash: str) -> bool:
    """Verify plaintext password against stored hash with fallback support.

    Args:
        plain: Plaintext password to verify.
        stored_hash: Stored password hash (salted hash, raw sha256 hex, or legacy plain).

    Returns:
        True if matching, False otherwise.
    """
    if not stored_hash:
        return False
    if "$" in stored_hash:
        salt, digest = stored_hash.split("$", 1)
        expected = hashlib.sha256((salt + plain).encode("utf-8")).hexdigest()
        return hmac.compare_digest(digest, expected)
    # Direct hash or plain comparison fallback
    direct_hash = hashlib.sha256(plain.encode("utf-8")).hexdigest()
    return hmac.compare_digest(stored_hash, direct_hash) or hmac.compare_digest(stored_hash, plain)


class User(Base):
    """User account entity representing a tournament participant or admin."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    elo: Mapped[int] = mapped_column(Integer, default=1200, nullable=False)
    wins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    losses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    draws: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    bots: Mapped[List["Bot"]] = relationship("Bot", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, plain: str) -> None:
        """Hash and update the user's password."""
        self.password_hash = hash_password(plain)

    def verify_password(self, plain: str) -> bool:
        """Verify candidate plaintext password against stored hash."""
        return verify_password_hash(plain, self.password_hash)


class Bot(Base):
    """Uploaded bot entity linked to a specific user."""

    __tablename__ = "bots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    filepath: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="bots")


class Match(Base):
    """Match execution record storing scores, Elo changes, and replay links."""

    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player1_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    player2_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    bot1_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("bots.id"), nullable=True)
    bot2_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("bots.id"), nullable=True)
    winner_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    win_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    total_turns: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    p1_elo_before: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    p1_elo_after: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    p2_elo_before: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    p2_elo_after: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    replay_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    is_bracket: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    player1: Mapped["User"] = relationship("User", foreign_keys=[player1_id])
    player2: Mapped["User"] = relationship("User", foreign_keys=[player2_id])
    winner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[winner_id])
    bot1: Mapped[Optional["Bot"]] = relationship("Bot", foreign_keys=[bot1_id])
    bot2: Mapped[Optional["Bot"]] = relationship("Bot", foreign_keys=[bot2_id])


class TournamentSetting(Base):
    """Key-value persistence for dynamic tournament parameters."""

    __tablename__ = "tournament_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class BracketMatch(Base):
    """Playoff bracket match pairing and results."""

    __tablename__ = "bracket_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    round_name: Mapped[str] = mapped_column(String(64), nullable=False)
    match_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    player1_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    player2_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    winner_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    score_p1: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    score_p2: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    player1: Mapped[Optional["User"]] = relationship("User", foreign_keys=[player1_id])
    player2: Mapped[Optional["User"]] = relationship("User", foreign_keys=[player2_id])
    winner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[winner_id])
