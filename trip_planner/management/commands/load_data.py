import csv
import time
from decimal import Decimal

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from trip_planner.models import FuelStation, Place
from trip_planner.text import US_STATES, city_key


class Command(BaseCommand):
    help = "Load city centroids and fuel stations (with coordinates) into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--lookup-missing",
            action="store_true",
            help="Resolve cities missing from the Gazetteer through Nominatim (1 request/second) "
            "and save them to data/city_lookup_extra.csv for future loads.",
        )

    def handle(self, *args, **options):
        config = settings.TRIP_PLANNER
        places = self.load_places(config["PLACES_CSV"])
        extra = self.read_extra(config["CITY_LOOKUP_CSV"])
        stations = self.read_stations(config["FUEL_PRICES_CSV"])

        missing = sorted({(s["city"], s["state"]) for s in stations.values()
                          if self.locate(s, places, extra) is None})
        if missing and options["lookup_missing"]:
            self.lookup_cities(missing, extra, config)
            self.write_extra(config["CITY_LOOKUP_CSV"], extra)

        records, skipped = [], []
        for opis_id, row in stations.items():
            point = self.locate(row, places, extra)
            if point is None:
                skipped.append(f"{row['city']}, {row['state']}")
                continue
            records.append(FuelStation(opis_id=opis_id, latitude=point[0], longitude=point[1], **row))

        with transaction.atomic():
            FuelStation.objects.all().delete()
            FuelStation.objects.bulk_create(records, batch_size=1000)

        self.stdout.write(self.style.SUCCESS(f"Loaded {len(records)} US fuel stations."))
        if skipped:
            self.stdout.write(self.style.WARNING(
                f"Skipped {len(skipped)} stations in {len(set(skipped))} unknown cities "
                "(run with --lookup-missing to resolve them)."
            ))

    def load_places(self, path):
        places, records = {}, []
        with open(path, newline="") as handle:
            for row in csv.DictReader(handle):
                lat, lon = float(row["latitude"]), float(row["longitude"])
                places[(row["state"], row["key"])] = (lat, lon)
                records.append(Place(state=row["state"], name=row["name"], key=row["key"],
                                     latitude=lat, longitude=lon))
        with transaction.atomic():
            Place.objects.all().delete()
            Place.objects.bulk_create(records, batch_size=5000)
        self.stdout.write(f"Loaded {len(records)} places.")
        return places

    @staticmethod
    def read_stations(path):
        # US rows only, lowest price per OPIS id
        stations = {}
        with open(path, newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                state = row["State"].strip().upper()
                if state not in US_STATES:
                    continue
                opis_id = int(row["OPIS Truckstop ID"])
                price = Decimal(row["Retail Price"].strip())
                if opis_id in stations and stations[opis_id]["retail_price"] <= price:
                    continue
                rack = row["Rack ID"].strip()
                stations[opis_id] = {
                    "name": row["Truckstop Name"].strip(),
                    "address": row["Address"].strip(),
                    "city": row["City"].strip(),
                    "state": state,
                    "rack_id": int(rack) if rack.isdigit() else None,
                    "retail_price": price,
                }
        return stations

    @staticmethod
    def locate(row, places, extra):
        key = (row["state"], city_key(row["city"]))
        return places.get(key) or extra.get(key)

    @staticmethod
    def read_extra(path):
        extra = {}
        try:
            with open(path, newline="") as handle:
                for row in csv.DictReader(handle):
                    extra[(row["state"], row["key"])] = (
                        float(row["latitude"]), float(row["longitude"]))
        except FileNotFoundError:
            pass
        return extra

    @staticmethod
    def write_extra(path, extra):
        with open(path, "w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["state", "key", "latitude", "longitude"])
            for (state, key), (lat, lon) in sorted(extra.items()):
                writer.writerow([state, key, f"{lat:.6f}", f"{lon:.6f}"])

    def lookup_cities(self, missing, extra, config):
        session = requests.Session()
        session.headers["User-Agent"] = config["HTTP_USER_AGENT"]
        self.stdout.write(f"Looking up {len(missing)} cities through Nominatim...")
        for city, state in missing:
            response = session.get(
                f"{config['NOMINATIM_URL']}/search",
                params={"city": city, "state": US_STATES[state], "country": "USA",
                        "format": "jsonv2", "limit": 1},
                timeout=config["HTTP_TIMEOUT_SECONDS"],
            )
            results = response.json() if response.ok else []
            if results:
                extra[(state, city_key(city))] = (float(results[0]["lat"]), float(results[0]["lon"]))
            else:
                self.stdout.write(self.style.WARNING(f"  not found: {city}, {state}"))
            time.sleep(1.1)  # nominatim limit: 1 req/s
