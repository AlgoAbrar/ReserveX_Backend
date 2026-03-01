"""
Dashboard App URL Configuration
URL patterns for role-based dashboard endpoints
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create routers for each dashboard type
user_router = DefaultRouter()
user_router.register(r'user', views.UserDashboardView, basename='user-dashboard')

manager_router = DefaultRouter()
manager_router.register(r'manager', views.ManagerDashboardView, basename='manager-dashboard')

admin_router = DefaultRouter()
admin_router.register(r'admin', views.AdminDashboardView, basename='admin-dashboard')

# URL patterns
urlpatterns = [
    # User dashboard endpoints
    path('user/overview/', 
         views.UserDashboardView.as_view({'get': 'overview'}), 
         name='user-dashboard-overview'),
    
    path('user/bookings/', 
         views.UserDashboardView.as_view({'get': 'bookings'}), 
         name='user-dashboard-bookings'),
    
    path('user/statistics/', 
         views.UserDashboardView.as_view({'get': 'statistics'}), 
         name='user-dashboard-statistics'),
    
    # Manager dashboard endpoints
    path('manager/overview/', 
         views.ManagerDashboardView.as_view({'get': 'overview'}), 
         name='manager-dashboard-overview'),
    
    path('manager/bookings/', 
         views.ManagerDashboardView.as_view({'get': 'bookings'}), 
         name='manager-dashboard-bookings'),
    
    path('manager/pending-approvals/', 
         views.ManagerDashboardView.as_view({'get': 'pending_approvals'}), 
         name='manager-dashboard-pending-approvals'),
    
    path('manager/restaurant-performance/', 
         views.ManagerDashboardView.as_view({'get': 'restaurant_performance'}), 
         name='manager-dashboard-performance'),
    
    # Admin dashboard endpoints
    path('admin/overview/', 
         views.AdminDashboardView.as_view({'get': 'overview'}), 
         name='admin-dashboard-overview'),
    
    path('admin/users/', 
         views.AdminDashboardView.as_view({'get': 'users'}), 
         name='admin-dashboard-users'),
    
    path('admin/restaurants/', 
         views.AdminDashboardView.as_view({'get': 'restaurants'}), 
         name='admin-dashboard-restaurants'),
    
    path('admin/analytics/', 
         views.AdminDashboardView.as_view({'get': 'analytics'}), 
         name='admin-dashboard-analytics'),
]

# Include router URLs
urlpatterns += [
    path('', include(user_router.urls)),
    path('', include(manager_router.urls)),
    path('', include(admin_router.urls)),
]

# API versioning support
app_name = 'dashboard'