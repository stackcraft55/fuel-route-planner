import csv
import io
import re
import zipfile

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from trip_planner.text import US_STATES, city_key

GAZETTEER_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/{year}_Gazetteer/{year}_Gaz_{kind}_national.zip"
# places first, county subdivisions as fallback
SOURCES = ("place", "cousubs")

_TYPE_SUFFIX = re.compile(
    r"\s+(city and borough|consolidated government|unified government|metro government|"
    r"metropolitan government|urban county|charter township|city|town|village|borough|cdp|"
    r"municipality|township|plantation|gore|grant|location|purchase)$",
    re.IGNORECASE,
)
_PARENTHESES = re.compile(r"\s*\(.*?\)")


def name_variants(raw_name):
    # "Oklahoma City city" -> ["Oklahoma City city", "Oklahoma City"]
    name = _PARENTHESES.sub("", raw_name).strip()
    variants = [name]
    stripped = _TYPE_SUFFIX.sub("", name)
    if stripped != name:
        variants.append(stripped)
    return variants


class Command(BaseCommand):
    help = "Download the Census Gazetteer files and build data/us_places.csv (city centroids)."

    def add_arguments(self, parser):
        parser.add_argument("--year", default="2024")

    def handle(self, *args, **options):
        places = {}
        for kind in SOURCES:
            url = GAZETTEER_URL.format(year=options["year"], kind=kind)
            self.stdout.write(f"Downloading {url}")
            response = requests.get(url, timeout=120)
            response.raise_for_status()
            archive = zipfile.ZipFile(io.BytesIO(response.content))
            text = archive.read(archive.namelist()[0]).decode("latin-1")

            found = {}
            reader = csv.reader(io.StringIO(text), delimiter="\t")
            next(reader)
            for row in reader:
                row = [cell.strip() for cell in row]
                state, raw_name, land_area = row[0], row[3], float(row[6] or 0)
                if state not in US_STATES:
                    continue
                lat, lon = float(row[-2]), float(row[-1])
                for variant in name_variants(raw_name):
                    key = (state, city_key(variant))
                    # same name in one state: keep the larger one
                    if key not in found or land_area > found[key][3]:
                        found[key] = (variant, lat, lon, land_area)
            for key, value in found.items():
                places.setdefault(key, value)

        output = settings.TRIP_PLANNER["PLACES_CSV"]
        with open(output, "w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["state", "name", "key", "latitude", "longitude"])
            for (state, key), (name, lat, lon, _) in sorted(places.items()):
                writer.writerow([state, name, key, f"{lat:.6f}", f"{lon:.6f}"])
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(places)} places to {output}"))
