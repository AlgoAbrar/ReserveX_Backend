# from django.contrib import admin

# # Register your models here.
"""
Users App Admin Configuration
Django admin interface customization for User model and related models
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from django.contrib.admin import SimpleListFilter

from .models import User, UserActivity, UserPreference


class RoleFilter(SimpleListFilter):
    """Custom filter for user roles"""
    title = _('user role')
    parameter_name = 'role'
    
    def lookups(self, request, model_admin):
        return User.Role.choices
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(role=self.value())
        return queryset


class VerificationFilter(SimpleListFilter):
    """Custom filter for email verification status"""
    title = _('verification status')
    parameter_name = 'verification'
    
    def lookups(self, request, model_admin):
        return (
            ('verified', _('Verified')),
            ('unverified', _('Unverified')),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'verified':
            return queryset.filter(is_verified=True)
        if self.value() == 'unverified':
            return queryset.filter(is_verified=False)
        return queryset


class UserPreferenceInline(admin.StackedInline):
    """Inline admin for UserPreference"""
    model = UserPreference
    can_delete = False
    verbose_name_plural = 'Preferences'
    fieldsets = (
        (_('Notification Preferences'), {
            'fields': ('email_notifications', 'sms_notifications', 'push_notifications'),
            'classes': ('wide',)
        }),
        (_('Booking Preferences'), {
            'fields': ('default_duration', 'preferred_seat_types', 'dietary_restrictions'),
            'classes': ('wide',)
        }),
        (_('Regional Settings'), {
            'fields': ('language', 'timezone'),
            'classes': ('wide',)
        }),
    )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom User Admin with enhanced features
    """
    list_display = (
        'email', 'name', 'role_badge', 'verification_badge', 
        'status_badge', 'booking_count', 'last_activity_display'
    )
    list_filter = (RoleFilter, VerificationFilter, 'is_active', 'date_joined')
    search_fields = ('email', 'name', 'phone')
    ordering = ('-date_joined',)
    readonly_fields = (
        'id', 'date_joined', 'last_updated', 'last_activity',
        'user_activities_link', 'user_bookings_link'
    )
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('id', 'email', 'name', 'phone', 'avatar'),
            'classes': ('wide',)
        }),
        (_('Role & Permissions'), {
            'fields': ('role', 'is_active', 'is_verified', 'is_staff', 'is_superuser'),
            'classes': ('wide',)
        }),
        (_('Preferences'), {
            'fields': ('preferred_cuisine',),
            'classes': ('wide',)
        }),
        (_('Timestamps'), {
            'fields': ('date_joined', 'last_updated', 'last_activity'),
            'classes': ('wide',)
        }),
        (_('Related Data'), {
            'fields': ('user_activities_link', 'user_bookings_link'),
            'classes': ('wide',)
        }),
        (_('Metadata'), {
            'fields': ('metadata',),
            'classes': ('wide',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'phone', 'password1', 'password2', 'role'),
        }),
    )
    
    inlines = [UserPreferenceInline]
    
    def get_queryset(self, request):
        """Optimize queryset with related counts"""
        return super().get_queryset(request).annotate(
            booking_count=Count('booking', distinct=True)
        )
    
    def role_badge(self, obj):
        """Display role with colored badge"""
        colors = {
            'USER': '#28a745',      # Green
            'MANAGER': '#ffc107',    # Yellow
            'ADMIN': '#dc3545',      # Red
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 12px; font-weight: bold;">{}</span>',
            colors.get(obj.role, '#6c757d'),
            obj.get_role_display()
        )
    role_badge.short_description = _('Role')
    role_badge.admin_order_field = 'role'
    
    def verification_badge(self, obj):
        """Display verification status with badge"""
        if obj.is_verified:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 8px; '
                'border-radius: 3px;">✓ Verified</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 8px; '
            'border-radius: 3px;">✗ Unverified</span>'
        )
    verification_badge.short_description = _('Email Verification')
    verification_badge.admin_order_field = 'is_verified'
    
    def status_badge(self, obj):
        """Display account status with badge"""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 8px; '
                'border-radius: 3px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #6c757d; color: white; padding: 3px 8px; '
            'border-radius: 3px;">Inactive</span>'
        )
    status_badge.short_description = _('Status')
    status_badge.admin_order_field = 'is_active'
    
    def booking_count(self, obj):
        """Display total bookings count"""
        return getattr(obj, 'booking_count', 0)
    booking_count.short_description = _('Total Bookings')
    booking_count.admin_order_field = 'booking_count'
    
    def last_activity_display(self, obj):
        """Display last activity with time ago format"""
        from django.utils.timesince import timesince
        if obj.last_activity:
            return f"{timesince(obj.last_activity)} ago"
        return "Never"
    last_activity_display.short_description = _('Last Activity')
    
    def user_activities_link(self, obj):
        """Link to user activities"""
        count = obj.activities.count()
        url = reverse('admin:users_useractivity_changelist') + f'?user__id__exact={obj.id}'
        return format_html('<a href="{}">View Activities ({})</a>', url, count)
    user_activities_link.short_description = _('Activities')
    
    def user_bookings_link(self, obj):
        """Link to user bookings"""
        from django.apps import apps
        if apps.is_installed('bookings'):
            count = obj.booking_set.count()
            url = reverse('admin:bookings_booking_changelist') + f'?user__id__exact={obj.id}'
            return format_html('<a href="{}">View Bookings ({})</a>', url, count)
        return "Bookings app not installed"
    user_bookings_link.short_description = _('Bookings')
    
    actions = ['make_verified', 'make_unverified', 'make_active', 'make_inactive']
    
    def make_verified(self, request, queryset):
        """Mark selected users as verified"""
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} users marked as verified.')
    make_verified.short_description = _("Mark selected users as verified")
    
    def make_unverified(self, request, queryset):
        """Mark selected users as unverified"""
        updated = queryset.update(is_verified=False)
        self.message_user(request, f'{updated} users marked as unverified.')
    make_unverified.short_description = _("Mark selected users as unverified")
    
    def make_active(self, request, queryset):
        """Activate selected users"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} users activated.')
    make_active.short_description = _("Activate selected users")
    
    def make_inactive(self, request, queryset):
        """Deactivate selected users"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} users deactivated.')
    make_inactive.short_description = _("Deactivate selected users")
    
    def save_model(self, request, obj, form, change):
        """Log user changes in admin"""
        super().save_model(request, obj, form, change)
        if change:
            UserActivity.objects.create(
                user=obj,
                activity_type=UserActivity.ActivityType.PROFILE_UPDATE,
                description=f"User updated via admin by {request.user.email}",
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT'),
                metadata={'admin': request.user.email}
            )


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    """
    Admin interface for user activities
    """
    list_display = ('user_email', 'activity_type', 'description_short', 'ip_address', 'created_at')
    list_filter = ('activity_type', 'created_at')
    search_fields = ('user__email', 'user__name', 'description', 'ip_address')
    readonly_fields = ('id', 'user', 'activity_type', 'description', 'ip_address', 
                      'user_agent', 'metadata', 'created_at')
    date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('user')
    
    def user_email(self, obj):
        """Display user email with link"""
        url = reverse('admin:users_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    user_email.short_description = _('User')
    user_email.admin_order_field = 'user__email'
    
    def description_short(self, obj):
        """Truncate long descriptions"""
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
    description_short.short_description = _('Description')
    
    def has_add_permission(self, request):
        """Prevent manual addition of activity logs"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent editing of activity logs"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion only for admins"""
        return request.user.is_superuser


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    """
    Admin interface for user preferences
    """
    list_display = ('user_email', 'language', 'timezone', 'email_notifications', 
                   'sms_notifications', 'push_notifications', 'updated_at')
    list_filter = ('language', 'timezone', 'email_notifications', 'sms_notifications')
    search_fields = ('user__email', 'user__name')
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    fieldsets = (
        (_('User'), {
            'fields': ('user',),
            'classes': ('wide',)
        }),
        (_('Notification Preferences'), {
            'fields': ('email_notifications', 'sms_notifications', 'push_notifications'),
            'classes': ('wide',)
        }),
        (_('Booking Preferences'), {
            'fields': ('default_duration', 'preferred_seat_types', 'dietary_restrictions'),
            'classes': ('wide',)
        }),
        (_('Regional Settings'), {
            'fields': ('language', 'timezone'),
            'classes': ('wide',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('wide',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('user')
    
    def user_email(self, obj):
        """Display user email with link"""
        url = reverse('admin:users_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    user_email.short_description = _('User')
    user_email.admin_order_field = 'user__email'
    
    def save_model(self, request, obj, form, change):
        """Log preference changes"""
        super().save_model(request, obj, form, change)
        if change:
            UserActivity.objects.create(
                user=obj.user,
                activity_type=UserActivity.ActivityType.PROFILE_UPDATE,
                description=f"Preferences updated via admin by {request.user.email}",
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT'),
                metadata={'admin': request.user.email}
            )


# Unregister the default Group model if we don't need it
# admin.site.unregister(Group)