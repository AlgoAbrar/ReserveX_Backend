from rest_framework import permissions


# -------------------------------
# 🔹 BASE ROLE PERMISSION
# -------------------------------
class BaseRolePermission(permissions.BasePermission):
    allowed_roles = []

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in self.allowed_roles
        )

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


# -------------------------------
# 🔹 SIMPLE ROLE PERMISSIONS
# -------------------------------
class IsAdmin(BaseRolePermission):
    allowed_roles = ['ADMIN']


class IsManager(BaseRolePermission):
    allowed_roles = ['MANAGER']


class IsUser(BaseRolePermission):
    allowed_roles = ['USER']


class IsAdminOrManager(BaseRolePermission):
    allowed_roles = ['ADMIN', 'MANAGER']


# -------------------------------
# 🔹 READ ONLY + ROLE
# -------------------------------
class IsAdminOrManagerOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in ['ADMIN', 'MANAGER']
        )

    has_object_permission = has_permission


# -------------------------------
# 🔹 OWNER OR ADMIN
# -------------------------------
class IsOwnerOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'ADMIN':
            return True

        return getattr(obj, 'user', None) == request.user or \
               getattr(obj, 'owner', None) == request.user or \
               obj == request.user


# -------------------------------
# 🔹 VERIFIED & ACTIVE
# -------------------------------
class IsVerifiedUser(BaseRolePermission):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_verified


class IsActiveUser(BaseRolePermission):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_active


# -------------------------------
# 🔹 RESTAURANT BASED
# -------------------------------
def get_restaurant(obj):
    return getattr(obj, 'restaurant', None) or \
           getattr(getattr(obj, 'branch', None), 'restaurant', None) or obj


class IsManagerOfRestaurant(BaseRolePermission):
    allowed_roles = ['MANAGER']

    def has_object_permission(self, request, view, obj):
        restaurant = get_restaurant(obj)
        return restaurant and restaurant.manager == request.user


class IsAdminOrManagerOfRestaurant(BaseRolePermission):
    allowed_roles = ['ADMIN', 'MANAGER']

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'ADMIN':
            return True
        restaurant = get_restaurant(obj)
        return restaurant and restaurant.manager == request.user


# -------------------------------
# 🔹 BOOKING / PAYMENT
# -------------------------------
class CanManageBookings(BaseRolePermission):
    allowed_roles = ['ADMIN', 'MANAGER', 'USER']

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'ADMIN':
            return True
        if request.user.role == 'USER':
            return getattr(obj, 'user', None) == request.user
        return obj.restaurant.manager == request.user


class CanManagePayments(BaseRolePermission):
    allowed_roles = ['ADMIN', 'MANAGER', 'USER']

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'ADMIN':
            return True
        if request.user.role == 'USER':
            return obj.booking.user == request.user
        return obj.booking.restaurant.manager == request.user


# -------------------------------
# 🔹 DASHBOARD ACCESS
# -------------------------------
class CanViewDashboard(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        role = request.user.role
        dashboard = view.kwargs.get('dashboard_type', 'user')

        rules = {
            'user': ['USER', 'ADMIN'],
            'manager': ['MANAGER', 'ADMIN'],
            'admin': ['ADMIN']
        }

        return role in rules.get(dashboard, [])