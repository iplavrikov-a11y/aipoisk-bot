import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch, MagicMock

import httpx

from app.billing import (
    KIND_EXACT_PRODUCT,
    MODE_EXACT_PRODUCT,
    requested_billing_units,
    effective_price_kopeks,
)
from app.exact_product import (
    ExactProductPosition,
    ExactProductReport,
    GispRegistryMatch,
    SpecParameterMatch,
    AlternativeProduct,
    find_minprom_gisp_match,
    write_exact_product_docx,
    write_exact_product_xlsx,
    analyze_exact_product,
    fetch_web_or_pdf_document,
)
from app.models import SystemSettings


def test_billing_units_and_pricing_for_exact_product():
    units = requested_billing_units(MODE_EXACT_PRODUCT)
    assert units[KIND_EXACT_PRODUCT] == 1

    price = effective_price_kopeks(None, None, KIND_EXACT_PRODUCT)
    assert price == 9900  # 99 rubles default


def test_gisp_registry_search_live_or_fallback():
    match = find_minprom_gisp_match("Диск щеточный беспроставочный", manufacturer="Профмаркет")
    if match:
        assert isinstance(match, GispRegistryMatch)
        assert match.registry_number or match.product


@pytest.mark.asyncio
async def test_fetch_web_or_pdf_document_html():
    html_content = """
    <html>
        <head><title>Паспорт насоса КМ 80-65-160 | Завод Энергомаш</title></head>
        <body>
            <h1>Технические характеристики консольного насоса КМ 80-65-160</h1>
            <table>
                <tr><th>Параметр</th><th>Значение</th></tr>
                <tr><td>Подача</td><td>50 м3/ч</td></tr>
                <tr><td>Напор</td><td>32 м</td></tr>
                <tr><td>Мощность электродвигателя</td><td>7.5 кВт</td></tr>
            </table>
        </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "text/html; charset=utf-8"}
    mock_resp.url = httpx.URL("https://energomash.ru/nasos-km-80-65-160")
    mock_resp.text = html_content

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    res = await fetch_web_or_pdf_document(mock_client, "https://energomash.ru/nasos-km-80-65-160")
    assert res is not None
    assert res["type"] == "html"
    assert "ТАБЛИЦА ТЕХНИЧЕСКИХ ХАРАКТЕРИСТИК" in res["text"]
    assert "Подача | 50 м3/ч" in res["text"]
    assert "7.5 кВт" in res["text"]


@pytest.mark.asyncio
async def test_fetch_web_or_pdf_document_pdf():
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "PASSPORT: Control Valve KR-50. Pressure 1.6 MPa. Temp 150 C.")
    pdf_bytes = doc.write()
    doc.close()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/pdf"}
    mock_resp.url = httpx.URL("https://zavod-armatury.ru/docs/pasport-kr-50.pdf")
    mock_resp.content = pdf_bytes

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    res = await fetch_web_or_pdf_document(mock_client, "https://zavod-armatury.ru/docs/pasport-kr-50.pdf")
    assert res is not None
    assert res["type"] == "pdf"
    assert "PASSPORT" in res["text"]
    assert "Control Valve" in res["text"]


def test_docx_and_xlsx_generation():
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        docx_dest = tmp_path / "Форма_2_Тест.docx"
        xlsx_dest = tmp_path / "Таблица_Аналогов.xlsx"

        param1 = SpecParameterMatch(
            param_name="Внутренний диаметр",
            tz_requirement="не менее 128 мм",
            product_fact="128 мм",
            status="match",
            comment="Полное соответствие ГОСТ",
            source_url="https://profmarket.ru/disk-128",
        )
        param2 = SpecParameterMatch(
            param_name="Материал ворса",
            tz_requirement="полипропилен морозостойкий",
            product_fact="первичный блок-сополимер пропилена",
            status="match",
            comment="Соответствует ТУ завода",
            source_url="https://profmarket.ru/disk-128",
        )
        param_unverified = SpecParameterMatch(
            param_name="Температура эксплуатации",
            tz_requirement="от -45 до +50 С",
            product_fact="В открытой документации не указано (требуется официальный паспорт завода)",
            status="clarify",
            comment="Параметр не подтвержден открытым паспортом завода",
        )

        alt_param1 = SpecParameterMatch(
            param_name="Внутренний диаметр",
            tz_requirement="не менее 128 мм",
            product_fact="128 мм",
            status="match",
            comment="Соответствует ТЗ",
        )
        alt_param2 = SpecParameterMatch(
            param_name="Материал ворса",
            tz_requirement="полипропилен морозостойкий",
            product_fact="полипропилен первичный",
            status="match",
            comment="Эквивалентный материал",
        )

        alt1 = AlternativeProduct(
            brand="Коминвест-АКМТ",
            model="Диск 128х550",
            manufacturer="АО Коминвест-АКМТ",
            confidence=0.95,
            notes="В наличии на складе в РФ, дешевле оригинала на ~12%",
            specs_breakdown=[alt_param1, alt_param2],
            source_url="https://kominvest.ru/catalog/diski",
        )

        gisp = GispRegistryMatch(
            registry_number="10855742",
            manufacturer="ООО «ПК Профмаркет»",
            product="Диск щеточный полипропиленовый беспроставочный",
            inn="7701234567",
        )

        pos = ExactProductPosition(
            position_no=1,
            name_in_tz="Диск щеточный 128х550 полипропиленовый",
            identified_brand="ПК Профмаркет",
            identified_model="Диск щеточный беспроставочный (билайн) 128х550",
            manufacturer="ООО «ПК Профмаркет»",
            confidence=0.98,
            reasoning="По геометрическим размерам посадочного кольца и типу замка «зигзаг» ТЗ скопировано с ТУ ПК Профмаркет.",
            specs_breakdown=[param1, param2, param_unverified],
            gisp_match=gisp,
            alternative_brands=[alt1],
            source_url="https://profmarket.ru/disk-128",
        )

        report = ExactProductReport(
            procurement_title="Поставка щеточных дисков для уборочной техники",
            total_positions=1,
            positions=[pos],
            summary="Выявлен 1 конкретный товар, ТЗ составлено под ПК Профмаркет с вероятностью 98%.",
            web_sources=["profmarket.ru", "kominvest.ru"],
            verified_documents=[
                {"title": "Паспорт диска щеточного ПК Профмаркет", "url": "https://profmarket.ru/docs/pasport.pdf", "type": "pdf"},
                {"title": "Каталог уборочных дисков Коминвест", "url": "https://kominvest.ru/catalog/diski", "type": "html"},
            ],
        )

        assert report.total_positions == 1

        # Check export to DOCX
        written_docx = write_exact_product_docx(docx_dest, report, title="Форма 2: Сведения о качестве")
        assert written_docx.exists()
        assert written_docx.stat().st_size > 1000

        # Check export to XLSX
        written_xlsx = write_exact_product_xlsx(xlsx_dest, report, title="Конкретные показатели и аналоги")
        assert written_xlsx.exists()
        assert written_xlsx.stat().st_size > 1000


@pytest.mark.asyncio
async def test_analyze_exact_product_pipeline_strict_grounding():
    mock_llm_response = json.dumps({
        "summary": "ТЗ скопировано под модель ПК Профмаркет",
        "positions": [
            {
                "position_no": 1,
                "name_in_tz": "Диск щеточный",
                "identified_brand": "ПК Профмаркет",
                "identified_model": "Диск 128х550",
                "manufacturer": "ООО «ПК Профмаркет»",
                "confidence": 0.95,
                "reasoning": "Совпадение по ТУ",
                "source_url": "https://profmarket.ru/disk-128",
                "specs_breakdown": [
                    {
                        "param_name": "Диаметр",
                        "tz_requirement": "128 мм",
                        "product_fact": "128 мм",
                        "status": "match",
                        "comment": "Подтверждено паспортом",
                    },
                    {
                        "param_name": "Масса одного диска",
                        "tz_requirement": "не более 0.85 кг",
                        "product_fact": "В открытой документации не указано (требуется официальный паспорт завода)",
                        "status": "clarify",
                        "comment": "Параметр не найден в открытом паспорте",
                    },
                ],
                "alternative_brands": [
                    {
                        "brand": "Коминвест",
                        "model": "Щетка-диск",
                        "manufacturer": "Коминвест",
                        "confidence": 0.90,
                        "notes": "В наличии",
                        "specs_breakdown": [
                            {
                                "param_name": "Диаметр",
                                "tz_requirement": "128 мм",
                                "product_fact": "128 мм",
                                "status": "match",
                                "comment": "Аналог соответствует",
                            }
                        ],
                    }
                ],
            }
        ]
    })

    settings = SystemSettings()
    with patch("app.exact_product.call_llm", AsyncMock(return_value=mock_llm_response)):
        report = await analyze_exact_product(settings, "Техническое задание на поставку дисков 128 мм")
        assert report.total_positions == 1
        assert report.positions[0].identified_brand == "ПК Профмаркет"
        assert report.positions[0].specs_breakdown[0].param_name == "Диаметр"
        assert report.positions[0].specs_breakdown[0].status == "match"
        assert report.positions[0].specs_breakdown[1].status == "clarify"
        assert "В открытой документации не указано" in report.positions[0].specs_breakdown[1].product_fact
        assert len(report.positions[0].alternative_brands[0].specs_breakdown) == 1


def test_process_exact_product_worker():
    from app.models import Client, Job, SystemSettings, Base
    from app.jobs import _process_exact_product
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_engine(f"sqlite:///{tmpdir}/test.db")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()

        client = Client(id="client-worker", telegram_id="12345", name="Тест", is_active=True, money_balance_kopeks=10000)
        job = Job(id="job-worker-exact", client_id=client.id, mode="exact_product", status="running", progress=10)
        settings = SystemSettings()
        db.add_all([client, job, settings])
        db.commit()

        mock_llm_response = json.dumps({
            "total_positions": 1,
            "summary": "Тест",
            "positions": [
                {
                    "name_in_tz": "Диск 128",
                    "identified_brand": "ПК Профмаркет",
                    "identified_model": "Диск 128х550",
                    "manufacturer": "ООО ПК Профмаркет",
                    "confidence": 0.95,
                    "reasoning": "ТУ",
                    "specs_breakdown": [],
                    "alternative_brands": []
                }
            ]
        })

        with patch("app.exact_product.call_llm", AsyncMock(return_value=mock_llm_response)), \
             patch("app.jobs.job_dir", return_value=Path(tmpdir)):
            _process_exact_product(db, job, settings, "Тестовое ТЗ")
            assert job.status == "completed"
            assert job.progress == 100
            assert Path(job.result_path).exists()
            assert Path(job.evidence_path).exists()
