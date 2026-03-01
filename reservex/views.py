"""
ReserveX Core Views
Production-ready views for API root, health checks, and error handling
"""

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.core.cache import cache
from django.conf import settings
from django.db import connection
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
import psutil
import platform
import time
from datetime import datetime


@api_view(['GET'])
@permission_classes([AllowAny])
def api_root_view(request):
    """
    API root endpoint that provides an overview of available endpoints
    and redirects to the appropriate API version.
    """
    base_url = request.build_absolute_uri('/api/v1/')
    
    api_info = {
        'name': 'ReserveX API',
        'version': 'v1',
        'description': 'Restaurant Reservation System',
        'documentation': {
            'swagger': request.build_absolute_uri('/swagger/'),
            'redoc': request.build_absolute_uri('/redoc/'),
        },
        'endpoints': {
            'health': request.build_absolute_uri('/health/'),
            'api_v1': base_url,
        },
        'authentication': {
            'type': 'JWT',
            'header_format': 'Authorization: JWT <your_token>',
            'endpoints': {
                'register': f'{base_url}auth/users/',
                'login': f'{base_url}auth/jwt/create/',
                'refresh': f'{base_url}auth/jwt/refresh/',
                'verify': f'{base_url}auth/jwt/verify/',
                'me': f'{base_url}auth/users/me/',
            }
        },
        'core_resources': {
            'restaurants': f'{base_url}restaurants/',
            'bookings': f'{base_url}bookings/',
            'payments': f'{base_url}payments/',
            'dashboard': {
                'user': f'{base_url}dashboard/user/overview/',
                'manager': f'{base_url}dashboard/manager/overview/',
                'admin': f'{base_url}dashboard/admin/overview/',
            }
        },
        'timestamp': timezone.now().isoformat(),
        'status': 'operational',
    }
    
    # If it's a browser request, show HTML welcome page
    if request.accepts('text/html'):
        context = {
            'api_info': api_info,
            'current_year': timezone.now().year,
            'debug': settings.DEBUG,
        }
        return render(request, 'api_root.html', context)
    
    # API clients get JSON response
    return Response(api_info, status=status.HTTP_200_OK)


@api_view(['GET', 'HEAD'])
@permission_classes([AllowAny])
def health_check_view(request):
    """
    Comprehensive health check endpoint for monitoring and load balancers.
    Returns system status, database connectivity, and cache status.
    """
    start_time = time.time()
    health_data = {
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'version': '1.0.0',
        'environment': {
            'debug': settings.DEBUG,
            'production': not settings.DEBUG,
            'database': 'postgresql',
            'cache': 'redis' if hasattr(settings, 'CACHES') else 'django_cache',
        },
    }
    
    # Check database connectivity
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        health_data['database'] = {
            'status': 'connected',
            'connection_time': connection.creation_time if hasattr(connection, 'creation_time') else None,
        }
    except Exception as e:
        health_data['database'] = {
            'status': 'error',
            'error': str(e),
        }
        health_data['status'] = 'degraded'
    
    # Check cache connectivity
    try:
        cache.set('health_check', 'ok', 5)
        cache.get('health_check')
        health_data['cache'] = {
            'status': 'operational',
        }
    except Exception as e:
        health_data['cache'] = {
            'status': 'error',
            'error': str(e),
        }
        health_data['status'] = 'degraded'
    
    # System information (sanitized for production)
    if settings.DEBUG:
        health_data['system'] = {
            'python_version': platform.python_version(),
            'platform': platform.platform(),
            'cpu_percent': psutil.cpu_percent(interval=0.1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage_percent': psutil.disk_usage('/').percent,
            'process_uptime': time.time() - psutil.Process().create_time(),
        }
    
    # Response time
    health_data['response_time_ms'] = round((time.time() - start_time) * 1000, 2)
    
    # For HEAD requests, return minimal response
    if request.method == 'HEAD':
        response = HttpResponse()
        response['X-Status'] = health_data['status']
        response['X-Version'] = health_data['version']
        return response
    
    return Response(health_data, status=status.HTTP_200_OK)


def bad_request_view(request, exception=None):
    """
    Custom 400 Bad Request error handler
    """
    response_data = {
        'error': 'Bad Request',
        'message': 'The server could not understand the request due to invalid syntax.',
        'status_code': 400,
        'timestamp': timezone.now().isoformat(),
    }
    
    if request.accepts('text/html'):
        return render(request, 'errors/400.html', response_data, status=400)
    
    return JsonResponse(response_data, status=400)


def permission_denied_view(request, exception=None):
    """
    Custom 403 Permission Denied error handler
    """
    response_data = {
        'error': 'Permission Denied',
        'message': 'You do not have permission to access this resource.',
        'status_code': 403,
        'timestamp': timezone.now().isoformat(),
    }
    
    if request.accepts('text/html'):
        return render(request, 'errors/403.html', response_data, status=403)
    
    return JsonResponse(response_data, status=403)


def not_found_view(request, exception=None):
    """
    Custom 404 Not Found error handler
    """
    response_data = {
        'error': 'Not Found',
        'message': 'The requested resource was not found on this server.',
        'path': request.path,
        'status_code': 404,
        'timestamp': timezone.now().isoformat(),
    }
    
    if request.accepts('text/html'):
        return render(request, 'errors/404.html', response_data, status=404)
    
    return JsonResponse(response_data, status=404)


def server_error_view(request):
    """
    Custom 500 Internal Server Error handler
    """
    response_data = {
        'error': 'Internal Server Error',
        'message': 'An unexpected error occurred. Our team has been notified.',
        'status_code': 500,
        'timestamp': timezone.now().isoformat(),
    }
    
    if request.accepts('text/html'):
        return render(request, 'errors/500.html', response_data, status=500)
    
    return JsonResponse(response_data, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_version_view(request):
    """
    Get information about available API versions
    """
    versions = {
        'versions': [
            {
                'version': 'v1',
                'status': 'active',
                'deprecated': False,
                'url': request.build_absolute_uri('/api/v1/'),
                'release_date': '2026-01-01',
                'documentation': request.build_absolute_uri('/swagger/'),
            }
        ],
        'current_version': 'v1',
        'latest_version': 'v1',
        'deprecation_policy': 'API versions are supported for 1 year after a new version is released.',
        'timestamp': timezone.now().isoformat(),
    }
    
    return Response(versions)


def robots_txt(request):
    """
    Serve robots.txt for search engine crawlers
    """
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /api/auth/",
        "Allow: /",
        f"Sitemap: {settings.FRONTEND_URL}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")