from rest_framework import serializers


class TripRequestSerializer(serializers.Serializer):
    start = serializers.CharField(max_length=200, help_text="'City, ST', a street address or 'lat,lon'.")
    finish = serializers.CharField(max_length=200, help_text="'City, ST', a street address or 'lat,lon'.")
    include_geometry = serializers.BooleanField(default=True, required=False)
