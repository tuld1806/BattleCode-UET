"""Domain 4 Deep Testing: Concurrency, SQLite WAL thread-safety, Elo clamping, and SQL injection safety."""

import concurrent.futures
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from server.database import Base
from server.models import User
from server.tournament import apply_elo_change, calculate_elo_delta


@pytest.fixture
def isolated_db_factory(tmp_path):
    """Create an isolated, dedicated SQLite database with WAL mode for concurrency testing."""
    db_file = tmp_path / "wal_concurrency.db"
    test_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    yield TestingSession
    test_engine.dispose()


def test_elo_floor_clamping_at_zero_extreme():
    """Verify Elo rating strictly clamps to 0 and never drops negative even under huge multiplier loss."""
    # Score 0.0 (Loss) against an equally rated player with x = 3.0
    delta_a, delta_b = calculate_elo_delta(
        r_a=50,
        r_b=50,
        score=0.0,
        multiplier=3.0,
        k=32,
    )
    # delta_a is -48
    assert delta_a < 0
    # Apply change to 30 Elo (30 - 48 = -18 -> clamped to 0)
    new_rating = apply_elo_change(30, delta_a)
    assert new_rating == 0  # Clamped to zero!
    assert apply_elo_change(10, -500) == 0


def test_sqlite_wal_multi_threaded_concurrency(isolated_db_factory):
    """Verify that multiple concurrent threads can read and write to SQLite simultaneously without locks."""
    def worker_task(thread_id: int) -> bool:
        db: Session = isolated_db_factory()
        try:
            # Create user
            username = f"worker_thread_user_{thread_id}"
            user = db.query(User).filter(User.username == username).first()
            if not user:
                user = User(username=username, elo=1200 + thread_id)
                user.set_password("pass123")
                db.add(user)
                db.commit()
                db.refresh(user)

            # Read all users
            all_users = db.query(User).all()
            assert len(all_users) >= 1

            # Update user stats
            user.wins += 1
            db.commit()
            return True
        finally:
            db.close()

    # Execute with 10 concurrent threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker_task, i) for i in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 10
    assert all(r is True for r in results)


def test_sql_injection_username_safety(isolated_db_factory):
    """Verify that SQL injection patterns in usernames are handled safely as literal strings."""
    db = isolated_db_factory()
    try:
        malicious_usernames = [
            "user' OR '1'='1",
            "admin'--",
            "test'; DROP TABLE users; --",
        ]

        for mal_name in malicious_usernames:
            user = db.query(User).filter(User.username == mal_name).first()
            if not user:
                user = User(username=mal_name, elo=1200)
                user.set_password("secret")
                db.add(user)
                db.commit()
                db.refresh(user)

            # Query back
            queried = db.query(User).filter(User.username == mal_name).first()
            assert queried is not None
            assert queried.username == mal_name
    finally:
        db.close()

