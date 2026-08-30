import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import (
    Client,
    Job,
    JobFile,
    SystemSettings,
    TariffPackage,
    WebUser,
    BillingTransaction,
)
from app.billing import KIND_SUPPLIER_SEARCH, OP_RESERVE
from app.web_auth import WebAuthContext
import app.jobs as jobs
import app.main as main_module
from app.main import (
    MODE_EXACT_PRODUCT,
    MODE_SUPPLIER_SEARCH,
    customer_job_to_dict,
    job_can_start_supplier_search,
    _customer_exact_product_summary,
    create_supplier_search_from_exact_product,
)


class TestExactToSupplierSearch(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self):
        Base.metadata.drop_all(self.engine)

    def test_job_can_start_supplier_search(self):
        job_done = MagicMock(mode=MODE_EXACT_PRODUCT, status="completed", error="")
        self.assertTrue(job_can_start_supplier_search(job_done))

        job_running = MagicMock(mode=MODE_EXACT_PRODUCT, status="running", error="")
        self.assertFalse(job_can_start_supplier_search(job_running))

        job_other_mode = MagicMock(mode=MODE_SUPPLIER_SEARCH, status="completed", error="")
        self.assertFalse(job_can_start_supplier_search(job_other_mode))

        job_error = MagicMock(mode=MODE_EXACT_PRODUCT, status="completed", error="Failed")
        self.assertFalse(job_can_start_supplier_search(job_error))

    def test_customer_exact_product_summary(self):
        from app.config import config
        orig_storage_dir = config.storage_dir
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config.storage_dir = str(temp_path)
            try:
                evidence_file = temp_path / "evidence.json"
                report_data = {
                    "exact_product_report": {
                        "positions": [
                            {
                                "position_no": 1,
                                "name_in_tz": "Клапан седельный",
                                "identified_brand": "Broen",
                                "identified_model": "Clorius M1F",
                                "manufacturer": "Broen A/S",
                                "alternative_brands": [
                                    {"brand": "Danfoss", "model": "VFM-2", "manufacturer": "Danfoss"},
                                    {"brand": "Теплосила", "model": "ТРВ-50", "manufacturer": "ЗАО Теплосила"},
                                ],
                            }
                        ]
                    }
                }
                evidence_file.write_text(json.dumps(report_data, ensure_ascii=False), encoding="utf-8")

                job = MagicMock(evidence_path=str(evidence_file))
                summary = _customer_exact_product_summary(job)
                self.assertIsNotNone(summary)
                self.assertEqual(summary["primary_product"], "Broen A/S Broen Clorius M1F")
                self.assertEqual(len(summary["alternatives"]), 2)
                self.assertIn("Danfoss Danfoss VFM-2", summary["alternatives"])
                self.assertIn("ЗАО Теплосила Теплосила ТРВ-50", summary["alternatives"])
            finally:
                config.storage_dir = orig_storage_dir

    def test_create_supplier_search_from_exact_product_success(self):
        from app.config import config
        orig_storage_dir = config.storage_dir
        original_job_dir = jobs.job_dir
        original_enqueue = main_module.enqueue_job
        db = self.Session()

        try:
            with TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                config.storage_dir = str(temp_path)
                jobs.job_dir = lambda _id: temp_path / "jobs" / _id
                main_module.enqueue_job = MagicMock()

                db.add(SystemSettings(id=1, default_supplier_target=10))
                db.add(TariffPackage(kind=KIND_SUPPLIER_SEARCH, name="Поиск поставщиков", units=1, price_kopeks=5000, is_active=True))
                client = Client(id="client-1", telegram_id="web:client-1", monthly_supplier_search_limit=5, money_balance_kopeks=10000)
                user = WebUser(id="user-1", client_id="client-1", email="test@tenderlex.ru", is_email_verified=True, password_hash="hash")
                db.add_all([client, user])
                db.commit()

                # Create original completed exact product job
                orig_dir = temp_path / "jobs" / "exact-job-1"
                orig_dir.mkdir(parents=True, exist_ok=True)
                orig_files_dir = orig_dir / "files"
                orig_files_dir.mkdir(parents=True, exist_ok=True)
                input_doc = orig_files_dir / "tz_doc.pdf"
                input_doc.write_bytes(b"Dummy PDF Specification Content")

                evidence_file = orig_dir / "output" / "evidence.json"
                evidence_file.parent.mkdir(parents=True, exist_ok=True)
                evidence_file.write_text(
                    json.dumps(
                        {
                            "subject": "Клапан регулирующий",
                            "exact_product_report": {
                                "positions": [
                                    {
                                        "position_no": 1,
                                        "name_in_tz": "Клапан",
                                        "identified_brand": "Broen",
                                        "identified_model": "Clorius",
                                        "manufacturer": "Broen",
                                        "alternative_brands": [
                                            {"brand": "Danfoss", "model": "VFM", "manufacturer": "Danfoss"}
                                        ],
                                    }
                                ]
                            },
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                original_job = Job(
                    id="exact-job-1",
                    client_id=client.id,
                    mode=MODE_EXACT_PRODUCT,
                    title="Техническое задание на клапан",
                    status="completed",
                    evidence_path=str(evidence_file),
                )
                db.add(original_job)
                db.commit()

                orig_job_file = JobFile(
                    id="file-1",
                    job_id=original_job.id,
                    original_filename="tz_doc.pdf",
                    stored_path=str(input_doc),
                )
                db.add(orig_job_file)
                db.commit()

                new_job = create_supplier_search_from_exact_product(
                    db,
                    client=client,
                    original_job=original_job,
                    created_by_telegram_id="web:user-1",
                    supplier_search_policy="normal",
                    include_alternatives=True,
                    additional_prompt="Только оптовые поставщики со складом в РФ",
                )

                self.assertIsNotNone(new_job)
                self.assertEqual(new_job.mode, MODE_SUPPLIER_SEARCH)
                self.assertTrue(new_job.title.startswith("Поставщики: "))
                self.assertEqual(new_job.client_id, client.id)

                # Check billing reservation
                reserve = (
                    db.query(BillingTransaction)
                    .filter(BillingTransaction.job_id == new_job.id)
                    .filter(BillingTransaction.operation == OP_RESERVE)
                    .one()
                )
                self.assertEqual(reserve.kind, KIND_SUPPLIER_SEARCH)
                self.assertEqual(reserve.units, 1)

                # Check that selection file and original file are present in new job
                new_files = new_job.files
                self.assertEqual(len(new_files), 2)
                filenames = [f.original_filename for f in new_files]
                self.assertIn("podbor_tovara_i_analogi_rezultat.txt", filenames)
                self.assertIn("tz_doc.pdf", filenames)

                # Check content of selection file
                sel_file = next(f for f in new_files if f.original_filename == "podbor_tovara_i_analogi_rezultat.txt")
                sel_text = Path(sel_file.stored_path).read_text(encoding="utf-8")
                self.assertIn("Broen Clorius", sel_text)
                self.assertIn("Danfoss VFM", sel_text)
                self.assertIn("Только оптовые поставщики со складом в РФ", sel_text)

                main_module.enqueue_job.assert_called_once_with(new_job.id)
        finally:
            config.storage_dir = orig_storage_dir
            jobs.job_dir = original_job_dir
            main_module.enqueue_job = original_enqueue
            db.close()

    def test_create_supplier_search_insufficient_balance(self):
        db = self.Session()
        try:
            db.add(SystemSettings(id=1, default_supplier_target=10))
            client = Client(id="client-2", telegram_id="web:client-2", monthly_supplier_search_limit=0, money_balance_kopeks=0)
            db.add(client)
            db.commit()

            original_job = Job(
                id="exact-job-2",
                client_id=client.id,
                mode=MODE_EXACT_PRODUCT,
                title="Подбор товара",
                status="completed",
            )
            db.add(original_job)
            db.commit()

            with self.assertRaises(HTTPException) as ctx:
                create_supplier_search_from_exact_product(
                    db,
                    client=client,
                    original_job=original_job,
                    created_by_telegram_id="web:user-2",
                )
            self.assertEqual(ctx.exception.status_code, 403)
        finally:
            db.close()
