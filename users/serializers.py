"""
Users App Serializers
Handles user data serialization, validation, and creation with role support
"""

from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.password_validation import validate_password
from django.core import exceptions as django_exceptions
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.settings import api_settings
from djoser.conf import settings as djoser_settings
from djoser.serializers import UserCreateSerializer as DjoserUserCreateSerializer
from djoser.serializers import UserSerializer as DjoserUserSerializer
import re

from .models import User, UserActivity, UserPreference

User = get_user_model()


class UserPreferenceSerializer(serializers.ModelSerializer):
    """
    Serializer for user preferences
    """
    class Meta:
        model = UserPreference
        fields = [
            'email_notifications', 'sms_notifications', 'push_notifications',
            'default_duration', 'preferred_seat_types', 'dietary_restrictions',
            'language', 'timezone'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def validate_default_duration(self, value):
        """Validate default booking duration"""
        if value not in [1, 2]:
            raise serializers.ValidationError(
                "Default duration must be either 1 or 2 hours."
            )
        return value
    
    def validate_preferred_seat_types(self, value):
        """Validate preferred seat types"""
        valid_types = ['W', 'C', 'NORMAL']
        if not all(seat_type in valid_types for seat_type in value):
            raise serializers.ValidationError(
                f"Seat types must be one of: {', '.join(valid_types)}"
            )
        return value


class UserSerializer(DjoserUserSerializer):
    """
    Enhanced user serializer with additional fields and validation
    """
    preferences = UserPreferenceSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()
    is_admin = serializers.BooleanField(read_only=True)
    is_manager = serializers.BooleanField(read_only=True)
    is_regular_user = serializers.BooleanField(read_only=True)
    
    class Meta(DjoserUserSerializer.Meta):
        model = User
        fields = (
            'id', 'email', 'name', 'phone', 'role', 'avatar',
            'is_active', 'is_verified', 'is_admin', 'is_manager', 'is_regular_user',
            'date_joined', 'last_activity', 'preferred_cuisine', 'preferences',
            'full_name'
        )
        read_only_fields = (
            'id', 'is_active', 'is_verified', 'date_joined', 'last_activity'
        )
    
    def get_full_name(self, obj):
        """Return user's full name"""
        return obj.get_full_name()
    
    def validate_phone(self, value):
        """Validate phone number format"""
        if value:
            # Remove any non-digit characters for validation
            phone_digits = re.sub(r'\D', '', value)
            if len(phone_digits) < 9 or len(phone_digits) > 15:
                raise serializers.ValidationError(
                    "Phone number must be between 9 and 15 digits."
                )
        return value


class UserCreateSerializer(DjoserUserCreateSerializer):
    """
    Enhanced user creation serializer with additional validation and preference creation
    """
    password = serializers.CharField(
        style={"input_type": "password"},
        write_only=True,
        validators=[validate_password]
    )
    confirm_password = serializers.CharField(
        style={"input_type": "password"},
        write_only=True
    )
    preferences = UserPreferenceSerializer(required=False)
    
    class Meta(DjoserUserCreateSerializer.Meta):
        model = User
        fields = (
            'email', 'name', 'phone', 'password', 'confirm_password',
            'preferred_cuisine', 'preferences'
        )
    
    def validate(self, attrs):
        """Validate password match and email domain if needed"""
        # Validate password match
        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError({
                'confirm_password': "Passwords do not match."
            })
        
        # Remove confirm_password from attrs
        attrs.pop('confirm_password', None)
        
        # Validate email domain (optional business rule)
        email = attrs.get('email', '')
        if email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise serializers.ValidationError({
                'email': "Enter a valid email address."
            })
        
        # Validate phone if provided
        if attrs.get('phone'):
            phone = attrs['phone']
            phone_digits = re.sub(r'\D', '', phone)
            if len(phone_digits) < 9 or len(phone_digits) > 15:
                raise serializers.ValidationError({
                    'phone': "Phone number must be between 9 and 15 digits."
                })
        
        return attrs
    
    @transaction.atomic
    def create(self, validated_data):
        """Create user with atomic transaction"""
        preferences_data = validated_data.pop('preferences', None)
        
        try:
            # Create user
            user = User.objects.create_user(**validated_data)
            
            # Create default preferences
            if preferences_data:
                UserPreference.objects.create(user=user, **preferences_data)
            else:
                UserPreference.objects.create(user=user)
            
            # Log user creation activity
            request = self.context.get('request')
            UserActivity.objects.create(
                user=user,
                activity_type=UserActivity.ActivityType.PROFILE_UPDATE,
                description="User account created",
                ip_address=request.META.get('REMOTE_ADDR') if request else None,
                user_agent=request.META.get('HTTP_USER_AGENT') if request else None,
                metadata={'method': 'registration'}
            )
            
            return user
            
        except IntegrityError as e:
            if 'email' in str(e).lower():
                raise serializers.ValidationError({
                    'email': 'A user with this email already exists.'
                })
            raise serializers.ValidationError(str(e))


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user profile
    """
    class Meta:
        model = User
        fields = ('name', 'phone', 'avatar', 'preferred_cuisine')
    
    def validate_phone(self, value):
        """Validate phone number format"""
        if value:
            phone_digits = re.sub(r'\D', '', value)
            if len(phone_digits) < 9 or len(phone_digits) > 15:
                raise serializers.ValidationError(
                    "Phone number must be between 9 and 15 digits."
                )
        return value
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update user with atomic transaction"""
        # Track changes for activity log
        changes = {}
        for field, value in validated_data.items():
            if getattr(instance, field) != value:
                changes[field] = {
                    'old': str(getattr(instance, field)),
                    'new': str(value)
                }
        
        # Update instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Log activity if changes were made
        if changes:
            request = self.context.get('request')
            UserActivity.objects.create(
                user=instance,
                activity_type=UserActivity.ActivityType.PROFILE_UPDATE,
                description="Profile updated",
                ip_address=request.META.get('REMOTE_ADDR') if request else None,
                user_agent=request.META.get('HTTP_USER_AGENT') if request else None,
                metadata={'changes': changes}
            )
        
        return instance


class UserActivitySerializer(serializers.ModelSerializer):
    """
    Serializer for user activities
    """
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True)
    
    class Meta:
        model = UserActivity
        fields = (
            'id', 'user_email', 'user_name', 'activity_type',
            'description', 'ip_address', 'user_agent', 'metadata',
            'created_at'
        )
        read_only_fields = fields


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for password change
    """
    old_password = serializers.CharField(
        style={"input_type": "password"},
        write_only=True
    )
    new_password = serializers.CharField(
        style={"input_type": "password"},
        write_only=True,
        validators=[validate_password]
    )
    confirm_new_password = serializers.CharField(
        style={"input_type": "password"},
        write_only=True
    )
    
    def validate(self, attrs):
        """Validate password match"""
        if attrs.get('new_password') != attrs.get('confirm_new_password'):
            raise serializers.ValidationError({
                'confirm_new_password': "New passwords do not match."
            })
        return attrs
    
    def validate_old_password(self, value):
        """Validate old password"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value


class UserRoleSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user role (admin only)
    """
    class Meta:
        model = User
        fields = ('role',)
    
    def validate_role(self, value):
        """Validate role change"""
        if value not in [User.Role.USER, User.Role.MANAGER, User.Role.ADMIN]:
            raise serializers.ValidationError("Invalid role specified.")
        return value
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update user role with atomic transaction"""
        old_role = instance.role
        new_role = validated_data.get('role')
        
        if old_role != new_role:
            instance.role = new_role
            instance.save()
            
            # Log role change
            request = self.context.get('request')
            UserActivity.objects.create(
                user=instance,
                activity_type=UserActivity.ActivityType.PROFILE_UPDATE,
                description=f"Role changed from {old_role} to {new_role}",
                ip_address=request.META.get('REMOTE_ADDR') if request else None,
                user_agent=request.META.get('HTTP_USER_AGENT') if request else None,
                metadata={'old_role': old_role, 'new_role': new_role}
            )
        
        return instance


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login
    """
    email = serializers.EmailField()
    password = serializers.CharField(
        style={"input_type": "password"},
        trim_whitespace=False,
        write_only=True
    )
    
    def validate(self, attrs):
        """Validate credentials and authenticate user"""
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            user = authenticate(
                request=self.context.get('request'),
                email=email,
                password=password
            )
            
            if not user:
                raise serializers.ValidationError(
                    "Unable to log in with provided credentials.",
                    code='authorization'
                )
            
            if not user.is_active:
                raise serializers.ValidationError(
                    "User account is disabled.",
                    code='authorization'
                )
            
            if not user.is_verified:
                raise serializers.ValidationError(
                    "Email not verified. Please check your email.",
                    code='authorization'
                )
            
            attrs['user'] = user
            
            # Log login activity
            UserActivity.objects.create(
                user=user,
                activity_type=UserActivity.ActivityType.LOGIN,
                ip_address=self.context.get('request').META.get('REMOTE_ADDR'),
                user_agent=self.context.get('request').META.get('HTTP_USER_AGENT'),
                metadata={'method': 'password'}
            )
            
            # Update last activity
            user.update_last_activity()
            
        else:
            raise serializers.ValidationError(
                'Must include "email" and "password".',
                code='authorization'
            )
        
        return attrs