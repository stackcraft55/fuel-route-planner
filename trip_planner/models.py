from django.db import models


class Place(models.Model):
    # city centroid from the Census Gazetteer

    state = models.CharField(max_length=2)
    name = models.CharField(max_length=120)
    key = models.CharField(max_length=120)
    latitude = models.FloatField()
    longitude = models.FloatField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["state", "key"], name="unique_place_key")]
        indexes = [models.Index(fields=["state", "key"])]

    def __str__(self):
        return f"{self.name}, {self.state}"


class FuelStation(models.Model):
    opis_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=120)
    state = models.CharField(max_length=2)
    rack_id = models.IntegerField(null=True, blank=True)
    retail_price = models.DecimalField(max_digits=8, decimal_places=5)
    latitude = models.FloatField()
    longitude = models.FloatField()

    class Meta:
        ordering = ["opis_id"]

    def __str__(self):
        return f"{self.name} ({self.city}, {self.state}) ${self.retail_price}"
