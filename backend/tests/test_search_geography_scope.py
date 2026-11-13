import pytest
from app.jobs import (
    GEO_SCOPE_RU,
    GEO_SCOPE_CIS,
    GEO_SCOPE_WORLD,
    VALID_GEO_SCOPES,
    normalize_geo_scope,
)
from app.supplier_search import (
    is_domain_allowed_for_geo,
    FOREIGN_NATIONAL_CCTLDS,
    CIS_CCTLDS,
    FOREIGN_B2B_PORTALS,
)
from app.report_builder import _format_supplier_location


def test_normalize_geo_scope_basic():
    assert normalize_geo_scope("ru", "normal") == GEO_SCOPE_RU
    assert normalize_geo_scope("cis", "normal") == GEO_SCOPE_CIS
    assert normalize_geo_scope("world", "normal") == GEO_SCOPE_WORLD
    assert normalize_geo_scope("invalid", "normal") == GEO_SCOPE_RU
    assert normalize_geo_scope("", "normal") == GEO_SCOPE_RU
    assert normalize_geo_scope(None, "normal") == GEO_SCOPE_RU


def test_normalize_geo_scope_locks_to_ru_for_minpromtorg():
    # Iron rule: registry policy requires domestic Russian goods (PP RF 719)
    assert normalize_geo_scope("world", "minprom_registry_only") == GEO_SCOPE_RU
    assert normalize_geo_scope("cis", "minprom_registry_only") == GEO_SCOPE_RU
    assert normalize_geo_scope("world", "minprom_registry_priority") == GEO_SCOPE_RU
    assert normalize_geo_scope("cis", "minprom_registry_priority") == GEO_SCOPE_RU
    assert normalize_geo_scope("ru", "minprom_registry_only") == GEO_SCOPE_RU


def test_is_domain_allowed_for_geo_ru():
    assert is_domain_allowed_for_geo("zavod-kabel.ru", GEO_SCOPE_RU) is True
    assert is_domain_allowed_for_geo("завод.рф", GEO_SCOPE_RU) is True
    assert is_domain_allowed_for_geo("electrosila.su", GEO_SCOPE_RU) is True
    assert is_domain_allowed_for_geo("belarus-metal.by", GEO_SCOPE_RU) is False
    assert is_domain_allowed_for_geo("kazakhstan-trade.kz", GEO_SCOPE_RU) is False
    assert is_domain_allowed_for_geo("china-factory.cn", GEO_SCOPE_RU) is False
    assert is_domain_allowed_for_geo("made-in-china.com", GEO_SCOPE_RU) is False
    assert is_domain_allowed_for_geo("global-b2b.com", GEO_SCOPE_RU) is True  # .com could be Russian, but foreign ccTLDs strictly rejected


def test_is_domain_allowed_for_geo_cis():
    assert is_domain_allowed_for_geo("zavod-kabel.ru", GEO_SCOPE_CIS) is True
    assert is_domain_allowed_for_geo("minsk-transformator.by", GEO_SCOPE_CIS) is True
    assert is_domain_allowed_for_geo("astana-truba.kz", GEO_SCOPE_CIS) is True
    assert is_domain_allowed_for_geo("yerevan-armatura.am", GEO_SCOPE_CIS) is True
    assert is_domain_allowed_for_geo("bishkek-kabel.kg", GEO_SCOPE_CIS) is True
    # Non-CIS foreign countries rejected
    assert is_domain_allowed_for_geo("china-factory.cn", GEO_SCOPE_CIS) is False
    assert is_domain_allowed_for_geo("berlin-werk.de", GEO_SCOPE_CIS) is False


def test_is_domain_allowed_for_geo_world():
    assert is_domain_allowed_for_geo("zavod-kabel.ru", GEO_SCOPE_WORLD) is True
    assert is_domain_allowed_for_geo("china-factory.cn", GEO_SCOPE_WORLD) is True
    assert is_domain_allowed_for_geo("shenzhen-sensor.hk", GEO_SCOPE_WORLD) is True
    # Blacklisted foreign aggregator portals always blocked even in world scope
    assert is_domain_allowed_for_geo("made-in-china.com", GEO_SCOPE_WORLD) is False
    assert is_domain_allowed_for_geo("alibaba.com", GEO_SCOPE_WORLD) is False
    assert is_domain_allowed_for_geo("aliexpress.com", GEO_SCOPE_WORLD) is False


def test_format_supplier_location_with_foreign_country():
    # Domestic Russian row
    row_ru = {"city": "Казань", "country": "Россия"}
    assert _format_supplier_location(row_ru) == "Казань"

    # Belarus
    row_by = {"city": "Минск", "country": "Беларусь 🇧🇾"}
    assert _format_supplier_location(row_by) == "Минск [Беларусь 🇧🇾]"

    # Kazakhstan
    row_kz = {"city": "Алматы", "country": "Казахстан 🇰🇿"}
    assert _format_supplier_location(row_kz) == "Алматы [Казахстан 🇰🇿]"

    # China
    row_cn = {"city": "Шэньчжэнь", "country": "Китай 🇨🇳"}
    assert _format_supplier_location(row_cn) == "Шэньчжэнь [Китай 🇨🇳]"

    # Country only
    row_cn_no_city = {"country": "Китай 🇨🇳"}
    assert _format_supplier_location(row_cn_no_city) == "[Китай 🇨🇳]"


def test_exclude_candidates_respects_geo_scope():
    from app.supplier_search import _exclude_candidates, Candidate

    candidates = [
        Candidate(url="https://zavod-kabel.ru", domain="zavod-kabel.ru", title="Завод Кабель"),
        Candidate(url="https://minsk-energo.by", domain="minsk-energo.by", title="Минск Энерго"),
        Candidate(url="https://china-pipes.cn", domain="china-pipes.cn", title="China Pipes"),
        Candidate(url="https://made-in-china.com", domain="made-in-china.com", title="Made in China Aggregator"),
    ]

    # RU scope filters out .by, .cn, and blocked aggregators
    ru_filtered = _exclude_candidates(candidates, set(), geo_scope=GEO_SCOPE_RU)
    ru_domains = [c.domain for c in ru_filtered]
    assert "zavod-kabel.ru" in ru_domains
    assert "minsk-energo.by" not in ru_domains
    assert "china-pipes.cn" not in ru_domains
    assert "made-in-china.com" not in ru_domains

    # CIS scope keeps RU and BY, filters out CN and aggregator
    cis_filtered = _exclude_candidates(candidates, set(), geo_scope=GEO_SCOPE_CIS)
    cis_domains = [c.domain for c in cis_filtered]
    assert "zavod-kabel.ru" in cis_domains
    assert "minsk-energo.by" in cis_domains
    assert "china-pipes.cn" not in cis_domains
    assert "made-in-china.com" not in cis_domains

    # World scope keeps RU, BY, CN, but still excludes aggregator
    world_filtered = _exclude_candidates(candidates, set(), geo_scope=GEO_SCOPE_WORLD)
    world_domains = [c.domain for c in world_filtered]
    assert "zavod-kabel.ru" in world_domains
    assert "minsk-energo.by" in world_domains
    assert "china-pipes.cn" in world_domains
    assert "made-in-china.com" not in world_domains


def test_customer_job_to_dict_geo_scope():
    from app.models import Job
    from app.main import customer_job_to_dict

    # Default job with no geo_scope set
    job_default = Job(id="test_geo_1", created_by_telegram_id="123", mode="supplier_search")
    job_dict_default = customer_job_to_dict(job_default)
    assert job_dict_default["geo_scope"] == "ru"

    # Job with explicit geo_scope
    job_world = Job(id="test_geo_2", created_by_telegram_id="123", mode="supplier_search", geo_scope="world")
    job_dict_world = customer_job_to_dict(job_world)
    assert job_dict_world["geo_scope"] == "world"


def test_price_monitoring_geo_scope_domain_filtering():
    from app.price_monitoring.extractor import is_foreign_source, is_valid_domain

    # RU mode: domestic allowed, .by/.kz/.cn blocked
    assert is_valid_domain("https://kabel-snab.ru/catalog/1", geo_scope="ru") is True
    assert is_valid_domain("https://minsk-kabel.by/catalog/1", geo_scope="ru") is False
    assert is_valid_domain("https://shanghai-cable.cn/product/1", geo_scope="ru") is False
    assert is_foreign_source("https://minsk-kabel.by/p", geo_scope="ru") is True
    assert is_foreign_source("https://kabel-snab.ru/p", geo_scope="ru") is False

    # CIS mode: .by and .kz allowed, .cn/.de blocked
    assert is_valid_domain("https://kabel-snab.ru/catalog/1", geo_scope="cis") is True
    assert is_valid_domain("https://minsk-kabel.by/catalog/1", geo_scope="cis") is True
    assert is_valid_domain("https://almaty-truba.kz/catalog/1", geo_scope="cis") is True
    assert is_valid_domain("https://shanghai-cable.cn/product/1", geo_scope="cis") is False
    assert is_foreign_source("https://minsk-kabel.by/p", geo_scope="cis") is False
    assert is_foreign_source("https://shanghai-cable.cn/p", geo_scope="cis") is True

    # World mode: foreign domains allowed, but aggregators like made-in-china still blocked
    assert is_valid_domain("https://shanghai-cable.cn/product/1", filter_foreign=False, geo_scope="world") is True
    assert is_valid_domain("https://made-in-china.com/product/1", filter_foreign=False, geo_scope="world") is False
    assert is_foreign_source("https://shanghai-cable.cn/p", geo_scope="world") is False
