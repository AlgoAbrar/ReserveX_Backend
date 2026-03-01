from django.shortcuts import render

# Create your views here.
"""
Payments App Views
Handles payment processing endpoints for ReserveX
"""

from rest_framework import viewsets, status, filters, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.conf import settings
from decimal import Decimal
import logging
import uuid
import json
import hashlib
import hmac
from datetime import timedelta, datetime

from .models import Payment, PaymentLog, PaymentMethod, Refund
from .serializers import (
    PaymentSerializer, PaymentDetailSerializer, PaymentCreateSerializer,
    PaymentMethodSerializer, PaymentMethodCreateSerializer,
    RefundSerializer, RefundCreateSerializer,
    PaymentStatisticsSerializer, PaymentGatewaySerializer
)
from bookings.models import Booking
from users.permissions import IsAdmin, IsManager, IsOwnerOrAdmin, CanManagePayments
from core.utils import send_payment_notification, get_client_ip

logger = logging.getLogger(__name__)


class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Payment CRUD operations
    """
    queryset = Payment.objects.select_related(
        'booking', 'user'
    ).prefetch_related('logs', 'refunds').all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'payment_status': ['exact', 'in'],
        'payment_method': ['exact'],
        'user': ['exact'],
        'booking': ['exact'],
        'created_at': ['exact', 'gte', 'lte'],
        'amount': ['exact', 'gte', 'lte'],
    }
    search_fields = ['transaction_id', 'user__email', 'booking__booking_id']
    ordering_fields = ['created_at', 'amount', 'completed_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset based on user role"""
        queryset = super().get_queryset()
        user = self.request.user
        
        if not user or not user.is_authenticated:
            return queryset.none()
        
        # Admin sees all payments
        if user.role == 'ADMIN':
            return queryset
        
        # Managers see payments for their restaurants
        if user.role == 'MANAGER':
            return queryset.filter(booking__restaurant__manager=user)
        
        # Regular users see only their own payments
        return queryset.filter(user=user)
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return PaymentSerializer
        elif self.action == 'create':
            return PaymentCreateSerializer
        elif self.action in ['retrieve']:
            return PaymentDetailSerializer
        return PaymentSerializer
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        elif self.action == 'create':
            permission_classes = [IsAuthenticated]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsAdmin]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def start(self, request):
        """
        Start payment process for a booking
        Endpoint: /api/v1/payments/start/<booking_id>/
        """
        booking_id = request.data.get('booking_id')
        payment_method_id = request.data.get('payment_method_id')
        
        if not booking_id:
            return Response(
                {'error': 'booking_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get booking
        try:
            booking = Booking.objects.select_related('user', 'restaurant').get(
                id=booking_id,
                user=request.user,
                status=Booking.Status.PENDING_PAYMENT
            )
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Booking not found or not in pending payment state'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if booking is expired
        if booking.expires_at and booking.expires_at < timezone.now():
            booking.expire_booking()
            return Response(
                {'error': 'Booking has expired. Please create a new booking.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get payment method if provided
        payment_method = None
        if payment_method_id:
            try:
                payment_method = PaymentMethod.objects.get(
                    id=payment_method_id,
                    user=request.user,
                    is_active=True
                )
            except PaymentMethod.DoesNotExist:
                return Response(
                    {'error': 'Payment method not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Create payment record
        with transaction.atomic():
            payment = Payment.objects.create(
                booking=booking,
                user=request.user,
                amount=booking.total_price,
                payment_method=payment_method.method_type if payment_method else 'CREDIT_CARD',
                payment_status='PENDING'
            )
            
            # Log payment start
            PaymentLog.objects.create(
                payment=payment,
                log_level='INFO',
                message='Payment initiated',
                data={
                    'booking_id': str(booking.id),
                    'amount': float(booking.total_price),
                    'payment_method': payment_method.method_type if payment_method else 'CREDIT_CARD'
                },
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
        
        # Simulate payment gateway processing (in production, integrate with Stripe/PayPal)
        # For demo, we'll simulate a successful payment after 2 seconds
        # In production, this would be handled by webhooks
        
        # For demo purposes, we'll return a success response
        # In production, you would redirect to payment gateway
        return Response({
            'payment_id': payment.id,
            'transaction_id': payment.transaction_id,
            'amount': float(payment.amount),
            'status': 'pending',
            'redirect_url': f'/api/v1/payments/process/{payment.id}/',
            'checkout_url': f'https://checkout.example.com/{payment.transaction_id}'
        })
    
    @action(detail=True, methods=['post'], permission_classes=[AllowAny])
    def success(self, request, pk=None):
        """
        Handle successful payment callback
        Endpoint: /api/v1/payments/success/<payment_id>/
        """
        payment = self.get_object()
        
        # Verify payment is in pending state
        if payment.payment_status != 'PENDING':
            return Response(
                {'error': f'Payment already in {payment.payment_status} state'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Process successful payment
        with transaction.atomic():
            # Update payment
            payment.payment_status = 'SUCCESS'
            payment.completed_at = timezone.now()
            payment.gateway_response = {
                'status': 'success',
                'timestamp': timezone.now().isoformat(),
                'transaction_id': payment.transaction_id
            }
            payment.save()
            
            # Confirm the booking
            payment.booking.confirm_booking()
            
            # Log success
            PaymentLog.objects.create(
                payment=payment,
                log_level='INFO',
                message='Payment completed successfully',
                data={'gateway_response': 'success'},
                ip_address=get_client_ip(request)
            )
        
        # Send notification
        try:
            send_payment_notification(payment, 'SUCCESS')
        except Exception as e:
            logger.error(f"Failed to send payment notification: {str(e)}")
        
        return Response({
            'status': 'success',
            'message': 'Payment processed successfully',
            'booking_id': payment.booking.booking_id,
            'transaction_id': payment.transaction_id,
            'redirect_url': f'/api/v1/bookings/{payment.booking.id}/'
        })
    
    @action(detail=True, methods=['post'], permission_classes=[AllowAny])
    def fail(self, request, pk=None):
        """
        Handle failed payment callback
        Endpoint: /api/v1/payments/fail/<payment_id>/
        """
        payment = self.get_object()
        
        # Verify payment is in pending state
        if payment.payment_status != 'PENDING':
            return Response(
                {'error': f'Payment already in {payment.payment_status} state'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        error_message = request.data.get('error', 'Payment failed')
        
        # Process failed payment
        with transaction.atomic():
            # Update payment
            payment.payment_status = 'FAILED'
            payment.gateway_response = {
                'status': 'failed',
                'timestamp': timezone.now().isoformat(),
                'error': error_message
            }
            payment.save()
            
            # Log failure
            PaymentLog.objects.create(
                payment=payment,
                log_level='ERROR',
                message=f'Payment failed: {error_message}',
                data={'error': error_message},
                ip_address=get_client_ip(request)
            )
        
        # Send notification
        try:
            send_payment_notification(payment, 'FAILED', error_message)
        except Exception as e:
            logger.error(f"Failed to send payment notification: {str(e)}")
        
        return Response({
            'status': 'failed',
            'message': 'Payment processing failed',
            'error': error_message
        }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdmin])
    def refund(self, request, pk=None):
        """
        Process refund for a payment (admin only)
        """
        payment = self.get_object()
        
        # Verify payment is successful
        if payment.payment_status != 'SUCCESS':
            return Response(
                {'error': 'Only successful payments can be refunded'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        amount = request.data.get('amount')
        reason = request.data.get('reason', '')
        
        if amount:
            try:
                amount = Decimal(amount)
            except:
                return Response(
                    {'error': 'Invalid amount'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if amount > payment.remaining_amount:
                return Response(
                    {'error': f'Refund amount exceeds remaining amount ({payment.remaining_amount})'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Process refund
        refund = Refund.objects.create(
            payment=payment,
            amount=amount if amount else payment.remaining_amount,
            currency=payment.currency,
            reason=reason,
            initiated_by=request.user,
            status='PROCESSING'
        )
        
        # Simulate refund processing
        with transaction.atomic():
            refund.status = 'COMPLETED'
            refund.completed_at = timezone.now()
            refund.gateway_response = {'status': 'completed', 'refund_id': str(uuid.uuid4())}
            refund.save()
            
            # Update payment
            payment.process_refund(amount, reason)
        
        return Response({
            'status': 'success',
            'message': 'Refund processed successfully',
            'refund_id': refund.refund_id,
            'amount': float(refund.amount),
            'remaining_amount': float(payment.remaining_amount)
        })
    
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def logs(self, request, pk=None):
        """Get payment logs"""
        payment = self.get_object()
        logs = payment.logs.all()
        
        data = [{
            'id': log.id,
            'log_level': log.log_level,
            'message': log.message,
            'data': log.data,
            'created_at': log.created_at
        } for log in logs]
        
        return Response(data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_payments(self, request):
        """Get current user's payments"""
        payments = self.get_queryset().filter(user=request.user)
        
        # Filter by status
        status_filter = request.query_params.get('status')
        if status_filter:
            payments = payments.filter(payment_status=status_filter)
        
        # Filter by date range
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        if from_date:
            payments = payments.filter(created_at__gte=from_date)
        if to_date:
            payments = payments.filter(created_at__lte=to_date)
        
        # Pagination
        page = self.paginate_queryset(payments)
        if page is not None:
            serializer = PaymentSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsAdmin])
    def statistics(self, request):
        """Get payment statistics (admin only)"""
        # Date range filter
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)
        
        from_date = request.query_params.get('from_date', start_date)
        to_date = request.query_params.get('to_date', end_date)
        
        payments = Payment.objects.filter(created_at__gte=from_date, created_at__lte=to_date)
        
        # Statistics
        stats = {
            'total_payments': payments.count(),
            'total_successful': payments.filter(payment_status='SUCCESS').count(),
            'total_failed': payments.filter(payment_status='FAILED').count(),
            'total_pending': payments.filter(payment_status='PENDING').count(),
            'total_refunded': payments.filter(payment_status='REFUNDED').count(),
            
            'total_revenue': payments.filter(
                payment_status='SUCCESS'
            ).aggregate(total=Sum('amount'))['total'] or 0,
            
            'total_refunded_amount': payments.filter(
                payment_status__in=['REFUNDED', 'PARTIALLY_REFUNDED']
            ).aggregate(total=Sum('refund_amount'))['total'] or 0,
            
            'average_payment': payments.filter(
                payment_status='SUCCESS'
            ).aggregate(avg=Avg('amount'))['avg'] or 0,
        }
        
        # Payments by method
        by_method = payments.values('payment_method').annotate(
            count=Count('id'),
            total=Sum('amount')
        )
        
        # Payments by day
        by_day = payments.filter(
            payment_status='SUCCESS'
        ).extra(
            {'day': "date(created_at)"}
        ).values('day').annotate(
            count=Count('id'),
            total=Sum('amount')
        ).order_by('day')
        
        stats.update({
            'by_payment_method': list(by_method),
            'by_day': list(by_day),
            'period': {
                'from': from_date,
                'to': to_date
            }
        })
        
        return Response(stats)


class PaymentMethodViewSet(viewsets.ModelViewSet):
    """
    ViewSet for PaymentMethod CRUD operations
    """
    queryset = PaymentMethod.objects.select_related('user').all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['method_type', 'is_default', 'is_active']
    search_fields = ['card_brand', 'last_four']
    
    def get_queryset(self):
        """Filter queryset to user's own payment methods"""
        user = self.request.user
        if user.role == 'ADMIN':
            return super().get_queryset()
        return super().get_queryset().filter(user=user)
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return PaymentMethodCreateSerializer
        return PaymentMethodSerializer
    
    def get_permissions(self):
        """Set permissions based on action"""
        permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        """Create payment method for current user"""
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def set_default(self, request, pk=None):
        """Set payment method as default"""
        payment_method = self.get_object()
        payment_method.is_default = True
        payment_method.save()
        return Response({'status': 'default payment method updated'})


class RefundViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing refunds (read-only for most users)
    """
    queryset = Refund.objects.select_related('payment', 'initiated_by').all()
    serializer_class = RefundSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['payment', 'status', 'currency']
    ordering_fields = ['created_at', 'amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset based on user role"""
        queryset = super().get_queryset()
        user = self.request.user
        
        if not user or not user.is_authenticated:
            return queryset.none()
        
        # Admin sees all refunds
        if user.role == 'ADMIN':
            return queryset
        
        # Managers see refunds for their restaurants
        if user.role == 'MANAGER':
            return queryset.filter(payment__booking__restaurant__manager=user)
        
        # Regular users see only their own refunds
        return queryset.filter(payment__user=user)
    
    def get_permissions(self):
        """Set permissions"""
        permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    
class PaymentGatewayView(viewsets.GenericViewSet):
    """
    Payment gateway simulation endpoints
    In production, these would be replaced with actual gateway integration
    """
    permission_classes = [AllowAny]
    serializer_class = PaymentGatewaySerializer
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def webhook(self, request):
        """
        Simulate payment gateway webhook
        """
        # In production, verify webhook signature
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
        
        # Process webhook based on event type
        event_type = request.data.get('type')
        data = request.data.get('data', {})
        
        if event_type == 'payment_intent.succeeded':
            # Handle successful payment
            payment_intent_id = data.get('object', {}).get('id')
            # Find payment and update status
            try:
                payment = Payment.objects.get(transaction_id=payment_intent_id)
                payment.process_success(request.data)
            except Payment.DoesNotExist:
                logger.error(f"Payment not found for transaction: {payment_intent_id}")
        
        elif event_type == 'payment_intent.payment_failed':
            # Handle failed payment
            payment_intent_id = data.get('object', {}).get('id')
            error_message = data.get('object', {}).get('last_payment_error', {}).get('message', '')
            try:
                payment = Payment.objects.get(transaction_id=payment_intent_id)
                payment.process_failure(request.data, error_message)
            except Payment.DoesNotExist:
                logger.error(f"Payment not found for transaction: {payment_intent_id}")
        
        return Response({'status': 'success'})
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def simulate(self, request):
        """
        Simulate payment for testing
        """
        payment_id = request.data.get('payment_id')
        action = request.data.get('action', 'success')  # success or fail
        
        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return Response(
                {'error': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if action == 'success':
            return self.success(request, pk=payment_id)
        else:
            return self.fail(request, pk=payment_id)