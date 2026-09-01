from __future__ import annotations

import os
import tempfile
import pytest

# Configure isolated test database for entire test session
_test_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_test_db_path = _test_db_file.name
_test_db_file.close()

os.environ["AIPOISK_DATABASE_URL"] = f"sqlite:///{_test_db_path}"

from app.db import init_db


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    init_db()
    yield
    try:
        if os.path.exists(_test_db_path):
            os.remove(_test_db_path)
    except Exception:
        pass
