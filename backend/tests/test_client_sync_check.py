import pytest
from app.db import SessionLocal
from app.models import Client, WebUser, Job
from app.main import clients_sync_check


def test_clients_sync_check():
    db = SessionLocal()
    try:
        # Check initial sync check
        res1 = clients_sync_check(db=db)
        assert "version_key" in res1
        assert "clients_count" in res1
        assert "jobs_count" in res1

        # Add dummy client
        c = Client(telegram_id="test_sync_check_tg_9999", name="Sync Check Client")
        db.add(c)
        db.commit()
        db.refresh(c)

        res2 = clients_sync_check(db=db)
        assert res2["clients_count"] == res1["clients_count"] + 1
        assert res2["version_key"] != res1["version_key"]
        assert res2["latest_client"] is not None
        assert res2["latest_client"]["name"] == "Sync Check Client"

        # Cleanup
        db.delete(c)
        db.commit()

        res3 = clients_sync_check(db=db)
        assert res3["clients_count"] == res1["clients_count"]
    finally:
        db.close()
