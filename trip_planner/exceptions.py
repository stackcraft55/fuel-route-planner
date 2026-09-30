class TripPlanningError(Exception):
    status_code = 400
    code = "trip_planning_error"

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class LocationNotFound(TripPlanningError):
    status_code = 400
    code = "location_not_found"


class RouteNotFound(TripPlanningError):
    status_code = 422
    code = "route_not_found"


class UnreachableSegment(TripPlanningError):
    status_code = 422
    code = "no_fuel_available"


class ExternalServiceError(TripPlanningError):
    status_code = 502
    code = "upstream_service_error"
