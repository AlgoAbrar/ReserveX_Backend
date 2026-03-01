# from django.db import models

# # Create your models here.
"""
Users App Models
Custom User Model with role-based permissions for ReserveX
"""

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator, EmailValidator, MinLengthValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import uuid


class UserManager(BaseUserManager):
    """
    Custom user manager for User model with email as username field
    """
    
    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save a regular user with the given email and password.
        """
        if not email:
            raise ValueError(_('The Email field must be set'))
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and save a superuser with the given email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_verified', True)
        extra_fields.setdefault('role', self.model.Role.ADMIN)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        
        return self.create_user(email, password, **extra_fields)
    
    def get_verified_users(self):
        """Return queryset of verified users"""
        return self.filter(is_verified=True)
    
    def get_by_role(self, role):
        """Return users with specific role"""
        return self.filter(role=role)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User Model for ReserveX
    
    Uses email as the unique identifier instead of username.
    Supports role-based access control with three roles:
    - USER: Regular customer who can make bookings
    - MANAGER: Restaurant manager who can manage restaurants
    - ADMIN: System administrator with full access
    """
    
    class Role(models.TextChoices):
        USER = 'USER', _('Regular User')
        MANAGER = 'MANAGER', _('Restaurant Manager')
        ADMIN = 'ADMIN', _('Administrator')
    
    # Basic Information
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_index=True
    )
    email = models.EmailField(
        _('email address'),
        unique=True,
        db_index=True,
        validators=[EmailValidator()],
        error_messages={
            'unique': _('A user with this email already exists.'),
        }
    )
    name = models.CharField(
        _('full name'),
        max_length=255,
        validators=[MinLengthValidator(2)],
        db_index=True
    )
    phone = models.CharField(
        _('phone number'),
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message=_("Phone number must be entered in format: '+999999999'. Up to 15 digits allowed.")
            )
        ],
        blank=True,
        null=True
    )
    
    # Role and Permissions
    role = models.CharField(
        _('user role'),
        max_length=10,
        choices=Role.choices,
        default=Role.USER,
        db_index=True
    )
    
    # Status flags
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'
        ),
        db_index=True
    )
    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_('Designates whether the user can log into this admin site.')
    )
    is_verified = models.BooleanField(
        _('verified'),
        default=False,
        help_text=_('Designates whether the user has verified their email address.'),
        db_index=True
    )
    
    # Timestamps
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)
    last_updated = models.DateTimeField(_('last updated'), auto_now=True)
    last_activity = models.DateTimeField(_('last activity'), null=True, blank=True)
    
    # Profile
    avatar = models.URLField(_('avatar URL'), max_length=500, blank=True)
    preferred_cuisine = models.JSONField(
        _('preferred cuisine'),
        default=list,
        blank=True,
        help_text=_('Array of preferred cuisine types')
    )
    
    # Metadata
    metadata = models.JSONField(
        _('metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional user metadata in JSON format')
    )
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['email', 'is_active']),
            models.Index(fields=['role', 'is_verified']),
            models.Index(fields=['date_joined']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=['USER', 'MANAGER', 'ADMIN']),
                name='valid_role'
                ),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.email})"
    
    def save(self, *args, **kwargs):
        """Override save to ensure admin users are staff"""
        if self.role == self.Role.ADMIN:
            self.is_staff = True
        super().save(*args, **kwargs)
    
    def get_full_name(self):
        """Return the full name of the user"""
        return self.name
    
    def get_short_name(self):
        """Return the short name of the user"""
        return self.name.split()[0] if self.name else self.email
    
    def update_last_activity(self):
        """Update last activity timestamp"""
        self.last_activity = timezone.now()
        self.save(update_fields=['last_activity'])
    
    @property
    def is_admin(self):
        """Check if user is admin"""
        return self.role == self.Role.ADMIN
    
    @property
    def is_manager(self):
        """Check if user is manager"""
        return self.role == self.Role.MANAGER
    
    @property
    def is_regular_user(self):
        """Check if user is regular user"""
        return self.role == self.Role.USER
    
    def has_restaurant_permission(self, restaurant):
        """
        Check if user has permission to manage a specific restaurant
        Managers can manage their own restaurants, admins can manage all
        """
        if self.is_admin:
            return True
        if self.is_manager:
            from restaurants.models import Restaurant
            return Restaurant.objects.filter(manager=self, id=restaurant.id).exists()
        return False
    
    def get_managed_restaurants(self):
        """Get restaurants managed by this user"""
        if self.is_admin:
            from restaurants.models import Restaurant
            return Restaurant.objects.all()
        elif self.is_manager:
            return self.managed_restaurants.all()
        return Restaurant.objects.none()


class UserActivity(models.Model):
    """
    Track user activities for analytics and audit
    """
    class ActivityType(models.TextChoices):
        LOGIN = 'LOGIN', _('Login')
        LOGOUT = 'LOGOUT', _('Logout')
        BOOKING = 'BOOKING', _('Booking')
        PAYMENT = 'PAYMENT', _('Payment')
        PROFILE_UPDATE = 'PROFILE_UPDATE', _('Profile Update')
        PASSWORD_CHANGE = 'PASSWORD_CHANGE', _('Password Change')
        RESTAURANT_CREATE = 'RESTAURANT_CREATE', _('Restaurant Create')
        RESTAURANT_UPDATE = 'RESTAURANT_UPDATE', _('Restaurant Update')
        RESTAURANT_DELETE = 'RESTAURANT_DELETE', _('Restaurant Delete')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='activities',
        db_index=True
    )
    activity_type = models.CharField(
        max_length=20,
        choices=ActivityType.choices,
        db_index=True
    )
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    
    class Meta:
        verbose_name = _('user activity')
        verbose_name_plural = _('user activities')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['activity_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.activity_type} at {self.created_at}"


class UserPreference(models.Model):
    """
    User preferences for personalized experience
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='preferences',
        db_index=True
    )
    
    # Notification preferences
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=False)
    
    # Booking preferences
    default_duration = models.PositiveSmallIntegerField(
        default=2,
        help_text=_('Default booking duration in hours')
    )
    preferred_seat_types = models.JSONField(
        default=list,
        blank=True,
        help_text=_('Preferred seat types (W, C, NORMAL)')
    )
    dietary_restrictions = models.JSONField(
        default=list,
        blank=True,
        help_text=_('Dietary restrictions or preferences')
    )
    
    # Communication
    language = models.CharField(max_length=10, default='en')
    timezone = models.CharField(max_length=50, default='UTC')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('user preference')
        verbose_name_plural = _('user preferences')
    
    def __str__(self):
        return f"Preferences for {self.user.email}"