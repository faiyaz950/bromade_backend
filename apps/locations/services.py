import math
import re

from .models import City

_PLACE_SUFFIXES = (
    'municipal corporation',
    'district',
    'urban',
    'city',
    'ncr',
)
_NON_ALNUM = re.compile(r'[^a-z0-9\s]+')
_SPACES = re.compile(r'\s+')


def normalize_place(value):
    text = _SPACES.sub(' ', _NON_ALNUM.sub(' ', (value or '').lower())).strip()
    changed = True
    while changed and text:
        changed = False
        for suffix in _PLACE_SUFFIXES:
            token = f' {suffix}'
            if text.endswith(token):
                text = text[: -len(token)].strip()
                changed = True
                break
    return text


def check_service_coverage(
    latitude=None,
    longitude=None,
    city_name='',
    place_names=None,
    city_id=None,
):
    cities = list(City.objects.all())
    live_cities = [city for city in cities if city.is_active]
    matched = None
    detected_name = _first_name(city_name, place_names)

    if city_id:
        matched = next((city for city in cities if str(city.id) == str(city_id)), None)
        if matched is not None:
            detected_name = matched.name
    if matched is None:
        matched = _match_by_coordinates(cities, latitude, longitude)
        if matched is not None and not detected_name:
            detected_name = matched.name
    if matched is None:
        matched = _match_by_names(cities, city_name, place_names)
        if matched is not None and not detected_name:
            detected_name = matched.name

    if matched is None:
        return _payload(
            available=False,
            city=None,
            detected_name=detected_name,
            message=_soon_message(detected_name=detected_name),
            available_cities=live_cities,
        )

    if matched.is_active:
        return _payload(
            available=True,
            city=matched,
            detected_name=detected_name or matched.name,
            message=f'Home services are live in {matched.name}.',
            available_cities=live_cities,
        )

    return _payload(
        available=False,
        city=matched,
        detected_name=detected_name or matched.name,
        message=_soon_message(city=matched, detected_name=detected_name or matched.name),
        available_cities=live_cities,
    )


def _first_name(city_name, place_names):
    if (city_name or '').strip():
        return city_name.strip()
    for name in place_names or []:
        if (name or '').strip():
            return name.strip()
    return ''


def _city_tokens(city):
    tokens = {normalize_place(city.name), (city.slug or '').lower()}
    for alias in (city.aliases or '').split(','):
        token = normalize_place(alias)
        if token:
            tokens.add(token)
    return {token for token in tokens if token}


def _candidate_names(city_name, place_names):
    names = []
    if (city_name or '').strip():
        names.append(city_name.strip())
    for name in place_names or []:
        if (name or '').strip() and name.strip() not in names:
            names.append(name.strip())
    return names


def _match_by_names(cities, city_name, place_names):
    candidates = [normalize_place(name) for name in _candidate_names(city_name, place_names)]
    candidates = [name for name in candidates if name]
    if not candidates:
        return None
    for candidate in candidates:
        for city in cities:
            if candidate in _city_tokens(city):
                return city
    return None


def _match_by_coordinates(cities, latitude, longitude):
    try:
        lat = float(latitude)
        lng = float(longitude)
    except (TypeError, ValueError):
        return None

    nearest = None
    nearest_km = None
    for city in cities:
        if city.latitude is None or city.longitude is None:
            continue
        distance = _haversine_km(lat, lng, float(city.latitude), float(city.longitude))
        radius = city.service_radius_km or 0
        if distance > radius:
            continue
        if nearest is None or distance < nearest_km:
            nearest = city
            nearest_km = distance
    return nearest


def _haversine_km(lat1, lon1, lat2, lon2):
    radius = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def _soon_message(city=None, detected_name=''):
    if city is not None and (city.coming_soon_message or '').strip():
        return city.coming_soon_message.strip()
    name = ((city.name if city is not None else '') or detected_name).strip()
    if name:
        return f"We're not in {name} yet — available soon. We'll show services here as soon as we go live."
    return "Home services are available soon in your city. We'll show them here as soon as we go live."


def _city_payload(city):
    return {
        'id': str(city.id),
        'name': city.name,
        'slug': city.slug,
        'state': city.state,
        'is_active': city.is_active,
    }


def _payload(*, available, city, detected_name, message, available_cities):
    return {
        'available': available,
        'city': _city_payload(city) if city is not None else None,
        'detected_name': detected_name,
        'message': message,
        'available_cities': [_city_payload(item) for item in available_cities],
    }
