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

def _load_city_coordinates() -> dict[str, tuple[float, float]]:
    coords: dict[str, tuple[float, float]] = dict(CITY_COORDINATES)
    json_path = os.path.join(os.path.dirname(__file__), "data", "city_coordinates.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    if isinstance(v, (list, tuple)) and len(v) == 2:
                        coords[normalize_city_name(k)] = (float(v[0]), float(v[1]))
        except Exception as e:
            logger.warning("failed_to_load_city_coordinates_json", error=str(e))
    return coords

ROAD_DISTANCE_FACTOR: float = 1.15  # Average road curvature coefficient on Russian highways

RUSSIAN_REGION_CAPITALS: dict[str, str] = {
    "вологодская область": "вологда",
    "вологодская обл": "вологда",
    "московская область": "москва",
    "московская обл": "москва",
    "подмосковье": "москва",
    "ленинградская область": "санкт-петербург",
    "ленинградская обл": "санкт-петербург",
    "свердловская область": "екатеринбург",
    "свердловская обл": "екатеринбург",
    "новосибирская область": "новосибирск",
    "новосибирская обл": "новосибирск",
    "красноярский край": "красноярск",
    "нижегородская область": "нижний новгород",
    "нижегородская обл": "нижний новгород",
    "ярославская область": "ярославль",
    "ярославская обл": "ярославль",
    "костромская область": "кострома",
    "костромская обл": "кострома",
    "тверская область": "тверь",
    "тверская обл": "тверь",
    "архангельская область": "архангельск",
    "архангельская обл": "архангельск",
    "республика татарстан": "казань",
    "татарстан": "казань",
    "республика башкортостан": "уфа",
    "башкортостан": "уфа",
    "самарская область": "самара",
    "самарская обл": "самара",
    "пензенская область": "пенза",
    "пензенская обл": "пенза",
    "краснодарский край": "краснодар",
    "иркутская область": "иркутск",
    "иркутская обл": "иркутск",
    "ростовская область": "ростов-на-дону",
    "ростовская обл": "ростов-на-дону",
    "челябинская область": "челябинск",
    "челябинская обл": "челябинск",
    "воронежская область": "воронеж",
    "воронежская обл": "воронеж",
    "пермский край": "пермь",
    "волгоградская область": "волгоград",
    "волгоградская обл": "волгоград",
    "саратовская область": "саратов",
    "саратовская обл": "саратов",
    "тюменская область": "тюмень",
    "тюменская обл": "тюмень",
    "алтайский край": "барнаул",
    "удмуртская республика": "ижевск",
    "удмуртия": "ижевск",
    "ульяновская область": "ульяновск",
    "ульяновская обл": "ульяновск",
    "хабаровский край": "хабаровск",
    "приморский край": "владивосток",
    "томская область": "томск",
    "томская обл": "томск",
    "оренбургская область": "оренбург",
    "оренбургская обл": "оренбург",
    "кемеровская область": "кемерово",
    "кемеровская обл": "кемерово",
    "кузбасс": "кемерово",
    "рязанская область": "рязань",
    "рязанская обл": "рязань",
    "астраханская область": "астрахань",
    "астраханская обл": "астрахань",
    "липецкая область": "липецк",
    "липецкая обл": "липецк",
    "тульская область": "тула",
    "тульская обл": "тула",
    "кировская область": "киров",
    "кировская обл": "киров",
    "чувашская республика": "чебоксары",
    "чувашия": "чебоксары",
    "калининградская область": "калининград",
    "калининградская обл": "калининград",
    "брянская область": "брянск",
    "брянская обл": "брянск",
    "курская область": "курск",
    "курская обл": "курск",
    "ивановская область": "иваново",
    "ивановская обл": "иваново",
    "ставропольский край": "ставрополь",
    "белгородская область": "белгород",
    "белгородская обл": "белгород",
    "владимирская область": "владимир",
    "владимирская обл": "владимир",
    "курганская область": "курган",
    "курганская обл": "курган",
    "смоленская область": "смоленск",
    "смоленская обл": "смоленск",
    "калужская область": "калуга",
    "калужская обл": "калуга",
    "орловская область": "орел",
    "орловская обл": "орел",
    "мурманская область": "мурманск",
    "мурманская обл": "мурманск",
    "тамбовская область": "тамбов",
    "тамбовская обл": "тамбов",
    "республика карелия": "петрозаводск",
    "карелия": "петрозаводск",
    "республика коми": "сыктывкар",
    "коми": "сыктывкар",
    "республика марий эл": "йошкар-ола",
    "марий эл": "йошкар-ола",
    "республика мордовия": "саранск",
    "мордовия": "саранск",
    "новгородская область": "великий новгород",
    "новгородская обл": "великий новгород",
    "псковская область": "псков",
    "псковская обл": "псков",
    "ханты-мансийский автономный округ": "сургут",
    "хмао": "сургут",
    "ямало-ненецкий автономный округ": "новый уренгой",
    "янао": "новый уренгой",
}


def normalize_city_name(value: str | None) -> str:
    city = str(value or "").strip().lower().replace("ё", "е")
    city = re.sub(r"^(?:г\.?|город)\s+", "", city, flags=re.IGNORECASE)
    city = re.sub(r"[^0-9a-zа-я\s.-]+", " ", city, flags=re.IGNORECASE)
    city = re.sub(r"\s+", " ", city)
    norm = city.strip(" .-")
    return norm


# Merge full Russian cities coordinates into CITY_COORDINATES
CITY_COORDINATES.update(_load_city_coordinates())


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


def geocode_city_dadata_sync(city_or_address: str) -> tuple[float, float] | None:
    """Geocode any Russian settlement or address via DaData Suggestions API (instant fallback)."""
    norm = normalize_city_name(city_or_address)
    norm = RUSSIAN_REGION_CAPITALS.get(norm, norm)
    if not norm:
        return None
    if norm in CITY_COORDINATES:
        return CITY_COORDINATES[norm]

    try:
        from .dadata_client import _get_dadata_api_key
        token = _get_dadata_api_key()
        if not token:
            return None
        import httpx
        url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address"
        headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
        with httpx.Client(timeout=3.5) as client:
            resp = client.post(url, json={"query": city_or_address, "count": 1}, headers=headers)
            if resp.status_code == 200:
                payload = resp.json()
                suggestions = payload.get("suggestions", [])
                if suggestions:
                    data = suggestions[0].get("data", {}) or {}
                    lat = data.get("geo_lat")
                    lon = data.get("geo_lon")
                    if lat is not None and lon is not None:
                        coords = (float(lat), float(lon))
                        CITY_COORDINATES[norm] = coords
                        return coords
    except Exception as exc:
        logger.debug("dadata_sync_geocoding_failed", query=city_or_address, error=str(exc))
    return None


def calculate_city_distance_fast(
    from_city: str,
    to_city: str,
    *,
    apply_road_factor: bool = True,
    allow_dadata_fallback: bool = False,
) -> int | None:
    from_norm = normalize_city_name(from_city)
    to_norm = normalize_city_name(to_city)
    from_norm = RUSSIAN_REGION_CAPITALS.get(from_norm, from_norm)
    to_norm = RUSSIAN_REGION_CAPITALS.get(to_norm, to_norm)
    if not from_norm or not to_norm:
        return None
    if from_norm == to_norm:
        return 0
    c1 = CITY_COORDINATES.get(from_norm)
    c2 = CITY_COORDINATES.get(to_norm)
    if not c1 and allow_dadata_fallback:
        c1 = geocode_city_dadata_sync(from_city)
    if not c2 and allow_dadata_fallback:
        c2 = geocode_city_dadata_sync(to_city)
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
        region_str = str(item.get("region") or "").strip()
        if not supplier_city:
            # Do not concatenate independent fields: an address marker in one
            # field must not validate a delivery city mentioned in another.
            for address_evidence in (
                str(item.get("address") or ""),
                str(item.get("legal_address") or ""),
                str(item.get("comments") or ""),
            ):
                extracted = extract_evidenced_city_from_text(address_evidence)
                if extracted:
                    supplier_city = extracted
                    item["supplier_city"] = extracted
                    break

        # A regional registration is not a dispatch city.  In particular, do
        # not let calculate_city_distance_fast map it to a regional capital.
        supplier_city_for_distance = normalize_city_name(supplier_city)
        if (
            supplier_city_for_distance not in CITY_COORDINATES
            or supplier_city_for_distance in RUSSIAN_REGION_CAPITALS
        ):
            supplier_city_for_distance = ""
        distance = item.get("supplier_distance_km")
        if distance is None and supplier_city_for_distance and delivery_city:
            distance = calculate_city_distance_fast(delivery_city, supplier_city_for_distance)
            if distance is not None:
                item["supplier_distance_km"] = distance

        item["supplier_distance_radius_km"] = radius_km
        if distance is None:
            item["supplier_distance_km"] = None
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


def annotate_price_quotes_radius_status(
    quotes: list[Any],
    delivery_city: str,
    radius_km: int | None,
) -> dict[str, int]:
    """Annotate price quotes from their evidenced address/contact city only.

    A company registration region or a guessed warehouse is not enough to
    establish a delivery radius, so quotes without an extractable city stay
    explicitly unknown.
    """
    stats = {"within_radius": 0, "outside_radius": 0, "unknown_distance": 0}
    if not radius_km or radius_km <= 0 or not delivery_city:
        return stats
    for quote in quotes:
        supplier_city = str(getattr(quote, "supplier_city", "") or "").strip()
        location_source = str(getattr(quote, "supplier_location_source", "") or "")
        if not supplier_city:
            supplier_city = extract_evidenced_city_from_text(str(getattr(quote, "contacts", "") or ""))
            if supplier_city:
                quote.supplier_city = supplier_city.capitalize()
                location_source = "contact_address_city"
        supplier_city_for_distance = normalize_city_name(supplier_city)
        if (
            supplier_city_for_distance not in CITY_COORDINATES
            or supplier_city_for_distance in RUSSIAN_REGION_CAPITALS
            or location_source != "contact_address_city"
        ):
            supplier_city_for_distance = ""
        distance = calculate_city_distance_fast(delivery_city, supplier_city_for_distance) if supplier_city_for_distance else None
        quote.supplier_distance_radius_km = radius_km
        if distance is None:
            quote.supplier_distance_km = None
            quote.supplier_distance_radius_status = "unknown_distance"
            quote.supplier_distance_within_radius = None
            quote.supplier_location_source = ""
            quote.supplier_location_confidence = "unknown"
            stats["unknown_distance"] += 1
        elif distance <= radius_km:
            quote.supplier_distance_km = distance
            quote.supplier_distance_radius_status = "within_radius"
            quote.supplier_distance_within_radius = True
            quote.supplier_location_source = location_source
            quote.supplier_location_confidence = "city_centroid"
            stats["within_radius"] += 1
        else:
            quote.supplier_distance_km = distance
            quote.supplier_distance_radius_status = "outside_radius"
            quote.supplier_distance_within_radius = False
            quote.supplier_location_source = location_source
            quote.supplier_location_confidence = "city_centroid"
            stats["outside_radius"] += 1
    return stats


def sort_quotes_by_radius_priority(quotes: list[Any]) -> None:
    """Keep all offers, placing local evidence before unknown and remote ones."""
    def key(quote: Any) -> tuple[int, bool, float]:
        within = getattr(quote, "supplier_distance_within_radius", None)
        rank = 0 if within is True else (1 if within is None else 2)
        return (rank, bool(getattr(quote, "is_outlier", False)), float(getattr(quote, "price_rub", 0) or 0))

    quotes.sort(key=key)


def extract_evidenced_city_from_text(text: str) -> str:
    """Extract only a known city written in an address, never a region proxy.

    ``extract_city_from_text`` intentionally supports region names for search
    expansion. Radius evidence has a stricter contract: a legal region is not
    a warehouse or a dispatch city.
    """
    if not text:
        return ""

    # A city alone can describe a delivery destination.  Radius ranking needs
    # an address-shaped assertion about the supplier (legal/postal address,
    # office, warehouse, production site, or street/house details).
    address_proof = re.compile(
        r"\b(?:адрес|юр(?:идическ(?:ий|ого))?\s+адрес|местонахожд\w*|офис|склад|производств\w*|"
        r"представительств\w*|пункт\s+выдачи|ул\.?|улиц\w*|просп\.?|пр-т|переул\w*|шоссе|д\.?|дом)\b",
        re.IGNORECASE,
    )
    delivery_destination = re.compile(
        r"\b(?:достав\w*|отправ\w*|привез\w*|доставляем|самовывоз\w*)\b",
        re.IGNORECASE,
    )
    unconfirmed_location = re.compile(
        r"\b(?:адрес|офис|склад|производств\w*|местонахожд\w*)\b.{0,40}"
        r"\b(?:уточня\w*|не\s+указан\w*|по\s+запросу)\b",
        re.IGNORECASE,
    )
    city_prefix = re.compile(r"(?:г\.|город|гор\.)\s*([А-Яа-яЁё0-9\-]+)", re.IGNORECASE)

    # Contacts are commonly separated into clauses.  Keeping the evidence in
    # one clause avoids treating "Доставка Москва; адрес: ..." as an address.
    clauses = [part.strip() for part in re.split(r"[;\n|]+", text) if part.strip()]
    for clause in clauses or [text]:
        if (
            delivery_destination.search(clause)
            or unconfirmed_location.search(clause)
            or not address_proof.search(clause)
        ):
            continue
        explicit = city_prefix.search(clause)
        if explicit:
            candidate = normalize_city_name(explicit.group(1))
            if candidate in CITY_COORDINATES:
                return candidate
        clean = re.sub(r"[^\w\s-]", " ", clause.lower().replace("ё", "е"))
        words = clean.split()
        for size in (3, 2, 1):
            for start in range(len(words) - size + 1):
                candidate = normalize_city_name(" ".join(words[start : start + size]))
                if candidate in CITY_COORDINATES:
                    return candidate
    return ""


def extract_city_from_text(text: str) -> str:
    """Find known Russian city or region in text, address, or comment string."""
    if not text:
        return ""
    # 1. Match explicit city prefixes: г. Москва, город Ростов-на-Дону, гор. Шахты
    m = re.search(r'(?:г\.|город|гор\.)\s*([А-Яа-яЁё0-9\-]+)', text, re.IGNORECASE)
    if m:
        candidate = normalize_city_name(m.group(1))
        if candidate in CITY_COORDINATES or candidate in RUSSIAN_REGION_CAPITALS:
            return RUSSIAN_REGION_CAPITALS.get(candidate, candidate)
    # 2. Fast O(1) dictionary lookup on word n-grams (3-word, 2-word, 1-word)
    clean = re.sub(r'[^\w\s-]', ' ', text.lower().replace('ё', 'е'))
    words = clean.split()
    if not words:
        return ""
    for n in (3, 2, 1):
        for i in range(len(words) - n + 1):
            cand = normalize_city_name(" ".join(words[i : i + n]))
            if cand in CITY_COORDINATES:
                return cand
            if cand in RUSSIAN_REGION_CAPITALS:
                return RUSSIAN_REGION_CAPITALS[cand]
    return ""


def get_cities_within_radius(center_city: str, radius_km: int) -> list[str]:
    """Return all known cities within given radius km from center city, sorted by distance ascending."""
    norm_center = normalize_city_name(center_city)
    norm_center = RUSSIAN_REGION_CAPITALS.get(norm_center, norm_center)
    if not norm_center or norm_center not in CITY_COORDINATES:
        return []
    candidates: list[tuple[int, str]] = []
    seen: set[str] = set()
    for city in CITY_COORDINATES:
        norm = normalize_city_name(city)
        if norm in seen or norm in RUSSIAN_REGION_CAPITALS:
            continue
        dist = calculate_city_distance_fast(norm_center, norm)
        if dist is not None and dist <= radius_km:
            seen.add(norm)
            candidates.append((dist, norm))
    # Sort strictly by distance ascending so closest major cities come first
    candidates.sort(key=lambda x: x[0])
    return [c[1] for c in candidates]
