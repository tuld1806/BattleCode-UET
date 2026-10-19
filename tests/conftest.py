"""Pytest test suite configuration and database isolation."""

import os

# Isolate automated tests to test.db so running pytest does not drop production/dev app.db tables
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
