from __future__ import annotations

import math
import re
from decimal import Decimal

from .models import City

_SUFFIXES = (
    ' municipal corporation',
    ' nagar nigam',
    ' urban',
    ' district',
    ' city',
)


def normalize_place(value):
    text = re.sub(r'\s+', ' ', (value or '').strip().lower())
    if not text:
        return ''
    changed = True
    while changed:
        changed = False
        for suffix in _SUFFIXES:
            if text.endswith(suffix) and len(text) > len(suffix) + 2:
                text = text[: -len(suffix)].strip()
                changed = True
    return text


def haversine_km(lat1, lon1, lat2, lon2):
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def _to_float(value):
    if value is None or value == '':
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _city_names(city: City):
    names = {normalize_place(city.name), normalize_place(city.slug.replace('-', ' '))}
    names.update(normalize_place(alias) for alias in city.alias_list())
    names.discard('')
    return names


def _name_matches(city: City, candidates):
    city_names = _city_names(city)
    for raw in candidates:
        needle = normalize_place(raw)
        if not needle:
            continue
        if needle in city_names:
            return True
        for city_name in city_names:
            if len(city_name) < 4:
                continue
            if re.search(rf'\b{re.escape(city_name)}\b', needle):
                return True
            if re.search(rf'\b{re.escape(needle)}\b', city_name):
                return True
    return False


def _gps_distance_km(city: City, latitude, longitude):
    city_lat = _to_float(city.latitude)
    city_lng = _to_float(city.longitude)
    if city_lat is None or city_lng is None:
        return None
    return haversine_km(latitude, longitude, city_lat, city_lng)


def _serialize_city(city: City | None):
    if city is None:
        return None
    return {
        'id': str(city.id),
        'name': city.name,
        'slug': city.slug,
        'state': city.state,
        'is_active': city.is_active,
    }


def _detected_name(city, city_name, place_names):
    if city is not None:
        return city.name
    cleaned = (city_name or '').strip()
    if cleaned:
        return cleaned
    for name in place_names or []:
        if (name or '').strip():
            return name.strip()
    return ''


def _message_for(*, available, city, detected_name):
    if available and city is not None:
        return f'Home services are live in {city.name}.'
    if city is not None and (city.coming_soon_message or '').strip():
        return city.coming_soon_message.strip()
    label = detected_name or 'your city'
    return f"We're not in {label} yet — available soon."


def check_service_coverage(*, latitude=None, longitude=None, city_name='', place_names=None, city_id=None):
    cities = list(City.objects.all())
    live_cities = [city for city in cities if city.is_active]
    candidates = [city_name, *(place_names or [])]
    lat = _to_float(latitude)
    lng = _to_float(longitude)

    matched = None

    if city_id:
        matched = next((city for city in cities if str(city.id) == str(city_id)), None)

    if matched is None and lat is not None and lng is not None:
        nearby = []
        for city in cities:
            distance = _gps_distance_km(city, lat, lng)
            if distance is None:
                continue
            radius = city.service_radius_km or 40
            if distance <= radius:
                nearby.append((distance, 0 if city.is_active else 1, city))
        if nearby:
            nearby.sort(key=lambda item: (item[0], item[1], item[2].name))
            matched = nearby[0][2]

    if matched is None:
        name_hits = [city for city in cities if _name_matches(city, candidates)]
        if name_hits:
            name_hits.sort(key=lambda city: (0 if city.is_active else 1, city.name))
            matched = name_hits[0]

    detected_name = _detected_name(matched, city_name, place_names)
    available = bool(matched and matched.is_active)
    return {
        'available': available,
        'detected_name': detected_name,
        'message': _message_for(available=available, city=matched, detected_name=detected_name),
        'city': _serialize_city(matched),
        'available_cities': [_serialize_city(city) for city in live_cities],
    }
