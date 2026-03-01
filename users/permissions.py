"""
Users App Permissions
Custom permission classes for role-based access control in ReserveX
"""

from rest_framework import permissions
from django.core.exceptions import ObjectDoesNotExist


class IsAdmin(permissions.BasePermission):
    """
    Permission class for admin users only.
    Grants access to users with ADMIN role.
    """
    message = "This resource is only accessible to administrators."
    
    def has_permission(self, request, view):
        """Check if user is authenticated and has admin role"""
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'ADMIN'
        )
    
    def has_object_permission(self, request, view, obj):
        """Object-level permission for admin users"""
        return self.has_permission(request, view)


class IsManager(permissions.BasePermission):
    """
    Permission class for manager users.
    Grants access to users with MANAGER role.
    """
    message = "This resource is only accessible to restaurant managers."
    
    def has_permission(self, request, view):
        """Check if user is authenticated and has manager role"""
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'MANAGER'
        )
    
    def has_object_permission(self, request, view, obj):
        """Object-level permission for manager users"""
        return self.has_permission(request, view)


class IsUser(permissions.BasePermission):
    """
    Permission class for regular users.
    Grants access to users with USER role.
    """
    message = "This resource is only accessible to regular users."
    
    def has_permission(self, request, view):
        """Check if user is authenticated and has user role"""
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'USER'
        )
    
    def has_object_permission(self, request, view, obj):
        """Object-level permission for regular users"""
        return self.has_permission(request, view)


class IsAdminOrManager(permissions.BasePermission):
    """
    Permission class for admin or manager users.
    Grants access to users with ADMIN or MANAGER role.
    """
    message = "This resource is only accessible to administrators or managers."
    
    def has_permission(self, request, view):
        """Check if user is authenticated and has admin or manager role"""
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role in ['ADMIN', 'MANAGER']
        )
    
    def has_object_permission(self, request, view, obj):
        """Object-level permission for admin or manager users"""
        return self.has_permission(request, view)


class IsAdminOrManagerOrReadOnly(permissions.BasePermission):
    """
    Permission class that allows:
    - Admin and manager users full access
    - Other authenticated users read-only access
    - Unauthenticated users read-only access for safe methods
    """
    message = "You don't have permission to perform this action."
    
    def has_permission(self, request, view):
        """Check permissions based on user role and request method"""
        # Allow read-only access to anyone for safe methods
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # For write operations, require authentication and admin/manager role
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role in ['ADMIN', 'MANAGER']
        )
    
    def has_object_permission(self, request, view, obj):
        """Object-level permission check"""
        # Allow read-only access for safe methods
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # For write operations, require admin/manager role
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role in ['ADMIN', 'MANAGER']
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission class that allows:
    - Admin users full access
    - Users to access their own objects
    - Others have no access
    """
    message = "You don't have permission to access this resource."
    
    def has_permission(self, request, view):
        """Basic permission check - must be authenticated"""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Check if user is owner or admin"""
        # Admin can access any object
        if request.user.role == 'ADMIN':
            return True
        
        # Check if object has 'user' attribute
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # Check if object has 'owner' attribute
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        
        # Check if object itself is a User instance
        if isinstance(obj, request.user.__class__):
            return obj == request.user
        
        return False


class IsManagerOfRestaurant(permissions.BasePermission):
    """
    Permission class for managers to access their own restaurants.
    Checks if the user is a manager and manages the specific restaurant.
    """
    message = "You can only access restaurants you manage."
    
    def has_permission(self, request, view):
        """Must be authenticated and have manager role"""
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'MANAGER'
        )
    
    def has_object_permission(self, request, view, obj):
        """Check if user manages this restaurant"""
        from restaurants.models import Restaurant
        
        # Get the restaurant object
        restaurant = None
        
        if isinstance(obj, Restaurant):
            restaurant = obj
        elif hasattr(obj, 'restaurant'):
            restaurant = obj.restaurant
        elif hasattr(obj, 'branch') and hasattr(obj.branch, 'restaurant'):
            restaurant = obj.branch.restaurant
        
        if restaurant:
            return restaurant.manager == request.user
        
        return False


class IsAdminOrManagerOfRestaurant(permissions.BasePermission):
    """
    Permission class that allows:
    - Admin users full access
    - Managers to access their own restaurants
    """
    message = "You don't have permission to access this resource."
    
    def has_permission(self, request, view):
        """Must be authenticated"""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Admin can access all, managers can access their own"""
        # Admin can access anything
        if request.user.role == 'ADMIN':
            return True
        
        # Managers can access their own restaurants
        if request.user.role == 'MANAGER':
            from restaurants.models import Restaurant
            
            # Get the restaurant object
            restaurant = None
            
            if isinstance(obj, Restaurant):
                restaurant = obj
            elif hasattr(obj, 'restaurant'):
                restaurant = obj.restaurant
            elif hasattr(obj, 'branch') and hasattr(obj.branch, 'restaurant'):
                restaurant = obj.branch.restaurant
            
            if restaurant:
                return restaurant.manager == request.user
        
        return False


class IsVerifiedUser(permissions.BasePermission):
    """
    Permission class that requires user to have verified email.
    """
    message = "Email verification required to access this resource."
    
    def has_permission(self, request, view):
        """Check if user is authenticated and verified"""
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.is_verified
        )
    
    def has_object_permission(self, request, view, obj):
        """Object-level permission for verified users"""
        return self.has_permission(request, view)


class IsActiveUser(permissions.BasePermission):
    """
    Permission class that requires user account to be active.
    """
    message = "Your account is inactive. Please contact support."
    
    def has_permission(self, request, view):
        """Check if user is authenticated and active"""
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.is_active
        )
    
    def has_object_permission(self, request, view, obj):
        """Object-level permission for active users"""
        return self.has_permission(request, view)


class CanManageBookings(permissions.BasePermission):
    """
    Permission class for booking management:
    - Admin can manage all bookings
    - Managers can manage bookings for their restaurants
    - Users can manage their own bookings
    """
    message = "You don't have permission to manage this booking."
    
    def has_permission(self, request, view):
        """Must be authenticated"""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Check if user can manage the booking"""
        from bookings.models import Booking
        
        # Admin can manage any booking
        if request.user.role == 'ADMIN':
            return True
        
        # Users can manage their own bookings
        if request.user.role == 'USER' and hasattr(obj, 'user'):
            return obj.user == request.user
        
        # Managers can manage bookings for their restaurants
        if request.user.role == 'MANAGER' and isinstance(obj, Booking):
            return obj.restaurant.manager == request.user
        
        return False


class CanManagePayments(permissions.BasePermission):
    """
    Permission class for payment management:
    - Admin can manage all payments
    - Users can view their own payments
    - Managers can view payments for their restaurants
    """
    message = "You don't have permission to access this payment."
    
    def has_permission(self, request, view):
        """Must be authenticated"""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Check if user can access the payment"""
        from payments.models import Payment
        
        # Admin can access any payment
        if request.user.role == 'ADMIN':
            return True
        
        # Users can access their own payments
        if request.user.role == 'USER' and hasattr(obj, 'booking') and hasattr(obj.booking, 'user'):
            return obj.booking.user == request.user
        
        # Managers can access payments for their restaurants
        if request.user.role == 'MANAGER' and isinstance(obj, Payment):
            return obj.booking.restaurant.manager == request.user
        
        return False


class CanViewDashboard(permissions.BasePermission):
    """
    Permission class for dashboard access:
    - Users can view user dashboard
    - Managers can view manager dashboard
    - Admins can view all dashboards
    """
    message = "You don't have permission to view this dashboard."
    
    def has_permission(self, request, view):
        """Must be authenticated"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        dashboard_type = view.kwargs.get('dashboard_type', 'user')
        
        if dashboard_type == 'user':
            return request.user.role in ['USER', 'ADMIN']
        elif dashboard_type == 'manager':
            return request.user.role in ['MANAGER', 'ADMIN']
        elif dashboard_type == 'admin':
            return request.user.role == 'ADMIN'
        
        return False