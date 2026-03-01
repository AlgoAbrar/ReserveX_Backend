"""
Payments App URL Configuration
URL patterns for payment-related endpoints
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router for ViewSets
router = DefaultRouter()
router.register(r'payments', views.PaymentViewSet, basename='payment')
router.register(r'methods', views.PaymentMethodViewSet, basename='payment-method')
router.register(r'refunds', views.RefundViewSet, basename='refund')
router.register(r'gateway', views.PaymentGatewayView, basename='payment-gateway')

# Additional URL patterns
urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
    
    # Payment initiation endpoints
    path('start/', 
         views.PaymentViewSet.as_view({'post': 'start'}), 
         name='payment-start'),
    
    # Payment callback endpoints (these are public endpoints called by payment gateway)
    path('success/<uuid:pk>/', 
         views.PaymentViewSet.as_view({'post': 'success'}), 
         name='payment-success'),
    
    path('fail/<uuid:pk>/', 
         views.PaymentViewSet.as_view({'post': 'fail'}), 
         name='payment-fail'),
    
    # User-specific payment endpoints
    path('my-payments/', 
         views.PaymentViewSet.as_view({'get': 'my_payments'}), 
         name='my-payments'),
    
    # Payment detail endpoints
    path('payments/<uuid:pk>/refund/', 
         views.PaymentViewSet.as_view({'post': 'refund'}), 
         name='payment-refund'),
    
    path('payments/<uuid:pk>/logs/', 
         views.PaymentViewSet.as_view({'get': 'logs'}), 
         name='payment-logs'),
    
    # Payment method endpoints
    path('methods/<uuid:pk>/set-default/', 
         views.PaymentMethodViewSet.as_view({'post': 'set_default'}), 
         name='payment-method-set-default'),
    
    # Statistics endpoint (admin only)
    path('statistics/', 
         views.PaymentViewSet.as_view({'get': 'statistics'}), 
         name='payment-statistics'),
    
    # Payment gateway simulation endpoints (for testing)
    path('gateway/webhook/', 
         views.PaymentGatewayView.as_view({'post': 'webhook'}), 
         name='payment-gateway-webhook'),
    
    path('gateway/simulate/', 
         views.PaymentGatewayView.as_view({'post': 'simulate'}), 
         name='payment-gateway-simulate'),
]

# API versioning support
app_name = 'payments'