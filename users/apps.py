# from django.apps import AppConfig


# class UsersConfig(AppConfig):
#     name = 'users'
"""
Users App Configuration
Django app configuration for the users app with signal registration
"""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class UsersConfig(AppConfig):
    """
    Configuration for the users app
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'
    verbose_name = _('User Management')
    
    def ready(self):
        """
        Initialize app when Django starts.
        Registers signals and performs any necessary startup tasks.
        """
        # Import signals to register them
        #from . import signals
        
        # Log app initialization in production
        import os
        if not os.environ.get('DEBUG'):
            import logging
            logger = logging.getLogger(__name__)
            logger.info("Users app initialized with role-based permissions")
        
        # Perform any other startup tasks here
        self._create_default_groups()
    
    # def _create_default_groups(self):
    #     """
    #     Create default permission groups if they don't exist.
    #     This ensures consistent role-based permissions across environments.
    #     """
    #     try:
    #         from django.contrib.auth.models import Group, Permission
    #         from django.contrib.contenttypes.models import ContentType
    #         from .models import User
            
    #         # Define default groups and their permissions
    #         groups_permissions = {
    #             'USER': [],  # Regular users get permissions via model-level checks
    #             'MANAGER': [
    #                 'add_restaurant', 'change_restaurant', 'delete_restaurant',
    #                 'add_branch', 'change_branch', 'delete_branch',
    #                 'add_table', 'change_table', 'delete_table',
    #                 'add_menuitem', 'change_menuitem', 'delete_menuitem',
    #                 'view_booking', 'change_booking',  # Can view and update bookings
    #             ],
    #             'ADMIN': [  # Admins get all permissions
    #                 'add_user', 'change_user', 'delete_user', 'view_user',
    #                 'add_restaurant', 'change_restaurant', 'delete_restaurant', 'view_restaurant',
    #                 'add_branch', 'change_branch', 'delete_branch', 'view_branch',
    #                 'add_table', 'change_table', 'delete_table', 'view_table',
    #                 'add_menuitem', 'change_menuitem', 'delete_menuitem', 'view_menuitem',
    #                 'add_booking', 'change_booking', 'delete_booking', 'view_booking',
    #                 'add_payment', 'change_payment', 'delete_payment', 'view_payment',
    #             ],
    #         }
            
    #         # Get content type for User model
    #         user_content_type = ContentType.objects.get_for_model(User)
            
    #         # Create or update groups
    #         for group_name, permissions in groups_permissions.items():
    #             group, created = Group.objects.get_or_create(name=group_name)
                
    #             if created:
    #                 # Add permissions to group
    #                 for perm_codename in permissions:
    #                     try:
    #                         # Try to find permission
    #                         permission = Permission.objects.get(
    #                             codename=perm_codename,
    #                             content_type=user_content_type
    #                         )
    #                         group.permissions.add(permission)
    #                     except Permission.DoesNotExist:
    #                         # Permission might belong to another model
    #                         try:
    #                             permission = Permission.objects.get(codename=perm_codename)
    #                             group.permissions.add(permission)
    #                         except Permission.DoesNotExist:
    #                             # Log missing permissions in development
    #                             import os
    #                             if os.environ.get('DEBUG'):
    #                                 import logging
    #                                 logger = logging.getLogger(__name__)
    #                                 logger.warning(f"Permission '{perm_codename}' not found for group '{group_name}'")
                    
    #                 group.save()
        
    #     except Exception as e:
    #         # Silently fail in production, log in development
    #         import os
    #         if os.environ.get('DEBUG'):
    #             import logging
    #             logger = logging.getLogger(__name__)
    #             logger.error(f"Error creating default groups: {e}")
    
    def _create_default_groups(self):
        """
        Create default permission groups if they don't exist.
        This ensures consistent role-based permissions across environments.
        """
        from django.apps import apps
    
        # Check if apps are ready before accessing models
        if not apps.ready:
         return
    
        try:
            from django.contrib.auth.models import Group, Permission
            from django.contrib.contenttypes.models import ContentType
            from .models import User
        
        # Rest of the method remains the same...
        # ... existing code ...
        
        except Exception as e:
        # Silently fail in production, log in development
            import os
            if os.environ.get('DEBUG'):
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error creating default groups: {e}")
    
    def get_role_display_name(self, role_code):
        """
        Get human-readable role name from role code.
        Useful for templates and API responses.
        """
        role_names = {
            'USER': 'Regular User',
            'MANAGER': 'Restaurant Manager',
            'ADMIN': 'Administrator',
        }
        return role_names.get(role_code, role_code)
    
    def get_role_permissions(self, role_code):
        """
        Get list of permissions for a given role.
        Returns a dictionary of permission categories.
        """
        base_permissions = {
            'can_view_own_profile': True,
            'can_edit_own_profile': True,
            'can_change_password': True,
        }
        
        role_specific = {
            'USER': {
                'can_book_restaurants': True,
                'can_view_own_bookings': True,
                'can_cancel_own_bookings': True,
                'can_make_payments': True,
                'can_view_restaurants': True,
                'can_view_menu': True,
            },
            'MANAGER': {
                'can_manage_own_restaurants': True,
                'can_manage_branches': True,
                'can_manage_tables': True,
                'can_manage_menu': True,
                'can_view_all_bookings': True,  # For owned restaurants
                'can_confirm_bookings': True,
                'can_reject_bookings': True,
                'can_view_restaurant_analytics': True,
            },
            'ADMIN': {
                'can_manage_all_users': True,
                'can_manage_all_restaurants': True,
                'can_manage_all_bookings': True,
                'can_manage_all_payments': True,
                'can_view_all_analytics': True,
                'can_manage_roles': True,
                'can_access_admin_panel': True,
            },
        }
        
        permissions = base_permissions.copy()
        permissions.update(role_specific.get(role_code, {}))
        
        return permissions
    
    def get_dashboard_components(self, role_code):
        """
        Get dashboard components available for a given role.
        Used by the dashboard app to render appropriate UI.
        """
        components = {
            'USER': [
                'upcoming_bookings',
                'booking_history',
                'favorite_restaurants',
                'recommendations',
                'recent_activity',
            ],
            'MANAGER': [
                'today_bookings',
                'restaurant_overview',
                'table_availability',
                'booking_requests',
                'revenue_today',
                'popular_menu_items',
                'customer_feedback',
            ],
            'ADMIN': [
                'system_overview',
                'user_statistics',
                'restaurant_statistics',
                'booking_statistics',
                'revenue_analytics',
                'platform_growth',
                'recent_activities',
            ],
        }
        
        return components.get(role_code, [])
    
    def get_max_booking_duration(self, role_code):
        """
        Get maximum allowed booking duration for a role.
        """
        durations = {
            'USER': 2,  # 2 hours max for regular users
            'MANAGER': 4,  # 4 hours max for managers (for testing)
            'ADMIN': 24,  # 24 hours max for admins
        }
        return durations.get(role_code, 2)
    
    def get_booking_limits(self, role_code):
        """
        Get booking limits for a role.
        Returns dictionary with various limits.
        """
        limits = {
            'USER': {
                'max_active_bookings': 3,  # Can have max 3 active bookings at once
                'max_advance_days': 30,  # Can book up to 30 days in advance
                'min_advance_hours': 1,  # Must book at least 1 hour in advance
            },
            'MANAGER': {
                'max_active_bookings': 10,
                'max_advance_days': 60,
                'min_advance_hours': 0,  # Can book immediately
            },
            'ADMIN': {
                'max_active_bookings': 100,
                'max_advance_days': 365,
                'min_advance_hours': 0,
            },
        }
        
        return limits.get(role_code, limits['USER'])