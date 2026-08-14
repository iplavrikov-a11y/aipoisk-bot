from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.account_linking import (
    TELEGRAM_TO_WEB,
    WEB_TO_TELEGRAM,
    AccountLinkError,
    active_account_link_token,
    consume_telegram_to_web_token,
    consume_web_to_telegram_token,
    create_account_link_token,
)
from app.db import Base
from app.journey import claim_reminder, reminder_candidates
from app.models import (
    AccountLinkToken,
    BillingTransaction,
    Client,
    ClientTelegramAccount,
    Job,
    OnboardingReminder,
    SystemSettings,
    UserJourneyEvent,
    WebUser,
)
from app.web_auth import create_web_user, touch_web_session_if_stale


class AccountLinkingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "test.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

    def tearDown(self) -> None:
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_web_to_telegram_link_preserves_identity_and_accounting(self) -> None:
        db = self.Session()
        try:
            client = Client(id="web-client", telegram_id="web:one", money_balance_kopeks=20_000, money_reserved_kopeks=3_000)
            user = WebUser(id="web-user", client_id=client.id, email="user@example.com", password_hash="hash")
            job = Job(id="job-1", client_id=client.id, mode="supplier_search")
            transaction = BillingTransaction(id="tx-1", client_id=client.id, kind="supplier_search", operation="grant", units=1)
            db.add_all([client, user, job, transaction])
            db.commit()

            raw, record = create_account_link_token(db, client=client, direction=WEB_TO_TELEGRAM, web_user=user)

            self.assertNotEqual(raw, record.token_hash)
            self.assertNotIn(raw, record.token_hash)
            result = consume_web_to_telegram_token(db, raw, telegram_id="123456", username="buyer", name="Buyer")

            self.assertEqual(result.client_id, client.id)
            self.assertEqual(db.get(Client, client.id).telegram_id, "123456")
            self.assertEqual(db.get(Client, client.id).money_balance_kopeks, 20_000)
            self.assertEqual(db.get(Client, client.id).money_reserved_kopeks, 3_000)
            self.assertEqual(db.query(Job).filter(Job.client_id == client.id).count(), 1)
            self.assertEqual(db.query(BillingTransaction).filter(BillingTransaction.client_id == client.id).count(), 1)
            self.assertEqual(db.query(ClientTelegramAccount).filter(ClientTelegramAccount.telegram_id == "123456").count(), 1)
            with self.assertRaises(AccountLinkError):
                consume_web_to_telegram_token(db, raw, telegram_id="123456")
        finally:
            db.close()

    def test_conflict_does_not_merge_or_change_balances(self) -> None:
        db = self.Session()
        try:
            target = Client(id="target", telegram_id="web:target", money_balance_kopeks=10_000)
            source = Client(id="source", telegram_id="777", money_balance_kopeks=20_000)
            user = WebUser(id="web-user", client_id=target.id, email="target@example.com", password_hash="hash")
            account = ClientTelegramAccount(id="tg", client_id=source.id, telegram_id="777")
            db.add_all([target, source, user, account, Job(id="source-job", client_id=source.id)])
            db.commit()
            raw, _record = create_account_link_token(db, client=target, direction=WEB_TO_TELEGRAM, web_user=user)

            with self.assertRaisesRegex(AccountLinkError, "ничего не объединили"):
                consume_web_to_telegram_token(db, raw, telegram_id="777")

            self.assertEqual(db.get(Client, target.id).money_balance_kopeks, 10_000)
            self.assertEqual(db.get(Client, source.id).money_balance_kopeks, 20_000)
            self.assertEqual(db.get(ClientTelegramAccount, "tg").client_id, source.id)
            self.assertEqual(db.get(Job, "source-job").client_id, source.id)
            self.assertEqual(db.query(Client).count(), 2)
            self.assertEqual(db.query(AccountLinkToken).one().status, "conflict")
        finally:
            db.close()

    def test_telegram_registration_uses_existing_client_without_second_trial(self) -> None:
        db = self.Session()
        try:
            client = Client(id="telegram-client", telegram_id="888", is_trial=True, money_balance_kopeks=20_000)
            db.add(client)
            db.commit()
            raw, _record = create_account_link_token(db, client=client, direction=TELEGRAM_TO_WEB, telegram_id="888")
            record = active_account_link_token(db, raw, direction=TELEGRAM_TO_WEB)

            user = create_web_user(db, email="linked@example.com", password="safe-password", client=client, commit=False)
            consume_telegram_to_web_token(db, record, user)
            db.commit()

            self.assertEqual(db.query(Client).count(), 1)
            self.assertEqual(user.client_id, client.id)
            self.assertEqual(db.get(Client, client.id).money_balance_kopeks, 20_000)
            self.assertEqual(db.get(AccountLinkToken, record.id).status, "linked")
        finally:
            db.close()

    def test_expired_token_is_rejected_and_revoked(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client", telegram_id="web:client")
            db.add(client)
            db.commit()
            raw, record = create_account_link_token(db, client=client, direction=WEB_TO_TELEGRAM)
            record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()

            with self.assertRaisesRegex(AccountLinkError, "истёк"):
                active_account_link_token(db, raw, direction=WEB_TO_TELEGRAM)
            self.assertEqual(db.get(AccountLinkToken, record.id).status, "revoked")
        finally:
            db.close()

    def test_reminder_requires_rollout_window_and_has_unique_claim(self) -> None:
        db = self.Session()
        try:
            now = datetime(2026, 7, 15, 9, 0, tzinfo=timezone.utc)  # 12:00 Moscow
            settings = SystemSettings(
                id=1,
                onboarding_reminders_enabled=True,
                onboarding_reminders_rollout_at=(now - timedelta(hours=30)).isoformat(),
            )
            client = Client(id="trial", telegram_id="999", is_trial=True)
            account = ClientTelegramAccount(id="tg", client_id=client.id, telegram_id="999", is_active=True)
            event = UserJourneyEvent(
                id="event",
                client_id=client.id,
                channel="telegram",
                event_name="bot_started",
                created_at=now - timedelta(hours=25),
            )
            db.add_all([settings, client, account, event])
            db.commit()

            candidates = reminder_candidates(db, settings, current_time=now)
            self.assertEqual([(item.id, telegram_id) for item, telegram_id in candidates], [(client.id, "999")])
            self.assertIsNotNone(claim_reminder(db, client.id))
            self.assertIsNone(claim_reminder(db, client.id))
            self.assertEqual(db.query(OnboardingReminder).count(), 1)
            self.assertEqual(reminder_candidates(db, settings, current_time=now), [])
        finally:
            db.close()

    def test_fresh_session_touch_does_not_write(self) -> None:
        db = Mock()
        session = SimpleNamespace(last_seen_at=datetime.now(timezone.utc))

        self.assertFalse(touch_web_session_if_stale(db, session))
        db.commit.assert_not_called()

    def test_session_touch_lock_is_non_fatal(self) -> None:
        db = Mock()
        db.commit.side_effect = OperationalError("UPDATE web_sessions", {}, RuntimeError("locked"))
        session = SimpleNamespace(last_seen_at=datetime.now(timezone.utc) - timedelta(hours=1))

        self.assertFalse(touch_web_session_if_stale(db, session))
        db.rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
