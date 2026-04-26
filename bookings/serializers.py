from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta

from .models import Booking, BookingMenu, BookingHistory, BookingNotification
from restaurants.models import Table, MenuItem, Restaurant, Branch
from restaurants.serializers import RestaurantListSerializer, TableSerializer
from users.serializers import UserSerializer



def validate_booking_time(date, start_time):
    now = timezone.now()

    if date < now.date():
        raise serializers.ValidationError({'date': 'Cannot be in past'})

    if date == now.date() and start_time < now.time():
        raise serializers.ValidationError({'start_time': 'Cannot be in past'})




class BookingMenuSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.CharField(source='menu_item.name', read_only=True)

    class Meta:
        model = BookingMenu
        fields = [
            'id', 'menu_item', 'menu_item_name',
            'quantity', 'unit_price', 'subtotal',
            'special_instructions'
        ]
        read_only_fields = ['id', 'subtotal']

    def validate(self, data):
        menu_item = data.get('menu_item')
        booking = self.context.get('booking') or getattr(self.instance, 'booking', None)

        if not menu_item:
            raise serializers.ValidationError({'menu_item': 'Required'})

        if booking and menu_item.restaurant_id != booking.restaurant_id:
            raise serializers.ValidationError('Invalid menu item')

        if not menu_item.is_available:
            raise serializers.ValidationError('Item not available')

        if data.get('quantity', 1) < 1:
            raise serializers.ValidationError({'quantity': 'Must be >= 1'})

        return data

    def create(self, validated_data):
        validated_data['unit_price'] = validated_data['menu_item'].current_price
        return super().create(validated_data)



class BookingListSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.name', read_only=True)
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    table_number = serializers.CharField(source='table.table_number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'booking_id', 'user_name', 'restaurant_name',
            'table_number', 'date', 'start_time',
            'total_guests', 'total_price', 'status', 'status_display'
        ]


class BookingDetailSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    restaurant = RestaurantListSerializer(read_only=True)
    table = TableSerializer(read_only=True)
    menu_items = BookingMenuSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Booking
        fields = '__all__'


class BookingCreateSerializer(serializers.ModelSerializer):
    menu_items = BookingMenuSerializer(many=True, required=False)

    class Meta:
        model = Booking
        fields = [
            'restaurant', 'branch', 'table',
            'date', 'start_time', 'duration',
            'total_guests', 'special_requests',
            'menu_items'
        ]

    def validate(self, data):
        user = self.context['request'].user

        restaurant = data['restaurant']
        branch = data['branch']
        table = data['table']

        # Basic validation
        if not restaurant.is_active:
            raise serializers.ValidationError('Restaurant inactive')

        if branch.restaurant_id != restaurant.id:
            raise serializers.ValidationError('Invalid branch')

        if table.branch_id != branch.id:
            raise serializers.ValidationError('Invalid table')

        # Time validation
        validate_booking_time(data['date'], data['start_time'])

        # Capacity
        if data['total_guests'] > table.capacity:
            raise serializers.ValidationError('Exceeds capacity')

        # Duration
        if data['duration'] not in [1, 2]:
            raise serializers.ValidationError('Duration must be 1 or 2 hours')

        # Overlapping check
        end_time = (
            datetime.combine(data['date'], data['start_time']) +
            timedelta(hours=data['duration'])
        ).time()

        if Booking.objects.filter(
            table_id=table.id,
            date=data['date'],
            status__in=[Booking.Status.PENDING_PAYMENT, Booking.Status.CONFIRMED],
            start_time__lt=end_time,
            end_time__gt=data['start_time']
        ).exists():
            raise serializers.ValidationError('Time slot already booked')

        return data

    @transaction.atomic
    def create(self, validated_data):
        menu_items_data = validated_data.pop('menu_items', [])
        user = self.context['request'].user

        booking = Booking.objects.create(user=user, **validated_data)

        # Bulk create menu items
        menu_objs = []
        total_price = 0

        for item in menu_items_data:
            price = item['menu_item'].current_price
            quantity = item.get('quantity', 1)

            total_price += price * quantity

            menu_objs.append(
                BookingMenu(
                    booking=booking,
                    menu_item=item['menu_item'],
                    quantity=quantity,
                    unit_price=price,
                    special_instructions=item.get('special_instructions', '')
                )
            )

        BookingMenu.objects.bulk_create(menu_objs)

        booking.total_price = total_price
        booking.save(update_fields=['total_price'])

        # History
        BookingHistory.objects.create(
            booking=booking,
            old_status='',
            new_status=Booking.Status.PENDING_PAYMENT,
            changed_by=user,
            reason='Booking created'
        )

        return booking




class BookingUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ['waiter_name', 'special_requests', 'metadata']

    @transaction.atomic
    def update(self, instance, validated_data):
        user = self.context['request'].user

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        BookingHistory.objects.create(
            booking=instance,
            old_status=instance.status,
            new_status=instance.status,
            changed_by=user,
            reason='Updated booking'
        )

        return instance



class BookingStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Booking.Status.choices)

    TRANSITIONS = {
        Booking.Status.PENDING_PAYMENT: [
            Booking.Status.CONFIRMED,
            Booking.Status.CANCELLED
        ],
        Booking.Status.CONFIRMED: [
            Booking.Status.COMPLETED,
            Booking.Status.CANCELLED
        ],
    }

    def validate(self, data):
        booking = self.context['booking']
        new_status = data['status']

        if new_status not in self.TRANSITIONS.get(booking.status, []):
            raise serializers.ValidationError("Invalid transition")

        return data

    def update(self, instance, validated_data):
        instance.status = validated_data['status']
        instance.save(update_fields=['status'])

        BookingHistory.objects.create(
            booking=instance,
            old_status=instance.status,
            new_status=validated_data['status'],
            changed_by=self.context['request'].user
        )

        return instance




class BookingHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingHistory
        fields = '__all__'



class BookingAvailabilitySerializer(serializers.Serializer):
    restaurant_id = serializers.UUIDField(required=False)
    branch_id = serializers.UUIDField(required=False)
    date = serializers.DateField()
    time = serializers.TimeField()
    duration = serializers.IntegerField(min_value=1, max_value=2)
    guests = serializers.IntegerField(min_value=1)

    def validate(self, data):
        validate_booking_time(data['date'], data['time'])
        return data




class BookingNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingNotification
        fields = '__all__'



class BookingStatisticsSerializer(serializers.Serializer):
    total_bookings = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_booking_value = serializers.DecimalField(max_digits=10, decimal_places=2)

    popular_times = serializers.ListField()
    popular_tables = serializers.ListField()
    popular_menu_items = serializers.ListField()
    bookings_by_day = serializers.ListField()