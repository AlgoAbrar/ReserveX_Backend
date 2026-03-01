"""
Restaurants App Serializers
Handles serialization and validation for Restaurant, Branch, Table, and MenuItem models
"""

from rest_framework import serializers
from django.db import transaction
from django.utils.text import slugify
from django.core.validators import ValidationError
from django.utils import timezone
import re

from .models import Restaurant, Branch, Table, MenuItem
from users.serializers import UserSerializer


class RestaurantListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for restaurant list views
    """
    manager_name = serializers.CharField(source='manager.name', read_only=True)
    manager_email = serializers.EmailField(source='manager.email', read_only=True)
    branches_count = serializers.IntegerField(source='total_branches', read_only=True)
    
    class Meta:
        model = Restaurant
        fields = [
            'id', 'name', 'slug', 'cuisine_type', 'price_level',
            'logo', 'cover_image', 'city', 'average_rating',
            'is_featured', 'is_verified', 'manager_name', 'manager_email',
            'branches_count', 'created_at'
        ]
        read_only_fields = ['id', 'slug', 'average_rating', 'created_at']


class RestaurantDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for restaurant detail views
    """
    manager = UserSerializer(read_only=True)
    branches = serializers.SerializerMethodField()
    menu_categories = serializers.SerializerMethodField()
    total_capacity = serializers.SerializerMethodField()
    cuisine_type_display = serializers.CharField(source='get_cuisine_type_display', read_only=True)
    price_level_display = serializers.CharField(source='get_price_level_display', read_only=True)
    
    class Meta:
        model = Restaurant
        fields = '__all__'
        read_only_fields = [
            'id', 'slug', 'total_branches', 'average_rating',
            'total_reviews', 'total_bookings', 'created_at', 'updated_at'
        ]
    
    def get_branches(self, obj):
        """Get branches with prefetched tables"""
        branches = obj.branches.prefetch_related('tables').all()
        return BranchSerializer(branches, many=True, context=self.context).data
    
    def get_menu_categories(self, obj):
        """Group menu items by category"""
        menu_items = obj.menu_items.filter(is_available=True)
        categories = {}
        for item in menu_items:
            category = item.category
            if category not in categories:
                categories[category] = []
            categories[category].append({
                'id': item.id,
                'name': item.name,
                'price': float(item.current_price),
                'description': item.description[:100] if item.description else '',
                'image': item.image,
                'is_popular': item.is_popular,
                'dietary_types': item.dietary_types,
                'preparation_time': item.preparation_time
            })
        return categories
    
    def get_total_capacity(self, obj):
        """Calculate total seating capacity"""
        return obj.get_total_capacity()
    
    def validate(self, data):
        """Validate restaurant data"""
        # Validate email format
        if data.get('email') and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', data['email']):
            raise serializers.ValidationError({'email': 'Enter a valid email address.'})
        
        # Validate phone number
        if data.get('phone'):
            phone = data['phone']
            phone_digits = re.sub(r'\D', '', phone)
            if len(phone_digits) < 9 or len(phone_digits) > 15:
                raise serializers.ValidationError({'phone': 'Phone number must be between 9 and 15 digits.'})
        
        # Validate coordinates
        if data.get('latitude') and data.get('longitude'):
            lat = float(data['latitude'])
            lng = float(data['longitude'])
            if lat < -90 or lat > 90:
                raise serializers.ValidationError({'latitude': 'Latitude must be between -90 and 90.'})
            if lng < -180 or lng > 180:
                raise serializers.ValidationError({'longitude': 'Longitude must be between -180 and 180.'})
        
        return data


class RestaurantCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new restaurants
    """
    class Meta:
        model = Restaurant
        fields = [
            'name', 'description', 'cuisine_type', 'price_level',
            'logo', 'cover_image', 'email', 'phone', 'website',
            'address', 'city', 'state', 'country', 'postal_code',
            'latitude', 'longitude', 'business_hours', 'features',
            'dietary_options'
        ]
    
    def validate_name(self, value):
        """Validate restaurant name"""
        if len(value) < 3:
            raise serializers.ValidationError("Restaurant name must be at least 3 characters long.")
        if Restaurant.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("A restaurant with this name already exists.")
        return value
    
    @transaction.atomic
    def create(self, validated_data):
        """Create restaurant with atomic transaction"""
        # Set default business hours if not provided
        if 'business_hours' not in validated_data:
            validated_data['business_hours'] = {
                'monday': {'open': '09:00', 'close': '22:00', 'closed': False},
                'tuesday': {'open': '09:00', 'close': '22:00', 'closed': False},
                'wednesday': {'open': '09:00', 'close': '22:00', 'closed': False},
                'thursday': {'open': '09:00', 'close': '22:00', 'closed': False},
                'friday': {'open': '09:00', 'close': '23:00', 'closed': False},
                'saturday': {'open': '10:00', 'close': '23:00', 'closed': False},
                'sunday': {'open': '10:00', 'close': '21:00', 'closed': False},
            }
        
        # Auto-generate slug
        base_slug = slugify(validated_data['name'])
        slug = base_slug
        counter = 1
        while Restaurant.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        validated_data['slug'] = slug
        
        return super().create(validated_data)


class RestaurantUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating restaurants
    """
    class Meta:
        model = Restaurant
        fields = [
            'name', 'description', 'cuisine_type', 'price_level',
            'logo', 'cover_image', 'gallery', 'email', 'phone', 'website',
            'address', 'city', 'state', 'country', 'postal_code',
            'latitude', 'longitude', 'business_hours', 'features',
            'dietary_options', 'is_active', 'is_featured', 'is_verified',
            'meta_title', 'meta_description', 'meta_keywords'
        ]
    
    def validate(self, data):
        """Validate update data"""
        # If name is being updated, check for duplicates
        if data.get('name'):
            name = data['name']
            if Restaurant.objects.filter(name__iexact=name).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError({'name': 'A restaurant with this name already exists.'})
        
        return data
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update restaurant with atomic transaction"""
        # Update slug if name changed
        if 'name' in validated_data and validated_data['name'] != instance.name:
            base_slug = slugify(validated_data['name'])
            slug = base_slug
            counter = 1
            while Restaurant.objects.filter(slug=slug).exclude(id=instance.id).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            validated_data['slug'] = slug
        
        return super().update(instance, validated_data)


class BranchSerializer(serializers.ModelSerializer):
    """
    Serializer for Branch model
    """
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    tables_count = serializers.IntegerField(source='total_tables', read_only=True)
    seats_count = serializers.IntegerField(source='total_seats', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Branch
        fields = [
            'id', 'restaurant', 'restaurant_name', 'name', 'code',
            'address', 'city', 'state', 'country', 'postal_code',
            'latitude', 'longitude', 'phone', 'email', 'business_hours',
            'total_tables', 'total_seats', 'tables_count', 'seats_count',
            'status', 'status_display', 'images', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'code', 'total_tables', 'total_seats', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validate branch data"""
        # Validate required fields
        if not data.get('address'):
            raise serializers.ValidationError({'address': 'Address is required.'})
        if not data.get('city'):
            raise serializers.ValidationError({'city': 'City is required.'})
        if not data.get('phone'):
            raise serializers.ValidationError({'phone': 'Phone number is required.'})
        
        # Validate phone number
        phone = data['phone']
        phone_digits = re.sub(r'\D', '', phone)
        if len(phone_digits) < 9 or len(phone_digits) > 15:
            raise serializers.ValidationError({'phone': 'Phone number must be between 9 and 15 digits.'})
        
        # Validate coordinates
        if data.get('latitude') and data.get('longitude'):
            lat = float(data['latitude'])
            lng = float(data['longitude'])
            if lat < -90 or lat > 90:
                raise serializers.ValidationError({'latitude': 'Latitude must be between -90 and 90.'})
            if lng < -180 or lng > 180:
                raise serializers.ValidationError({'longitude': 'Longitude must be between -180 and 180.'})
        
        return data


class TableSerializer(serializers.ModelSerializer):
    """
    Serializer for Table model
    """
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    restaurant_name = serializers.CharField(source='branch.restaurant.name', read_only=True)
    seat_type_display = serializers.CharField(source='get_seat_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Table
        fields = [
            'id', 'branch', 'branch_name', 'restaurant_name',
            'table_number', 'seat_type', 'seat_type_display',
            'capacity', 'minimum_spend', 'is_accessible', 'is_private',
            'has_outlet', 'has_view', 'floor', 'section', 'status',
            'status_display', 'is_reserved', 'qr_code', 'notes',
            'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_reserved', 'qr_code', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validate table data"""
        # Validate table number uniqueness within branch
        branch = data.get('branch', self.instance.branch if self.instance else None)
        table_number = data.get('table_number')
        
        if table_number:
            existing = Table.objects.filter(
                branch=branch,
                table_number__iexact=table_number
            )
            if self.instance:
                existing = existing.exclude(id=self.instance.id)
            
            if existing.exists():
                raise serializers.ValidationError(
                    {'table_number': f'Table {table_number} already exists in this branch.'}
                )
        
        # Validate capacity
        if data.get('capacity', 0) < 1:
            raise serializers.ValidationError({'capacity': 'Capacity must be at least 1.'})
        
        # Validate minimum spend
        if data.get('minimum_spend', 0) < 0:
            raise serializers.ValidationError({'minimum_spend': 'Minimum spend cannot be negative.'})
        
        return data


class TableAvailabilitySerializer(serializers.Serializer):
    """
    Serializer for checking table availability
    """
    date = serializers.DateField()
    time = serializers.TimeField()
    duration = serializers.IntegerField(min_value=1, max_value=2)
    
    def validate_date(self, value):
        """Validate date is not in the past"""
        if value < timezone.now().date():
            raise serializers.ValidationError("Date cannot be in the past.")
        return value
    
    def validate_time(self, value):
        """Validate time is valid"""
        if value < timezone.now().time() and self.initial_data.get('date') == timezone.now().date():
            raise serializers.ValidationError("Time cannot be in the past.")
        return value


class MenuItemSerializer(serializers.ModelSerializer):
    """
    Serializer for MenuItem model
    """
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    spice_level_display = serializers.CharField(source='get_spice_level_display', read_only=True)
    current_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    discount_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = MenuItem
        fields = [
            'id', 'restaurant', 'restaurant_name', 'name', 'description',
            'category', 'category_display', 'price', 'discount_price',
            'current_price', 'discount_percentage', 'dietary_types',
            'spice_level', 'spice_level_display', 'calories',
            'preparation_time', 'image', 'is_available', 'is_featured',
            'is_popular', 'includes', 'allergens', 'customization_options',
            'tags', 'total_orders', 'average_rating', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'total_orders', 'average_rating', 'created_at', 'updated_at'
        ]
    
    def get_discount_percentage(self, obj):
        """Get discount percentage"""
        return obj.get_discount_percentage()
    
    def validate(self, data):
        """Validate menu item data"""
        # Validate price
        if data.get('price', 0) <= 0:
            raise serializers.ValidationError({'price': 'Price must be greater than 0.'})
        
        # Validate discount price
        if data.get('discount_price'):
            if data['discount_price'] >= data.get('price', self.instance.price if self.instance else 0):
                raise serializers.ValidationError(
                    {'discount_price': 'Discount price must be less than regular price.'}
                )
        
        # Validate dietary types
        if data.get('dietary_types'):
            valid_types = ['VEGETARIAN', 'VEGAN', 'GLUTEN_FREE', 'DAIRY_FREE', 
                          'NUT_FREE', 'HALAL', 'KOSHER', 'SPICY']
            for dt in data['dietary_types']:
                if dt not in valid_types:
                    raise serializers.ValidationError(
                        {'dietary_types': f'Invalid dietary type: {dt}'}
                    )
        
        return data


class MenuItemCategorySerializer(serializers.Serializer):
    """
    Serializer for menu items grouped by category
    """
    category = serializers.CharField()
    items = MenuItemSerializer(many=True)


class RestaurantStatisticsSerializer(serializers.Serializer):
    """
    Serializer for restaurant statistics
    """
    total_restaurants = serializers.IntegerField()
    total_branches = serializers.IntegerField()
    total_tables = serializers.IntegerField()
    total_capacity = serializers.IntegerField()
    total_menu_items = serializers.IntegerField()
    average_rating = serializers.FloatField()
    popular_cuisines = serializers.ListField(child=serializers.DictField())
    recent_bookings = serializers.IntegerField()
    revenue_today = serializers.DecimalField(max_digits=10, decimal_places=2)
    revenue_week = serializers.DecimalField(max_digits=12, decimal_places=2)
    revenue_month = serializers.DecimalField(max_digits=12, decimal_places=2)


class BranchStatisticsSerializer(serializers.Serializer):
    """
    Serializer for branch statistics
    """
    branch_name = serializers.CharField()
    total_tables = serializers.IntegerField()
    occupied_tables = serializers.IntegerField()
    available_tables = serializers.IntegerField()
    total_seats = serializers.IntegerField()
    occupied_seats = serializers.IntegerField()
    occupancy_rate = serializers.FloatField()
    today_bookings = serializers.IntegerField()
    upcoming_bookings = serializers.IntegerField()