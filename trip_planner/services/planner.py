import hashlib
import time

import numpy as np
from django.conf import settings
from django.core.cache import cache

from trip_planner.services import geocoding, routing
from trip_planner.services.geometry import simplify
from trip_planner.services.http import ApiCallCounter
from trip_planner.services.optimizer import plan_fuel_stops
from trip_planner.services.stations import get_station_index

GEOMETRY_TOLERANCE_DEGREES = 0.001  # ~100 m


def plan_trip(start_query, finish_query):
    cache_key = "trip:" + hashlib.sha1(
        f"{start_query.strip().lower()}|{finish_query.strip().lower()}".encode()
    ).hexdigest()
    cached = cache.get(cache_key)
    if cached:
        payload, candidates = cached
        payload = {**payload, "meta": {**payload["meta"], "cached": True, "external_api_calls": 0,
                                       "external_api_services": [],
                                       "processing_ms": 0}}
        return payload, candidates

    started = time.perf_counter()
    options = settings.TRIP_PLANNER
    counter = ApiCallCounter()

    start = geocoding.resolve(start_query, counter)
    finish = geocoding.resolve(finish_query, counter)
    route = routing.fetch_route(start, finish, counter)

    stations = get_station_index().along_route(route, options["CORRIDOR_MILES"])
    stops = plan_fuel_stops(
        stations,
        total_miles=route.distance_miles,
        range_miles=options["VEHICLE_RANGE_MILES"],
        miles_per_gallon=options["MILES_PER_GALLON"],
        stop_overhead=options["STOP_OVERHEAD_DOLLARS"],
    )

    total_cost = sum(stop.cost for stop in stops)
    total_gallons = sum(stop.gallons for stop in stops)
    tank = options["VEHICLE_RANGE_MILES"] / options["MILES_PER_GALLON"]
    fuel_used = route.distance_miles / options["MILES_PER_GALLON"]

    line = simplify(np.column_stack((route.longitudes, route.latitudes)), GEOMETRY_TOLERANCE_DEGREES)
    payload = {
        "start": start.as_dict(),
        "finish": finish.as_dict(),
        "route": {
            "distance_miles": round(route.distance_miles, 1),
            "duration_hours": round(route.duration_seconds / 3600, 2),
            "geometry": {"type": "LineString", "coordinates": np.round(line, 5).tolist()},
        },
        "fuel_stops": [
            {
                "stop": number,
                "station_id": stop.station.station_id,
                "name": stop.station.name,
                "address": stop.station.address,
                "city": stop.station.city,
                "state": stop.station.state,
                "latitude": round(stop.station.latitude, 6),
                "longitude": round(stop.station.longitude, 6),
                "mile_marker": round(stop.station.mile_marker, 1),
                "distance_from_route_miles": round(stop.station.distance_from_route, 1),
                "price_per_gallon": round(stop.station.price, 3),
                "fuel_on_arrival_gallons": round(stop.fuel_on_arrival, 2),
                "gallons_purchased": round(stop.gallons, 2),
                "cost": round(stop.cost, 2),
            }
            for number, stop in enumerate(stops, start=1)
        ],
        "summary": {
            "total_fuel_cost": round(total_cost, 2),
            "total_gallons_purchased": round(total_gallons, 2),
            "total_gallons_used": round(fuel_used, 2),
            "number_of_stops": len(stops),
            "stations_near_route": len(stations),
            "vehicle": {
                "range_miles": options["VEHICLE_RANGE_MILES"],
                "miles_per_gallon": options["MILES_PER_GALLON"],
                "tank_gallons": tank,
            },
            "assumptions": [
                "The vehicle leaves the start with a full tank; total_fuel_cost covers fuel bought on the way.",
                "Only as much fuel as needed is bought, so the vehicle arrives close to empty.",
                f"Stations within {options['CORRIDOR_MILES']:g} miles of the route are considered.",
                f"Stops that would save less than ${options['STOP_OVERHEAD_DOLLARS']:g} are skipped.",
            ],
        },
        "meta": {
            "cached": False,
            "external_api_calls": counter.total,
            "external_api_services": counter.calls,
            "processing_ms": round((time.perf_counter() - started) * 1000),
        },
    }
    candidates = [
        {"name": s.name, "city": s.city, "state": s.state, "price": round(s.price, 3),
         "latitude": s.latitude, "longitude": s.longitude, "mile_marker": round(s.mile_marker, 1)}
        for s in stations
    ]
    cache.set(cache_key, (payload, candidates))
    return payload, candidates
