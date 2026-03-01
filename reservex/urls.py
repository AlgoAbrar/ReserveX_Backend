# """
# URL configuration for reservex project.

# The `urlpatterns` list routes URLs to views. For more information please see:
#     https://docs.djangoproject.com/en/6.0/topics/http/urls/
# Examples:
# Function views
#     1. Add an import:  from my_app import views
#     2. Add a URL to urlpatterns:  path('', views.home, name='home')
# Class-based views
#     1. Add an import:  from other_app.views import Home
#     2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
# Including another URLconf
#     1. Import the include() function: from django.urls import include, path
#     2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
# """
# from django.contrib import admin
# from django.urls import path

# urlpatterns = [
#     path('admin/', admin.site.urls),
# ]
"""
ReserveX URL Configuration
Production-ready URL routing with API versioning and documentation
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic.base import RedirectView
from debug_toolbar.toolbar import debug_toolbar_urls
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

from .views import api_root_view, health_check_view

# Schema view for Swagger documentation
schema_view = get_schema_view(
    openapi.Info(
        title="ReserveX - Restaurant Reservation System API",
        default_version='v1',
        description="""
        Complete Restaurant Reservation System API.
        
        ## Features
        - User authentication with JWT
        - Role-based access control (USER, MANAGER, ADMIN)
        - Restaurant and branch management
        - Table booking with conflict prevention
        - Payment processing simulation
        - Dashboard analytics for users and managers
        
        ## Authentication
        Use JWT token in Authorization header:
        `Authorization: JWT <your_token>`
        
        ## Roles
        - **USER**: Can browse restaurants and make bookings
        - **MANAGER**: Can manage their restaurants, tables, and bookings
        - **ADMIN**: Full system access
        """,
        terms_of_service="https://www.reservex.com/terms/",
        contact=openapi.Contact(
            name="ReserveX Support",
            email="support@reservex.com",
            url="https://www.reservex.com/contact"
        ),
        license=openapi.License(
            name="Proprietary License",
            url="https://www.reservex.com/license"
        ),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
    authentication_classes=[],
)

urlpatterns = [
    # Redirect root to /api/v1/
    path('', RedirectView.as_view(url='/api/v1/', permanent=False), name='root-redirect'),
    
    # Admin interface
    path('admin/', admin.site.urls),
    
    # Health check (keep this for monitoring)
    path('health/', health_check_view, name='health-check'),
    
    # API version 1 endpoints
    path('api/v1/', include('api.v1.urls'), name='api-v1'),
    
    # API Documentation
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), 
         name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), 
         name='schema-redoc'),
    
    # Redirect old API paths to versioned ones
    path('api/', RedirectView.as_view(url='/api/v1/', permanent=True)),
    
    # Debug toolbar URLs (only in development)
] + debug_toolbar_urls()

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Add debug toolbar URLs (only once)
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns

# Custom error handlers
handler400 = 'reservex.views.bad_request_view'
handler403 = 'reservex.views.permission_denied_view'
handler404 = 'reservex.views.not_found_view'
handler500 = 'reservex.views.server_error_view'

# Cache control for static files
from django.views.decorators.cache import cache_control
from django.contrib.staticfiles.views import serve as serve_static

if not settings.DEBUG:
    urlpatterns += [
        path('static/<path:path>', cache_control(public=True, max_age=3600)(serve_static)),
    ]

# API versioning note:
# When adding new API versions, follow this pattern:
# path('api/v2/', include('api.v2.urls'), name='api-v2'),