"""Supplier location extraction and distance estimates for TenderLex.

Supports fast coordinate-based distance calculation (Haversine formula with road curvature factor),
automatic city normalization, and location enrichment for B2B procurement suppliers.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

CITY_COORDINATES: dict[str, tuple[float, float]] = {
    "москва": (55.7558, 37.6173),
    "санкт-петербург": (59.9343, 30.3351),
    "спб": (59.9343, 30.3351),
    "питер": (59.9343, 30.3351),
    "новосибирск": (55.0084, 82.9357),
    "екатеринбург": (56.8389, 60.6057),
    "екб": (56.8389, 60.6057),
    "казань": (55.7961, 49.1064),
    "нижний новгород": (56.3269, 44.0059),
    "н новгород": (56.3269, 44.0059),
    "челябинск": (55.1644, 61.4368),
    "самара": (53.1959, 50.1002),
    "омск": (54.9885, 73.3242),
    "ростов-на-дону": (47.2225, 39.7187),
    "ростов на дону": (47.2225, 39.7187),
    "уфа": (54.7388, 55.9721),
    "красноярск": (56.0153, 92.8932),
    "воронеж": (51.6608, 39.2003),
    "пермь": (58.0105, 56.2502),
    "волгоград": (48.7080, 44.5133),
    "краснодар": (45.0355, 38.9753),
    "саратов": (51.5335, 46.0343),
    "тюмень": (57.1530, 65.5412),
    "тольятти": (53.5078, 49.4204),
    "барнаул": (53.3498, 83.7836),
    "ижевск": (56.8524, 53.2114),
    "ульяновск": (54.3142, 48.4031),
    "иркутск": (52.2870, 104.3050),
    "хабаровск": (48.4827, 135.0779),
    "ярославль": (57.6261, 39.8845),
    "владивосток": (43.1155, 131.8855),
    "махачкала": (42.9831, 47.5046),
    "томск": (56.4977, 84.9744),
    "оренбург": (51.7682, 55.0970),
    "кемерово": (55.3547, 86.0872),
    "новокузнецк": (53.7596, 87.1216),
    "рязань": (54.6292, 39.7366),
    "астрахань": (46.3497, 48.0408),
    "пенза": (53.1950, 45.0183),
    "липецк": (52.6103, 39.5947),
    "тула": (54.1931, 37.6173),
    "киров": (58.6035, 49.6679),
    "чебоксары": (56.1439, 47.2489),
    "калининград": (54.7104, 20.4522),
    "гусев": (54.5922, 22.2000),
    "советск": (55.0833, 21.8833),
    "черняховск": (54.6333, 21.8167),
    "светлый": (54.6750, 20.1347),
    "балтийск": (54.6528, 19.9103),
    "зеленоградск": (54.9575, 20.4744),
    "светлогорск": (54.9431, 20.1542),
    "гвардейск": (54.6500, 21.0667),
    "пионерский": (54.9508, 20.2275),
    "брянск": (53.2424, 34.3639),
    "курск": (51.7304, 36.1927),
    "иваново": (56.9997, 40.9729),
    "магнитогорск": (53.4072, 58.9794),
    "тверь": (56.8587, 35.9176),
    "ставрополь": (45.0445, 41.9691),
    "симферополь": (44.9521, 34.1024),
    "белгород": (50.5954, 36.5873),
    "архангельск": (64.5399, 40.5170),
    "владимир": (56.1290, 40.4066),
    "севастополь": (44.6166, 33.5254),
    "сочи": (43.6028, 39.7342),
    "курган": (55.4410, 65.3411),
    "смоленск": (54.7826, 32.0453),
    "калуга": (54.5138, 36.2612),
    "чита": (52.0336, 113.5009),
    "орел": (52.9651, 36.0785),
    "волжский": (48.7858, 44.7797),
    "череповец": (59.1226, 37.9033),
    "владикавказ": (43.0367, 44.6678),
    "мурманск": (68.9585, 33.0827),
    "сургут": (61.2540, 73.3962),
    "вологда": (59.2205, 39.8915),
    "тамбов": (52.7212, 41.4523),
    "стерлитамак": (53.6245, 55.9587),
    "грозный": (43.3179, 45.6983),
    "якутск": (62.0355, 129.6755),
    "кострома": (57.7677, 40.9269),
    "комсомольск-на-амуре": (50.5503, 137.0094),
    "петрозаводск": (61.7850, 34.3469),
    "таганрог": (47.2362, 38.8969),
    "нижневартовск": (60.9385, 76.5589),
    "йошкар-ола": (56.6344, 47.8999),
    "братск": (56.1514, 101.6341),
    "новороссийск": (44.7154, 37.7619),
    "дзержинск": (56.2389, 43.4631),
    "шахты": (47.7089, 40.2163),
    "каменск-шахтинский": (48.3197, 40.2647),
    "новочеркасск": (47.4222, 40.0931),
    "батайск": (47.1397, 39.7517),
    "аксай": (47.2694, 39.8639),
    "волгодонск": (47.5147, 42.1528),
    "нальчик": (43.4853, 43.6071),
    "орск": (51.2049, 58.5668),
    "сыктывкар": (61.6688, 50.8354),
    "нижнекамск": (55.6366, 51.8239),
    "ангарск": (52.5444, 103.8882),
    "старый оскол": (51.2974, 37.8353),
    "великий новгород": (58.5215, 31.2755),
    "балашиха": (55.7982, 37.9680),
    "благовещенск": (50.2796, 127.5405),
    "прокопьевск": (53.9042, 86.7230),
    "бийск": (52.5398, 85.2072),
    "энгельс": (51.4982, 46.1264),
    "рыбинск": (58.0484, 38.8584),
    "балаково": (52.0287, 47.7842),
    "северодвинск": (64.5635, 39.8302),
    "арзамас": (55.3949, 43.8399),
    "подольск": (55.4312, 37.5457),
    "королев": (55.9142, 37.8288),
    "мытищи": (55.9105, 37.7363),
    "люберцы": (55.6772, 37.8932),
    "красногорск": (55.8314, 37.3297),
    "химки": (55.8970, 37.4297),
    "зеленоград": (55.9825, 37.1814),
    "обнинск": (55.1107, 36.6119),
    "тучково": (55.5986, 36.4714),
    "армавир": (44.9961, 41.1242),
    "домодедово": (55.4431, 37.7478),
    "одинцово": (55.6789, 37.2644),
    "раменское": (55.5681, 38.2253),
    "серпухов": (54.9156, 37.4161),
    "щелково": (55.9208, 37.9944),
    "орехово-зуево": (55.8078, 38.9619),
    "коломна": (55.0939, 38.7783),
    "долгопрудный": (55.9353, 37.5158),
    "реутов": (55.7600, 37.8617),
    "жуковский": (55.5986, 38.1206),
    "пушкино": (56.0119, 37.8483),
    "ногинск": (55.8569, 38.4419),
    "электросталь": (55.7958, 38.4422),
    "сергиев посад": (56.3153, 38.1361),
    "внуково": (55.6053, 37.2867),
    "видное": (55.5528, 37.7083),
    "котельники": (55.6600, 37.8631),
    "дзержинский": (55.6319, 37.8486),
    "лыткарино": (55.5744, 37.9044),
    "лобня": (56.0125, 37.4764),
    "троицк": (55.4833, 37.3000),
    "щербинка": (55.5000, 37.5500),
}

ROAD_DISTANCE_FACTOR: float = 1.15  # Average road curvature coefficient on Russian highways


def normalize_city_name(value: str | None) -> str:
    city = str(value or "").strip().lower().replace("ё", "е")
    city = re.sub(r"^(?:г\.?|город)\s+", "", city, flags=re.IGNORECASE)
    city = re.sub(r"[^0-9a-zа-я\s.-]+", " ", city, flags=re.IGNORECASE)
    city = re.sub(r"\s+", " ", city)
    return city.strip(" .-")


def haversine_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    *,
    apply_road_factor: bool = True,
) -> int:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    direct_km = R * c
    if apply_road_factor and direct_km > 0:
        return int(round(direct_km * ROAD_DISTANCE_FACTOR))
    return int(round(direct_km))


def calculate_city_distance_fast(
    from_city: str,
    to_city: str,
    *,
    apply_road_factor: bool = True,
) -> int | None:
    from_norm = normalize_city_name(from_city)
    to_norm = normalize_city_name(to_city)
    if not from_norm or not to_norm:
        return None
    if from_norm == to_norm:
        return 0
    c1 = CITY_COORDINATES.get(from_norm)
    c2 = CITY_COORDINATES.get(to_norm)
    if c1 and c2:
        return haversine_distance_km(c1[0], c1[1], c2[0], c2[1], apply_road_factor=apply_road_factor)
    return None


def normalize_location_records(value: Any, *, max_locations: int = 7) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = [{"city": raw}]
    if isinstance(value, dict):
        if isinstance(value.get("locations"), list):
            value = value["locations"]
        elif value.get("city"):
            value = [value]
        else:
            return []
    if not isinstance(value, list):
        return []

    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if isinstance(item, str):
            item = {"city": item}
        if not isinstance(item, dict):
            continue
        city = str(
            item.get("city")
            or item.get("city_name")
            or item.get("location_city")
            or item.get("name")
            or ""
        ).strip()
        normalized = normalize_city_name(city)
        if not city or not normalized or normalized in seen:
            continue
        seen.add(normalized)
        confidence_raw = item.get("confidence", item.get("score", 0.0))
        try:
            confidence = float(confidence_raw or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        records.append(
            {
                "city": city[:255],
                "normalized_city": normalized[:255],
                "region": str(item.get("region") or "").strip()[:255],
                "country": str(item.get("country") or "").strip()[:255],
                "is_primary": bool(item.get("is_primary")) or not records,
                "confidence": max(0.0, min(1.0, confidence)),
                "source": str(item.get("source") or item.get("evidence_url") or "").strip()[:1000],
                "evidence": str(item.get("evidence") or "").strip()[:1000],
            }
        )
        if len(records) >= max_locations:
            break
    if records and not any(item.get("is_primary") for item in records):
        records[0]["is_primary"] = True
    return records


def primary_city(locations: list[dict[str, Any]]) -> str:
    if not locations:
        return ""
    primary = next((item for item in locations if item.get("is_primary")), locations[0])
    return str(primary.get("city") or "").strip()


def serialize_locations(locations: list[dict[str, Any]]) -> str:
    return json.dumps(normalize_location_records(locations), ensure_ascii=False)


def nearest_location_distance(
    *,
    delivery_city: str,
    locations: list[dict[str, Any]],
) -> dict[str, Any]:
    if not delivery_city:
        return {"city": "", "distance_km": None, "confidence": "unknown", "source": "no_delivery_city"}
    best: dict[str, Any] | None = None
    for location in normalize_location_records(locations):
        city = str(location.get("city") or "").strip()
        if not city:
            continue
        distance = calculate_city_distance_fast(delivery_city, city)
        if distance is None:
            continue
        candidate = {
            "city": city,
            "distance_km": int(distance),
            "confidence": "high" if location.get("confidence", 0) > 0.7 else "medium",
            "source": "geo_coords",
        }
        if best is None or candidate["distance_km"] < best["distance_km"]:
            best = candidate
    return best or {"city": "", "distance_km": None, "confidence": "unknown", "source": "unknown"}


def annotate_contacts_radius_status(
    contacts: list[dict[str, Any]],
    delivery_city: str,
    radius_km: int | None,
) -> dict[str, int]:
    stats = {
        "within_radius": 0,
        "outside_radius": 0,
        "unknown_distance": 0,
    }
    if not radius_km or radius_km <= 0 or not delivery_city:
        return stats
    for item in contacts:
        supplier_city = str(item.get("supplier_city") or item.get("city") or "").strip()
        distance = item.get("supplier_distance_km")
        if distance is None and supplier_city and delivery_city:
            distance = calculate_city_distance_fast(delivery_city, supplier_city)
            if distance is not None:
                item["supplier_distance_km"] = distance

        item["supplier_distance_radius_km"] = radius_km
        if distance is None:
            item["supplier_distance_radius_status"] = "unknown_distance"
            item["supplier_distance_within_radius"] = None
            stats["unknown_distance"] += 1
            continue
        if distance > radius_km:
            item["supplier_distance_radius_status"] = "outside_radius"
            item["supplier_distance_within_radius"] = False
            stats["outside_radius"] += 1
            continue
        item["supplier_distance_radius_status"] = "within_radius"
        item["supplier_distance_within_radius"] = True
        stats["within_radius"] += 1
    return stats


def extract_city_from_text(text: str) -> str:
    """Find known Russian city in text, address, or comment string."""
    if not text:
        return ""
    # 1. Match explicit city prefixes: г. Москва, город Ростов-на-Дону, гор. Шахты
    m = re.search(r'(?:г\.|город|гор\.)\s*([А-Яа-яЁё0-9\-]+)', text, re.IGNORECASE)
    if m:
        candidate = normalize_city_name(m.group(1))
        if candidate in CITY_COORDINATES:
            return candidate
    # 2. Check known cities in CITY_COORDINATES (longest first to avoid substring false positives)
    text_lower = text.lower()
    for city in sorted(CITY_COORDINATES.keys(), key=len, reverse=True):
        pattern = r'(?<![а-яё0-9])' + re.escape(city) + r'(?![а-яё0-9])'
        if re.search(pattern, text_lower):
            return city
    return ""


def get_cities_within_radius(center_city: str, radius_km: int) -> list[str]:
    """Return all known cities within given radius km from center city."""
    norm_center = normalize_city_name(center_city)
    if not norm_center or norm_center not in CITY_COORDINATES:
        return []
    res = []
    seen = set()
    for city in CITY_COORDINATES:
        dist = calculate_city_distance_fast(norm_center, city)
        if dist is not None and dist <= radius_km:
            norm = normalize_city_name(city)
            if norm not in seen:
                seen.add(norm)
                res.append(norm)
    return res
