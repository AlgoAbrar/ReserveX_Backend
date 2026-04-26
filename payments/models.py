from django.db import models, transaction
from django.utils import timezone
from decimal import Decimal
import uuid


# ==================== PAYMENT ====================

class Payment(models.Model):

    class Status(models.TextChoices):
        PENDING = 'PENDING'
        SUCCESS = 'SUCCESS'
        FAILED = 'FAILED'
        REFUNDED = 'REFUNDED'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_id = models.CharField(max_length=100, unique=True, blank=True)

    booking = models.OneToOneField('bookings.Booking', on_delete=models.CASCADE)
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    created_at = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = f"TXN-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def mark_success(self):
        self.status = self.Status.SUCCESS
        self.save()

        # confirm booking
        self.booking.status = 'CONFIRMED'
        self.booking.save()

    def mark_failed(self):
        self.status = self.Status.FAILED
        self.save()

    def refund(self):
        self.status = self.Status.REFUNDED
        self.save()

        self.booking.status = 'CANCELLED'
        self.booking.save()

    def __str__(self):
        return f"{self.transaction_id} - {self.status}"


# ==================== PAYMENT LOG ====================

class PaymentLog(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='logs')
    message = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.payment.transaction_id} - {self.message[:20]}"


# ==================== PAYMENT METHOD ====================

class PaymentMethod(models.Model):
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)

    method_type = models.CharField(max_length=20)  # CARD / PAYPAL
    token = models.CharField(max_length=255)

    is_default = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.is_default:
            PaymentMethod.objects.filter(user=self.user).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.method_type}"


# ==================== REFUND ====================

class Refund(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(default=timezone.now)

    def process(self):
        with transaction.atomic():
            self.payment.refund()