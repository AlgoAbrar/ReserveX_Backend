"""
API v1 URL Configuration
Main URL routing for API version 1, aggregating all app endpoints
"""

from django.urls import path, include
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.conf import settings
from django.urls import reverse
from django.urls import path, include
from django.views.generic.base import RedirectView


# API root view for v1
# @api_view(['GET'])
# @permission_classes([AllowAny])
# def api_v1_root(request):
#     """
#     API v1 root endpoint providing an overview of all available endpoints
#     """
#     base_url = request.build_absolute_uri('/api/v1/')
    
#     return Response({
#         'name': 'ReserveX API v1',
#         'version': '1.0.0',
#         'description': 'Restaurant Reservation System API',
#         'documentation': {
#             'swagger': request.build_absolute_uri('/swagger/'),
#             'redoc': request.build_absolute_uri('/redoc/'),
#         },
#         'endpoints': {
#             # Authentication endpoints
#             'auth': {
#                 'register': reverse('user-create'),
#                 'login': reverse('jwt-create'),
#                 'refresh': reverse('jwt-refresh'),
#                 'verify': reverse('jwt-verify'),
#                 'password_reset': reverse('user-reset-password'),
#                 'password_reset_confirm': reverse('user-reset-password-confirm'),
#                 'activation': reverse('user-activation'),
#                 'resend_activation': reverse('user-resend-activation'),
#                 'me': reverse('user-me'),
#                 'users': reverse('user-list'),
#             },
            
#             # Core app endpoints
#             'restaurants': {
#                 'list': reverse('restaurant-list'),
#                 'detail': 'restaurant-detail',
#                 'branches': 'restaurant-branches',
#                 'menu': 'restaurant-menu',
#                 'availability': 'restaurant-availability',
#                 'featured': reverse('restaurant-featured'),
#                 'search_by_location': reverse('restaurant-search-location'),
#             },
            
#             'branches': {
#                 'list': reverse('branch-list'),
#                 'detail': 'branch-detail',
#                 'tables': 'branch-tables',
#                 'availability': 'branch-availability',
#                 'statistics': 'branch-statistics',
#             },
            
#             'tables': {
#                 'list': reverse('table-list'),
#                 'detail': 'table-detail',
#                 'reserve': 'table-reserve',
#             },
            
#             'menu_items': {
#                 'list': reverse('menuitem-list'),
#                 'detail': 'menuitem-detail',
#                 'popular': reverse('menu-items-popular'),
#                 'categories': reverse('menu-items-categories'),
#             },
            
#             # Bookings endpoints
#             'bookings': {
#                 'list': reverse('booking-list'),
#                 'detail': 'booking-detail',
#                 'my_bookings': reverse('my-bookings'),
#                 'upcoming': reverse('upcoming-bookings'),
#                 'check_availability': reverse('check-availability'),
#                 'update_status': 'booking-update-status',
#                 'history': 'booking-history',
#                 'menu_items': 'booking-menu-items',
#                 'pending_requests': reverse('pending-requests'),
#             },
            
#             'booking_menu': {
#                 'list': reverse('booking-menu-list'),
#                 'detail': 'booking-menu-detail',
#             },
            
#             'booking_history': {
#                 'list': reverse('booking-history-list'),
#                 'detail': 'booking-history-detail',
#             },
            
#             # Payments endpoints
#             'payments': {
#                 'list': reverse('payment-list'),
#                 'detail': 'payment-detail',
#                 'start': reverse('payment-start'),
#                 'my_payments': reverse('my-payments'),
#                 'refund': 'payment-refund',
#                 'logs': 'payment-logs',
#                 'statistics': reverse('payment-statistics'),
#             },
            
#             'payment_methods': {
#                 'list': reverse('payment-method-list'),
#                 'detail': 'payment-method-detail',
#                 'set_default': 'payment-method-set-default',
#             },
            
#             'refunds': {
#                 'list': reverse('refund-list'),
#                 'detail': 'refund-detail',
#             },
            
#             # Dashboard endpoints
#             'dashboard': {
#                 'user_overview': reverse('user-dashboard-overview'),
#                 'user_bookings': reverse('user-dashboard-bookings'),
#                 'user_statistics': reverse('user-dashboard-statistics'),
#                 'manager_overview': reverse('manager-dashboard-overview'),
#                 'manager_bookings': reverse('manager-dashboard-bookings'),
#                 'manager_pending': reverse('manager-dashboard-pending-approvals'),
#                 'manager_performance': reverse('manager-dashboard-performance'),
#                 'admin_overview': reverse('admin-dashboard-overview'),
#                 'admin_users': reverse('admin-dashboard-users'),
#                 'admin_restaurants': reverse('admin-dashboard-restaurants'),
#                 'admin_analytics': reverse('admin-dashboard-analytics'),
#             },
#         },
#         'api_health': request.build_absolute_uri('/health/'),
#     })

@api_view(['GET'])
@permission_classes([AllowAny])
def api_v1_root(request):
    """
    API v1 root endpoint redirecting to the main API documentation
    """
    return Response({
        'message': 'Welcome to ReserveX API v1',
        'documentation': request.build_absolute_uri('/swagger/'),
        'endpoints': request.build_absolute_uri('/api/v1/'),
    })

# URL patterns for v1
# urlpatterns = [
#     # API v1 root
#     path('', api_v1_root, name='api-v1-root'),
    
#     # Authentication endpoints (using djoser)
#     path('auth/', include('djoser.urls')),
#     path('auth/', include('djoser.urls.jwt')),
    
#     # App endpoints
#     path('', include('users.urls')),
#     path('', include('restaurants.urls')),
#     path('', include('bookings.urls')),
#     path('', include('payments.urls')),
#     path('', include('dashboard.urls')),
# ]

urlpatterns = [
    # API v1 root
    path('', api_v1_root, name='api-v1-root'),
    
    # Redirect /api/v1 to the full API root
    path('', RedirectView.as_view(url='/api/v1/', permanent=False)),
    
    # Authentication endpoints (using djoser)
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.jwt')),
    
    # App endpoints
    path('', include('users.urls')),
    path('', include('restaurants.urls')),
    path('', include('bookings.urls')),
    path('', include('payments.urls')),
    path('', include('dashboard.urls')),
]

# Debug toolbar URLs (only in development)
if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns

# API versioning note:
# When adding v2, create a new file api/v2/urls.py and include it in the main urls.py
# with path('api/v2/', include('api.v2.urls')),