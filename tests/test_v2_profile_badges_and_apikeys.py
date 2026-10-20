"""Unit tests for user profile enhancements: CLI API Keys and Badges."""

import pytest
from fastapi.testclient import TestClient

from server.database import get_db_context, init_db
from server.main import app
from server.models import ApiKey, Badge, User, UserBadge

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_api_key_lifecycle_and_badge_query():
    """Verify creating, listing, and revoking API keys, and querying user badges."""
    with get_db_context() as db:
        user = db.query(User).filter(User.username == "profile_test_user").first()
        if not user:
            user = User(username="profile_test_user")
            user.set_password("UserPass123!")
            db.add(user)
            db.commit()
            db.refresh(user)

        # Ensure a badge exists and is assigned
        b = db.query(Badge).filter(Badge.slug == "active_player").first()
        if b:
            ub = db.query(UserBadge).filter(UserBadge.user_id == user.id, UserBadge.badge_id == b.id).first()
            if not ub:
                db.add(UserBadge(user_id=user.id, badge_id=b.id))
                db.commit()

    # Login
    login_res = client.post(
        "/api/auth/login",
        json={"username": "profile_test_user", "password": "UserPass123!"},
    )
    assert login_res.status_code == 200
    cookies = login_res.cookies

    # 1. Create API key
    res = client.post("/api/auth/api-keys", json={"name": "My CLI Token"}, cookies=cookies)
    assert res.status_code == 201
    data = res.json()
    assert "token" in data
    assert data["token"].startswith("bcuet_")
    assert data["name"] == "My CLI Token"
    key_id = data["id"]

    # 2. List keys
    list_res = client.get("/api/auth/api-keys", cookies=cookies)
    assert list_res.status_code == 200
    keys = list_res.json()
    assert any(k["id"] == key_id for k in keys)

    # 3. Badges endpoint
    badge_res = client.get("/api/profile/badges", cookies=cookies)
    assert badge_res.status_code == 200
    badges_data = badge_res.json()
    assert len(badges_data) >= 1
    assert any(b["slug"] == "active_player" for b in badges_data)

    # 4. Delete key
    del_res = client.delete(f"/api/auth/api-keys/{key_id}", cookies=cookies)
    assert del_res.status_code == 200

    # Verify deleted
    with get_db_context() as db:
        deleted = db.query(ApiKey).filter(ApiKey.id == key_id).first()
        assert deleted is None
