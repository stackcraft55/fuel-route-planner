from dataclasses import dataclass

import numpy as np
from django.conf import settings
from django.core.cache import cache

from trip_planner.exceptions import RouteNotFound
from trip_planner.services.http import get_json

METERS_PER_MILE = 1609.344


@dataclass
class Route:
    latitudes: np.ndarray
    longitudes: np.ndarray
    distance_miles: float
    duration_seconds: float


def fetch_route(start, finish, counter):
    coordinates = f"{start.longitude:.6f},{start.latitude:.6f};{finish.longitude:.6f},{finish.latitude:.6f}"
    cache_key = f"route:{coordinates}"
    payload = cache.get(cache_key)

    if payload is None:
        status, body = get_json(
            f"{settings.TRIP_PLANNER['OSRM_URL']}/route/v1/driving/{coordinates}",
            {"overview": "full", "geometries": "geojson", "alternatives": "false", "steps": "false"},
            "osrm",
            counter,
        )
        if status != 200 or body.get("code") != "Ok" or not body.get("routes"):
            raise RouteNotFound(body.get("message") or "No drivable route was found between these locations.")
        best = body["routes"][0]
        payload = {
            "coordinates": best["geometry"]["coordinates"],
            "distance": best["distance"],
            "duration": best["duration"],
        }
        cache.set(cache_key, payload, timeout=60 * 60 * 24)

    points = np.asarray(payload["coordinates"], dtype=float)
    return Route(
        latitudes=points[:, 1],
        longitudes=points[:, 0],
        distance_miles=payload["distance"] / METERS_PER_MILE,
        duration_seconds=payload["duration"],
    )
