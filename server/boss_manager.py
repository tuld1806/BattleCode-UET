"""Management utilities for deploying, retracting, and querying benchmark boss bots."""

from __future__ import annotations

import secrets
from typing import Any, List
from sqlalchemy.orm import Session

from server.bosses import BOSS_REGISTRY, get_all_bosses, get_boss
from server.models import Bot, User


def get_all_bosses_status(db: Session) -> List[dict[str, Any]]:
    """Retrieve current deployment and rating status for all registered boss bots.

    Args:
        db: Active SQLAlchemy database session.

    Returns:
        List of boss status dictionaries sorted by level ascending.
    """
    statuses: List[dict[str, Any]] = []
    for boss_meta in get_all_bosses():
        slug = boss_meta["slug"]
        display_name = boss_meta["display_name"]
        user = db.query(User).filter(User.username == display_name).first()
        is_deployed = False
        elo = boss_meta["default_elo"]
        user_id = None
        bot_id = None

        if user:
            user_id = user.id
            elo = user.elo
            active_bot = (
                db.query(Bot)
                .filter(Bot.user_id == user.id, Bot.is_active == True)  # noqa: E712
                .first()
            )
            if active_bot:
                is_deployed = True
                bot_id = active_bot.id

        statuses.append({
            "boss_slug": slug,
            "slug": slug,
            "name": boss_meta["name"],
            "display_name": display_name,
            "level": boss_meta["level"],
            "description": boss_meta["description"],
            "default_elo": boss_meta["default_elo"],
            "elo": elo,
            "is_deployed": is_deployed,
            "user_id": user_id,
            "bot_id": bot_id,
        })
    return statuses


def deploy_boss(db: Session, boss_slug: str) -> dict[str, Any]:
    """Deploy a registered boss bot by creating or activating its user account and bot record.

    Args:
        db: Active SQLAlchemy database session.
        boss_slug: Identifier slug of the boss to deploy.

    Returns:
        Updated status dictionary of the deployed boss.

    Raises:
        ValueError: If boss_slug is not registered in BOSS_REGISTRY.
    """
    boss_meta = get_boss(boss_slug)
    if not boss_meta:
        raise ValueError(f"Unknown boss slug: '{boss_slug}'")

    display_name = boss_meta["display_name"]
    user = db.query(User).filter(User.username == display_name).first()

    if not user:
        user = User(
            username=display_name,
            is_admin=False,
            elo=boss_meta["default_elo"],
            wins=0,
            losses=0,
            draws=0,
        )
        user.set_password(secrets.token_hex(16))
        db.add(user)
        db.flush()
    else:
        user.is_admin = False

    # Check for existing bot entry for this user
    bot = db.query(Bot).filter(Bot.user_id == user.id).first()
    if not bot:
        bot = Bot(
            user_id=user.id,
            filename=f"{boss_slug}_bot.py",
            filepath=boss_meta["file_path"],
            is_active=True,
        )
        db.add(bot)
    else:
        bot.filename = f"{boss_slug}_bot.py"
        bot.filepath = boss_meta["file_path"]
        bot.is_active = True

    # Ensure any unexpected duplicate bots for this user are deactivated
    other_bots = db.query(Bot).filter(Bot.user_id == user.id, Bot.id != bot.id).all()
    for extra_bot in other_bots:
        extra_bot.is_active = False

    db.commit()
    db.refresh(user)
    db.refresh(bot)

    return {
        "boss_slug": boss_slug,
        "slug": boss_slug,
        "name": boss_meta["name"],
        "display_name": display_name,
        "level": boss_meta["level"],
        "description": boss_meta["description"],
        "default_elo": boss_meta["default_elo"],
        "elo": user.elo,
        "is_deployed": True,
        "user_id": user.id,
        "bot_id": bot.id,
    }


def retract_boss(db: Session, boss_slug: str) -> dict[str, Any]:
    """Retract a registered boss bot by deactivating its bot records.

    Args:
        db: Active SQLAlchemy database session.
        boss_slug: Identifier slug of the boss to retract.

    Returns:
        Updated status dictionary of the retracted boss.

    Raises:
        ValueError: If boss_slug is not registered in BOSS_REGISTRY.
    """
    boss_meta = get_boss(boss_slug)
    if not boss_meta:
        raise ValueError(f"Unknown boss slug: '{boss_slug}'")

    display_name = boss_meta["display_name"]
    user = db.query(User).filter(User.username == display_name).first()
    elo = boss_meta["default_elo"]
    user_id = None

    if user:
        user_id = user.id
        elo = user.elo
        user.is_admin = False
        bots = db.query(Bot).filter(Bot.user_id == user.id).all()
        for bot in bots:
            bot.is_active = False
        db.commit()
        db.refresh(user)

    return {
        "boss_slug": boss_slug,
        "slug": boss_slug,
        "name": boss_meta["name"],
        "display_name": display_name,
        "level": boss_meta["level"],
        "description": boss_meta["description"],
        "default_elo": boss_meta["default_elo"],
        "elo": elo,
        "is_deployed": False,
        "user_id": user_id,
        "bot_id": None,
    }
