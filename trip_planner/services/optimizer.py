import math
from dataclasses import dataclass

import numpy as np

from trip_planner.exceptions import UnreachableSegment

# 0.1 gal steps
GALLON_RESOLUTION = 0.1


@dataclass
class FuelStop:
    station: object
    gallons: float
    fuel_on_arrival: float

    @property
    def cost(self):
        return self.gallons * self.station.price


def plan_fuel_stops(stations, total_miles, range_miles, miles_per_gallon,
                    start_fuel=None, stop_overhead=0.0):
    # DP over tank levels. stations sorted by mile_marker.
    # leaving[L] = min cost to leave the current station with L units in the tank.
    # stop_overhead is added per stop during the search only.
    unit = GALLON_RESOLUTION
    tank_units = int(round(range_miles / miles_per_gallon / unit))
    start_units = tank_units if start_fuel is None else min(int(start_fuel / unit), tank_units)
    miles_per_unit = miles_per_gallon * unit
    levels = np.arange(tank_units + 1)

    def units_at(mile):
        # round up so the plan never assumes extra range
        return math.ceil(mile / miles_per_unit - 1e-9)

    ahead = [s for s in stations if 0 <= s.mile_marker < total_miles]
    positions = [units_at(s.mile_marker) for s in ahead]

    leaving = np.full(tank_units + 1, np.inf)
    leaving[start_units] = 0.0
    history = []  # level bought from, -1 if no stop
    previous = 0

    for station, position in zip(ahead, positions):
        arriving = shift_down(leaving, position - previous)
        price = station.price * unit

        adjusted = arriving - levels * price
        best = np.minimum.accumulate(adjusted)
        best_from = np.maximum.accumulate(np.where(adjusted <= best, levels, 0))
        with_stop = best + levels * price + stop_overhead
        if position * miles_per_unit > station.mile_marker + 1e-9:
            # real fuel is up to 1 unit above the plan here, so no filling to the top
            with_stop[-1] = np.inf

        stopped = with_stop < arriving - 1e-9
        leaving = np.where(stopped, with_stop, arriving)
        history.append(np.where(stopped, best_from, -1))
        previous = position

    last_leg = units_at(total_miles) - previous
    finish = shift_down(leaving, last_leg)
    if not np.isfinite(finish).any():
        raise UnreachableSegment(describe_gap(ahead, total_miles, range_miles))

    # on a tie, finish with less fuel
    level = int(np.flatnonzero(finish <= finish.min() + 1e-9)[0]) + last_leg

    stops = []
    for index in range(len(ahead) - 1, -1, -1):
        bought_from = history[index][level]
        if 0 <= bought_from < level:
            stops.append(FuelStop(
                station=ahead[index],
                gallons=(level - bought_from) * unit,
                fuel_on_arrival=bought_from * unit,
            ))
            level = bought_from
        if index:
            level += positions[index] - positions[index - 1]
    stops.reverse()
    return settle_real_fuel(stops, range_miles / miles_per_gallon,
                            start_units * unit, miles_per_gallon)


def settle_real_fuel(stops, tank, start_fuel, miles_per_gallon):
    # recompute fuel levels with exact mileage
    fuel, position = start_fuel, 0.0
    for stop in stops:
        fuel -= (stop.station.mile_marker - position) / miles_per_gallon
        stop.fuel_on_arrival = max(fuel, 0.0)
        stop.gallons = min(stop.gallons, tank - stop.fuel_on_arrival)
        fuel = stop.fuel_on_arrival + stop.gallons
        position = stop.station.mile_marker
    return stops


def shift_down(costs, used):
    if used <= 0:
        return costs.copy()
    shifted = np.full_like(costs, np.inf)
    if used < len(costs):
        shifted[:-used] = costs[used:]
    return shifted


def describe_gap(stations, total_miles, range_miles):
    markers = [0.0] + [s.mile_marker for s in stations] + [total_miles]
    for before, after in zip(markers, markers[1:]):
        if after - before > range_miles:
            return (f"No fuel station between mile {before:.0f} and mile {after:.0f} "
                    f"of the route; the vehicle range is {range_miles:.0f} miles.")
    return "The route cannot be completed with the available fuel stations."
