"""
Users App URL Configuration
Handles authentication and user-related endpoints using Djoser + JWT
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserProfileViewSet, UserActivityViewSet

# -------------------------------
# 🔹 Router Configuration
# -------------------------------
router = DefaultRouter()
router.register(r'profiles', UserProfileViewSet, basename='user-profile')
router.register(r'activities', UserActivityViewSet, basename='user-activity')

# -------------------------------
# 🔹 URL Patterns
# -------------------------------
urlpatterns = [

    # ===============================
    # 🔐 AUTHENTICATION (DJOSER + JWT)
    # ===============================
    path('auth/', include('djoser.urls')),          # User management
    path('auth/', include('djoser.urls.jwt')),      # JWT login/refresh/verify

    # ===============================
    # 👤 CUSTOM USER MODULES
    # ===============================
    path('', include(router.urls)),

    # ===============================
    # ⚙️ OPTIONAL CUSTOM ENDPOINTS
    # ===============================
    # path('profile/', UserProfileView.as_view(), name='user-profile'),
    # path('activities/', UserActivityView.as_view(), name='user-activities'),
]

# -------------------------------
# 🔹 App Namespace
# -------------------------------
app_name = 'users'