# # """
# # WSGI config for reservex project.

# # It exposes the WSGI callable as a module-level variable named ``application``.

# # For more information on this file, see
# # https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
# # """

# # import os

# # from django.core.wsgi import get_wsgi_application

# # os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reservex.settings')

# # application = get_wsgi_application()
# """
# ReserveX WSGI Configuration
# Production-ready WSGI entry point with Vercel deployment support
# """

# import os
# import sys
# from pathlib import Path

# # Add the project directory to the sys.path
# project_dir = Path(__file__).resolve().parent.parent
# if str(project_dir) not in sys.path:
#     sys.path.append(str(project_dir))

# # Set the Django settings module
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reservex.settings')

# # Initialize WSGI application
# from django.core.wsgi import get_wsgi_application

# # This is the application object that Vercel will use
# app = get_wsgi_application()

# # For backward compatibility with some WSGI servers
# application = app

# # Optional: Add health check endpoint for WSGI servers
# def health_check(environ, start_response):
#     """Simple health check for load balancers"""
#     if environ.get('PATH_INFO') == '/health':
#         status = '200 OK'
#         headers = [('Content-Type', 'text/plain')]
#         start_response(status, headers)
#         return [b'OK']
#     return app(environ, start_response)

# # Uncomment the line below if you want to use the health check
# # application = health_check

# # Performance optimization: Pre-load models and apps
# from django.apps import apps
# apps.populate(settings.INSTALLED_APPS)

# # Log startup in production
# if not os.environ.get('DEBUG'):
#     import logging
#     logging.basicConfig(level=logging.INFO)
#     logger = logging.getLogger(__name__)
#     logger.info("ReserveX WSGI application initialized successfully")

"""
ReserveX WSGI Configuration
Production-ready WSGI entry point with Vercel deployment support
"""

import os
import sys
from pathlib import Path

# Add the project directory to the sys.path
project_dir = Path(__file__).resolve().parent.parent
if str(project_dir) not in sys.path:
    sys.path.append(str(project_dir))

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reservex.settings')

# Initialize WSGI application
from django.core.wsgi import get_wsgi_application

# This is the application object that Vercel will use
app = get_wsgi_application()

# For backward compatibility with some WSGI servers
application = app

# Optional: Add health check endpoint for WSGI servers
def health_check(environ, start_response):
    """Simple health check for load balancers"""
    if environ.get('PATH_INFO') == '/health':
        status = '200 OK'
        headers = [('Content-Type', 'text/plain')]
        start_response(status, headers)
        return [b'OK']
    return app(environ, start_response)

# Uncomment the line below if you want to use the health check
# application = health_check

# Performance optimization: Pre-load models and apps
# Comment out or fix this section - it's causing the error
# from django.conf import settings
# from django.apps import apps
# apps.populate(settings.INSTALLED_APPS)

# Log startup in production
if not os.environ.get('DEBUG'):
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info("ReserveX WSGI application initialized successfully")