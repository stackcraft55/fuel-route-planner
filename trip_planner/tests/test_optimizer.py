import random
from dataclasses import dataclass

from django.test import SimpleTestCase

from trip_planner.exceptions import UnreachableSegment
from trip_planner.services.optimizer import plan_fuel_stops


@dataclass
class Stop:
    mile_marker: float
    price: float


def plan(stations, total, start_fuel=None, stop_overhead=0.0):
    return plan_fuel_stops(stations, total_miles=total, range_miles=500, miles_per_gallon=10,
                           start_fuel=start_fuel, stop_overhead=stop_overhead)


class PlanFuelStopsTests(SimpleTestCase):
    def test_short_trip_needs_no_stop(self):
        self.assertEqual(plan([Stop(100, 3.0)], total=450), [])

    def test_buys_only_what_is_needed_to_finish(self):
        stops = plan([Stop(400, 3.0)], total=700)
        self.assertEqual(len(stops), 1)
        # 10 gal left at mile 400, 30 gal needed to finish
        self.assertAlmostEqual(stops[0].gallons, 20)
        self.assertAlmostEqual(stops[0].cost, 60)

    def test_prefers_cheaper_station_further_ahead(self):
        stations = [Stop(300, 4.0), Stop(450, 3.0), Stop(600, 5.0)]
        stops = plan(stations, total=900)
        self.assertEqual([s.station.mile_marker for s in stops], [450])
        self.assertAlmostEqual(stops[0].gallons, 40)

    def test_fills_up_at_cheap_station_before_expensive_stretch(self):
        stations = [Stop(100, 2.0), Stop(400, 5.0), Stop(550, 5.0)]
        stops = plan(stations, total=900)
        self.assertEqual(stops[0].station.mile_marker, 100)
        self.assertAlmostEqual(stops[0].gallons, 10)
        self.assertAlmostEqual(sum(s.gallons for s in stops), 40)

    def test_total_cost_matches_exhaustive_search(self):
        stations = [Stop(120, 3.4), Stop(260, 3.1), Stop(410, 3.9), Stop(590, 2.9),
                    Stop(760, 3.6), Stop(930, 3.2), Stop(1100, 3.0)]
        total = 1350
        greedy = sum(s.cost for s in plan(stations, total))
        self.assertAlmostEqual(greedy, self.reference_min_cost(stations, total), places=6)

    def test_random_routes_match_exhaustive_search(self):
        generator = random.Random(7)
        for _ in range(40):
            miles = sorted({generator.randrange(1, 180) * 10 for _ in range(generator.randint(6, 25))})
            stations = [Stop(m, round(generator.uniform(2.8, 4.5), 3)) for m in miles]
            total = miles[-1] + generator.randrange(1, 50) * 10
            try:
                greedy = sum(s.cost for s in plan(stations, total))
            except UnreachableSegment:
                continue
            self.assertAlmostEqual(greedy, self.reference_min_cost(stations, total), places=6)

    def test_stop_overhead_skips_tiny_savings(self):
        stations = [Stop(400, 3.00), Stop(520, 2.99)]
        self.assertEqual(len(plan(stations, total=880)), 2)
        stops = plan(stations, total=880, stop_overhead=5)
        self.assertEqual(len(stops), 1)
        self.assertAlmostEqual(stops[0].gallons, 38)

    def test_fuel_never_runs_out_or_overflows(self):
        generator = random.Random(11)
        for _ in range(30):
            stations = [Stop(m + generator.random() * 40, generator.uniform(2.8, 4.5))
                        for m in range(20, 2600, generator.randint(40, 200))]
            total = 2600.4
            try:
                stops = plan(stations, total=total, stop_overhead=generator.choice([0, 5]))
            except UnreachableSegment:
                continue
            fuel, position = 50.0, 0.0
            for stop in stops:
                fuel -= (stop.station.mile_marker - position) / 10
                self.assertGreaterEqual(fuel, -1e-9)
                fuel += stop.gallons
                self.assertLessEqual(fuel, 50 + 1e-9)
                position = stop.station.mile_marker
            self.assertGreaterEqual(fuel - (total - position) / 10, -1e-9)

    def test_gap_longer_than_range_is_reported(self):
        with self.assertRaises(UnreachableSegment):
            plan([Stop(100, 3.0), Stop(700, 3.0)], total=900)

    def test_partial_start_tank(self):
        stops = plan([Stop(50, 3.0)], total=300, start_fuel=10)
        self.assertAlmostEqual(stops[0].gallons, 20)

    @staticmethod
    def reference_min_cost(stations, total):
        # brute force over whole-gallon tank levels
        tank, mpg = 50, 10
        best = {tank: 0.0}
        position = 0
        for station in stations + [Stop(total, 0.0)]:
            used = (station.mile_marker - position) / mpg
            arrived = {}
            for level, cost in best.items():
                remaining = level - used
                if remaining >= -1e-9:
                    key = round(remaining)
                    arrived[key] = min(arrived.get(key, float("inf")), cost)
            if station.mile_marker == total:
                return min(arrived.values())
            best = {}
            for level, cost in arrived.items():
                for new_level in range(level, tank + 1):
                    value = cost + (new_level - level) * station.price
                    best[new_level] = min(best.get(new_level, float("inf")), value)
            position = station.mile_marker
