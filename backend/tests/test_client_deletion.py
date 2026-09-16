import pytest
from app.db import SessionLocal
from app.models import (
    Client,
    ClientTelegramAccount,
    WebUser,
    Job,
    SupplierResult,
    JobFile,
    JobSource,
    BillingTransaction,
    AccountLinkToken,
    UserJourneyEvent,
    OnboardingReminder,
    ClientTariffOverride,
)
from app.main import _force_delete_client


def test_safe_force_delete_client():
    db = SessionLocal()
    try:
        # Create dummy client A (to delete) and client B (to remain untouched)
        client_a = Client(telegram_id="test_del_a_999999", name="Удаляемый Клиент")
        client_b = Client(telegram_id="test_keep_b_999999", name="Сохраняемый Клиент")
        db.add_all([client_a, client_b])
        db.commit()
        db.refresh(client_a)
        db.refresh(client_b)

        # Attach child records to client A
        tg_acc = ClientTelegramAccount(client_id=client_a.id, telegram_id="tg_del_999999", name="Акк")
        wu = WebUser(client_id=client_a.id, email="test_del_999999@example.com", name="Веб")
        job = Job(client_id=client_a.id, title="Тестовая задача")
        db.add_all([tg_acc, wu, job])
        db.commit()
        db.refresh(job)

        sr = SupplierResult(job_id=job.id, company_name="Тест Поставщик")
        jf = JobFile(job_id=job.id, original_filename="test.pdf", stored_path="/tmp/test.pdf")
        js = JobSource(job_id=job.id, value="https://zakupki.gov.ru")
        bt = BillingTransaction(client_id=client_a.id, job_id=job.id, kind="supplier_search", operation="charge", amount_kopeks=100)
        uj = UserJourneyEvent(client_id=client_a.id, channel="web", event_name="login")
        rem = OnboardingReminder(client_id=client_a.id, channel="web")
        override = ClientTariffOverride(client_id=client_a.id, kind="supplier_search", price_kopeks=50)

        db.add_all([sr, jf, js, bt, uj, rem, override])
        db.commit()

        # Execute safe deletion of Client A
        _force_delete_client(db, client_a)
        db.commit()

        # Verify Client A and all its children are gone
        assert db.get(Client, client_a.id) is None
        assert db.query(ClientTelegramAccount).filter(ClientTelegramAccount.client_id == client_a.id).first() is None
        assert db.query(WebUser).filter(WebUser.client_id == client_a.id).first() is None
        assert db.query(Job).filter(Job.client_id == client_a.id).first() is None
        assert db.query(SupplierResult).filter(SupplierResult.job_id == job.id).first() is None
        assert db.query(JobFile).filter(JobFile.job_id == job.id).first() is None
        assert db.query(JobSource).filter(JobSource.job_id == job.id).first() is None
        assert db.query(BillingTransaction).filter(BillingTransaction.client_id == client_a.id).first() is None

        # Verify Client B is completely untouched and safe!
        assert db.get(Client, client_b.id) is not None
        assert db.get(Client, client_b.id).name == "Сохраняемый Клиент"

    finally:
        # Clean up Client B
        if db.get(Client, client_b.id):
            _force_delete_client(db, client_b)
            db.commit()
        db.close()
