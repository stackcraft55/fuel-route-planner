import threading
from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree

from trip_planner.models import FuelStation
from trip_planner.services import geometry


@dataclass
class RouteStation:
    station_id: int
    name: str
    address: str
    city: str
    state: str
    latitude: float
    longitude: float
    price: float
    mile_marker: float
    distance_from_route: float


class StationIndex:
    def __init__(self, stations):
        self.records = stations
        self.latitudes = np.array([s.latitude for s in stations], dtype=float)
        self.longitudes = np.array([s.longitude for s in stations], dtype=float)
        self.prices = np.array([float(s.retail_price) for s in stations], dtype=float)
        self.points = geometry.unit_vectors(self.latitudes, self.longitudes) if stations else np.empty((0, 3))

    def __len__(self):
        return len(self.records)

    def along_route(self, route, corridor_miles, step_miles=0.5):
        if not len(self):
            return []
        lat, lon, cumulative = geometry.densify(route.latitudes, route.longitudes, step_miles)
        # scale to the OSRM distance
        if cumulative[-1] > 0:
            cumulative *= route.distance_miles / cumulative[-1]

        # bbox prefilter
        pad = corridor_miles / 50.0 + 0.1
        in_box = np.flatnonzero(
            (self.latitudes >= lat.min() - pad) & (self.latitudes <= lat.max() + pad)
            & (self.longitudes >= lon.min() - pad * 1.5) & (self.longitudes <= lon.max() + pad * 1.5)
        )
        if not len(in_box):
            return []

        route_tree = cKDTree(geometry.unit_vectors(lat, lon))
        chord, nearest = route_tree.query(
            self.points[in_box], distance_upper_bound=geometry.miles_to_chord(corridor_miles)
        )
        hit = np.isfinite(chord)

        found = []
        for index, chord_value, route_index in zip(in_box[hit], chord[hit], nearest[hit]):
            station = self.records[index]
            found.append(RouteStation(
                station_id=station.opis_id,
                name=station.name,
                address=station.address,
                city=station.city,
                state=station.state,
                latitude=station.latitude,
                longitude=station.longitude,
                price=float(station.retail_price),
                mile_marker=float(cumulative[route_index]),
                distance_from_route=float(geometry.chord_to_miles(chord_value)),
            ))
        found.sort(key=lambda s: (s.mile_marker, s.price))
        return found


_index = None
_lock = threading.Lock()


def get_station_index():
    global _index
    if _index is None:
        with _lock:
            if _index is None:
                _index = StationIndex(list(FuelStation.objects.all()))
    return _index


def reset_station_index():
    global _index
    _index = None
