"""
Bookings App Serializers
Handles serialization and validation for Booking and BookingMenu models
"""

from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from datetime import datetime, timedelta, time
import re

from .models import Booking, BookingMenu, BookingHistory, BookingNotification
from restaurants.models import Table, MenuItem, Restaurant, Branch
from restaurants.serializers import RestaurantListSerializer, TableSerializer, MenuItemSerializer
from users.serializers import UserSerializer


class BookingMenuSerializer(serializers.ModelSerializer):
    """
    Serializer for BookingMenu model
    """
    menu_item_name = serializers.CharField(source='menu_item.name', read_only=True)
    menu_item_category = serializers.CharField(source='menu_item.category', read_only=True)
    
    class Meta:
        model = BookingMenu
        fields = [
            'id', 'menu_item', 'menu_item_name', 'menu_item_category',
            'quantity', 'unit_price', 'subtotal', 'special_instructions',
            'created_at'
        ]
        read_only_fields = ['id', 'subtotal', 'created_at']
    
    def validate(self, data):
        """Validate menu item data"""
        menu_item = data.get('menu_item')
        booking = self.context.get('booking') or self.instance.booking if self.instance else None
        
        if booking and menu_item:
            # Check if menu item belongs to the restaurant
            if menu_item.restaurant != booking.restaurant:
                raise serializers.ValidationError(
                    {'menu_item': 'Menu item does not belong to this restaurant.'}
                )
            
            # Check if menu item is available
            if not menu_item.is_available:
                raise serializers.ValidationError(
                    {'menu_item': 'This menu item is currently not available.'}
                )
        
        # Validate quantity
        if data.get('quantity', 0) < 1:
            raise serializers.ValidationError(
                {'quantity': 'Quantity must be at least 1.'}
            )
        
        return data
    
    def create(self, validated_data):
        """Create booking menu item with unit price from current menu item price"""
        menu_item = validated_data['menu_item']
        validated_data['unit_price'] = menu_item.current_price
        return super().create(validated_data)


class BookingListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for booking list views
    """
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    table_number = serializers.CharField(source='table.table_number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    duration_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Booking
        fields = [
            'id', 'booking_id', 'user_name', 'user_email', 'restaurant_name',
            'branch_name', 'table_number', 'date', 'start_time', 'end_time',
            'duration', 'duration_display', 'total_guests', 'total_price',
            'status', 'status_display', 'created_at'
        ]
        read_only_fields = fields
    
    def get_duration_display(self, obj):
        """Return duration in hours with suffix"""
        return f"{obj.duration} hour{'s' if obj.duration > 1 else ''}"


class BookingDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for booking detail views
    """
    user = UserSerializer(read_only=True)
    restaurant = RestaurantListSerializer(read_only=True)
    table = TableSerializer(read_only=True)
    menu_items = BookingMenuSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    time_remaining = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    can_modify = serializers.SerializerMethodField()
    
    class Meta:
        model = Booking
        fields = [
            'id', 'booking_id', 'user', 'restaurant', 'branch', 'table',
            'date', 'start_time', 'end_time', 'duration', 'total_guests',
            'special_requests', 'total_price', 'deposit_amount', 'status',
            'status_display', 'waiter_name', 'menu_items', 'created_at',
            'updated_at', 'expires_at', 'confirmed_at', 'completed_at',
            'cancelled_at', 'time_remaining', 'can_cancel', 'can_modify',
            'metadata'
        ]
        read_only_fields = [
            'id', 'booking_id', 'total_price', 'deposit_amount', 'created_at',
            'updated_at', 'expires_at', 'confirmed_at', 'completed_at', 'cancelled_at'
        ]
    
    def get_time_remaining(self, obj):
        """Get time remaining for pending payment"""
        if obj.status == Booking.Status.PENDING_PAYMENT and obj.expires_at:
            remaining = obj.expires_at - timezone.now()
            if remaining.total_seconds() > 0:
                return {
                    'minutes': int(remaining.total_seconds() // 60),
                    'seconds': int(remaining.total_seconds() % 60),
                    'total_seconds': int(remaining.total_seconds())
                }
        return None
    
    def get_can_cancel(self, obj):
        """Check if booking can be cancelled"""
        return obj.status in [Booking.Status.PENDING_PAYMENT, Booking.Status.CONFIRMED]
    
    def get_can_modify(self, obj):
        """Check if booking can be modified"""
        return obj.status == Booking.Status.PENDING_PAYMENT


class BookingCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new bookings
    """
    menu_items = BookingMenuSerializer(many=True, required=False)
    
    class Meta:
        model = Booking
        fields = [
            'restaurant', 'branch', 'table', 'date', 'start_time',
            'duration', 'total_guests', 'special_requests', 'menu_items'
        ]
    
    def validate(self, data):
        """Validate booking creation data"""
        request = self.context.get('request')
        user = request.user if request else None
        
        # Validate user is authenticated
        if not user or not user.is_authenticated:
            raise serializers.ValidationError("Authentication required to create booking.")
        
        # Validate user role
        if user.role not in ['USER', 'MANAGER', 'ADMIN']:
            raise serializers.ValidationError("Invalid user role for booking.")
        
        # Get related objects
        restaurant = data.get('restaurant')
        branch = data.get('branch')
        table = data.get('table')
        date = data.get('date')
        start_time = data.get('start_time')
        duration = data.get('duration')
        total_guests = data.get('total_guests')
        
        # Validate restaurant is active
        if not restaurant.is_active:
            raise serializers.ValidationError(
                {'restaurant': 'This restaurant is currently not accepting bookings.'}
            )
        
        # Validate branch belongs to restaurant
        if branch.restaurant != restaurant:
            raise serializers.ValidationError(
                {'branch': 'Branch does not belong to this restaurant.'}
            )
        
        # Validate branch is open
        if branch.status != 'OPEN':
            raise serializers.ValidationError(
                {'branch': f'This branch is currently {branch.get_status_display().lower()}.'}
            )
        
        # Validate table belongs to branch
        if table.branch != branch:
            raise serializers.ValidationError(
                {'table': 'Table does not belong to this branch.'}
            )
        
        # Validate table capacity
        if total_guests > table.capacity:
            raise serializers.ValidationError(
                {'total_guests': f'Table capacity is {table.capacity} guests.'}
            )
        
        # Validate date is not in past
        if date < timezone.now().date():
            raise serializers.ValidationError(
                {'date': 'Booking date cannot be in the past.'}
            )
        
        # Validate time for today
        if date == timezone.now().date() and start_time < timezone.now().time():
            raise serializers.ValidationError(
                {'start_time': 'Booking time cannot be in the past.'}
            )
        
        # Validate duration
        if duration not in [1, 2]:
            raise serializers.ValidationError(
                {'duration': 'Duration must be either 1 or 2 hours.'}
            )
        
        # Calculate end time
        start_datetime = datetime.combine(date, start_time)
        end_datetime = start_datetime + timedelta(hours=duration)
        end_time = end_datetime.time()
        
        # Check if branch is open at this time
        if not branch.is_open_at(date, start_time):
            raise serializers.ValidationError(
                {'start_time': 'Branch is closed at this time.'}
            )
        
        # Check if end time is within operating hours
        weekday = date.strftime('%A').lower()
        hours = branch.business_hours.get(weekday, {})
        close_time = hours.get('close')
        if close_time and end_time.strftime('%H:%M') > close_time:
            raise serializers.ValidationError(
                {'duration': 'Booking would end after closing time.'}
            )
        
        # Check for overlapping bookings
        overlapping = Booking.objects.filter(
            table=table,
            date=date,
            status__in=[Booking.Status.PENDING_PAYMENT, Booking.Status.CONFIRMED],
            start_time__lt=end_time,
            end_time__gt=start_time
        ).exists()
        
        if overlapping:
            raise serializers.ValidationError(
                'This table is already booked for the selected time slot.'
            )
        
        # Check user's active bookings limit (for regular users)
        if user.role == 'USER':
            active_bookings = Booking.objects.filter(
                user=user,
                status__in=[Booking.Status.PENDING_PAYMENT, Booking.Status.CONFIRMED],
                date__gte=timezone.now().date()
            ).count()
            
            if active_bookings >= 3:
                raise serializers.ValidationError(
                    'You have reached the maximum limit of 3 active bookings.'
                )
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        """Create booking with atomic transaction"""
        menu_items_data = validated_data.pop('menu_items', [])
        request = self.context.get('request')
        user = request.user
        
        # Create booking
        booking = Booking.objects.create(
            user=user,
            **validated_data
        )
        
        # Add menu items
        total_price = 0
        for item_data in menu_items_data:
            menu_item = item_data['menu_item']
            quantity = item_data.get('quantity', 1)
            
            BookingMenu.objects.create(
                booking=booking,
                menu_item=menu_item,
                quantity=quantity,
                unit_price=menu_item.current_price,
                special_instructions=item_data.get('special_instructions', '')
            )
            
            total_price += menu_item.current_price * quantity
        
        # Update booking total price
        booking.total_price = total_price
        booking.save(update_fields=['total_price'])
        
        # Create booking history entry
        BookingHistory.objects.create(
            booking=booking,
            old_status='',
            new_status=Booking.Status.PENDING_PAYMENT,
            changed_by=user,
            reason='Booking created',
            metadata={'ip_address': request.META.get('REMOTE_ADDR')}
        )
        
        return booking


class BookingUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating bookings (for managers)
    """
    class Meta:
        model = Booking
        fields = [
            'waiter_name', 'special_requests', 'metadata'
        ]
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update booking with atomic transaction"""
        request = self.context.get('request')
        
        # Update booking
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Log update in history
        BookingHistory.objects.create(
            booking=instance,
            old_status=instance.status,
            new_status=instance.status,
            changed_by=request.user,
            reason='Booking details updated',
            metadata={'updated_fields': list(validated_data.keys())}
        )
        
        return instance


class BookingStatusUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating booking status
    """
    status = serializers.ChoiceField(choices=Booking.Status.choices)
    reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate_status(self, value):
        """Validate status transition"""
        booking = self.context.get('booking')
        if not booking:
            raise serializers.ValidationError("Booking context required.")
        
        # Define allowed transitions
        allowed_transitions = {
            Booking.Status.PENDING_PAYMENT: [
                Booking.Status.CONFIRMED,
                Booking.Status.REJECTED,
                Booking.Status.CANCELLED,
                Booking.Status.EXPIRED
            ],
            Booking.Status.CONFIRMED: [
                Booking.Status.COMPLETED,
                Booking.Status.CANCELLED
            ],
            Booking.Status.REJECTED: [],
            Booking.Status.CANCELLED: [],
            Booking.Status.EXPIRED: [],
            Booking.Status.COMPLETED: [],
        }
        
        if value not in allowed_transitions.get(booking.status, []):
            raise serializers.ValidationError(
                f"Cannot transition from {booking.status} to {value}."
            )
        
        return value
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update booking status"""
        request = self.context.get('request')
        new_status = validated_data['status']
        reason = validated_data.get('reason', '')
        
        old_status = instance.status
        
        # Perform status-specific actions
        if new_status == Booking.Status.CONFIRMED:
            instance.confirm_booking()
        elif new_status == Booking.Status.CANCELLED:
            instance.cancel_booking(request.user)
        elif new_status == Booking.Status.REJECTED:
            instance.reject_booking(request.user, reason)
        elif new_status == Booking.Status.COMPLETED:
            instance.complete_booking()
        elif new_status == Booking.Status.EXPIRED:
            instance.expire_booking()
        else:
            instance.status = new_status
            instance.save()
        
        # Log status change
        BookingHistory.objects.create(
            booking=instance,
            old_status=old_status,
            new_status=new_status,
            changed_by=request.user,
            reason=reason
        )
        
        return instance


class BookingHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for booking history
    """
    changed_by_name = serializers.CharField(source='changed_by.name', read_only=True)
    changed_by_email = serializers.EmailField(source='changed_by.email', read_only=True)
    old_status_display = serializers.CharField(source='get_old_status_display', read_only=True)
    new_status_display = serializers.CharField(source='get_new_status_display', read_only=True)
    
    class Meta:
        model = BookingHistory
        fields = [
            'id', 'old_status', 'old_status_display', 'new_status',
            'new_status_display', 'changed_by_name', 'changed_by_email',
            'changed_at', 'reason', 'metadata'
        ]
        read_only_fields = fields


class BookingAvailabilitySerializer(serializers.Serializer):
    """
    Serializer for checking booking availability
    """
    restaurant_id = serializers.UUIDField(required=False)
    branch_id = serializers.UUIDField(required=False)
    date = serializers.DateField()
    time = serializers.TimeField()
    duration = serializers.IntegerField(min_value=1, max_value=2)
    guests = serializers.IntegerField(min_value=1, max_value=20)
    seat_type = serializers.ChoiceField(
        choices=['W', 'C', 'NORMAL', 'PRIVATE', 'OUTDOOR', 'BAR'],
        required=False
    )
    
    def validate(self, data):
        """Validate availability check data"""
        date = data['date']
        time = data['time']
        
        # Validate date is not in past
        if date < timezone.now().date():
            raise serializers.ValidationError(
                {'date': 'Date cannot be in the past.'}
            )
        
        # Validate time for today
        if date == timezone.now().date() and time < timezone.now().time():
            raise serializers.ValidationError(
                {'time': 'Time cannot be in the past.'}
            )
        
        return data


class BookingNotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for booking notifications
    """
    booking_id = serializers.CharField(source='booking.booking_id', read_only=True)
    
    class Meta:
        model = BookingNotification
        fields = [
            'id', 'booking_id', 'notification_type', 'sent_to',
            'sent_at', 'subject', 'body', 'is_successful', 'error_message'
        ]
        read_only_fields = fields


class BookingStatisticsSerializer(serializers.Serializer):
    """
    Serializer for booking statistics
    """
    total_bookings = serializers.IntegerField()
    pending_payments = serializers.IntegerField()
    confirmed = serializers.IntegerField()
    completed = serializers.IntegerField()
    cancelled = serializers.IntegerField()
    rejected = serializers.IntegerField()
    expired = serializers.IntegerField()
    
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_booking_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    popular_times = serializers.ListField(child=serializers.DictField())
    popular_tables = serializers.ListField(child=serializers.DictField())
    popular_menu_items = serializers.ListField(child=serializers.DictField())
    
    bookings_by_day = serializers.ListField(child=serializers.DictField())
    revenue_by_day = serializers.ListField(child=serializers.DictField())