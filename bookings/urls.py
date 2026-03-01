"""
Bookings App URL Configuration
URL patterns for booking-related endpoints
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router for ViewSets
router = DefaultRouter()
router.register(r'bookings', views.BookingViewSet, basename='booking')
router.register(r'booking-menu', views.BookingMenuViewSet, basename='booking-menu')
router.register(r'booking-history', views.BookingHistoryViewSet, basename='booking-history')
router.register(r'booking-notifications', views.BookingNotificationViewSet, basename='booking-notification')

# Additional URL patterns
urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
    
    # User-specific booking endpoints
    path('my-bookings/', 
         views.BookingViewSet.as_view({'get': 'my_bookings'}), 
         name='my-bookings'),
    
    path('upcoming/', 
         views.BookingViewSet.as_view({'get': 'upcoming'}), 
         name='upcoming-bookings'),
    
    # Availability check endpoint (public)
    path('check-availability/', 
         views.BookingViewSet.as_view({'get': 'check_availability'}), 
         name='check-availability'),
    
    # Manager endpoints
    path('pending-requests/', 
         views.BookingViewSet.as_view({'get': 'pending_requests'}), 
         name='pending-requests'),
    
    # Admin endpoints
    path('expire-pending/', 
         views.BookingViewSet.as_view({'post': 'expire_pending'}), 
         name='expire-pending'),
    
    path('statistics/', 
         views.BookingViewSet.as_view({'get': 'statistics'}), 
         name='booking-statistics'),
    
    # Booking detail endpoints
    path('bookings/<uuid:pk>/update-status/', 
         views.BookingViewSet.as_view({'post': 'update_status'}), 
         name='booking-update-status'),
    
    path('bookings/<uuid:pk>/history/', 
         views.BookingViewSet.as_view({'get': 'history'}), 
         name='booking-history'),
    
    path('bookings/<uuid:pk>/menu-items/', 
         views.BookingViewSet.as_view({'get': 'menu_items', 'post': 'add_menu_items'}), 
         name='booking-menu-items'),
]

# API versioning support
app_name = 'bookings'