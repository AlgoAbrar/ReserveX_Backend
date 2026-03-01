# """
# Users App URL Configuration
# URL patterns for user-related endpoints
# """

# from django.urls import path, include
# from rest_framework.routers import DefaultRouter
# from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView

# # Since we're using djoser for most auth endpoints, we don't need additional views here
# # This file is just for completeness and any custom user endpoints

# urlpatterns = [
#     # JWT endpoints (these are also provided by djoser, but included for completeness)
#     path('jwt/create/', TokenObtainPairView.as_view(), name='jwt-create'),
#     path('jwt/refresh/', TokenRefreshView.as_view(), name='jwt-refresh'),
#     path('jwt/verify/', TokenVerifyView.as_view(), name='jwt-verify'),
    
#     # Djoser provides these endpoints:
#     # /users/ - user list and create
#     # /users/me/ - current user
#     # /users/confirm-email/ - email confirmation
#     # /users/resend-activation/ - resend activation email
#     # /users/set-password/ - set password
#     # /users/reset-password/ - reset password
#     # /users/reset-password-confirm/ - reset password confirm
#     # /users/set-username/ - set username
#     # /users/reset-username/ - reset username
#     # /users/reset-username-confirm/ - reset username confirm
# ]

# # API versioning support
# app_name = 'users'
"""
Users App URL Configuration
Complete URL patterns for user-related endpoints
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# If you create custom views for users
router = DefaultRouter()
# router.register(r'profiles', views.UserProfileViewSet, basename='user-profile')
# router.register(r'activities', views.UserActivityViewSet, basename='user-activity')

urlpatterns = [
    # Include djoser URLs for authentication
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.jwt')),
    
    # Include router URLs if you have custom views
    # path('', include(router.urls)),
    
    # Custom endpoints
    # path('profile/', views.UserProfileView.as_view(), name='user-profile'),
    # path('activities/', views.UserActivityView.as_view(), name='user-activities'),
]

app_name = 'users'