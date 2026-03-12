from typing import override

from django.db import models


class Product(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        OUT_OF_STOCK = "out_of_stock", "Out of Stock"
        HIDDEN = "hidden", "Hidden"

    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_count = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=Status,
        default=Status.AVAILABLE,
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    @override
    def __str__(self) -> str:
        return self.name
