"""
Bookings App Models - Optimized
Booking and BookingMenu models for ReserveX restaurant reservation system
"""

from django.db import models, transaction
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum, F
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
import uuid
from datetime import timedelta, datetime, time


class Booking(models.Model):
    """
    Booking model representing a restaurant table reservation
    
    Booking ID format: RSX-YYYY-000001 (sequential per year)
    Status flow: PENDING_PAYMENT -> CONFIRMED -> COMPLETED
                or -> REJECTED/CANCELLED/EXPIRED
    """
    
    class Status(models.TextChoices):
        PENDING_PAYMENT = 'PENDING_PAYMENT', _('Pending Payment')
        CONFIRMED = 'CONFIRMED', _('Confirmed')
        REJECTED = 'REJECTED', _('Rejected')
        CANCELLED = 'CANCELLED', _('Cancelled')
        EXPIRED = 'EXPIRED', _('Expired')
        COMPLETED = 'COMPLETED', _('Completed')
    
    ACTIVE_STATUSES = [Status.PENDING_PAYMENT, Status.CONFIRMED]
    INACTIVE_STATUSES = [Status.CANCELLED, Status.REJECTED, Status.EXPIRED]
    
    # Primary identifier
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_index=True)
    booking_id = models.CharField(
        _('booking ID'),
        max_length=20,
        unique=True,
        editable=False,
        db_index=True,
        help_text=_('Format: RSX-YYYY-000001')
    )
    
    # Relationships - using select_related in queries
    user = models.ForeignKey(
        'users.User',
        on_delete=models.PROTECT,
        related_name='bookings',
        db_index=True
    )
    restaurant = models.ForeignKey(
        'restaurants.Restaurant',
        on_delete=models.PROTECT,
        related_name='bookings',
        db_index=True
    )
    branch = models.ForeignKey(
        'restaurants.Branch',
        on_delete=models.PROTECT,
        related_name='bookings',
        db_index=True
    )
    table = models.ForeignKey(
        'restaurants.Table',
        on_delete=models.PROTECT,
        related_name='bookings',
        db_index=True
    )
    
    # Booking details - using DateTimeField for better query performance
    booking_datetime = models.DateTimeField(_('booking date and time'), db_index=True)
    duration = models.PositiveSmallIntegerField(
        _('duration (hours)'),
        validators=[MinValueValidator(1), MaxValueValidator(2)],
        help_text=_('Booking duration in hours (1-2)')
    )
    
    # Denormalized fields for faster querying
    date = models.DateField(_('booking date'), db_index=True)
    start_time = models.TimeField(_('start time'), db_index=True)
    end_time = models.TimeField(_('end time'), db_index=True)
    
    # Guest information
    total_guests = models.PositiveSmallIntegerField(
        _('total guests'),
        validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
    special_requests = models.TextField(_('special requests'), blank=True)
    
    # Pricing
    total_price = models.DecimalField(
        _('total price'),
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    deposit_amount = models.DecimalField(
        _('deposit amount'),
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    
    # Status
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_PAYMENT,
        db_index=True
    )
    
    # Waiter assignment
    waiter_name = models.CharField(_('waiter name'), max_length=255, blank=True)
    
    # Timestamps - using auto_now_add for created_at
    created_at = models.DateTimeField(_('created at'), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    expires_at = models.DateTimeField(_('expires at'), null=True, blank=True)
    confirmed_at = models.DateTimeField(_('confirmed at'), null=True, blank=True)
    completed_at = models.DateTimeField(_('completed at'), null=True, blank=True)
    cancelled_at = models.DateTimeField(_('cancelled at'), null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(_('metadata'), default=dict, blank=True)
    
    class Meta:
        verbose_name = _('booking')
        verbose_name_plural = _('bookings')
        ordering = ['-booking_datetime']
        indexes = [
            models.Index(fields=['booking_id']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['restaurant', 'date']),
            models.Index(fields=['branch', 'date', 'status']),
            models.Index(fields=['table', 'date', 'start_time']),
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['booking_datetime']),  # New index for range queries
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(duration__gte=1) & models.Q(duration__lte=2),
                name='valid_duration'
            ),
            models.CheckConstraint(
                condition=models.Q(total_guests__gte=1) & models.Q(total_guests__lte=20),
                name='valid_total_guests'
            ),
            models.UniqueConstraint(
                fields=['table', 'date', 'start_time'],
                condition=~Q(status__in=Booking.INACTIVE_STATUSES),
                name='unique_active_booking_per_table'
            ),
        ]
    
    def __str__(self):
        return f"{self.booking_id} - {self.user.email} - {self.restaurant.name}"
    
    def save(self, *args, **kwargs):
        """Override save to generate booking_id and validate business rules"""
        is_new = self._state.adding
        
        # Generate booking_id for new bookings
        if is_new and not self.booking_id:
            self.booking_id = self._generate_booking_id()
        
        # Set time fields based on booking_datetime
        if self.booking_datetime and self.duration:
            self.date = self.booking_datetime.date()
            self.start_time = self.booking_datetime.time()
            end_datetime = self.booking_datetime + timedelta(hours=self.duration)
            self.end_time = end_datetime.time()
        
        # Set expiry for pending payment bookings
        if is_new and self.status == self.Status.PENDING_PAYMENT:
            self.expires_at = timezone.now() + timedelta(minutes=1)
        
        # Validate before saving
        if not is_new:
            self._validate_status_change()
        
        super().save(*args, **kwargs)
    
    def _validate_status_change(self):
        """Validate status change logic"""
        if hasattr(self, '_original_status'):
            if self._original_status != self.status:
                # Add status change validation logic here
                pass
    
    def _generate_booking_id(self):
        """
        Generate unique booking ID in format: RSX-YYYY-000001
        Optimized with select_for_update and reduced queries
        """
        with transaction.atomic():
            current_year = timezone.now().year
            prefix = f"RSX-{current_year}-"
            
            # Use annotate with max for better performance
            last_booking = Booking.objects.filter(
                booking_id__startswith=prefix
            ).select_for_update().only('booking_id').order_by('-booking_id').first()
            
            if last_booking:
                last_sequence = int(last_booking.booking_id.split('-')[-1])
                new_sequence = last_sequence + 1
            else:
                new_sequence = 1
            
            return f"{prefix}{new_sequence:06d}"
    
    def clean(self):
        """Validate booking business rules"""
        # Cache current date/time to avoid multiple calls
        now = timezone.now()
        today = now.date()
        current_time = now.time()
        
        # Check if date is not in the past
        if self.date < today:
            raise ValidationError({'date': 'Booking date cannot be in the past.'})
        
        # Check if booking is for today and time is not in the past
        if self.date == today and self.start_time < current_time:
            raise ValidationError({'start_time': 'Booking time cannot be in the past.'})
        
        # Validate relationships with single query
        self._validate_relationships()
        
        # Check for overlapping bookings (optimized query)
        if self._has_overlapping_booking():
            raise ValidationError(
                'This table is already booked for the selected time slot.'
            )
        
        # Check branch operating hours (cached in memory if possible)
        self._validate_branch_hours(now)
    
    def _validate_relationships(self):
        """Validate all relationships in one go"""
        if self.table.branch_id != self.branch_id:
            raise ValidationError({'table': 'Table does not belong to this branch.'})
        
        if self.branch.restaurant_id != self.restaurant_id:
            raise ValidationError({'branch': 'Branch does not belong to this restaurant.'})
    
    def _validate_branch_hours(self, now):
        """Validate branch operating hours"""
        # Check if branch is open at start time
        if not self.branch.is_open_at(self.date, self.start_time):
            raise ValidationError({'start_time': 'Branch is closed at this time.'})
        
        # Check if end time is within operating hours
        end_datetime = datetime.combine(self.date, self.end_time)
        if not self.branch.is_open_at(self.date, self.end_time) and end_datetime.time() > time(0, 0):
            weekday = self.date.strftime('%A').lower()
            hours = self.branch.business_hours.get(weekday, {})
            close_time = hours.get('close')
            if close_time and self.end_time.strftime('%H:%M') != close_time:
                raise ValidationError(
                    {'duration': 'Booking end time must be within operating hours.'}
                )
    
    def _has_overlapping_booking(self):
        """Optimized check for overlapping bookings"""
        return Booking.objects.filter(
            table=self.table,
            date=self.date,
            status__in=self.ACTIVE_STATUSES
        ).exclude(id=self.id).filter(
            start_time__lt=self.end_time,
            end_time__gt=self.start_time
        ).exists()  # Use exists() instead of count() or exists()
    
    def confirm_booking(self):
        """Confirm booking after successful payment"""
        if self.status != self.Status.PENDING_PAYMENT:
            raise ValidationError('Only pending payment bookings can be confirmed.')
        
        # Use update() for efficiency where possible
        self.status = self.Status.CONFIRMED
        self.confirmed_at = timezone.now()
        self.expires_at = None
        
        # Update in bulk
        self.save(update_fields=['status', 'confirmed_at', 'expires_at', 'updated_at'])
        
        # Update restaurant booking count using F expression
        self.restaurant.total_bookings = F('total_bookings') + 1
        self.restaurant.save(update_fields=['total_bookings'])
    
    def cancel_booking(self, cancelled_by=None):
        """Cancel booking with audit trail"""
        if self.status in [self.Status.COMPLETED, self.Status.CANCELLED, self.Status.EXPIRED]:
            raise ValidationError(f'Booking cannot be cancelled in {self.status} status.')
        
        old_status = self.status
        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()
        self.expires_at = None
        
        # Store cancellation info in metadata
        self.metadata.update({
            'cancelled_by': cancelled_by.email if cancelled_by else 'system',
            'cancelled_at': self.cancelled_at.isoformat(),
            'previous_status': old_status
        })
        
        self.save(update_fields=['status', 'cancelled_at', 'expires_at', 'metadata', 'updated_at'])
    
    def reject_booking(self, rejected_by=None, reason=''):
        """Reject booking (by manager)"""
        if self.status != self.Status.PENDING_PAYMENT:
            raise ValidationError('Only pending payment bookings can be rejected.')
        
        self.status = self.Status.REJECTED
        self.expires_at = None
        
        # Update metadata
        self.metadata.update({
            'rejected_by': rejected_by.email if rejected_by else 'system',
            'rejected_at': timezone.now().isoformat(),
            'rejection_reason': reason
        })
        
        self.save(update_fields=['status', 'expires_at', 'metadata', 'updated_at'])
    
    def expire_booking(self):
        """Mark booking as expired (after payment timeout)"""
        if self.status != self.Status.PENDING_PAYMENT:
            return False
        
        self.status = self.Status.EXPIRED
        self.expires_at = None
        self.metadata['expired_at'] = timezone.now().isoformat()
        self.save(update_fields=['status', 'expires_at', 'metadata', 'updated_at'])
        return True
    
    def complete_booking(self):
        """Mark booking as completed"""
        if self.status != self.Status.CONFIRMED:
            raise ValidationError('Only confirmed bookings can be completed.')
        
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])
    
    @classmethod
    def expire_pending_bookings(cls):
        """Optimized bulk expiration of pending bookings"""
        return cls.objects.filter(
            status=cls.Status.PENDING_PAYMENT,
            expires_at__lt=timezone.now()
        ).update(
            status=cls.Status.EXPIRED,
            expires_at=None,
            metadata=models.F('metadata')  # Trigger JSONField update
        )


# Signal to update table status efficiently
@receiver(post_save, sender=Booking)
def update_table_status(sender, instance, created, **kwargs):
    """Update table reservation status based on booking status"""
    if instance.status == Booking.Status.CONFIRMED:
        Table = models.get_model('restaurants', 'Table')
        Table.objects.filter(id=instance.table_id).update(status='RESERVED')
    elif instance.status in Booking.INACTIVE_STATUSES:
        Table = models.get_model('restaurants', 'Table')
        Table.objects.filter(id=instance.table_id).update(status='AVAILABLE')


class BookingMenu(models.Model):
    """
    Optimized BookingMenu model with better query performance
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_index=True)
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='menu_items',
        db_index=True
    )
    menu_item = models.ForeignKey(
        'restaurants.MenuItem',
        on_delete=models.PROTECT,
        related_name='booking_menus',
        db_index=True
    )
    
    quantity = models.PositiveSmallIntegerField(
        _('quantity'),
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(50)]
    )
    unit_price = models.DecimalField(
        _('unit price'),
        max_digits=10,
        decimal_places=2
    )
    subtotal = models.DecimalField(
        _('subtotal'),
        max_digits=10,
        decimal_places=2,
        editable=False
    )
    
    special_instructions = models.TextField(_('special instructions'), blank=True)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('booking menu item')
        verbose_name_plural = _('booking menu items')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['booking', 'menu_item']),
        ]
        unique_together = [['booking', 'menu_item']]
    
    def __str__(self):
        return f"{self.booking.booking_id} - {self.menu_item.name} x{self.quantity}"
    
    def save(self, *args, **kwargs):
        """Calculate subtotal before saving"""
        self.subtotal = self.unit_price * self.quantity
        super().save(*args, **kwargs)
        
        # Optimized update of booking total price using aggregate
        from django.db.models import Sum
        total = self.booking.menu_items.aggregate(total=Sum('subtotal'))['total'] or 0
        Booking.objects.filter(id=self.booking_id).update(total_price=total)
    
    def clean(self):
        """Validate menu item belongs to the restaurant"""
        if self.menu_item.restaurant_id != self.booking.restaurant_id:
            raise ValidationError(
                {'menu_item': 'Menu item does not belong to this restaurant.'}
            )


class BookingHistory(models.Model):
    """
    Optimized BookingHistory model for audit trail
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='history',
        db_index=True
    )
    
    old_status = models.CharField(
        _('old status'),
        max_length=20,
        choices=Booking.Status.choices
    )
    new_status = models.CharField(
        _('new status'),
        max_length=20,
        choices=Booking.Status.choices
    )
    
    changed_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='booking_changes',
        db_index=True
    )
    changed_at = models.DateTimeField(_('changed at'), auto_now_add=True, db_index=True)
    
    reason = models.TextField(_('reason'), blank=True)
    metadata = models.JSONField(_('metadata'), default=dict, blank=True)
    
    class Meta:
        verbose_name = _('booking history')
        verbose_name_plural = _('booking histories')
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['booking', 'changed_at']),
            models.Index(fields=['new_status', 'changed_at']),
        ]
    
    def __str__(self):
        return f"{self.booking.booking_id}: {self.old_status} -> {self.new_status} at {self.changed_at}"
    
    @classmethod
    def log_change(cls, booking, new_status, changed_by=None, reason='', metadata=None):
        """Create a history entry for booking status change with minimal queries"""
        return cls.objects.create(
            booking=booking,
            old_status=booking.status,
            new_status=new_status,
            changed_by=changed_by,
            reason=reason,
            metadata=metadata or {}
        )


class BookingNotification(models.Model):
    """
    Optimized BookingNotification model for tracking notifications
    """
    class NotificationType(models.TextChoices):
        CONFIRMATION = 'CONFIRMATION', _('Booking Confirmation')
        REMINDER = 'REMINDER', _('Booking Reminder')
        CANCELLATION = 'CANCELLATION', _('Booking Cancellation')
        REJECTION = 'REJECTION', _('Booking Rejection')
        EXPIRY = 'EXPIRY', _('Booking Expiry')
        COMPLETION = 'COMPLETION', _('Booking Completion')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='notifications',
        db_index=True
    )
    
    notification_type = models.CharField(
        _('notification type'),
        max_length=20,
        choices=NotificationType.choices,
        db_index=True
    )
    
    sent_to = models.EmailField(_('sent to'))
    sent_at = models.DateTimeField(_('sent at'), auto_now_add=True, db_index=True)
    
    subject = models.CharField(_('subject'), max_length=255)
    body = models.TextField(_('body'))
    
    is_successful = models.BooleanField(_('is successful'), default=True)
    error_message = models.TextField(_('error message'), blank=True)
    
    class Meta:
        verbose_name = _('booking notification')
        verbose_name_plural = _('booking notifications')
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['booking', 'notification_type']),
            models.Index(fields=['sent_at', 'is_successful']),
        ]
    
    def __str__(self):
        return f"{self.booking.booking_id} - {self.notification_type} at {self.sent_at}"