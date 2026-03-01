from django.db import models

# Create your models here.
"""
Payments App Models
Payment processing models for ReserveX restaurant reservation system
"""

from django.db import models, transaction
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
import uuid
import hashlib
import hmac
import json
from decimal import Decimal


class Payment(models.Model):
    """
    Payment model representing a payment transaction for a booking
    
    Payment flow:
    1. User initiates payment for booking (PENDING)
    2. Payment gateway processes (PROCESSING)
    3. Payment completed (SUCCESS) or failed (FAILED)
    4. On success: booking status updated to CONFIRMED
    """
    
    class PaymentMethod(models.TextChoices):
        CREDIT_CARD = 'CREDIT_CARD', _('Credit Card')
        DEBIT_CARD = 'DEBIT_CARD', _('Debit Card')
        PAYPAL = 'PAYPAL', _('PayPal')
        BANK_TRANSFER = 'BANK_TRANSFER', _('Bank Transfer')
        CASH = 'CASH', _('Cash')
        GIFT_CARD = 'GIFT_CARD', _('Gift Card')
    
    class PaymentStatus(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        PROCESSING = 'PROCESSING', _('Processing')
        SUCCESS = 'SUCCESS', _('Success')
        FAILED = 'FAILED', _('Failed')
        REFUNDED = 'REFUNDED', _('Refunded')
        PARTIALLY_REFUNDED = 'PARTIALLY_REFUNDED', _('Partially Refunded')
        CANCELLED = 'CANCELLED', _('Cancelled')
    
    # Primary identifier
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_index=True)
    transaction_id = models.CharField(
        _('transaction ID'),
        max_length=100,
        unique=True,
        db_index=True,
        help_text=_('Payment gateway transaction ID')
    )
    
    # Relationships
    booking = models.OneToOneField(
        'bookings.Booking',
        on_delete=models.PROTECT,
        related_name='payment',
        db_index=True
    )
    user = models.ForeignKey(
        'users.User',
        on_delete=models.PROTECT,
        related_name='payments',
        db_index=True
    )
    
    # Payment details
    amount = models.DecimalField(
        _('amount'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(_('currency'), max_length=3, default='USD')
    
    payment_method = models.CharField(
        _('payment method'),
        max_length=20,
        choices=PaymentMethod.choices,
        db_index=True
    )
    payment_status = models.CharField(
        _('payment status'),
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True
    )
    
    # Gateway information
    gateway = models.CharField(_('payment gateway'), max_length=50, default='STRIPE')
    gateway_response = models.JSONField(
        _('gateway response'),
        default=dict,
        blank=True,
        help_text=_('Raw response from payment gateway')
    )
    
    # Receipt
    receipt_url = models.URLField(_('receipt URL'), max_length=500, blank=True)
    receipt_number = models.CharField(_('receipt number'), max_length=100, blank=True)
    
    # Refund information
    refund_amount = models.DecimalField(
        _('refund amount'),
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    refund_reason = models.TextField(_('refund reason'), blank=True)
    refunded_at = models.DateTimeField(_('refunded at'), null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(_('metadata'), default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    completed_at = models.DateTimeField(_('completed at'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('payment')
        verbose_name_plural = _('payments')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transaction_id']),
            models.Index(fields=['user', 'payment_status']),
            models.Index(fields=['booking', 'payment_status']),
            models.Index(fields=['payment_status', 'created_at']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0.01),
                name='valid_payment_amount'
            ),
            models.CheckConstraint(
                condition=models.Q(refund_amount__gte=0),
                name='valid_refund_amount'
            ),
        ]
    
    def __str__(self):
        return f"{self.transaction_id} - {self.booking.booking_id} - {self.payment_status}"
    
    def save(self, *args, **kwargs):
        """Generate transaction ID if not provided"""
        if not self.transaction_id:
            self.transaction_id = self._generate_transaction_id()
        super().save(*args, **kwargs)
    
    def _generate_transaction_id(self):
        """Generate unique transaction ID"""
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        random_part = uuid.uuid4().hex[:8].upper()
        return f"TXN-{timestamp}-{random_part}"
    
    def process_success(self, gateway_response=None):
        """Process successful payment"""
        with transaction.atomic():
            self.payment_status = self.PaymentStatus.SUCCESS
            self.completed_at = timezone.now()
            if gateway_response:
                self.gateway_response = gateway_response
            self.save()
            
            # Confirm the booking
            self.booking.confirm_booking()
            
            # Create payment success notification
            self._create_notification('SUCCESS')
    
    def process_failure(self, gateway_response=None, error_message=''):
        """Process failed payment"""
        with transaction.atomic():
            self.payment_status = self.PaymentStatus.FAILED
            if gateway_response:
                self.gateway_response = gateway_response
            self.metadata['error_message'] = error_message
            self.save()
            
            # Create payment failure notification
            self._create_notification('FAILED', error_message)
    
    def process_refund(self, amount=None, reason=''):
        """Process refund for this payment"""
        with transaction.atomic():
            refund_amount = Decimal(amount) if amount else self.amount
            
            if refund_amount > self.amount - self.refund_amount:
                raise ValidationError("Refund amount exceeds remaining payment amount.")
            
            self.refund_amount += refund_amount
            self.refund_reason = reason
            self.refunded_at = timezone.now()
            
            if self.refund_amount >= self.amount:
                self.payment_status = self.PaymentStatus.REFUNDED
            else:
                self.payment_status = self.PaymentStatus.PARTIALLY_REFUNDED
            
            self.save()
            
            # Update booking status if fully refunded
            if self.payment_status == self.PaymentStatus.REFUNDED:
                self.booking.status = 'CANCELLED'
                self.booking.save()
            
            # Create refund notification
            self._create_notification('REFUNDED', f"Refunded: {refund_amount} {self.currency}")
    
    def _create_notification(self, notification_type, error_message=''):
        """Create payment notification"""
        from bookings.models import BookingNotification
        
        subject_map = {
            'SUCCESS': 'Payment Successful - Your Booking is Confirmed',
            'FAILED': 'Payment Failed - Please Try Again',
            'REFUNDED': 'Payment Refunded',
        }
        
        body_map = {
            'SUCCESS': f"Your payment of {self.amount} {self.currency} for booking {self.booking.booking_id} was successful.",
            'FAILED': f"Your payment of {self.amount} {self.currency} for booking {self.booking.booking_id} failed. {error_message}",
            'REFUNDED': f"A refund of {self.refund_amount} {self.currency} has been processed for booking {self.booking.booking_id}.",
        }
        
        try:
            BookingNotification.objects.create(
                booking=self.booking,
                notification_type=notification_type,
                sent_to=self.user.email,
                subject=subject_map.get(notification_type, 'Payment Update'),
                body=body_map.get(notification_type, ''),
                is_successful=True
            )
        except Exception as e:
            # Log but don't fail the transaction
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to create payment notification: {str(e)}")
    
    @property
    def is_successful(self):
        """Check if payment was successful"""
        return self.payment_status == self.PaymentStatus.SUCCESS
    
    @property
    def is_pending(self):
        """Check if payment is pending"""
        return self.payment_status == self.PaymentStatus.PENDING
    
    @property
    def is_refunded(self):
        """Check if payment was refunded"""
        return self.payment_status in [self.PaymentStatus.REFUNDED, self.PaymentStatus.PARTIALLY_REFUNDED]
    
    @property
    def remaining_amount(self):
        """Get remaining amount (not refunded)"""
        return self.amount - self.refund_amount


class PaymentLog(models.Model):
    """
    PaymentLog model for tracking all payment-related events
    Maintains audit trail for compliance and debugging
    """
    
    class LogLevel(models.TextChoices):
        INFO = 'INFO', _('Information')
        WARNING = 'WARNING', _('Warning')
        ERROR = 'ERROR', _('Error')
        DEBUG = 'DEBUG', _('Debug')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='logs',
        db_index=True
    )
    
    log_level = models.CharField(
        _('log level'),
        max_length=10,
        choices=LogLevel.choices,
        default=LogLevel.INFO
    )
    
    message = models.TextField(_('message'))
    data = models.JSONField(_('data'), default=dict, blank=True)
    
    ip_address = models.GenericIPAddressField(_('IP address'), null=True, blank=True)
    user_agent = models.TextField(_('user agent'), blank=True)
    
    created_at = models.DateTimeField(_('created at'), default=timezone.now, db_index=True)
    
    class Meta:
        verbose_name = _('payment log')
        verbose_name_plural = _('payment logs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payment', 'created_at']),
            models.Index(fields=['log_level', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.payment.transaction_id} - {self.log_level} at {self.created_at}"


class PaymentMethod(models.Model):
    """
    PaymentMethod model for storing user payment methods securely
    """
    
    class MethodType(models.TextChoices):
        CARD = 'CARD', _('Credit/Debit Card')
        PAYPAL = 'PAYPAL', _('PayPal')
        BANK_ACCOUNT = 'BANK_ACCOUNT', _('Bank Account')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='payment_methods',
        db_index=True
    )
    
    method_type = models.CharField(
        _('method type'),
        max_length=20,
        choices=MethodType.choices
    )
    
    # Tokenized/payment gateway reference
    token = models.CharField(_('token'), max_length=255, db_index=True)
    gateway = models.CharField(_('gateway'), max_length=50, default='STRIPE')
    
    # Display information (not sensitive)
    last_four = models.CharField(_('last four'), max_length=4, blank=True)
    card_brand = models.CharField(_('card brand'), max_length=20, blank=True)
    expiry_month = models.PositiveSmallIntegerField(_('expiry month'), null=True, blank=True)
    expiry_year = models.PositiveSmallIntegerField(_('expiry year'), null=True, blank=True)
    cardholder_name = models.CharField(_('cardholder name'), max_length=255, blank=True)
    
    # Billing address
    billing_address = models.JSONField(_('billing address'), default=dict, blank=True)
    
    # Metadata
    is_default = models.BooleanField(_('is default'), default=False)
    is_active = models.BooleanField(_('is active'), default=True)
    metadata = models.JSONField(_('metadata'), default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), default=timezone.now)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('payment method')
        verbose_name_plural = _('payment methods')
        ordering = ['-is_default', '-created_at']
        indexes = [
            models.Index(fields=['user', 'is_default']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['token']),
        ]
        unique_together = [['user', 'token']]
    
    def __str__(self):
        if self.method_type == self.MethodType.CARD:
            return f"{self.card_brand} ending in {self.last_four}"
        return f"{self.method_type} - {self.token[:10]}..."
    
    def save(self, *args, **kwargs):
        """Ensure only one default payment method per user"""
        if self.is_default:
            PaymentMethod.objects.filter(
                user=self.user,
                is_default=True
            ).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)


class Refund(models.Model):
    """
    Refund model for tracking individual refunds
    """
    
    class RefundStatus(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        PROCESSING = 'PROCESSING', _('Processing')
        COMPLETED = 'COMPLETED', _('Completed')
        FAILED = 'FAILED', _('Failed')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    refund_id = models.CharField(_('refund ID'), max_length=100, unique=True, db_index=True)
    
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='refunds',
        db_index=True
    )
    
    amount = models.DecimalField(
        _('amount'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(_('currency'), max_length=3, default='USD')
    
    reason = models.TextField(_('reason'), blank=True)
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=RefundStatus.choices,
        default=RefundStatus.PENDING,
        db_index=True
    )
    
    gateway_refund_id = models.CharField(_('gateway refund ID'), max_length=255, blank=True)
    gateway_response = models.JSONField(_('gateway response'), default=dict, blank=True)
    
    initiated_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='initiated_refunds'
    )
    
    metadata = models.JSONField(_('metadata'), default=dict, blank=True)
    
    created_at = models.DateTimeField(_('created at'), default=timezone.now)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    completed_at = models.DateTimeField(_('completed at'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('refund')
        verbose_name_plural = _('refunds')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['refund_id']),
            models.Index(fields=['payment', 'status']),
        ]
    
    def __str__(self):
        return f"{self.refund_id} - {self.amount} {self.currency}"
    
    def save(self, *args, **kwargs):
        """Generate refund ID if not provided"""
        if not self.refund_id:
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            random_part = uuid.uuid4().hex[:6].upper()
            self.refund_id = f"REF-{timestamp}-{random_part}"
        super().save(*args, **kwargs)
    
    def process_completed(self, gateway_response=None):
        """Mark refund as completed"""
        with transaction.atomic():
            self.status = self.RefundStatus.COMPLETED
            self.completed_at = timezone.now()
            if gateway_response:
                self.gateway_response = gateway_response
            self.save()
            
            # Update payment refund amount
            self.payment.refund_amount += self.amount
            if self.payment.refund_amount >= self.payment.amount:
                self.payment.payment_status = Payment.PaymentStatus.REFUNDED
            else:
                self.payment.payment_status = Payment.PaymentStatus.PARTIALLY_REFUNDED
            self.payment.save()