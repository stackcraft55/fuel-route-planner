# Fuel Route Planner

Django API that takes a start and finish location in the USA, gets the driving route and
picks fuel stops based on price. Returns the route, the stops, the total fuel cost and a
map link.

Vehicle: 500 mile range, 10 mpg (50 gal tank).

## Setup

Python 3.12+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py load_data
python manage.py runserver
```

## Endpoints

### GET/POST `/api/route/`

| Param              | Description                                      |
|--------------------|--------------------------------------------------|
| `start`            | `City, ST`, street address or `lat,lon`          |
| `finish`           | same as `start`                                  |
| `include_geometry` | optional, `false` to skip the route line         |

```
GET /api/route/?start=New York, NY&finish=Los Angeles, CA
```

Response (shortened):

```json
{
  "start": {"label": "New York, NY", "latitude": 40.662712, "longitude": -73.938677, "source": "census_gazetteer"},
  "finish": {"label": "Los Angeles, CA", "latitude": 34.019394, "longitude": -118.410825, "source": "census_gazetteer"},
  "route": {"distance_miles": 2810.4, "duration_hours": 50.31, "geometry": {"type": "LineString", "coordinates": []}},
  "fuel_stops": [
    {
      "stop": 1,
      "name": "SHEETZ #639",
      "city": "Youngstown",
      "state": "OH",
      "mile_marker": 396.0,
      "price_per_gallon": 3.059,
      "gallons_purchased": 36.5,
      "cost": 111.65
    }
  ],
  "summary": {"total_fuel_cost": 710.6, "total_gallons_purchased": 231.1, "number_of_stops": 6},
  "meta": {"cached": false, "external_api_calls": 1},
  "map_url": "http://127.0.0.1:8000/api/route/map/?start=New+York%2C+NY&finish=Los+Angeles%2C+CA"
}
```

Errors: `{"error": {"code": "...", "message": "..."}}` with 400 (location not found or
outside the USA), 422 (no route, or a gap over 500 miles with no station) or 502 (upstream
service failed).

### GET `/api/route/map/`

Same params. Leaflet map with the route and the stops.

A Postman collection is in `docs/`.

## How it works

- **Locations.** `City, ST` is looked up in a local table of Census Gazetteer centroids.
  `lat,lon` is used directly. Other addresses go to Nominatim.
- **Route.** One request to the public OSRM server.
- **Stations near the route.** The route line is split into 0.5 mile points and put in a
  KD-tree. Stations within 5 miles of the line are kept, each with its mile marker.
- **Stops.** Dynamic programming over tank level in 0.1 gal steps. A $5 per-stop penalty
  keeps it from stopping just to save a few cents. The penalty is not included in the
  cost; set `STOP_OVERHEAD_DOLLARS=0` to turn it off.
- **Cache.** Routes and results are cached in memory.

A normal request makes one external call (OSRM). A street-address input adds a Nominatim
call for each end.

## Data

The price file only has city and state, so `load_data` gives each station its city's
coordinates from the Census Gazetteer (`data/us_places.csv`). About 150 small towns missing
from the Gazetteer are in `data/city_lookup_extra.csv`. 6,620 of 6,626 US stations are
loaded. Canadian rows are skipped. Duplicate OPIS ids keep the lowest price.

## Assumptions

- The tank is full at the start. `total_fuel_cost` is what is paid at the stops.
- Only the fuel needed to reach the destination is bought.
- The detour to a station is not counted.

## Settings

Environment variables: `VEHICLE_RANGE_MILES` (500), `MILES_PER_GALLON` (10),
`CORRIDOR_MILES` (5), `STOP_OVERHEAD_DOLLARS` (5), `OSRM_URL`, `NOMINATIM_URL`.

## Tests

```bash
python manage.py test trip_planner
```
