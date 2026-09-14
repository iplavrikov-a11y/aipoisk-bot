from __future__ import annotations

import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.billing import (
    KIND_PROCUREMENT_REPORT,
    KIND_SUPPLIER_SEARCH,
    KIND_SUPPLIER_SEARCH_EXTRA,
    OP_CHARGE,
    OP_RELEASE,
    OP_RESERVE,
    STATUS_CUSTOMER_DECLINED,
    STATUS_DELIVERY_EXPIRED,
    expire_stale_confirmations,
    grant_package_units,
    reserve_job_units,
)
from app.db import Base
from app.models import BillingTransaction, Client, Job, UserJourneyEvent, now_utc
from app.result_offers import (
    CONFIRMATION_KIND_PARTIAL_COUNT,
    CONFIRMATION_KIND_REGISTRY_FALLBACK,
    MANIFEST_ANALYSIS_ONLY,
    MANIFEST_FULL,
    MANIFEST_LOCKED,
    accept_job_result_offer,
    active_result_offer_entitlements,
    active_result_offer_output_items,
    billing_kinds_for_result_delivery,
    claim_job_result_offer_delivery,
    complete_job_result_offer_delivery,
    decline_job_result_offer,
    expire_result_offers,
    publish_job_result_offer,
    result_offer_to_dict,
)


class ResultOfferTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def test_standalone_offer_charges_once_only_after_delivery(self) -> None:
        db = self.Session()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                client = Client(id="offer-client-1", telegram_id="101")
                job = Job(
                    id="offer-job-1",
                    client_id=client.id,
                    mode="supplier_search",
                    status="running",
                    verified_count=3,
                )
                db.add_all([client, job])
                db.commit()
                grant_package_units(db, client, kind=KIND_SUPPLIER_SEARCH, units=1)
                reserve_job_units(db, client, job)
                evidence_path, archive_path = self._write_manifests(Path(tmp), combined=False)
                job.evidence_path = str(evidence_path)
                publish_job_result_offer(db, job, kind=CONFIRMATION_KIND_REGISTRY_FALLBACK)
                db.commit()

                self.assertEqual(job.active_output_manifest, MANIFEST_LOCKED)
                self.assertEqual(active_result_offer_output_items(job), [])
                self.assertEqual(result_offer_to_dict(db, job)["alternative_verified_count"], 3)

                accept_job_result_offer(db, job, channel="web")
                self.assertEqual(job.active_output_manifest, MANIFEST_FULL)
                self.assertEqual(job.result_path, str(archive_path))
                self.assertEqual(job.offer_delivery_outcome, "pending")
                self.assertEqual(self._operations(db, job.id), [OP_RESERVE])

                token = claim_job_result_offer_delivery(db, job, channel="web")
                completed = complete_job_result_offer_delivery(
                    db,
                    job,
                    token,
                    channel="web",
                    note="test delivery",
                )
                self.assertTrue(completed)
                self.assertEqual(job.confirmation_outcome, "accepted")
                self.assertEqual(job.offer_delivery_outcome, "delivered")
                self.assertEqual(self._operations(db, job.id), [OP_RESERVE, OP_CHARGE])

                retry_token = claim_job_result_offer_delivery(db, job, channel="telegram")
                self.assertEqual(retry_token, "")
                self.assertFalse(
                    complete_job_result_offer_delivery(db, job, retry_token, channel="telegram")
                )
                self.assertEqual(self._operations(db, job.id), [OP_RESERVE, OP_CHARGE])
                events = [row.event_name for row in db.query(UserJourneyEvent).order_by(UserJourneyEvent.created_at).all()]
                self.assertEqual(
                    events,
                    ["registry_fallback_offered", "registry_fallback_accepted", "registry_fallback_delivered"],
                )
        finally:
            db.close()

    def test_additional_offer_accepts_and_charges_extra_reservation(self) -> None:
        db = self.Session()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                client = Client(id="offer-client-extra-accept", telegram_id="201")
                job = Job(
                    id="offer-job-extra-accept",
                    client_id=client.id,
                    mode="supplier_search",
                    supplier_search_run_type="additional",
                    status="running",
                    verified_count=3,
                )
                db.add_all([client, job])
                db.commit()
                grant_package_units(db, client, kind=KIND_SUPPLIER_SEARCH_EXTRA, units=1)
                reserve_job_units(db, client, job)
                # Existing pending offers may still carry the old supplier_search
                # marker and must be interpreted according to the job run type.
                evidence_path, _archive_path = self._write_manifests(Path(tmp), combined=False)
                job.evidence_path = str(evidence_path)
                publish_job_result_offer(db, job, kind=CONFIRMATION_KIND_REGISTRY_FALLBACK)
                db.commit()

                accept_job_result_offer(db, job, channel="web")
                self.assertEqual(active_result_offer_entitlements(job), [KIND_SUPPLIER_SEARCH_EXTRA])
                self.assertEqual(
                    [item["billing_kind"] for item in active_result_offer_output_items(job)],
                    [KIND_SUPPLIER_SEARCH_EXTRA, KIND_SUPPLIER_SEARCH_EXTRA],
                )
                token = claim_job_result_offer_delivery(db, job, channel="web")
                complete_job_result_offer_delivery(db, job, token, channel="web")

                operations = self._operations_by_kind(db, job.id)
                self.assertEqual(operations[KIND_SUPPLIER_SEARCH_EXTRA], [OP_RESERVE, OP_CHARGE])
                self.assertNotIn(KIND_SUPPLIER_SEARCH, operations)
        finally:
            db.close()

    def test_additional_offer_decline_releases_extra_reservation(self) -> None:
        db = self.Session()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                client = Client(id="offer-client-extra-decline", telegram_id="202")
                job = Job(
                    id="offer-job-extra-decline",
                    client_id=client.id,
                    mode="supplier_search",
                    supplier_search_run_type="additional",
                    status="running",
                )
                db.add_all([client, job])
                db.commit()
                grant_package_units(db, client, kind=KIND_SUPPLIER_SEARCH_EXTRA, units=1)
                reserve_job_units(db, client, job)
                evidence_path, _archive_path = self._write_manifests(Path(tmp), combined=False)
                job.evidence_path = str(evidence_path)
                publish_job_result_offer(db, job, kind=CONFIRMATION_KIND_REGISTRY_FALLBACK)
                db.commit()

                decline_job_result_offer(db, job, channel="telegram")

                operations = self._operations_by_kind(db, job.id)
                self.assertEqual(operations[KIND_SUPPLIER_SEARCH_EXTRA], [OP_RESERVE, OP_RELEASE])
                self.assertNotIn(KIND_SUPPLIER_SEARCH, operations)
        finally:
            db.close()

    def test_additional_offer_delivery_expiry_releases_extra_reservation(self) -> None:
        db = self.Session()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                client = Client(id="offer-client-extra-expire", telegram_id="203")
                job = Job(
                    id="offer-job-extra-expire",
                    client_id=client.id,
                    mode="supplier_search",
                    supplier_search_run_type="additional",
                    status="running",
                )
                db.add_all([client, job])
                db.commit()
                grant_package_units(db, client, kind=KIND_SUPPLIER_SEARCH_EXTRA, units=1)
                reserve_job_units(db, client, job)
                evidence_path, _archive_path = self._write_manifests(Path(tmp), combined=False)
                job.evidence_path = str(evidence_path)
                publish_job_result_offer(db, job, kind=CONFIRMATION_KIND_REGISTRY_FALLBACK)
                db.commit()
                accept_job_result_offer(db, job, channel="web")
                job.delivery_expires_at = now_utc() - timedelta(seconds=1)
                db.commit()

                self.assertEqual(expire_result_offers(db), 1)

                operations = self._operations_by_kind(db, job.id)
                self.assertEqual(operations[KIND_SUPPLIER_SEARCH_EXTRA], [OP_RESERVE, OP_RELEASE])
                self.assertNotIn(KIND_SUPPLIER_SEARCH, operations)
        finally:
            db.close()

    def test_additional_offer_decision_expiry_releases_extra_reservation(self) -> None:
        db = self.Session()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                client = Client(id="offer-client-extra-decision-expire", telegram_id="204")
                job = Job(
                    id="offer-job-extra-decision-expire",
                    client_id=client.id,
                    mode="supplier_search",
                    supplier_search_run_type="additional",
                    status="running",
                )
                db.add_all([client, job])
                db.commit()
                grant_package_units(db, client, kind=KIND_SUPPLIER_SEARCH_EXTRA, units=1)
                reserve_job_units(db, client, job)
                evidence_path, _archive_path = self._write_manifests(Path(tmp), combined=False)
                job.evidence_path = str(evidence_path)
                publish_job_result_offer(db, job, kind=CONFIRMATION_KIND_REGISTRY_FALLBACK)
                job.confirmation_expires_at = now_utc() - timedelta(seconds=1)
                db.commit()

                self.assertEqual(expire_result_offers(db), 1)

                operations = self._operations_by_kind(db, job.id)
                self.assertEqual(operations[KIND_SUPPLIER_SEARCH_EXTRA], [OP_RESERVE, OP_RELEASE])
                self.assertNotIn(KIND_SUPPLIER_SEARCH, operations)
        finally:
            db.close()

    def test_combined_decline_releases_supplier_and_exposes_analysis_only(self) -> None:
        db = self.Session()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                client = Client(id="offer-client-2", telegram_id="102")
                job = Job(
                    id="offer-job-2",
                    client_id=client.id,
                    mode="analysis_and_suppliers",
                    status="running",
                    verified_count=4,
                )
                db.add_all([client, job])
                db.commit()
                grant_package_units(db, client, kind=KIND_SUPPLIER_SEARCH, units=1)
                grant_package_units(db, client, kind=KIND_PROCUREMENT_REPORT, units=1)
                reserve_job_units(db, client, job)
                evidence_path, _archive_path = self._write_manifests(Path(tmp), combined=True)
                job.evidence_path = str(evidence_path)
                publish_job_result_offer(db, job, kind=CONFIRMATION_KIND_REGISTRY_FALLBACK)
                db.commit()

                decline_job_result_offer(db, job, channel="telegram")

                self.assertEqual(job.confirmation_outcome, "declined")
                self.assertEqual(job.active_output_manifest, MANIFEST_ANALYSIS_ONLY)
                self.assertEqual(job.status, "completed")
                self.assertEqual([item["kind"] for item in active_result_offer_output_items(job)], ["analysis", "quote_request"])
                self.assertEqual(billing_kinds_for_result_delivery(job), [KIND_PROCUREMENT_REPORT])
                operations = self._operations_by_kind(db, job.id)
                self.assertEqual(operations[KIND_SUPPLIER_SEARCH], [OP_RESERVE, OP_RELEASE])
                self.assertEqual(operations[KIND_PROCUREMENT_REPORT], [OP_RESERVE])
                self.assertNotEqual(job.status, STATUS_CUSTOMER_DECLINED)
        finally:
            db.close()

    def test_accepted_but_undelivered_expires_without_losing_acceptance(self) -> None:
        db = self.Session()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                client = Client(id="offer-client-3", telegram_id="103")
                job = Job(
                    id="offer-job-3",
                    client_id=client.id,
                    mode="supplier_search",
                    status="running",
                    verified_count=2,
                )
                db.add_all([client, job])
                db.commit()
                grant_package_units(db, client, kind=KIND_SUPPLIER_SEARCH, units=1)
                reserve_job_units(db, client, job)
                evidence_path, _archive_path = self._write_manifests(Path(tmp), combined=False)
                job.evidence_path = str(evidence_path)
                publish_job_result_offer(db, job, kind=CONFIRMATION_KIND_REGISTRY_FALLBACK)
                db.commit()
                accept_job_result_offer(db, job, channel="web")
                decided_at = job.confirmation_decided_at
                job.delivery_expires_at = now_utc() - timedelta(seconds=1)
                db.commit()

                self.assertEqual(expire_result_offers(db), 1)
                db.refresh(job)

                self.assertEqual(job.confirmation_outcome, "accepted")
                self.assertEqual(job.confirmation_decided_at, decided_at)
                self.assertEqual(job.offer_delivery_outcome, "expired")
                self.assertEqual(job.status, STATUS_DELIVERY_EXPIRED)
                self.assertEqual(job.result_path, "")
                self.assertEqual(self._operations(db, job.id), [OP_RESERVE, OP_RELEASE])
                payload = result_offer_to_dict(db, job)
                self.assertEqual(payload["decision_outcome"], "accepted")
                self.assertEqual(payload["delivery_outcome"], "expired")
                self.assertFalse(payload["can_accept"])
        finally:
            db.close()

    def test_legacy_expirer_cannot_override_typed_combined_offer(self) -> None:
        db = self.Session()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                client = Client(id="offer-client-legacy-guard", telegram_id="105")
                job = Job(
                    id="offer-job-legacy-guard",
                    client_id=client.id,
                    mode="analysis_and_suppliers",
                    status="running",
                    verified_count=2,
                )
                db.add_all([client, job])
                db.commit()
                grant_package_units(db, client, kind=KIND_SUPPLIER_SEARCH, units=1)
                grant_package_units(db, client, kind=KIND_PROCUREMENT_REPORT, units=1)
                reserve_job_units(db, client, job)
                evidence_path, _archive_path = self._write_manifests(Path(tmp), combined=True)
                job.evidence_path = str(evidence_path)
                publish_job_result_offer(db, job, kind=CONFIRMATION_KIND_REGISTRY_FALLBACK)
                db.commit()
                accept_job_result_offer(db, job, channel="web")
                job.updated_at = now_utc() - timedelta(hours=25)
                job.delivery_expires_at = now_utc() - timedelta(seconds=1)
                db.commit()

                self.assertEqual(expire_stale_confirmations(db, older_than=timedelta(hours=24)), 0)
                db.refresh(job)
                self.assertEqual(job.confirmation_outcome, "accepted")
                self.assertEqual(job.offer_delivery_outcome, "pending")
                self.assertEqual(job.active_output_manifest, MANIFEST_FULL)
                self.assertEqual(self._operations_by_kind(db, job.id)[KIND_PROCUREMENT_REPORT], [OP_RESERVE])

                self.assertEqual(expire_result_offers(db), 1)
                db.refresh(job)
                self.assertEqual(job.confirmation_outcome, "accepted")
                self.assertEqual(job.offer_delivery_outcome, "expired")
                self.assertEqual(job.active_output_manifest, MANIFEST_ANALYSIS_ONLY)
                operations = self._operations_by_kind(db, job.id)
                self.assertEqual(operations[KIND_SUPPLIER_SEARCH], [OP_RESERVE, OP_RELEASE])
                self.assertEqual(operations[KIND_PROCUREMENT_REPORT], [OP_RESERVE])
        finally:
            db.close()

    def test_offer_decision_window_starts_when_offer_is_published(self) -> None:
        db = self.Session()
        try:
            client = Client(id="offer-client-4", telegram_id="104")
            old_created_at = now_utc() - timedelta(days=3)
            job = Job(
                id="offer-job-4",
                client_id=client.id,
                mode="supplier_search",
                status="running",
                created_at=old_created_at,
            )
            db.add_all([client, job])
            db.commit()
            offered_at = now_utc()
            publish_job_result_offer(
                db,
                job,
                kind=CONFIRMATION_KIND_REGISTRY_FALLBACK,
                offered_at=offered_at,
            )
            db.commit()

            stored_offered_at = job.confirmation_offered_at.replace(tzinfo=offered_at.tzinfo)
            stored_expires_at = job.confirmation_expires_at.replace(tzinfo=offered_at.tzinfo)
            stored_created_at = job.created_at.replace(tzinfo=offered_at.tzinfo)
            self.assertEqual(stored_offered_at, offered_at)
            self.assertEqual(stored_expires_at, offered_at + timedelta(hours=24))
            self.assertGreater(stored_expires_at, stored_created_at + timedelta(days=2))
        finally:
            db.close()

    def test_typed_partial_count_delivery_is_not_expired_after_charge(self) -> None:
        db = self.Session()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                result_path = Path(tmp) / "partial.xlsx"
                result_path.write_bytes(b"partial")
                client = Client(id="partial-client", telegram_id="106")
                job = Job(
                    id="partial-job",
                    client_id=client.id,
                    mode="supplier_search",
                    status="running",
                    result_path=str(result_path),
                    verified_count=5,
                )
                db.add_all([client, job])
                db.commit()
                grant_package_units(db, client, kind=KIND_SUPPLIER_SEARCH, units=1)
                reserve_job_units(db, client, job)
                publish_job_result_offer(db, job, kind=CONFIRMATION_KIND_PARTIAL_COUNT)
                db.commit()

                accept_job_result_offer(db, job, channel="telegram")
                token = claim_job_result_offer_delivery(db, job, channel="telegram")
                complete_job_result_offer_delivery(db, job, token, channel="telegram")
                job.delivery_expires_at = now_utc() - timedelta(seconds=1)
                job.updated_at = now_utc() - timedelta(hours=25)
                db.commit()

                self.assertEqual(expire_result_offers(db), 0)
                self.assertEqual(expire_stale_confirmations(db), 0)
                db.refresh(job)
                self.assertEqual(job.status, "partial")
                self.assertEqual(job.confirmation_outcome, "accepted")
                self.assertEqual(job.offer_delivery_outcome, "delivered")
                self.assertEqual(self._operations(db, job.id), [OP_RESERVE, OP_CHARGE])
        finally:
            db.close()

    @staticmethod
    def _write_manifests(root: Path, *, combined: bool) -> tuple[Path, Path]:
        root.mkdir(parents=True, exist_ok=True)
        analysis = root / "analysis.docx"
        suppliers = root / "suppliers.xlsx"
        quote = root / "quote.docx"
        full_archive = root / "full.zip"
        analysis_archive = root / "analysis.zip"
        for path in (analysis, suppliers, quote, full_archive, analysis_archive):
            path.write_bytes(b"result")
        supplier_item = {
            "kind": "suppliers",
            "label": "Поставщики",
            "path": str(suppliers),
            "billing_kind": KIND_SUPPLIER_SEARCH,
        }
        quote_item = {
            "kind": "quote_request",
            "label": "Запрос КП",
            "path": str(quote),
            "billing_kind": KIND_PROCUREMENT_REPORT if combined else KIND_SUPPLIER_SEARCH,
        }
        full_files = [supplier_item, quote_item]
        manifests = {
            "full": {
                "files": full_files,
                "archive_path": str(full_archive),
                "entitlements": [KIND_SUPPLIER_SEARCH],
            }
        }
        if combined:
            analysis_item = {
                "kind": "analysis",
                "label": "Анализ",
                "path": str(analysis),
                "billing_kind": KIND_PROCUREMENT_REPORT,
            }
            full_files.insert(0, analysis_item)
            manifests["full"]["entitlements"] = [KIND_PROCUREMENT_REPORT, KIND_SUPPLIER_SEARCH]
            manifests["analysis_only"] = {
                "files": [analysis_item, quote_item],
                "archive_path": str(analysis_archive),
                "entitlements": [KIND_PROCUREMENT_REPORT],
            }
        evidence_path = root / "evidence.json"
        evidence_path.write_text(json.dumps({"output_manifests": manifests}), encoding="utf-8")
        return evidence_path, full_archive

    @staticmethod
    def _operations(db, job_id: str) -> list[str]:
        return [
            row.operation
            for row in db.query(BillingTransaction)
            .filter(BillingTransaction.job_id == job_id)
            .order_by(BillingTransaction.created_at, BillingTransaction.id)
            .all()
        ]

    @classmethod
    def _operations_by_kind(cls, db, job_id: str) -> dict[str, list[str]]:
        rows = (
            db.query(BillingTransaction)
            .filter(BillingTransaction.job_id == job_id)
            .order_by(BillingTransaction.created_at, BillingTransaction.id)
            .all()
        )
        result: dict[str, list[str]] = {}
        for row in rows:
            result.setdefault(row.kind, []).append(row.operation)
        return result
