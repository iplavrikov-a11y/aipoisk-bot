import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.main import (
    customer_job_result_files,
    customer_job_to_dict,
    download_customer_job_file_api,
    download_job_file,
    job_to_dict,
    upload_admin_supplement,
)
from app.models import Client, Job, WebUser
from app.web_auth import WebAuthContext


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.mark.asyncio
async def test_admin_supplement_workflow(db):
    client = Client(name="Test Company", telegram_id="999888777")
    db.add(client)
    db.flush()

    user = WebUser(
        client_id=client.id,
        email="client@example.com",
        password_hash="hash",
        is_email_verified=True,
    )
    db.add(user)
    db.flush()

    job = Job(
        client_id=client.id,
        created_by_telegram_id="999888777",
        mode="supplier_search",
        status="completed",
        title="Шкаф вытяжной химический",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 1. Upload admin supplement
    comment_text = "Вручную нашли 5 прямых заводов-производителей."
    file_bytes = b"Mock XLSX content for supplementary suppliers"

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
        tf.write(file_bytes)
        tf_path = Path(tf.name)

    try:
        with tf_path.open("rb") as f:
            upload_file = UploadFile(file=f, filename="extended_suppliers.xlsx")

            with patch("app.bot.send_admin_supplement_telegram", new_callable=AsyncMock) as mock_tg:
                mock_tg.return_value = True

                res = await upload_admin_supplement(
                    job_id=job.id,
                    file=upload_file,
                    comment=comment_text,
                    notify_telegram=True,
                    db=db,
                )

                assert res["success"] is True
                assert res["telegram_notified"] is True
                assert res["job"]["has_admin_supplement"] is True
                assert res["job"]["admin_comment"] == comment_text
                assert res["job"]["admin_supplement_name"] == "extended_suppliers.xlsx"
                assert any(f["kind"] == "admin_supplement" for f in res["job"]["result_files"])

        # 2. Check customer serialization
        db.refresh(job)
        cust_dict = customer_job_to_dict(job, db=db)
        assert cust_dict["has_admin_supplement"] is True
        assert cust_dict["admin_comment"] == comment_text
        assert cust_dict["admin_supplement_name"] == "extended_suppliers.xlsx"

        cust_files = customer_job_result_files(job)
        assert any(f["kind"] == "admin_supplement" and f["filename"] == "extended_suppliers.xlsx" for f in cust_files)

        # 3. Test customer download
        auth_context = WebAuthContext(
            user=user,
            session=None,
        )

        response = download_customer_job_file_api(
            job_id=job.id,
            file_kind="admin_supplement",
            context=auth_context,
            db=db,
        )
        assert response.filename == "extended_suppliers.xlsx"
        assert Path(response.path).read_bytes() == file_bytes

        # 4. Test admin download
        admin_response = download_job_file(
            job_id=job.id,
            file_kind="admin_supplement",
            db=db,
        )
        assert admin_response.filename == "extended_suppliers.xlsx"
        assert Path(admin_response.path).read_bytes() == file_bytes

    finally:
        if tf_path.exists():
            tf_path.unlink()
        if job.admin_supplement_path and Path(job.admin_supplement_path).exists():
            try:
                Path(job.admin_supplement_path).unlink()
            except Exception:
                pass


@pytest.mark.asyncio
async def test_admin_supplement_from_existing_job_result(db, tmp_path):
    client = Client(name="Test Company 2", telegram_id="111222333")
    db.add(client)
    db.flush()

    job = Job(
        client_id=client.id,
        created_by_telegram_id="111222333",
        mode="supplier_search",
        status="completed",
        title="Сэндвич-панель для чистых помещений",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Create dummy output file in job evidence/output
    out_dir = tmp_path / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    supplier_file = out_dir / "suppliers_sandwich.xlsx"
    supplier_file.write_bytes(b"Fresh suppliers from rerun")

    mock_items = [{"kind": "suppliers", "label": "Поставщики", "path": str(supplier_file)}]

    with patch("app.main.package_job_output_items", return_value=mock_items):
        with patch("app.bot.send_admin_supplement_telegram", new_callable=AsyncMock) as mock_tg:
            mock_tg.return_value = True

            res = await upload_admin_supplement(
                job_id=job.id,
                file=None,
                comment="Автоматический комментарий эксперта.",
                notify_telegram=True,
                source_mode="job_file",
                file_kind="suppliers",
                db=db,
            )

            assert res["success"] is True
            assert res["job"]["has_admin_supplement"] is True
            assert res["job"]["admin_supplement_name"] == "suppliers_sandwich.xlsx"
            assert res["job"]["admin_comment"] == "Автоматический комментарий эксперта."
            db.refresh(job)
            assert Path(job.admin_supplement_path).read_bytes() == b"Fresh suppliers from rerun"


@pytest.mark.asyncio
async def test_admin_supplement_multi_files(db, tmp_path):
    client = Client(name="Test Company 3", telegram_id="555666777")
    db.add(client)
    db.flush()

    job = Job(
        client_id=client.id,
        created_by_telegram_id="555666777",
        mode="supplier_search",
        status="completed",
        title="Стеклянная магниевая сэндвич-панель",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    out_dir = tmp_path / "output2"
    out_dir.mkdir(parents=True, exist_ok=True)
    f1 = out_dir / "suppliers.xlsx"
    f1.write_bytes(b"File 1 XLSX content")
    f2 = out_dir / "quote_request.docx"
    f2.write_bytes(b"File 2 DOCX content")

    mock_items = [
        {"kind": "suppliers", "label": "Поставщики", "path": str(f1)},
        {"kind": "quote_request", "label": "Запрос КП", "path": str(f2)},
    ]

    with patch("app.main.package_job_output_items", return_value=mock_items):
        with patch("app.bot.send_admin_supplement_telegram", new_callable=AsyncMock) as mock_tg:
            mock_tg.return_value = True

            res = await upload_admin_supplement(
                job_id=job.id,
                file=None,
                comment="Отправляем оба отчета: поставщиков и запрос КП.",
                notify_telegram=True,
                source_mode="job_file",
                file_kinds="suppliers,quote_request",
                db=db,
            )

            assert res["success"] is True
            assert res["job"]["has_admin_supplement"] is True
            assert "suppliers.xlsx" in res["job"]["admin_supplement_name"]
            assert "quote_request.docx" in res["job"]["admin_supplement_name"]

            db.refresh(job)
            cust_files = customer_job_result_files(job)
            admin_supps = [f for f in cust_files if f.get("is_admin_supplement")]
            assert len(admin_supps) == 2
            assert any(f["kind"] == "admin_supplement_0" and f["filename"] == "suppliers.xlsx" for f in admin_supps)
            assert any(f["kind"] == "admin_supplement_1" and f["filename"] == "quote_request.docx" for f in admin_supps)


