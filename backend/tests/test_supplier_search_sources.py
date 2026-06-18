from __future__ import annotations

import base64
import unittest
from types import SimpleNamespace

from app.supplier_search import (
    Candidate,
    _accepted_supplier_results,
    _best_product_label,
    _clean_supplier_queries,
    _deterministic_queries,
    _ddgs_search_queries,
    _expand_search_queries,
    _exact_match_terms,
    html_text_to_page,
    _merge_candidates,
    _parse_google_items,
    _parse_yandex_xml,
    _provider_order,
    _product_phrases,
    assess_candidate_match,
    extract_company_name,
)


class SearchSourceTests(unittest.TestCase):
    def test_provider_order_defaults_to_yandex_google_then_auxiliary_sources(self) -> None:
        settings = SimpleNamespace(supplier_search_provider_order="")

        self.assertEqual(_provider_order(settings), ["yandex", "google", "tavily", "ddgs"])

    def test_html_text_to_page_extracts_mailto_and_tel_links(self) -> None:
        page = html_text_to_page(
            """
            <html><body>
              <h1>Поставщик оборудования</h1>
              <p>Каталог промышленного оборудования и отдел продаж.</p>
              <a href="mailto:sales@supplier.example">Email</a>
              <a href="tel:+79991112233">Phone</a>
            </body></html>
            """,
            "https://supplier.example",
        )

        self.assertIsNotNone(page)
        assert page is not None
        self.assertIn("sales@supplier.example", page["text"])
        self.assertIn("+79991112233", page["text"])

    def test_provider_order_accepts_custom_supported_order(self) -> None:
        settings = SimpleNamespace(supplier_search_provider_order="google,unknown,yandex,ddgs")

        self.assertEqual(_provider_order(settings), ["google", "yandex", "ddgs"])

    def test_parse_yandex_xml_builds_candidates_and_filters_blocked_domains(self) -> None:
        xml = """
        <yandexsearch>
          <response>
            <results>
              <grouping>
                <group>
                  <doc>
                    <url>https://spaszavod.ru/catalog</url>
                    <title>Спасательный завод</title>
                    <passages><passage>горноспасательное оборудование</passage></passages>
                  </doc>
                </group>
                <group>
                  <doc>
                    <url>https://market.yandex.ru/product/1</url>
                    <title>Маркет</title>
                  </doc>
                </group>
              </grouping>
            </results>
          </response>
        </yandexsearch>
        """

        candidates = _parse_yandex_xml(xml, query="горноспасательное оборудование")

        self.assertEqual([item.domain for item in candidates], ["spaszavod.ru"])
        self.assertEqual(candidates[0].source, "yandex")
        self.assertEqual(candidates[0].query, "горноспасательное оборудование")

    def test_parse_yandex_xml_accepts_base64_raw_data(self) -> None:
        raw = "<yandexsearch><response><results><grouping><group><doc><url>https://techspas.ru/</url><title>Techspas</title></doc></group></grouping></results></response></yandexsearch>"
        encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")

        candidates = _parse_yandex_xml(encoded, query="test")

        self.assertEqual([item.domain for item in candidates], ["techspas.ru"])

    def test_parse_google_items_builds_candidates_and_filters_blocked_domains(self) -> None:
        candidates = _parse_google_items(
            [
                {
                    "link": "https://npopuls.ru/catalog/gm-70",
                    "title": "НПО Пульс",
                    "snippet": "пожарная арматура",
                },
                {
                    "link": "https://zakupki.gov.ru/notice/1",
                    "title": "Закупка",
                    "snippet": "",
                },
            ],
            query="ГМ-70",
        )

        self.assertEqual([item.domain for item in candidates], ["npopuls.ru"])
        self.assertEqual(candidates[0].source, "google")
        self.assertEqual(candidates[0].query, "ГМ-70")

    def test_merge_candidates_keeps_first_domain_source(self) -> None:
        first = _parse_google_items(
            [{"link": "https://npopuls.ru/a", "title": "first", "snippet": ""}],
            query="first",
        )
        second = _parse_google_items(
            [{"link": "https://www.npopuls.ru/b", "title": "second", "snippet": ""}],
            query="second",
        )

        merged = _merge_candidates(first, second, max_results=10)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].title, "first")

    def test_expand_search_queries_interleaves_base_queries_before_variants(self) -> None:
        long_query = '"Приспособление для промежуточного подсоединения пожарных рукавов к трубопроводу (Сверло шахтное универсальное)" поставщик'
        expanded = _expand_search_queries(
            [
                long_query,
                '"СШУ-22" купить',
                "горноспасательное оборудование завод поставщик купить",
            ],
            max_queries=5,
        )

        self.assertIn('"СШУ-22" купить', expanded[:3])
        self.assertIn("горноспасательное оборудование завод поставщик купить", expanded[:3])

    def test_deterministic_queries_drop_generic_ocr_and_contract_phrases(self) -> None:
        context = """
        ТЕХНИЧЕСКОЕ ЗАДАНИЕ
        Система контроля бортовых и наземных кабельных изделий.
        1 | далее - Оборудование | OF-24 | PAGE-1
        Проверка проводится с использованием двух проводов и с использованием четырех проводов.
        Требуется автоматизированная измерительная система контроля жгутов ТЕСТ-9110 по ОСТ 92-0320-68.
        """

        queries = _deterministic_queries(context)
        joined = "\n".join(queries).lower()

        self.assertNotIn("далее - оборудование", joined)
        self.assertNotIn("page-1", joined)
        self.assertNotIn("of-24", joined)
        self.assertNotIn("ост-92", joined)
        self.assertNotIn("с использованием двух проводов", joined)
        self.assertIn("система контроля бортовых", joined)
        self.assertIn("тест-9110", joined)

    def test_clean_supplier_queries_filters_ai_generated_generic_queries(self) -> None:
        queries = _clean_supplier_queries(
            [
                '"далее - Оборудование" поставщик',
                '"PAGE-1" купить цена',
                '"OF-24" поставщик официальный сайт',
                "система контроля кабельных изделий ТЕСТ-9110 купить",
            ]
        )

        self.assertEqual(queries, ["система контроля кабельных изделий ТЕСТ-9110 купить"])

    def test_deterministic_queries_skip_generic_fallback_when_product_phrase_exists(self) -> None:
        context = """
        Установка скрайбирования и скалывания | Установка скрайбирования и скалывания | Производитель
        функциональные характеристики потребительские свойства эксплуатационные характеристики товара
        """

        queries = _deterministic_queries(context)
        joined = "\n".join(queries).lower()

        self.assertIn('"установка скрайбирования и скалывания" поставщик', joined)
        self.assertNotIn("потребительские свойства", joined)

    def test_deterministic_queries_do_not_infer_fire_hose_from_generic_pipeline_word(self) -> None:
        context = """
        На поставку газорегуляторного пункта блочного.
        Газорегуляторный пункт подключается к газовому трубопроводу.
        Комплектация: фильтр газовый ФГ-100; термоманометр ТМ-16; модем GSM-900; шкаф КУ-701; гидротолкатель ТЭГ-25.
        """

        queries = _deterministic_queries(context)
        joined = "\n".join(queries).lower()

        self.assertIn("газорегуляторного пункта блочного", joined)
        self.assertNotIn("фг-100", joined)
        self.assertNotIn("тм-16", joined)
        self.assertNotIn("gsm-900", joined)
        self.assertNotIn("ку-701", joined)
        self.assertNotIn("тэг-25", joined)
        self.assertNotIn("пожарных рукавов", joined)
        self.assertNotIn("врезки в трубопровод", joined)

    def test_deterministic_queries_do_not_add_mine_rescue_queries_for_wagonet_pushers(self) -> None:
        context = """
        | Предмет закупки | 1.1. Поставка толкателей вагонеток нижнего действия.
        Товар применяется в условиях угольных шахт.
        """

        queries = _deterministic_queries(context)
        joined = "\n".join(queries).lower()

        self.assertIn("толкателей вагонеток нижнего действия", joined)
        self.assertNotIn("горноспасательное", joined)
        self.assertNotIn("вгсч", joined)

    def test_exact_match_terms_exclude_generic_terms_that_caused_false_accepts(self) -> None:
        context = """
        1 | далее - Оборудование | OF-24 | PAGE-2 | IEC-320 | ПВ-100 | ТОРГ-12 | AISI-304
        ТЕХНИЧЕСКОЕ ЗАДАНИЕ Система контроля бортовых и наземных кабельных изделий
        с использованием двух проводов по ОСТ 92-0320-68
        входной контроль
        """

        terms = _exact_match_terms(context)

        self.assertNotIn("далее - оборудование", terms)
        self.assertNotIn("page-2", terms)
        self.assertNotIn("of-24", terms)
        self.assertNotIn("ост-92", terms)
        self.assertNotIn("iec-320", terms)
        self.assertNotIn("пв-100", terms)
        self.assertNotIn("торг-12", terms)
        self.assertNotIn("aisi-304", terms)
        self.assertNotIn("входной контроль", terms)
        self.assertNotIn("с использованием двух проводов", terms)

    def test_clean_supplier_queries_filters_service_process_and_material_queries(self) -> None:
        queries = _clean_supplier_queries(
            [
                '"ТОРГ-12" купить цена',
                '"IEC-320" поставщик официальный сайт',
                '"ПВ-100" купить цена',
                '"AISI-304" поставщик официальный сайт',
                '"входной контроль" производитель',
                "поликарбонат table наименование поставщик",
                "судовые холодильные камеры производство Россия",
            ]
        )

        self.assertEqual(queries, ["судовые холодильные камеры производство Россия"])

    def test_candidate_match_rejects_reference_pages_even_with_generic_commercial_words(self) -> None:
        context = """
        1 | далее - Оборудование | OF-24 | PAGE-1
        Система контроля бортовых и наземных кабельных изделий ТЕСТ-9110
        """
        candidate = Candidate(
            url="https://legalacts.ru/doc/example/",
            domain="legalacts.ru",
            title="О порядках составления и формах расчета производственной мощности оборудования",
            snippet="далее - Оборудование производитель контакты",
            source="yandex",
            query='"далее - Оборудование" производитель',
        )
        pages = [
            {
                "url": candidate.url,
                "text": "Приказ. Далее - Оборудование. Производственная мощность. Купить нельзя. info@legalacts.ru",
            }
        ]

        match = assess_candidate_match(candidate, context, pages)

        self.assertFalse(match.accepted)

    def test_candidate_match_rejects_unrelated_domofon_pages_for_cable_control_tz(self) -> None:
        context = "Система контроля бортовых и наземных кабельных изделий ТЕСТ-9110"
        candidate = Candidate(
            url="https://securtec.ru/catalog/domofony/",
            domain="securtec.ru",
            title="Домофоны купить",
            snippet="подключение с использованием двух проводов поставщик",
            source="google",
            query='"с использованием двух проводов" поставщик',
        )
        pages = [
            {
                "url": candidate.url,
                "text": "Каталог домофонов. Купить домофон. Подключение с использованием двух проводов. sale@securtec.ru",
            }
        ]

        match = assess_candidate_match(candidate, context, pages)

        self.assertFalse(match.accepted)

    def test_accepted_supplier_results_count_only_rows_above_quality_gate(self) -> None:
        reviewed = [
            {
                "company_name": "weak",
                "site": "https://weak.example.ru",
                "evidence_status": "verified",
                "match_level": "exact",
                "quality_score": 35,
                "source": "test",
                "search_query": "система контроля кабельных изделий",
            },
            {
                "company_name": "strong",
                "site": "https://strong.example.ru/catalog/test-9110",
                "evidence_url": "https://strong.example.ru/catalog/test-9110",
                "contact_url": "https://strong.example.ru/contacts",
                "phone": "+7 999 111 22 33",
                "email": "sales@strong.example.ru",
                "evidence_status": "verified",
                "match_level": "exact",
                "source": "test",
                "search_query": "система контроля кабельных изделий ТЕСТ-9110",
            },
        ]

        accepted = _accepted_supplier_results(reviewed, target=2)

        self.assertEqual([item["company_name"] for item in accepted], ["strong"])

    def test_ddgs_queries_do_not_inject_fire_mine_queries_for_unrelated_tz(self) -> None:
        queries = _ddgs_search_queries(["сотовый поликарбонат 6 мм поставщик"])
        joined = "\n".join(queries).lower()

        self.assertIn("сотовый поликарбонат 6 мм поставщик", queries)
        self.assertNotIn("горноспасательное", joined)
        self.assertNotIn("пожарные рукава", joined)

    def test_candidate_match_rejects_exact_code_without_context_overlap(self) -> None:
        context = """
        Поставка установки скрайбирования и скалывания пластин.
        Оборудование для разделения полупроводниковых пластин GaAs/InP.
        Сетевой разъем IEC-320 указан как комплектующая характеристика.
        """
        candidate = Candidate(
            url="https://cabeus-shop.ru/iec-320-c13",
            domain="cabeus-shop.ru",
            title="Cabeus IEC-320-C13 вилка купить",
            snippet="компоненты кабельных систем",
            source="yandex",
            query='"IEC-320" купить цена',
        )
        pages = [
            {
                "url": candidate.url,
                "text": "Купить вилка IEC-320-C13. Кабельные компоненты, каталог, контакты sales@cabeus-shop.ru",
            }
        ]

        match = assess_candidate_match(candidate, context, pages)

        self.assertFalse(match.accepted)

    def test_candidate_match_accepts_exact_code_with_context_overlap(self) -> None:
        context = "Система контроля бортовых и наземных кабельных изделий ТЕСТ-9110 автоматизированная измерительная система контроля жгутов"
        candidate = Candidate(
            url="https://windeq.ru/catalog/test-9110-vxi/",
            domain="windeq.ru",
            title="ТЕСТ-9110-VXI система контроля жгутов и кабелей",
            snippet="оборудование для обработки проводов и кабелей",
            source="yandex",
            query='"ТЕСТ-9110" купить цена',
        )
        pages = [
            {
                "url": candidate.url,
                "text": "ТЕСТ-9110-VXI Полет. Автоматизированная система контроля жгутов и кабелей. Контакты info@windeq.ru +7 495 419-24-11",
            }
        ]

        match = assess_candidate_match(candidate, context, pages)

        self.assertTrue(match.accepted)

    def test_candidate_match_rejects_blog_pages_even_with_commercial_words(self) -> None:
        context = """
        Техническое задание
        Поставка сварочного полуавтомата для MIG/MAG сварки с инверторным источником.
        """
        candidate = Candidate(
            url="https://vtmstol.ru/blog/kak-vybrat-svarochnyi-poluavtomat/",
            domain="vtmstol.ru",
            title="Как выбрать сварочный полуавтомат: купить, цена, характеристики",
            snippet="Обзор сварочного полуавтомата MIG MAG, советы по выбору, купить или заказать.",
            source="ddgs",
            query="сварочный полуавтомат производитель официальный сайт",
        )
        pages = [
            {
                "url": candidate.url,
                "text": "Блог. Как выбрать сварочный полуавтомат MIG MAG с инверторным источником. Купить можно после консультации.",
            }
        ]

        match = assess_candidate_match(candidate, context, pages)

        self.assertFalse(match.accepted)

    def test_candidate_match_rejects_information_articles_without_catalog_path(self) -> None:
        context = "Установка скрайбирования и скалывания для полупроводниковых пластин"
        candidate = Candidate(
            url="https://polymernagrev.ru/nagrev-v-proizvodstve/protsess-proizvodstva-poluprovodnikov/",
            domain="polymernagrev.ru",
            title="Процесс производства полупроводников",
            snippet="Информационная статья компании о производстве полупроводников",
            source="ddgs",
            query="завод полупроводникового технологического оборудования",
        )
        pages = [
            {
                "url": candidate.url,
                "text": "Информационная статья компании Полимернагрев. Описание процесса производства полупроводников, скрайбирования и оборудования.",
            }
        ]

        match = assess_candidate_match(candidate, context, pages)

        self.assertFalse(match.accepted)

    def test_candidate_match_rejects_profession_pages(self) -> None:
        context = "Установка скрайбирования и скалывания для полупроводниковых пластин"
        candidate = Candidate(
            url="https://plan-your-time.com/profession/skraibirovshchik-plastin/",
            domain="plan-your-time.com",
            title="Скрайбировщик пластин",
            snippet="Профессия, обучение, зарплата, производство пластин",
            source="ddgs",
            query="завод оборудования для микроэлектроники скрайбирование",
        )
        pages = [
            {
                "url": candidate.url,
                "text": "Профессия скрайбировщик пластин. Обучение, навыки, зарплата. Описание производства полупроводниковых пластин.",
            }
        ]

        match = assess_candidate_match(candidate, context, pages)

        self.assertFalse(match.accepted)

    def test_candidate_match_rejects_video_platforms(self) -> None:
        candidate = Candidate(
            url="https://rutube.ru/video/49c8beebf950dda93a31992949ef9460/",
            domain="rutube.ru",
            title="Толкатель вагонеток видео",
            snippet="завод горно-шахтного оборудования толкатели",
            source="ddgs",
            query="завод горно-шахтного оборудования толкатели",
        )

        match = assess_candidate_match(candidate, "толкатель вагонеток", [{"url": candidate.url, "text": "Видео про толкатели вагонеток"}])

        self.assertFalse(match.accepted)

    def test_extract_company_name_ignores_generic_service_navigation(self) -> None:
        candidate = Candidate(
            url="https://example-supplier.ru/catalog/welding",
            domain="example-supplier.ru",
            title="Сварочный полуавтомат купить - Интернет-магазин",
            snippet="",
            source="test",
            query="сварочный полуавтомат поставщик",
        )
        pages = [
            {
                "url": candidate.url,
                "text": "Интернет\nГарантия и сервис\nКаталог\nСварочный полуавтомат MIG/MAG\nКонтакты",
            }
        ]

        self.assertEqual(extract_company_name(candidate, pages), "example-supplier.ru")

    def test_product_phrases_keep_material_procurement_subjects(self) -> None:
        context = """
        ТЕХНИЧЕСКОЕ ЗАДАНИЕ
        Поставка поликарбоната и вермикулита Коломна
        Техническое задание
        === TABLE 1 ===
        Характеристики копировать полностью | Монолитный поликарбонат прозрачный 8 мм | Вермикулит вспученный
        """

        phrases = _product_phrases(context)
        queries = _clean_supplier_queries(
            [
                "характеристики копировать полностью поставщик",
                "монолитный поликарбонат прозрачный 8 мм поставщик",
            ]
        )

        self.assertIn("поликарбоната и вермикулита Коломна", phrases)
        self.assertEqual(queries, ["монолитный поликарбонат прозрачный 8 мм поставщик"])

    def test_product_phrases_extract_subject_lines_and_product_table_rows(self) -> None:
        context = """
        | Предмет закупки | 1.1. Поставка толкателей вагонеток верхнего действия.
        на поставку сварочного полуавтомата в количестве 3 шт.
        1. | сварочный полуавтомат для механизированной сварки в среде защитных газов | Назначение
        Установка скрайбирования и скалывания | Установка скрайбирования и скалывания | Производитель
        """

        phrases = _product_phrases(context)

        self.assertIn("толкателей вагонеток верхнего действия", phrases)
        self.assertIn("сварочный полуавтомат для механизированной сварки в среде защитных газов", phrases)
        self.assertIn("Установка скрайбирования и скалывания", phrases)
        self.assertNotIn("швеллер № 18 «сваренный» в короб", phrases)

    def test_product_phrases_drop_service_and_quantity_characteristic_rows(self) -> None:
        context = """
        поставка оборудования, установка и пуско - наладочные работы: демонтаж кабель-канала; программирование системы
        Работы (пуско-наладочные (ПНР), участие в швартовых и ходовых испытаниях (ШИ, ХИ) заказа)
        Система обнаружения утечек Панель сигнализации об утечке, щитовая (до 18 датчиков) - 1 шт. Датчик обнаружения утечки хладагента - 5 шт
        на поставку электропневматического преобразователя для судна «Мурман» Северного филиала
        Поставка провизионных кладовых (камер) с выполнением пуско-наладочных работ (ПНР), участием в швартовых испытаниях
        """

        phrases = _product_phrases(context)

        self.assertNotIn(
            "поставка оборудования, установка и пуско - наладочные работы: демонтаж кабель-канала; программирование системы",
            phrases,
        )
        self.assertNotIn("Работы (пуско-наладочные (ПНР), участие в швартовых и ходовых испытаниях (ШИ, ХИ) заказа)", phrases)
        self.assertNotIn(
            "Система обнаружения утечек Панель сигнализации об утечке, щитовая (до 18 датчиков) - 1 шт. Датчик обнаружения утечки хладагента - 5 шт",
            phrases,
        )
        self.assertIn("электропневматического преобразователя", phrases)
        self.assertIn("провизионных кладовых (камер)", phrases)

    def test_candidate_match_rejects_tender_registry_and_court_pages_with_exact_phrase(self) -> None:
        context = "Поставка установки скрайбирования и скалывания"
        cases = [
            (
                "https://sudact.ru/arbitral/doc/kFFz2zo5NILa/",
                "Решение от 29 марта 2023 г. по делу № А11",
                "Судебное решение. Установка скрайбирования и скалывания. Производитель указан в материалах дела.",
            ),
            (
                "https://www.94fz.ru/num/0528100000111000002",
                "Специальное технологическое оборудование для производства электронной техники",
                "Закупка по 44-ФЗ. Заказчик приобретает установку скрайбирования и скалывания.",
            ),
            (
                "https://reestrinform.ru/reestr-sertifikatov-sootvetstviia/example.html",
                "Сертификат соответствия",
                "Реестр сертификатов соответствия. Установка скрайбирования и скалывания.",
            ),
        ]

        for url, title, page_text in cases:
            candidate = Candidate(
                url=url,
                domain=url.split("/")[2].removeprefix("www."),
                title=title,
                snippet="купить поставщик производитель",
                source="test",
                query='"Установка скрайбирования и скалывания" производитель',
            )
            match = assess_candidate_match(candidate, context, [{"url": url, "text": page_text}])
            self.assertFalse(match.accepted, url)

    def test_best_product_label_uses_matching_phrase_for_multi_item_tz(self) -> None:
        context = """
        - Гидроизоляционный шовный состав «Кальматрон-Шовный»
        - Гидрошпонка Ультрабанд ХВС-150
        - Гидробетон СРГ-Ф2
        """

        self.assertEqual(
            _best_product_label(context, ("гидрошпонка ультрабанд хвс-150",)),
            "Гидрошпонка Ультрабанд ХВС-150",
        )

    def test_extract_company_name_uses_domain_for_plain_product_titles(self) -> None:
        candidate = Candidate(
            url="https://supplier.example/catalog/hvs-150",
            domain="supplier.example",
            title="Гидрошпонка Ультрабанд ХВС-150",
            snippet="",
            source="test",
            query="гидрошпонка поставщик",
        )

        self.assertEqual(extract_company_name(candidate, [{"url": candidate.url, "text": "Каталог\nГидрошпонка Ультрабанд ХВС-150"}]), "supplier.example")


if __name__ == "__main__":
    unittest.main()
