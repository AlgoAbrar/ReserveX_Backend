# from django.db import models

# # Create your models here.
"""
Restaurants App Models
Restaurant, Branch, Table, and MenuItem models for ReserveX
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
import uuid


class Restaurant(models.Model):
    """
    Restaurant model representing a restaurant business
    Each restaurant can have multiple branches and is managed by a manager
    """
    
    class CuisineType(models.TextChoices):
        ITALIAN = 'ITALIAN', _('Italian')
        CHINESE = 'CHINESE', _('Chinese')
        INDIAN = 'INDIAN', _('Indian')
        JAPANESE = 'JAPANESE', _('Japanese')
        MEXICAN = 'MEXICAN', _('Mexican')
        THAI = 'THAI', _('Thai')
        FRENCH = 'FRENCH', _('French')
        AMERICAN = 'AMERICAN', _('American')
        MEDITERRANEAN = 'MEDITERRANEAN', _('Mediterranean')
        VEGETARIAN = 'VEGETARIAN', _('Vegetarian')
        VEGAN = 'VEGAN', _('Vegan')
        SEAFOOD = 'SEAFOOD', _('Seafood')
        STEAKHOUSE = 'STEAKHOUSE', _('Steakhouse')
        BBQ = 'BBQ', _('BBQ')
        BAKERY = 'BAKERY', _('Bakery')
        CAFE = 'CAFE', _('Cafe')
        FAST_FOOD = 'FAST_FOOD', _('Fast Food')
        OTHER = 'OTHER', _('Other')
    
    class PriceLevel(models.TextChoices):
        BUDGET = '$', _('Budget - Under $15')
        MODERATE = '$$', _('Moderate - $15-$30')
        EXPENSIVE = '$$$', _('Expensive - $30-$50')
        LUXURY = '$$$$', _('Luxury - Over $50')
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_index=True)
    name = models.CharField(_('restaurant name'), max_length=255, db_index=True)
    slug = models.SlugField(_('slug'), max_length=255, unique=True, db_index=True)
    description = models.TextField(_('description'), blank=True)
    
    # Cuisine and Pricing
    cuisine_type = models.CharField(
        _('cuisine type'),
        max_length=20,
        choices=CuisineType.choices,
        default=CuisineType.OTHER,
        db_index=True
    )
    price_level = models.CharField(
        _('price level'),
        max_length=4,
        choices=PriceLevel.choices,
        default=PriceLevel.MODERATE
    )
    
    # Images
    logo = models.URLField(_('logo URL'), max_length=500, blank=True)
    cover_image = models.URLField(_('cover image URL'), max_length=500, blank=True)
    gallery = models.JSONField(_('gallery'), default=list, blank=True)
    
    # Contact Information
    email = models.EmailField(_('contact email'), blank=True)
    phone = models.CharField(
        _('contact phone'),
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message=_("Phone number must be entered in format: '+999999999'. Up to 15 digits allowed.")
            )
        ],
        blank=True
    )
    website = models.URLField(_('website'), max_length=500, blank=True)
    
    # Location (Primary/Restaurant HQ)
    address = models.TextField(_('address'), blank=True)
    city = models.CharField(_('city'), max_length=100, blank=True, db_index=True)
    state = models.CharField(_('state'), max_length=100, blank=True)
    country = models.CharField(_('country'), max_length=100, blank=True)
    postal_code = models.CharField(_('postal code'), max_length=20, blank=True)
    latitude = models.DecimalField(
        _('latitude'),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        _('longitude'),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    
    # Management
    manager = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_restaurants',
        limit_choices_to={'role': 'MANAGER'},
        db_index=True
    )
    
    # Business Hours (JSON format)
    business_hours = models.JSONField(
        _('business hours'),
        default=dict,
        help_text=_('Business hours in JSON format: {"monday": {"open": "09:00", "close": "22:00", "closed": false}}')
    )
    
    # Features and Amenities
    features = models.JSONField(
        _('features'),
        default=list,
        help_text=_('Restaurant features like "parking", "wifi", "outdoor_seating", etc.')
    )
    
    dietary_options = models.JSONField(
        _('dietary options'),
        default=list,
        help_text=_('Dietary options like "vegetarian", "vegan", "gluten_free", etc.')
    )
    
    # Statistics
    total_branches = models.PositiveIntegerField(_('total branches'), default=0)
    average_rating = models.DecimalField(
        _('average rating'),
        max_digits=3,
        decimal_places=2,
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    total_reviews = models.PositiveIntegerField(_('total reviews'), default=0)
    total_bookings = models.PositiveIntegerField(_('total bookings'), default=0)
    
    # Status
    is_active = models.BooleanField(_('active'), default=True, db_index=True)
    is_featured = models.BooleanField(_('featured'), default=False)
    is_verified = models.BooleanField(_('verified'), default=False)
    
    # SEO
    meta_title = models.CharField(_('meta title'), max_length=255, blank=True)
    meta_description = models.TextField(_('meta description'), blank=True)
    meta_keywords = models.CharField(_('meta keywords'), max_length=500, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('restaurant')
        verbose_name_plural = _('restaurants')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['name', 'city']),
            models.Index(fields=['cuisine_type', 'city']),
            models.Index(fields=['average_rating', '-total_bookings']),
            models.Index(fields=['is_active', 'is_verified']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(average_rating__gte=0) & models.Q(average_rating__lte=5),
                name='valid_average_rating'
            ),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Auto-generate slug if not provided"""
        if not self.slug:
            from django.utils.text import slugify
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Restaurant.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)
    
    def update_statistics(self):
        """Update restaurant statistics based on branches and bookings"""
        self.total_branches = self.branches.count()
        
        # Update average rating from reviews (if reviews model exists)
        # This is a placeholder for future implementation
        
        self.save(update_fields=['total_branches', 'average_rating'])
    
    def has_manager(self):
        """Check if restaurant has a manager assigned"""
        return self.manager is not None
    
    def get_manager_email(self):
        """Get manager email if exists"""
        return self.manager.email if self.manager else None
    
    def get_branches_with_tables(self):
        """Get branches with prefetched tables"""
        return self.branches.prefetch_related('tables').all()
    
    def get_total_capacity(self):
        """Calculate total seating capacity across all branches"""
        from django.db.models import Sum
        result = self.branches.aggregate(
            total=Sum('tables__capacity')
        )
        return result['total'] or 0


class Branch(models.Model):
    """
    Branch model representing a physical restaurant location
    Each branch belongs to one restaurant and has multiple tables
    """
    
    class Status(models.TextChoices):
        OPEN = 'OPEN', _('Open')
        CLOSED = 'CLOSED', _('Closed')
        RENOVATING = 'RENOVATING', _('Renovating')
        TEMPORARILY_CLOSED = 'TEMPORARILY_CLOSED', _('Temporarily Closed')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_index=True)
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='branches',
        db_index=True
    )
    
    name = models.CharField(_('branch name'), max_length=255)
    code = models.CharField(_('branch code'), max_length=20, unique=True, db_index=True)
    
    # Location
    address = models.TextField(_('address'))
    city = models.CharField(_('city'), max_length=100, db_index=True)
    state = models.CharField(_('state'), max_length=100)
    country = models.CharField(_('country'), max_length=100)
    postal_code = models.CharField(_('postal code'), max_length=20)
    latitude = models.DecimalField(
        _('latitude'),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        _('longitude'),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    
    # Contact
    phone = models.CharField(_('phone'), max_length=20)
    email = models.EmailField(_('email'), blank=True)
    
    # Business Hours
    business_hours = models.JSONField(
        _('business hours'),
        default=dict,
        help_text=_('Branch-specific business hours (overrides restaurant hours)')
    )
    
    # Capacity
    total_tables = models.PositiveIntegerField(_('total tables'), default=0)
    total_seats = models.PositiveIntegerField(_('total seats'), default=0)
    
    # Status
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True
    )
    
    # Images
    images = models.JSONField(_('branch images'), default=list, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), default=timezone.now)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('branch')
        verbose_name_plural = _('branches')
        ordering = ['restaurant__name', 'name']
        indexes = [
            models.Index(fields=['restaurant', 'city']),
            models.Index(fields=['code']),
            models.Index(fields=['status']),
        ]
        unique_together = [['restaurant', 'code']]
    
    def __str__(self):
        return f"{self.restaurant.name} - {self.name}"
    
    def save(self, *args, **kwargs):
        """Auto-generate branch code if not provided"""
        if not self.code:
            import random
            import string
            prefix = self.restaurant.name[:3].upper()
            random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            self.code = f"{prefix}{random_chars}"
        super().save(*args, **kwargs)
    
    def update_capacity(self):
        """Update branch capacity based on tables"""
        from django.db.models import Sum
        result = self.tables.aggregate(
            tables=models.Count('id'),
            seats=Sum('capacity')
        )
        self.total_tables = result['tables'] or 0
        self.total_seats = result['seats'] or 0
        self.save(update_fields=['total_tables', 'total_seats'])
    
    def get_available_tables(self, date, start_time, duration):
        """Get available tables for a specific time slot"""
        from bookings.models import Booking
        from django.db.models import Q
        
        end_time = (timezone.datetime.combine(date, start_time) + 
                   timezone.timedelta(hours=duration)).time()
        
        # Get booked tables for this time slot
        booked_tables = Booking.objects.filter(
            branch=self,
            date=date,
            status__in=['PENDING_PAYMENT', 'CONFIRMED'],
            start_time__lt=end_time,
            end_time__gt=start_time
        ).values_list('table_id', flat=True)
        
        return self.tables.exclude(id__in=booked_tables)
    
    def is_open_at(self, date, time):
        """Check if branch is open at specific date and time"""
        weekday = date.strftime('%A').lower()
        hours = self.business_hours.get(weekday, {})
        
        if hours.get('closed', False):
            return False
        
        open_time = hours.get('open')
        close_time = hours.get('close')
        
        if not open_time or not close_time:
            # Fall back to restaurant hours
            hours = self.restaurant.business_hours.get(weekday, {})
            open_time = hours.get('open')
            close_time = hours.get('close')
        
        if not open_time or not close_time:
            return False
        
        # Convert times to comparable format
        time_str = time.strftime('%H:%M')
        return open_time <= time_str <= close_time


class Table(models.Model):
    """
    Table model representing a specific table in a branch
    """
    
    class SeatType(models.TextChoices):
        WINDOW = 'W', _('Window')
        CORNER = 'C', _('Corner')
        NORMAL = 'NORMAL', _('Normal')
        PRIVATE = 'PRIVATE', _('Private')
        OUTDOOR = 'OUTDOOR', _('Outdoor')
        BAR = 'BAR', _('Bar')
    
    class Status(models.TextChoices):
        AVAILABLE = 'AVAILABLE', _('Available')
        RESERVED = 'RESERVED', _('Reserved')
        OCCUPIED = 'OCCUPIED', _('Occupied')
        MAINTENANCE = 'MAINTENANCE', _('Under Maintenance')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_index=True)
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='tables',
        db_index=True
    )
    
    table_number = models.CharField(_('table number'), max_length=10, db_index=True)
    seat_type = models.CharField(
        _('seat type'),
        max_length=10,
        choices=SeatType.choices,
        default=SeatType.NORMAL,
        db_index=True
    )
    
    capacity = models.PositiveSmallIntegerField(
        _('capacity'),
        validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
    minimum_spend = models.DecimalField(
        _('minimum spend'),
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    
    # Features
    is_accessible = models.BooleanField(_('wheelchair accessible'), default=False)
    is_private = models.BooleanField(_('private'), default=False)
    has_outlet = models.BooleanField(_('has electrical outlet'), default=False)
    has_view = models.BooleanField(_('has view'), default=False)
    
    # Location
    floor = models.CharField(_('floor'), max_length=20, blank=True)
    section = models.CharField(_('section'), max_length=50, blank=True)
    
    # Status
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
        db_index=True
    )
    is_reserved = models.BooleanField(_('is reserved'), default=False, db_index=True)
    
    # QR Code for table management
    qr_code = models.URLField(_('QR code URL'), max_length=500, blank=True)
    
    # Metadata
    notes = models.TextField(_('notes'), blank=True)
    metadata = models.JSONField(_('metadata'), default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), default=timezone.now)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('table')
        verbose_name_plural = _('tables')
        ordering = ['branch', 'table_number']
        indexes = [
            models.Index(fields=['branch', 'status']),
            models.Index(fields=['branch', 'seat_type']),
            models.Index(fields=['branch', 'capacity']),
            models.Index(fields=['is_reserved']),
        ]
        unique_together = [['branch', 'table_number']]
    
    def __str__(self):
        return f"{self.branch.name} - Table {self.table_number}"
    
    def save(self, *args, **kwargs):
        """Update is_reserved based on status"""
        self.is_reserved = self.status == self.Status.RESERVED
        super().save(*args, **kwargs)
        
        # Update branch capacity
        self.branch.update_capacity()
    
    def is_available_at(self, date, start_time, duration):
        """Check if table is available for a specific time slot"""
        from bookings.models import Booking
        
        end_time = (timezone.datetime.combine(date, start_time) + 
                   timezone.timedelta(hours=duration)).time()
        
        # Check for overlapping bookings
        overlapping = Booking.objects.filter(
            table=self,
            date=date,
            status__in=['PENDING_PAYMENT', 'CONFIRMED'],
            start_time__lt=end_time,
            end_time__gt=start_time
        ).exists()
        
        return not overlapping and self.status == self.Status.AVAILABLE


class MenuItem(models.Model):
    """
    MenuItem model representing a dish or item on the restaurant menu
    """
    
    class Category(models.TextChoices):
        APPETIZER = 'APPETIZER', _('Appetizer')
        MAIN_COURSE = 'MAIN_COURSE', _('Main Course')
        SOUP = 'SOUP', _('Soup')
        SALAD = 'SALAD', _('Salad')
        SEAFOOD = 'SEAFOOD', _('Seafood')
        PASTA = 'PASTA', _('Pasta')
        PIZZA = 'PIZZA', _('Pizza')
        BURGER = 'BURGER', _('Burger')
        SANDWICH = 'SANDWICH', _('Sandwich')
        DESSERT = 'DESSERT', _('Dessert')
        BEVERAGE = 'BEVERAGE', _('Beverage')
        ALCOHOL = 'ALCOHOL', _('Alcoholic Beverage')
        SIDE = 'SIDE', _('Side Dish')
        BREAKFAST = 'BREAKFAST', _('Breakfast')
        LUNCH = 'LUNCH', _('Lunch Special')
        DINNER = 'DINNER', _('Dinner Special')
        COMBO = 'COMBO', _('Combo Meal')
        KIDS = 'KIDS', _("Kids' Menu")
    
    class DietaryType(models.TextChoices):
        VEGETARIAN = 'VEGETARIAN', _('Vegetarian')
        VEGAN = 'VEGAN', _('Vegan')
        GLUTEN_FREE = 'GLUTEN_FREE', _('Gluten Free')
        DAIRY_FREE = 'DAIRY_FREE', _('Dairy Free')
        NUT_FREE = 'NUT_FREE', _('Nut Free')
        HALAL = 'HALAL', _('Halal')
        KOSHER = 'KOSHER', _('Kosher')
        SPICY = 'SPICY', _('Spicy')
    
    class SpiceLevel(models.TextChoices):
        MILD = 'MILD', _('Mild')
        MEDIUM = 'MEDIUM', _('Medium')
        HOT = 'HOT', _('Hot')
        EXTRA_HOT = 'EXTRA_HOT', _('Extra Hot')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_index=True)
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='menu_items',
        db_index=True
    )
    
    # Basic Information
    name = models.CharField(_('item name'), max_length=255, db_index=True)
    description = models.TextField(_('description'), blank=True)
    category = models.CharField(
        _('category'),
        max_length=20,
        choices=Category.choices,
        db_index=True
    )
    
    # Pricing
    price = models.DecimalField(
        _('price'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    discount_price = models.DecimalField(
        _('discount price'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    
    # Dietary Information
    dietary_types = models.JSONField(
        _('dietary types'),
        default=list,
        blank=True
    )
    spice_level = models.CharField(
        _('spice level'),
        max_length=10,
        choices=SpiceLevel.choices,
        default=SpiceLevel.MILD
    )
    
    # Calories and Nutrition (optional)
    calories = models.PositiveIntegerField(_('calories'), null=True, blank=True)
    preparation_time = models.PositiveSmallIntegerField(
        _('preparation time (minutes)'),
        default=15
    )
    
    # Images
    image = models.URLField(_('image URL'), max_length=500, blank=True)
    
    # Availability
    is_available = models.BooleanField(_('available'), default=True, db_index=True)
    is_featured = models.BooleanField(_('featured'), default=False)
    is_popular = models.BooleanField(_('popular'), default=False)
    
    # For combo meals
    includes = models.JSONField(_('includes'), default=list, blank=True)
    
    # Allergens
    allergens = models.JSONField(_('allergens'), default=list, blank=True)
    
    # Customization Options
    customization_options = models.JSONField(
        _('customization options'),
        default=dict,
        blank=True
    )
    
    # Metadata
    tags = models.JSONField(_('tags'), default=list, blank=True)
    metadata = models.JSONField(_('metadata'), default=dict, blank=True)
    
    # Statistics
    total_orders = models.PositiveIntegerField(_('total orders'), default=0)
    average_rating = models.DecimalField(
        _('average rating'),
        max_digits=3,
        decimal_places=2,
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), default=timezone.now)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('menu item')
        verbose_name_plural = _('menu items')
        ordering = ['category', 'name']
        indexes = [
            models.Index(fields=['restaurant', 'category']),
            models.Index(fields=['restaurant', 'is_available']),
            models.Index(fields=['restaurant', 'is_featured']),
            models.Index(fields=['price']),
        ]
        unique_together = [['restaurant', 'name', 'category']]
    
    def __str__(self):
        return f"{self.restaurant.name} - {self.name}"
    
    @property
    def current_price(self):
        """Get current price (with discount if available)"""
        return self.discount_price if self.discount_price else self.price
    
    def is_discounted(self):
        """Check if item has active discount"""
        return self.discount_price is not None and self.discount_price < self.price
    
    def get_discount_percentage(self):
        """Calculate discount percentage"""
        if self.is_discounted():
            return round(((self.price - self.discount_price) / self.price) * 100)
        return 0