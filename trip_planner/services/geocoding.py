import re
from dataclasses import asdict, dataclass

from django.conf import settings
from django.core.cache import cache

from trip_planner.exceptions import LocationNotFound
from trip_planner.models import Place
from trip_planner.services.http import get_json
from trip_planner.text import city_key, parse_state

# lower 48, Alaska, Hawaii
US_BOUNDS = (
    (24.4, 49.5, -125.0, -66.8),
    (51.0, 71.5, -180.0, -129.9),
    (18.8, 22.4, -160.5, -154.7),
)
_COORDINATES = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")
_COUNTRY_SUFFIX = re.compile(r",?\s*(usa|u\.s\.a\.|us|u\.s\.|united states(?: of america)?)\s*$", re.I)
_ZIP_SUFFIX = re.compile(r"\s+\d{5}(?:-\d{4})?$")


@dataclass(frozen=True)
class Location:
    query: str
    label: str
    latitude: float
    longitude: float
    source: str

    def as_dict(self):
        return asdict(self)


def inside_usa(lat, lon):
    return any(s <= lat <= n and w <= lon <= e for s, n, w, e in US_BOUNDS)


def resolve(query, counter):
    # "lat,lon" -> local place table -> nominatim
    text = query.strip()
    if not text:
        raise LocationNotFound("Location must not be empty.")

    match = _COORDINATES.match(text)
    if match:
        lat, lon = float(match.group(1)), float(match.group(2))
        if not inside_usa(lat, lon):
            raise LocationNotFound(f"'{query}' is outside the USA. Use 'latitude,longitude'.")
        return Location(query, f"{lat:.5f}, {lon:.5f}", lat, lon, "coordinates")

    local = lookup_place(text)
    if local:
        return Location(query, f"{local.name}, {local.state}", local.latitude, local.longitude, "census_gazetteer")

    return search_nominatim(query, text, counter)


def lookup_place(text):
    text = _ZIP_SUFFIX.sub("", _COUNTRY_SUFFIX.sub("", text)).strip(" ,")
    if "," in text:
        city, _, state = text.rpartition(",")
    else:
        parts = text.rsplit(" ", 2)
        # two-word states, e.g. "New York"
        if len(parts) == 3 and parse_state(" ".join(parts[1:])):
            city, state = parts[0], " ".join(parts[1:])
        elif len(parts) >= 2:
            city, state = " ".join(parts[:-1]), parts[-1]
        else:
            return None
    state_code = parse_state(state)
    if not state_code or not city.strip():
        return None
    return Place.objects.filter(state=state_code, key=city_key(city)).first()


def search_nominatim(query, text, counter):
    cache_key = f"geocode:{city_key(text)}"
    cached = cache.get(cache_key)
    if cached:
        return Location(**{**cached, "query": query})

    status, results = get_json(
        f"{settings.TRIP_PLANNER['NOMINATIM_URL']}/search",
        {"q": text, "countrycodes": "us", "format": "jsonv2", "limit": 1},
        "nominatim",
        counter,
    )
    if status != 200 or not results:
        raise LocationNotFound(f"Could not find '{query}' in the USA.")
    best = results[0]
    location = Location(query, best.get("display_name", text), float(best["lat"]), float(best["lon"]), "nominatim")
    cache.set(cache_key, location.as_dict(), timeout=60 * 60 * 24 * 30)
    return location
