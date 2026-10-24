from unittest.mock import patch

from app.product_inventory import extract_structured_product_inventory


def sample_document():
    return """Извещение о проведении закупки
Гарантия 12 месяцев. ИНН 1234567890
|№|Наименование товара|Единица|Кол-во|
|п/п||измерения||
|1|Панель стеновая ПСТ 100 RAL 8017|шт.|9|
|2|Панель стеновая EPS 50 RAL|шт.|40|
||9003|||
|3|Панель кровельная EPS 100 RAL 5005|шт.|10|
|4|Саморез 140*5,5|шт.|300|
|5|Саморез 95*5,5|шт.|700|
|6|Уголок внутренний 100х100|пог. м|25|
|7|Уголок наружный 100х100|пог. м|12,5|
|8|Фасонный внешний угол|пог. м|200|
||при вертикальном монтаже|||
||ФЭ 10х120х120х10 RAL 5005|||

|№|Наименование товара|Показатель|Значение|Инструкция участнику|
|1|2|3|4|5|
|1|Панель стеновая ПСТ|Толщина|100 мм|Не менять|
||100 RAL 8017||||
|2|Саморез|Саморез со сверлом|Не менять|
||140*5,5 RAL 8017|и шайбой||
|3|Уголок внутренний 100х100|Материал|Оцинкованная сталь|Не менять|
|4|Уголок наружный 100х100|Материал|Сталь 0,45 мм|Не менять|
|5|Панель стеновая EPS 50 RAL 9003|Толщина|50 мм|Не менять|
|6|Панель кровельная EPS 100 RAL 5005|Толщина|100 мм|Не менять|
|7|Саморез 95*5,5 RAL 9003|Тип головки|Шестигранная|Не менять|
|8|Фасонный внешний угол при вертикальном монтаже ФЭ 10х120х120х10 RAL 5005|Цвет|RAL 5005|Не менять|

Общие требования: новый товар. Порядок оплаты и контакты.
"""


def test_authoritative_table_excludes_legal_lines_and_repeated_details():
    rows = extract_structured_product_inventory([], context=sample_document())
    assert len(rows) == 8
    assert [row["position_no"] for row in rows] == list(range(1, 9))
    assert rows[1]["name"] == "Панель стеновая EPS 50 RAL 9003"
    assert rows[6]["quantity"] == "12,5"
    assert rows[6]["unit"] == "пог. м"
    assert rows[7]["name"].endswith("ФЭ 10х120х120х10 RAL 5005")
    assert all("Гарантия" not in row["name"] for row in rows)


def test_characteristics_match_by_name_not_reordered_table_index():
    rows = extract_structured_product_inventory([], context=sample_document())
    assert rows[1]["requirements"] == [{"param_name": "Толщина", "tz_requirement": "50 мм"}]
    assert rows[3]["requirements"] == [{"param_name": "Описание товара", "tz_requirement": "Саморез со сверлом и шайбой"}]
    assert rows[4]["requirements"] == [{"param_name": "Тип головки", "tz_requirement": "Шестигранная"}]
    assert rows[5]["requirements"] == [{"param_name": "Материал", "tz_requirement": "Оцинкованная сталь"}]


def test_document_path_records_source_coordinates_without_network(tmp_path):
    path = tmp_path / "spec.doc"
    path.write_bytes(b"document")
    with patch("app.document_parser.extract_text", return_value=(sample_document(), "ok")):
        rows = extract_structured_product_inventory([path])
    assert len(rows) == 8
    assert rows[0]["source_file"] == "spec.doc"
    assert rows[0]["source_row"] == 5


def test_plain_text_returns_unstructured_marker():
    assert extract_structured_product_inventory([], context="Клапан 25 мм\nНасос 5 кВт") is None


def test_spreadsheet_preserves_duplicate_names_and_distinct_units(tmp_path):
    import openpyxl
    workbook = openpyxl.Workbook()
    workbook.active.append(["№", "Наименование", "Ед.изм.", "Количество", "Диаметр"])
    workbook.active.append([2, "Труба", "м", 5, "25 мм"])
    workbook.active.append([9, "Труба", "шт", 2, "50 мм"])
    path = tmp_path / "spec.xlsx"
    workbook.save(path)
    rows = extract_structured_product_inventory([path])
    assert len(rows) == 2
    assert [row["position_no"] for row in rows] == [2, 9]
    assert [row["unit"] for row in rows] == ["м", "шт"]


def test_monitoring_uses_authoritative_inventory_instead_of_document_lines(tmp_path):
    from app.price_monitoring.cleaner import extract_items_from_files_or_text
    path = tmp_path / "spec.doc"
    path.write_bytes(b"document")
    with patch("app.document_parser.extract_text", return_value=(sample_document(), "ok")):
        items = extract_items_from_files_or_text([path], context=sample_document())
    assert len(items) == 8
    assert items[3][0] == "Саморез 140*5,5"


def test_monitoring_keeps_duplicate_structured_rows_with_distinct_units(tmp_path):
    import openpyxl
    from app.price_monitoring.cleaner import extract_items_from_files_or_text
    workbook = openpyxl.Workbook()
    workbook.active.append(["Наименование", "Ед.изм.", "Количество"])
    workbook.active.append(["Труба", "м", 5])
    workbook.active.append(["Труба", "шт", 2])
    path = tmp_path / "spec.xlsx"
    workbook.save(path)
    assert extract_items_from_files_or_text([path]) == [("Труба", "м"), ("Труба", "шт")]


def test_identifier_prefix_never_attaches_different_sku_characteristics():
    text = """|№|Наименование|Единица|Кол-во|
|1|Болт М6|шт|2|

|№|Наименование|Показатель|Значение|Инструкция|
|1|Болт М60 RAL 5005|Диаметр|60 мм|Не менять|
"""
    assert extract_structured_product_inventory([], context=text)[0]["requirements"] == []


def test_repeated_page_header_does_not_pollute_previous_product():
    text = """|№|Наименование|Единица|Кол-во|
|1|Болт М6|шт|2|
|№|Наименование|Единица|Кол-во|
|п/п||измерения||
|2|Болт М8|шт|3|
"""
    rows = extract_structured_product_inventory([], context=text)
    assert [row["name"] for row in rows] == ["Болт М6", "Болт М8"]
    assert rows[0]["unit"] == "шт"
