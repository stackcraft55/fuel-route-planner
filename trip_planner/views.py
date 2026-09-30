from urllib.parse import urlencode

from django.shortcuts import render
from django.urls import reverse
from rest_framework.response import Response
from rest_framework.views import APIView

from trip_planner.exceptions import TripPlanningError
from trip_planner.serializers import TripRequestSerializer
from trip_planner.services.planner import plan_trip


def error_body(error):
    return {"error": {"code": error.code, "message": error.message}}


class TripPlanView(APIView):
    def get(self, request):
        return self.plan(request, request.query_params)

    def post(self, request):
        return self.plan(request, request.data)

    def plan(self, request, data):
        serializer = TripRequestSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        params = serializer.validated_data

        try:
            payload, _ = plan_trip(params["start"], params["finish"])
        except TripPlanningError as error:
            return Response(error_body(error), status=error.status_code)

        payload = dict(payload)
        if not params["include_geometry"]:
            payload["route"] = {k: v for k, v in payload["route"].items() if k != "geometry"}
        query = urlencode({"start": params["start"], "finish": params["finish"]})
        payload["map_url"] = request.build_absolute_uri(f"{reverse('trip-map')}?{query}")
        return Response(payload)


def trip_map(request):
    serializer = TripRequestSerializer(data=request.GET)
    if not serializer.is_valid():
        return render(request, "trip_planner/map.html",
                      {"error": "Both 'start' and 'finish' query parameters are required."}, status=400)
    params = serializer.validated_data
    try:
        payload, candidates = plan_trip(params["start"], params["finish"])
    except TripPlanningError as error:
        return render(request, "trip_planner/map.html", {"error": error.message}, status=error.status_code)
    return render(request, "trip_planner/map.html", {
        "trip": payload,
        "trip_data": {"trip": payload, "candidates": candidates},
    })


class ApiRootView(APIView):
    def get(self, request):
        example = urlencode({"start": "New York, NY", "finish": "Los Angeles, CA"})
        return Response({
            "plan_trip": request.build_absolute_uri(f"{reverse('trip-plan')}?{example}"),
            "map": request.build_absolute_uri(f"{reverse('trip-map')}?{example}"),
            "parameters": {
                "start": "'City, ST', a US street address, or 'latitude,longitude'",
                "finish": "'City, ST', a US street address, or 'latitude,longitude'",
                "include_geometry": "true/false - include the GeoJSON route line (default true)",
            },
        })
