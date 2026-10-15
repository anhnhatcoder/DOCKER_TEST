from django.db import models

# Create your models here.
class Country(models.Model):
    name = models.CharField(max_length=100)
    capital = models.CharField(max_length=100)
    area = models.FloatField(help_text="Area in square kilometers")
    