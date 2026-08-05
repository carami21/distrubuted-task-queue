import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

REPO_ROOT = Path(__file__).resolve().parent.parent
for path in (
    REPO_ROOT,
    REPO_ROOT / "services" / "api",
    REPO_ROOT / "services" / "worker",
    REPO_ROOT / "services" / "scheduler",
):
    p = str(path)
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture
def mock_conn():
    """A fake psycopg2 connection/cursor pair usable as a context manager."""
    cursor = MagicMock()
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = False
    conn.cursor.return_value.__enter__.return_value = cursor
    conn.cursor.return_value.__exit__.return_value = False
    return conn, cursor


@pytest.fixture
def api_client(monkeypatch):
    from fastapi.testclient import TestClient
    import main as api_main

    return TestClient(api_main.app)
