import requests
from django.conf import settings

from trip_planner.exceptions import ExternalServiceError


class ApiCallCounter:
    def __init__(self):
        self.calls = []

    def record(self, service):
        self.calls.append(service)

    @property
    def total(self):
        return len(self.calls)


_session = None


def get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers["User-Agent"] = settings.TRIP_PLANNER["HTTP_USER_AGENT"]
    return _session


def get_json(url, params, service, counter):
    counter.record(service)
    try:
        response = get_session().get(
            url, params=params, timeout=settings.TRIP_PLANNER["HTTP_TIMEOUT_SECONDS"]
        )
    except requests.RequestException as exc:
        raise ExternalServiceError(f"{service} request failed: {exc}") from exc
    if response.status_code >= 500 or response.status_code == 429:
        raise ExternalServiceError(f"{service} responded with HTTP {response.status_code}.")
    try:
        return response.status_code, response.json()
    except ValueError as exc:
        raise ExternalServiceError(f"{service} returned an invalid response.") from exc
