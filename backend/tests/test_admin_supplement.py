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
    _clean_customer_job_subject,
    _customer_job_title_for_subject,
    admin_rerun_job,
    customer_job_result_files,
    customer_job_to_dict,
    download_customer_job_file_api,
    download_job_file,
    get_job_supplement_candidates,
    human_job_title,
    job_to_dict,
    upload_admin_supplement,
)
from app.models import Client, Job, JobFile, JobSource, WebUser
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


@pytest.mark.asyncio
async def test_admin_rerun_all_modes(db, tmp_path):
    client = Client(name="Test Company Rerun", telegram_id="999111222")
    db.add(client)
    db.flush()

    modes = ["exact_product", "supplier_search", "procurement_report", "analysis_and_suppliers"]
    for mode in modes:
        job = Job(
            client_id=client.id,
            created_by_telegram_id="999111222",
            mode=mode,
            status="completed",
            title=f"Тестовая задача {mode}",
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        dummy_file = tmp_path / f"input_{mode}.docx"
        dummy_file.write_bytes(b"Dummy input TZ")
        jf = JobFile(
            job_id=job.id,
            original_filename=f"input_{mode}.docx",
            stored_path=str(dummy_file),
            parse_status="parsed",
            extracted_chars=120,
        )
        js = JobSource(
            job_id=job.id,
            kind="procurement_url",
            label="Ссылка",
            value="https://zakupki.gov.ru/test",
            parse_status="parsed",
        )
        db.add(jf)
        db.add(js)
        db.commit()
        db.refresh(job)

        with patch("app.main.enqueue_job") as mock_enqueue:
            res = admin_rerun_job(job_id=job.id, policy=None, db=db)
            assert res["success"] is True
            assert res["job"]["title"] == f"[Админ] Тестовая задача {mode}"
            assert res["job"]["is_admin_rerun"] is True
            assert res["job"]["parent_job_id"] == job.id
            assert res["parent_job_id"] == job.id
            mock_enqueue.assert_called_once_with(res["job"]["id"])

            new_job_record = db.get(Job, res["job"]["id"])
            assert len(new_job_record.files) == 1
            assert new_job_record.files[0].original_filename == f"input_{mode}.docx"
            assert len(new_job_record.sources) == 1
            assert new_job_record.sources[0].value == "https://zakupki.gov.ru/test"

            # Verify the original job was NOT modified or overwritten!
            db.refresh(job)
            assert job.status == "completed"
            assert not job.title.startswith("[Админ]")


@pytest.mark.asyncio
async def test_admin_rerun_supplement_candidates(db, tmp_path):
    client = Client(name="Test Company Candidates", telegram_id="444555666")
    db.add(client)
    db.flush()

    orig_job = Job(
        client_id=client.id,
        created_by_telegram_id="444555666",
        mode="exact_product",
        status="completed",
        title="Шкаф вытяжной химический",
    )
    db.add(orig_job)
    db.commit()
    db.refresh(orig_job)

    out_orig = tmp_path / "orig_out"
    out_orig.mkdir(parents=True, exist_ok=True)
    f_orig = out_orig / "exact_product_orig.docx"
    f_orig.write_bytes(b"Original docx")

    with patch("app.main.package_job_output_items") as mock_pkg:
        # 1. Candidate lookup on original job
        mock_pkg.return_value = [{"kind": "exact_product", "label": "Подбор товара и аналогов", "path": str(f_orig)}]
        res = get_job_supplement_candidates(orig_job.id, db=db)
        assert res["success"] is True
        assert len(res["candidates"]) == 1
        assert res["candidates"][0]["is_admin_rerun"] is False

        # 2. Admin reruns job
        with patch("app.main.enqueue_job"):
            rerun_res = admin_rerun_job(orig_job.id, db=db)
            rerun_id = rerun_res["job"]["id"]

        rerun_job = db.get(Job, rerun_id)
        out_rerun = tmp_path / "rerun_out"
        out_rerun.mkdir(parents=True, exist_ok=True)
        f_rerun = out_rerun / "exact_product_admin.docx"
        f_rerun.write_bytes(b"Admin improved docx")

        def side_effect_pkg(j):
            if j.id == rerun_id:
                return [{"kind": "exact_product", "label": "Подбор товара и аналогов", "path": str(f_rerun)}]
            return [{"kind": "exact_product", "label": "Подбор товара и аналогов", "path": str(f_orig)}]

        mock_pkg.side_effect = side_effect_pkg

        # 3. Candidate lookup on orig_job now sees BOTH rerun and original files
        cand_res = get_job_supplement_candidates(orig_job.id, db=db)
        assert cand_res["success"] is True
        assert len(cand_res["candidates"]) == 2
        rerun_cands = [c for c in cand_res["candidates"] if c["is_admin_rerun"]]
        assert len(rerun_cands) == 1
        assert rerun_cands[0]["job_id"] == rerun_id


def test_exact_product_title_and_human_title(db):
    # Test cleaning subject
    assert _clean_customer_job_subject("Точный товар и аналоги: [Админ] Подбор товара и аналогов") == ""
    assert _clean_customer_job_subject("[Админ] Шкаф вытяжной химический") == "Шкаф вытяжной химический"
    assert _clean_customer_job_subject("ТЗ: Стеклянная магниевая сэндвич-панель.docx") == "Стеклянная магниевая сэндвич-панель"

    # Test title formatting
    assert _customer_job_title_for_subject("exact_product", "Шкаф вытяжной") == "Подбор товаров: Шкаф вытяжной"
    assert _customer_job_title_for_subject("supplier_search", "Шкаф вытяжной") == "ТЗ: Шкаф вытяжной"

    # Test Job human_title
    job = Job(
        mode="exact_product",
        title="Шкаф вытяжной химический",
    )
    assert human_job_title(job) == "Подбор товаров: Шкаф вытяжной химический"

    # Test Admin rerun title
    job_admin = Job(
        mode="exact_product",
        title="[Админ] Шкаф вытяжной химический",
        is_admin_rerun=True,
    )
    assert human_job_title(job_admin) == "[Админ] Подбор товаров: Шкаф вытяжной химический"


def test_admin_rerun_embedded_in_parent_job_to_dict(db, tmp_path):
    client = Client(name="Test Company Embedded", telegram_id="555666777")
    db.add(client)
    db.flush()

    orig_job = Job(
        client_id=client.id,
        created_by_telegram_id="555666777",
        mode="supplier_search",
        status="completed",
        title="Сэндвич-панели",
    )
    db.add(orig_job)
    db.commit()
    db.refresh(orig_job)

    # Initial state: no rerun
    d1 = job_to_dict(orig_job, db=db)
    assert d1["admin_rerun"] is None

    # Trigger admin rerun
    with patch("app.main.enqueue_job"):
        rerun_res = admin_rerun_job(orig_job.id, db=db)
        rerun_id = rerun_res["job"]["id"]

    rerun_job = db.get(Job, rerun_id)
    rerun_job.status = "completed"
    rerun_job.progress = 100
    rerun_job.message = "Завершено"
    rerun_job.yandex_requests_count = 12
    rerun_job.yandex_cost_rub = 0.48
    db.commit()

    # Now parent job_to_dict contains admin_rerun data
    d2 = job_to_dict(orig_job, db=db)
    assert d2["admin_rerun"] is not None
    assert d2["admin_rerun"]["id"] == rerun_id
    assert d2["admin_rerun"]["status"] == "completed"
    assert d2["admin_rerun"]["progress"] == 100
    assert d2["admin_rerun"]["yandex_requests_count"] == 12
    assert d2["admin_rerun"]["yandex_cost_rub"] == 0.48


@pytest.mark.asyncio
async def test_supplement_candidates_recommend_only_latest_healthy_rerun_and_zero_charge_suppresses_offer(db, tmp_path):
    from datetime import datetime, timedelta
    from app.models import BillingTransaction

    client = Client(name="Ольга Тест", telegram_id="web:olga-test", money_balance_kopeks=39600)
    db.add(client)
    db.flush()

    t0 = datetime(2026, 11, 11, 12, 6, 0)
    orig_job = Job(
        client_id=client.id,
        created_by_telegram_id="web:olga-test",
        mode="exact_product",
        status="completed",
        verified_count=1,
        job_number=1074,
        title="Подбор товаров: перчатки нитрил",
        admin_comment=(
            "Здравствуйте! Специалисты TenderLex пересчитали спецификацию: найдено 1 поз. (ранее было 1 поз.). "
            "Готовы выдать дополненный экспертный отчёт. Стоимость доплаты составит 0.0 ₽ с баланса. Подтвердите, пожалуйста, согласие на карточке задачи."
        ),
        created_at=t0,
    )
    db.add(orig_job)
    db.flush()

    db.add(
        BillingTransaction(
            client_id=client.id,
            job_id=orig_job.id,
            kind="exact_product",
            operation="charge",
            units=1,
            amount_kopeks=9900,
            note="Подбор товаров: подобрано 1 из 5 поз. по 99.00 ₽",
        )
    )

    broken_rerun = Job(
        client_id=client.id,
        parent_job_id=orig_job.id,
        is_admin_rerun=True,
        created_by_telegram_id="web:olga-test",
        mode="exact_product",
        status="completed",
        verified_count=0,
        job_number=1078,
        title="[Админ] Подбор товаров: перчатки нитрил",
        created_at=t0 + timedelta(hours=1),
    )
    good_rerun = Job(
        client_id=client.id,
        parent_job_id=orig_job.id,
        is_admin_rerun=True,
        created_by_telegram_id="web:olga-test",
        mode="exact_product",
        status="completed",
        verified_count=1,
        job_number=1079,
        title="[Админ] Подбор товаров: перчатки нитрил",
        created_at=t0 + timedelta(hours=9),
    )
    db.add_all([broken_rerun, good_rerun])
    db.commit()

    f_orig = tmp_path / "orig.docx"
    f_broken = tmp_path / "broken_admin.docx"
    f_good = tmp_path / "good_admin.docx"
    f_orig.write_bytes(b"orig")
    f_broken.write_bytes(b"broken")
    f_good.write_bytes(b"good")

    def fake_pkg(j):
        if j.id == good_rerun.id:
            return [{"kind": "exact_product", "label": "Подбор товара и аналоги", "path": str(f_good)}]
        if j.id == broken_rerun.id:
            return [{"kind": "exact_product", "label": "Подбор товара и аналоги", "path": str(f_broken)}]
        return [{"kind": "exact_product", "label": "Подбор товара и аналоги", "path": str(f_orig)}]

    with patch("app.main.package_job_output_items", side_effect=fake_pkg):
        res = get_job_supplement_candidates(orig_job.id, db=db)

    cands_by_jid = {c["job_id"]: c for c in res["candidates"]}
    assert cands_by_jid[good_rerun.id]["is_recommended"] is True
    assert cands_by_jid[good_rerun.id]["is_empty_result"] is False
    assert cands_by_jid[broken_rerun.id]["is_recommended"] is False
    assert cands_by_jid[broken_rerun.id]["is_empty_result"] is True
    assert cands_by_jid[orig_job.id]["is_recommended"] is False

    prev = res["offer_preview"]
    assert prev["charge_amount_rub"] == 0.0
    assert prev["already_charged_rub"] == 99.0
    assert prev["requires_payment_approval"] is False
    assert prev["default_offer_comment"] == ""

    # Even if a stale caller submits as_offer=True with a 0.0 ₽ comment, publish cleanly without awaiting payment confirmation
    with patch("app.main.package_job_output_items", side_effect=fake_pkg):
        pub_res = await upload_admin_supplement(
            job_id=orig_job.id,
            comment=(
                "Здравствуйте! Специалисты TenderLex пересчитали спецификацию: найдено 1 поз. (ранее было 1 поз.). "
                "Готовы выдать дополненный экспертный отчёт. Стоимость доплаты составит 0.0 ₽ с баланса. Подтвердите, пожалуйста, согласие на карточке задачи."
            ),
            notify_telegram=False,
            source_mode="job_file",
            file_kinds=f"{good_rerun.id}:exact_product",
            as_offer=True,
            offer_charge_rub=0.0,
            db=db,
        )
    assert pub_res["success"] is True
    db.refresh(orig_job)
    assert orig_job.status == "completed"
    assert "0.0 ₽" not in (orig_job.admin_comment or "")





