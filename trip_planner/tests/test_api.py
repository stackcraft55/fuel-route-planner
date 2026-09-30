from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from trip_planner.models import FuelStation, Place
from trip_planner.services import stations as station_service
from trip_planner.services.geocoding import lookup_place

# straight road along lon -100, ~1036 miles
ROUTE_COORDINATES = [[-100.0, 30.0 + i * 0.5] for i in range(31)]


def fake_osrm(url, params=None, timeout=None):
    response = mock.Mock(status_code=200)
    response.json.return_value = {
        "code": "Ok",
        "routes": [{"geometry": {"coordinates": ROUTE_COORDINATES}, "distance": 1_667_000, "duration": 54_000}],
    }
    return response


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                                       "LOCATION": "tests"}})
class TripPlanApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Place.objects.create(state="TX", name="Southville", key="southville", latitude=30.0, longitude=-100.0)
        Place.objects.create(state="NE", name="Northville", key="northville", latitude=45.0, longitude=-100.0)
        rows = [(1, "CHEAP STOP", 33.0, "2.90"), (2, "PRICEY STOP", 34.0, "4.50"),
                (3, "MIDDLE STOP", 37.0, "3.20"), (4, "FAR AWAY STOP", 37.0, "1.00"),
                (5, "NORTH STOP", 41.0, "3.50")]
        for opis_id, name, lat, price in rows:
            lon = -100.0 if opis_id != 4 else -97.0  # station 4 is ~165 miles off the route
            FuelStation.objects.create(opis_id=opis_id, name=name, address="I-00 Exit 1", city="Town",
                                       state="TX", retail_price=Decimal(price), latitude=lat, longitude=lon)

    def setUp(self):
        cache.clear()
        station_service.reset_station_index()
        self.client = APIClient()

    @mock.patch("trip_planner.services.http.requests.Session.get", side_effect=fake_osrm)
    def test_plan_uses_one_routing_call_and_cheapest_stops(self, http_get):
        response = self.client.get("/api/route/", {"start": "Southville, TX", "finish": "Northville, Nebraska"})
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()

        self.assertEqual(http_get.call_count, 1)
        self.assertEqual(body["meta"]["external_api_calls"], 1)
        names = [stop["name"] for stop in body["fuel_stops"]]
        self.assertNotIn("FAR AWAY STOP", names)
        self.assertNotIn("PRICEY STOP", names)
        self.assertIn("CHEAP STOP", names)
        self.assertEqual(body["summary"]["total_fuel_cost"],
                         round(sum(stop["cost"] for stop in body["fuel_stops"]), 2))
        self.assertEqual(body["route"]["geometry"]["type"], "LineString")
        self.assertIn("/api/route/map/?", body["map_url"])

    @mock.patch("trip_planner.services.http.requests.Session.get", side_effect=fake_osrm)
    def test_repeat_request_is_served_from_cache(self, http_get):
        params = {"start": "30.0,-100.0", "finish": "45.0,-100.0"}
        self.client.get("/api/route/", params)
        second = self.client.post("/api/route/", params, format="json").json()
        self.assertEqual(http_get.call_count, 1)
        self.assertTrue(second["meta"]["cached"])

    @mock.patch("trip_planner.services.http.requests.Session.get", side_effect=fake_osrm)
    def test_map_page_renders(self, http_get):
        response = self.client.get("/api/route/map/", {"start": "Southville, TX", "finish": "Northville, NE"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CHEAP STOP")

    def test_missing_parameters(self):
        response = self.client.get("/api/route/", {"start": "Southville, TX"})
        self.assertEqual(response.status_code, 400)

    def test_coordinates_outside_usa_are_rejected(self):
        response = self.client.get("/api/route/", {"start": "51.5,-0.12", "finish": "Southville, TX"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "location_not_found")

    def test_place_lookup_formats(self):
        for text in ["Southville, TX", "southville tx", "Southville, Texas, USA", "SOUTHVILLE TX 78000"]:
            self.assertIsNotNone(lookup_place(text), text)
