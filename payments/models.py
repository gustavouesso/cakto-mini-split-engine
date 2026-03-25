from django.db import models
import uuid


class Payment(models.Model):
    PAYMENT_STATUS_CAPTURED = "captured"

    PAYMENT_METHOD_PIX = "pix"
    PAYMENT_METHOD_CARD = "card"

    STATUS_CHOICES = [
        (PAYMENT_STATUS_CAPTURED, "Captured"),
    ]

    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_METHOD_PIX, "PIX"),
        (PAYMENT_METHOD_CARD, "Card"),
    ]

    id = models.CharField(primary_key=True, max_length=50, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PAYMENT_STATUS_CAPTURED)

    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    platform_fee_amount = models.DecimalField(max_digits=12, decimal_places=2)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)

    currency = models.CharField(max_length=3, default="BRL")
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES)
    installments = models.PositiveSmallIntegerField(null=True, blank=True)

    idempotency_key = models.CharField(max_length=255, unique=True)
    payload_hash = models.CharField(max_length=64)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f"pmt_{uuid.uuid4().hex[:12]}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.id} - {self.status}"


class LedgerEntry(models.Model):
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="ledger_entries",
    )
    recipient_id = models.CharField(max_length=100)
    role = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.payment_id} - {self.recipient_id} - {self.amount}"


class OutboxEvent(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PUBLISHED = "published"

    TYPE_PAYMENT_CAPTURED = "payment_captured"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PUBLISHED, "Published"),
    ]

    TYPE_CHOICES = [
        (TYPE_PAYMENT_CAPTURED, "Payment Captured"),
    ]

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="outbox_events",
    )
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, default=TYPE_PAYMENT_CAPTURED)
    payload = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.type} - {self.status}"