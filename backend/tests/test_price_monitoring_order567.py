import pytest
from app.price_monitoring.extractor import (
    is_listing_url,
    is_foreign_source,
    is_valid_domain,
    is_price_grounded_in_text,
)
from app.price_monitoring.pipeline import (
    calculate_variation_coefficient,
    cluster_and_reconcile_item_quotes,
)
from app.price_monitoring.models import ItemPriceResult, SupplierQuote


def test_calculate_variation_coefficient_order_567():
    # По Приказу Минэка №567: n=3, цены 100, 110, 120
    # mean = 110, stdev = 10, V = (10 / 110) * 100 = 9.09%
    prices = [100.0, 110.0, 120.0]
    v = calculate_variation_coefficient(prices)
    assert 9.08 < v < 9.10

    # 1 позиция -> 0%
    assert calculate_variation_coefficient([100.0]) == 0.0
    assert calculate_variation_coefficient([]) == 0.0


def test_cluster_and_reconcile_5_homogeneous_suppliers():
    quotes = [
        SupplierQuote(company_name=f"ООО Поставщик {i}", price_rub=p, url=f"https://sup{i}.ru")
        for i, p in enumerate([100.0, 105.0, 110.0, 115.0, 120.0], 1)
    ]
    item_res = ItemPriceResult(row_number=1, raw_name="Подшипник 205", clean_name="Подшипник 205", unit="шт", quotes=quotes)
    
    cluster_and_reconcile_item_quotes(item_res, max_suppliers=5, max_variation_pct=33.0)
    
    # Все 5 должны быть в кластере, V <= 33%
    valid = [q for q in item_res.quotes if not q.is_outlier]
    assert len(valid) == 5
    assert all(not q.is_outlier for q in valid)


def test_cluster_filters_extreme_outlier_maintains_44fz_quorum():
    # 4 поставщика около 1000 руб, 1 поставщик за 5000 руб (выброс / омоним)
    quotes = [
        SupplierQuote(company_name="ООО 1", price_rub=1000.0, url="https://s1.ru"),
        SupplierQuote(company_name="ООО 2", price_rub=1050.0, url="https://s2.ru"),
        SupplierQuote(company_name="ООО 3", price_rub=1100.0, url="https://s3.ru"),
        SupplierQuote(company_name="ООО 4", price_rub=1150.0, url="https://s4.ru"),
        SupplierQuote(company_name="ООО 5", price_rub=5000.0, url="https://s5.ru"),
    ]
    item_res = ItemPriceResult(row_number=1, raw_name="Лента Р1763", clean_name="Лента Р1763", unit="м2", quotes=quotes)
    
    cluster_and_reconcile_item_quotes(item_res, max_suppliers=5, max_variation_pct=33.0)
    
    valid = [q for q in item_res.quotes if not q.is_outlier]
    assert len(valid) == 4
    outliers = [q for q in item_res.quotes if q.is_outlier]
    assert len(outliers) == 1
    assert outliers[0].price_rub == 5000.0


def test_divergent_custom_goods_honestly_marked_as_missing():
    # Дробильные плиты / датчики турбин без открытых цен: найдены только дико разные котировки (500 руб vs 45 600 руб)
    quotes = [
        SupplierQuote(company_name="ООО 1", price_rub=500.0, url="https://s1.ru"),
        SupplierQuote(company_name="ООО 2", price_rub=45600.0, url="https://s2.ru"),
    ]
    item_res = ItemPriceResult(row_number=1, raw_name="Било Л-04.524", clean_name="Било Л-04.524", unit="шт", quotes=quotes)
    
    cluster_and_reconcile_item_quotes(item_res, max_suppliers=5, max_variation_pct=33.0)
    
    # Ни одна цена не должна быть подтверждена, т.к. V > 33%
    valid = [q for q in item_res.quotes if not q.is_outlier]
    assert len(valid) == 0
    assert all(q.is_outlier for q in item_res.quotes)


def test_is_listing_url():
    assert is_listing_url("https://vseinstrumenti.ru/tag-page/lentadiagrammnaya/") is True
    assert is_listing_url("https://maktex.ru/catalog/") is True
    assert is_listing_url("https://example.ru/product?page=2") is True
    assert is_listing_url("https://urallitcom.ru/catalog/bilo-l-04-524/") is False


def test_is_foreign_source():
    assert is_foreign_source("https://aliexpress.ru/item/123.html") is False  # .ru tld, but domain in marketplace
    assert is_foreign_source("https://shopozz.ru/item/123") is True  # Forwarder
    assert is_foreign_source("https://cdek.shopping/p/123") is True  # Forwarder
    assert is_foreign_source("https://somestore.com/item") is True  # Foreign .com without ru content
    assert is_foreign_source("https://somestore.de/item") is True  # .de foreign TLD


def test_is_price_grounded_in_text():
    page_text = "Купить датчик давления. Цена со склада: 45 600 руб. В наличии."
    assert is_price_grounded_in_text(45600.0, page_text) is True
    assert is_price_grounded_in_text(45600, page_text) is True
    
    # Галлюцинация LLM (цена, которой нет на странице)
    assert is_price_grounded_in_text(12345.0, page_text) is False
