from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.legal import (
    LEGAL_DOCUMENT_PERSONAL_DATA,
    LEGAL_DOCUMENT_TERMS,
    LEGAL_VERSION,
    has_current_legal_acceptances,
    record_legal_acceptance,
)
from app.models import LegalAcceptance


class LegalAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.db = sessionmaker(bind=engine, autoflush=False, autocommit=False)()

    def tearDown(self) -> None:
        self.db.close()

    def test_current_acceptance_requires_both_documents_and_is_idempotent(self) -> None:
        record_legal_acceptance(
            self.db,
            subject_type="telegram",
            subject_id="123",
            document_type=LEGAL_DOCUMENT_TERMS,
            source="telegram",
        )
        record_legal_acceptance(
            self.db,
            subject_type="telegram",
            subject_id="123",
            document_type=LEGAL_DOCUMENT_TERMS,
            source="telegram",
        )
        self.assertFalse(has_current_legal_acceptances(self.db, subject_type="telegram", subject_id="123"))
        self.assertEqual(self.db.query(LegalAcceptance).count(), 1)

        record_legal_acceptance(
            self.db,
            subject_type="telegram",
            subject_id="123",
            document_type=LEGAL_DOCUMENT_PERSONAL_DATA,
            source="telegram",
        )
        self.assertTrue(has_current_legal_acceptances(self.db, subject_type="telegram", subject_id="123"))

    def test_old_document_version_does_not_unlock_current_service(self) -> None:
        for document_type in (LEGAL_DOCUMENT_TERMS, LEGAL_DOCUMENT_PERSONAL_DATA):
            record_legal_acceptance(
                self.db,
                subject_type="telegram",
                subject_id="old-user",
                document_type=document_type,
                document_version="2026-06-07",
                source="telegram",
            )

        self.assertFalse(has_current_legal_acceptances(self.db, subject_type="telegram", subject_id="old-user"))
        self.assertEqual(LEGAL_VERSION, "2026-07-17")
