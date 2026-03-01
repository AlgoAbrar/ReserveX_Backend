"""
Restaurants App URL Configuration
URL patterns for restaurant-related endpoints
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router for ViewSets
router = DefaultRouter()
router.register(r'restaurants', views.RestaurantViewSet, basename='restaurant')
router.register(r'branches', views.BranchViewSet, basename='branch')
router.register(r'tables', views.TableViewSet, basename='table')
router.register(r'menu-items', views.MenuItemViewSet, basename='menuitem')

# Additional URL patterns
urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
    
    # Restaurant-specific additional endpoints
    path('restaurants/<uuid:pk>/branches/', 
         views.RestaurantViewSet.as_view({'get': 'branches'}), 
         name='restaurant-branches'),
    
    path('restaurants/<uuid:pk>/menu/', 
         views.RestaurantViewSet.as_view({'get': 'menu'}), 
         name='restaurant-menu'),
    
    path('restaurants/<uuid:pk>/availability/', 
         views.RestaurantViewSet.as_view({'get': 'availability'}), 
         name='restaurant-availability'),
    
    path('restaurants/<uuid:pk>/statistics/', 
         views.RestaurantViewSet.as_view({'get': 'statistics'}), 
         name='restaurant-statistics'),
    
    path('restaurants/<uuid:pk>/assign-manager/', 
         views.RestaurantViewSet.as_view({'post': 'assign_manager'}), 
         name='restaurant-assign-manager'),
    
    # Public endpoints
    path('featured/', 
         views.RestaurantViewSet.as_view({'get': 'featured'}), 
         name='restaurant-featured'),
    
    path('search/location/', 
         views.RestaurantViewSet.as_view({'get': 'search_by_location'}), 
         name='restaurant-search-location'),
    
    # Branch-specific endpoints
    path('branches/<uuid:pk>/tables/', 
         views.BranchViewSet.as_view({'get': 'tables'}), 
         name='branch-tables'),
    
    path('branches/<uuid:pk>/availability/', 
         views.BranchViewSet.as_view({'get': 'availability'}), 
         name='branch-availability'),
    
    path('branches/<uuid:pk>/statistics/', 
         views.BranchViewSet.as_view({'get': 'statistics'}), 
         name='branch-statistics'),
    
    # Table-specific endpoints
    path('tables/<uuid:pk>/reserve/', 
         views.TableViewSet.as_view({'post': 'reserve'}), 
         name='table-reserve'),
    
    # Menu item endpoints
    path('menu-items/popular/', 
         views.MenuItemViewSet.as_view({'get': 'popular'}), 
         name='menu-items-popular'),
    
    path('menu-items/categories/', 
         views.MenuItemViewSet.as_view({'get': 'categories'}), 
         name='menu-items-categories'),
]

# API versioning support
app_name = 'restaurants'