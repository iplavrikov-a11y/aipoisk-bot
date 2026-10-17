import uuid
import hashlib
import hmac

from fastapi.testclient import TestClient


def test_public_get_unsubscribe_only_renders_confirmation(monkeypatch):
    from app.main import app
    import app.outreach_unsubscribe as unsubscribe

    calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(unsubscribe, "verify_unsubscribe_token", lambda email, token: True)
    monkeypatch.setattr(
        unsubscribe,
        "record_shared_suppression",
        lambda email, reason, source: calls.append((email, reason, source)),
    )

    response = TestClient(app).get(
        "/api/outreach/unsubscribe",
        params={"email": "recipient@example.ru", "token": "valid-token"},
    )

    assert response.status_code == 200
    assert "Отписаться" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert calls == []


def test_public_post_unsubscribe_updates_matching_outreach_lead(monkeypatch):
    from app.db import SessionLocal
    from app.main import app
    from app.outreach_models import OutreachLead
    import app.outreach_unsubscribe as unsubscribe

    email = f"public-optout-{uuid.uuid4().hex}@example.ru"
    lead_id = f"public-optout-{uuid.uuid4().hex}"
    calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(unsubscribe, "verify_unsubscribe_token", lambda recipient, token: recipient == email)
    monkeypatch.setattr(
        unsubscribe,
        "record_shared_suppression",
        lambda recipient, reason, source: calls.append((recipient, reason, source)),
    )

    db = SessionLocal()
    try:
        db.add(OutreachLead(id=lead_id, email=email, status="new", mx_valid=True))
        db.commit()

        response = TestClient(app).post(
            "/api/outreach/unsubscribe",
            data={"email": email, "token": "valid-token"},
        )

        assert response.status_code == 200
        assert email not in response.text
        db.expire_all()
        lead = db.query(OutreachLead).filter(OutreachLead.id == lead_id).one()
        assert lead.status == "unsubscribed"
        assert lead.mx_valid is False
        assert calls == [(email, "unsubscribed", "tenderlex_public_unsubscribe")]
    finally:
        db.query(OutreachLead).filter(OutreachLead.id == lead_id).delete()
        db.commit()
        db.close()


def test_public_unsubscribe_rejects_invalid_token_without_writing(monkeypatch):
    from app.main import app
    import app.outreach_unsubscribe as unsubscribe

    monkeypatch.setattr(unsubscribe, "verify_unsubscribe_token", lambda email, token: False)
    monkeypatch.setattr(
        unsubscribe,
        "record_shared_suppression",
        lambda *args: (_ for _ in ()).throw(AssertionError("must not write")),
    )

    response = TestClient(app).post(
        "/api/outreach/unsubscribe",
        data={"email": "recipient@example.ru", "token": "invalid-token"},
    )

    assert response.status_code == 400


def test_shared_token_verification_loads_shared_module_dependencies(monkeypatch, tmp_path):
    from app import outreach_suppression

    key = b"test-unsubscribe-key"
    key_path = tmp_path / "unsubscribe.key"
    key_path.write_bytes(key)
    email = "recipient@example.ru"
    token = hmac.new(
        key,
        b"tenderlex-outreach:unsubscribe:v1:" + email.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    monkeypatch.setenv("OUTREACH_UNSUBSCRIBE_KEY_FILE", str(key_path))
    outreach_suppression._shared_unsubscribe_module.cache_clear()

    assert outreach_suppression.verify_unsubscribe_token(email, token) is True
    assert outreach_suppression.verify_unsubscribe_token(email, "bad-token") is False
