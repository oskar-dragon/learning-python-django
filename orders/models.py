from typing import override

from django.db import models


class Order(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft"
        PENDING = "pending"
        SHIPPED = "shipped"
        CANCELLED = "cancelled"

    customer_name = models.CharField(max_length=255)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    items_count = models.IntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    tracking_number = models.CharField(max_length=100, null=True, blank=True)  # noqa: DJ001
    shipped_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=255, null=True, blank=True)  # noqa: DJ001
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @override
    def __str__(self) -> str:
        return f"Order {self.pk} ({self.status})"
