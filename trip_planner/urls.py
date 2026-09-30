from django.urls import path

from trip_planner import views

urlpatterns = [
    path("", views.ApiRootView.as_view(), name="api-root"),
    path("route/", views.TripPlanView.as_view(), name="trip-plan"),
    path("route/map/", views.trip_map, name="trip-map"),
]
