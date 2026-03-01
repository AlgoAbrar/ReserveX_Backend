# # """
# # ASGI config for reservex project.

# # It exposes the ASGI callable as a module-level variable named ``application``.

# # For more information on this file, see
# # https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
# # """

# # import os

# # from django.core.asgi import get_asgi_application

# # os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reservex.settings')

# # application = get_asgi_application()
# """
# ReserveX ASGI Configuration
# ASGI entry point for asynchronous support and WebSocket capabilities
# """

# import os
# import sys
# from pathlib import Path
# from django.core.asgi import get_asgi_application

# # Add the project directory to the sys.path
# project_dir = Path(__file__).resolve().parent.parent
# if str(project_dir) not in sys.path:
#     sys.path.append(str(project_dir))

# # Set the Django settings module
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reservex.settings')

# # Initialize Django ASGI application
# django_asgi_app = get_asgi_application()

# # ASGI application for HTTP requests
# application = django_asgi_app

# # WebSocket support placeholder for future real-time features
# # Uncomment and implement when WebSocket support is needed
# """
# from channels.routing import ProtocolTypeRouter, URLRouter
# from channels.auth import AuthMiddlewareStack
# from channels.security.websocket import AllowedHostsOriginValidator
# from django.urls import re_path
# from core.consumers import BookingConsumer

# websocket_urlpatterns = [
#     re_path(r'ws/bookings/(?P<booking_id>\w+)/$', BookingConsumer.as_asgi()),
# ]

# application = ProtocolTypeRouter({
#     'http': django_asgi_app,
#     'websocket': AllowedHostsOriginValidator(
#         AuthMiddlewareStack(
#             URLRouter(websocket_urlpatterns)
#         )
#     ),
# })
# """

# # Health check endpoint for ASGI servers
# async def health_check(scope, receive, send):
#     """Simple health check for load balancers"""
#     if scope['type'] == 'http' and scope['path'] == '/health':
#         await send({
#             'type': 'http.response.start',
#             'status': 200,
#             'headers': [(b'content-type', b'text/plain')],
#         })
#         await send({
#             'type': 'http.response.body',
#             'body': b'OK',
#         })
#         return

# # Uncomment to enable health check
# # application = health_check

# # Log startup in production
# if not os.environ.get('DEBUG'):
#     import logging
#     logging.basicConfig(level=logging.INFO)
#     logger = logging.getLogger(__name__)
#     logger.info("ReserveX ASGI application initialized successfully")

"""
ReserveX ASGI Configuration
ASGI entry point for asynchronous support and WebSocket capabilities
"""

import os
import sys
from pathlib import Path
from django.core.asgi import get_asgi_application

# Add the project directory to the sys.path
project_dir = Path(__file__).resolve().parent.parent
if str(project_dir) not in sys.path:
    sys.path.append(str(project_dir))

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reservex.settings')

# Initialize Django ASGI application
django_asgi_app = get_asgi_application()

# ASGI application for HTTP requests
application = django_asgi_app

# Log startup in production
if not os.environ.get('DEBUG'):
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info("ReserveX ASGI application initialized successfully")