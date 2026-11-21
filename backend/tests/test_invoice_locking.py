from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

import pytest

from app.db import SessionLocal
from app.models import Client, Invoice, new_id


def test_invoice_mutations_are_serialized_and_see_latest_status():
    from app.invoice_service import lock_invoice_for_update

    db = SessionLocal()
    client = Client(id=new_id(), telegram_id=f"lock-{new_id()}", name="Lock test", money_balance_kopeks=0)
    invoice = Invoice(client_id=client.id, invoice_number=f"LOCK-{new_id()}", amount_rub=5000, bonus_rub=0, total_credit_rub=5000, status="issued")
    db.add_all([client, invoice])
    db.commit()
    invoice_id = invoice.id
    first = lock_invoice_for_update(db, invoice_id)
    ready = Event()

    def second_reader():
        other = SessionLocal()
        try:
            ready.set()
            current = lock_invoice_for_update(other, invoice_id)
            status = current.status
            other.rollback()
            return status
        finally:
            other.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(second_reader)
        assert ready.wait(2)
        with pytest.raises(TimeoutError):
            future.result(timeout=0.2)
        first.status = "paid"
        db.commit()
        assert future.result(timeout=3) == "paid"
    db.close()

