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


@pytest.fixture(autouse=True)
def suppress_real_email_relay_in_tests(monkeypatch):
    """Prevent automated tests from hitting the live email relay and generating bounced email flood."""
    import app.web_auth as web_auth
    import app.nurturing as nurturing

    original_relay = web_auth._send_email_verification_via_relay

    def safe_relay(user, subject, html_body):
        # Prevent tests from calling the real production relay IP
        if "79.133.182.215" in str(web_auth.config.email_relay_url):
            return True
        return original_relay(user, subject, html_body)

    monkeypatch.setattr(web_auth, "_send_email_verification_via_relay", safe_relay)
    monkeypatch.setattr(nurturing, "_send_email_verification_via_relay", safe_relay)

