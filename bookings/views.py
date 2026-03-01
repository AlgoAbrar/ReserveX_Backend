from django.shortcuts import render

# Create your views here.
"""
Bookings App Views
Handles CRUD operations for Booking and related models
"""

from rest_framework import viewsets, status, filters, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.shortcuts import get_object_or_404
from datetime import timedelta, datetime, date
import logging

from .models import Booking, BookingMenu, BookingHistory, BookingNotification
from .serializers import (
    BookingListSerializer, BookingDetailSerializer, BookingCreateSerializer,
    BookingUpdateSerializer, BookingStatusUpdateSerializer, BookingMenuSerializer,
    BookingHistorySerializer, BookingAvailabilitySerializer, BookingNotificationSerializer,
    BookingStatisticsSerializer
)
from restaurants.models import Restaurant, Branch, Table, MenuItem
from users.permissions import (
    IsAdmin, IsManager, IsUser, IsOwnerOrAdmin,
    IsAdminOrManager, CanManageBookings, IsManagerOfRestaurant
)
from core.utils import send_payment_notification, get_client_ip

logger = logging.getLogger(__name__)


class BookingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Booking CRUD operations
    """
    queryset = Booking.objects.select_related(
        'user', 'restaurant', 'branch', 'table'
    ).prefetch_related('menu_items__menu_item').all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'status': ['exact', 'in'],
        'date': ['exact', 'gte', 'lte'],
        'restaurant': ['exact'],
        'branch': ['exact'],
        'user': ['exact'],
        'total_guests': ['exact', 'gte', 'lte'],
        'total_price': ['exact', 'gte', 'lte'],
    }
    search_fields = ['booking_id', 'user__email', 'user__name', 'restaurant__name']
    ordering_fields = ['created_at', 'date', 'start_time', 'total_price', 'total_guests']
    ordering = ['-date', '-start_time']
    
    def get_queryset(self):
        """Filter queryset based on user role"""
        queryset = super().get_queryset()
        user = self.request.user
        
        if not user or not user.is_authenticated:
            return queryset.none()
        
        # Admin sees all bookings
        if user.role == 'ADMIN':
            return queryset
        
        # Managers see bookings for their restaurants
        if user.role == 'MANAGER':
            return queryset.filter(
                Q(restaurant__manager=user) | Q(user=user)
            ).distinct()
        
        # Regular users see only their own bookings
        return queryset.filter(user=user)
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return BookingListSerializer
        elif self.action == 'create':
            return BookingCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return BookingUpdateSerializer
        elif self.action == 'update_status':
            return BookingStatusUpdateSerializer
        return BookingDetailSerializer
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        elif self.action == 'create':
            permission_classes = [IsAuthenticated]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, CanManageBookings]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        """Create booking and send notifications"""
        booking = serializer.save()
        
        # Send confirmation email/notification
        try:
            send_booking_notification(
                booking=booking,
                notification_type='CONFIRMATION',
                recipient=booking.user.email
            )
        except Exception as e:
            logger.error(f"Failed to send booking confirmation: {str(e)}")
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanManageBookings])
    def update_status(self, request, pk=None):
        """Update booking status (confirm, reject, cancel, complete)"""
        booking = self.get_object()
        serializer = self.get_serializer(booking, data=request.data)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            updated_booking = serializer.save()
            
            # Send notification based on new status
            try:
                notification_type = {
                    Booking.Status.CONFIRMED: 'CONFIRMATION',
                    Booking.Status.REJECTED: 'REJECTION',
                    Booking.Status.CANCELLED: 'CANCELLATION',
                    Booking.Status.COMPLETED: 'COMPLETION',
                    Booking.Status.EXPIRED: 'EXPIRY',
                }.get(updated_booking.status)
                
                if notification_type:
                    send_booking_notification(
                        booking=updated_booking,
                        notification_type=notification_type,
                        recipient=updated_booking.user.email
                    )
            except Exception as e:
                logger.error(f"Failed to send status update notification: {str(e)}")
        
        return Response(
            BookingDetailSerializer(updated_booking, context={'request': request}).data
        )
    
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def history(self, request, pk=None):
        """Get booking status history"""
        booking = self.get_object()
        history = booking.history.select_related('changed_by').all()
        serializer = BookingHistorySerializer(history, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def menu_items(self, request, pk=None):
        """Get menu items for this booking"""
        booking = self.get_object()
        menu_items = booking.menu_items.select_related('menu_item').all()
        serializer = BookingMenuSerializer(menu_items, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsUser])
    def add_menu_items(self, request, pk=None):
        """Add menu items to booking (only if pending payment)"""
        booking = self.get_object()
        
        if booking.status != Booking.Status.PENDING_PAYMENT:
            return Response(
                {'error': 'Can only add items to pending payment bookings.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if booking.user != request.user and request.user.role != 'ADMIN':
            return Response(
                {'error': 'You can only modify your own bookings.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = BookingMenuSerializer(
            data=request.data,
            context={'booking': booking}
        )
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            booking_menu = serializer.save(booking=booking)
        
        return Response(
            BookingMenuSerializer(booking_menu).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_bookings(self, request):
        """Get current user's bookings"""
        bookings = self.get_queryset().filter(user=request.user)
        
        # Filter by status
        status_filter = request.query_params.get('status')
        if status_filter:
            bookings = bookings.filter(status=status_filter)
        
        # Filter by date range
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        if from_date:
            bookings = bookings.filter(date__gte=from_date)
        if to_date:
            bookings = bookings.filter(date__lte=to_date)
        
        # Pagination
        page = self.paginate_queryset(bookings)
        if page is not None:
            serializer = BookingListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = BookingListSerializer(bookings, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def upcoming(self, request):
        """Get upcoming bookings for current user"""
        today = timezone.now().date()
        current_time = timezone.now().time()
        
        bookings = self.get_queryset().filter(
            Q(user=request.user) | Q(restaurant__manager=request.user)
        ).filter(
            date__gte=today,
            status__in=[Booking.Status.CONFIRMED, Booking.Status.PENDING_PAYMENT]
        ).exclude(
            date=today, start_time__lt=current_time
        ).order_by('date', 'start_time')[:10]
        
        serializer = BookingListSerializer(bookings, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsManager])
    def pending_requests(self, request):
        """Get pending booking requests for manager's restaurants"""
        bookings = self.get_queryset().filter(
            restaurant__manager=request.user,
            status=Booking.Status.PENDING_PAYMENT
        ).order_by('date', 'start_time')
        
        serializer = BookingListSerializer(bookings, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def check_availability(self, request):
        """Check table availability"""
        serializer = BookingAvailabilitySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        available_tables = []
        
        # Get tables based on criteria
        tables = Table.objects.filter(
            branch__restaurant__is_active=True,
            branch__status='OPEN',
            status='AVAILABLE',
            capacity__gte=data['guests']
        ).select_related('branch__restaurant')
        
        # Filter by restaurant
        if data.get('restaurant_id'):
            tables = tables.filter(branch__restaurant_id=data['restaurant_id'])
        
        # Filter by branch
        if data.get('branch_id'):
            tables = tables.filter(branch_id=data['branch_id'])
        
        # Filter by seat type
        if data.get('seat_type'):
            tables = tables.filter(seat_type=data['seat_type'])
        
        # Check each table for availability at the specified time
        for table in tables:
            if table.is_available_at(data['date'], data['time'], data['duration']):
                available_tables.append({
                    'table_id': table.id,
                    'table_number': table.table_number,
                    'branch_id': table.branch.id,
                    'branch_name': table.branch.name,
                    'restaurant_id': table.branch.restaurant.id,
                    'restaurant_name': table.branch.restaurant.name,
                    'seat_type': table.seat_type,
                    'capacity': table.capacity,
                    'minimum_spend': float(table.minimum_spend),
                    'features': {
                        'accessible': table.is_accessible,
                        'private': table.is_private,
                        'outlet': table.has_outlet,
                        'view': table.has_view
                    }
                })
        
        return Response({
            'date': data['date'],
            'time': data['time'].strftime('%H:%M'),
            'duration': data['duration'],
            'guests': data['guests'],
            'available_tables': available_tables,
            'total_available': len(available_tables)
        })
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsAdmin])
    def expire_pending(self, request):
        """Manually trigger expiry of pending bookings (admin only)"""
        count = Booking.expire_pending_bookings()
        return Response({
            'message': f'{count} pending bookings expired.',
            'expired_count': count
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsAdminOrManager])
    def statistics(self, request):
        """Get booking statistics"""
        user = request.user
        queryset = self.get_queryset()
        
        # Date range filter
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        from_date = request.query_params.get('from_date', start_date)
        to_date = request.query_params.get('to_date', end_date)
        
        bookings = queryset.filter(date__gte=from_date, date__lte=to_date)
        
        # Basic statistics
        stats = {
            'total_bookings': bookings.count(),
            'pending_payments': bookings.filter(status=Booking.Status.PENDING_PAYMENT).count(),
            'confirmed': bookings.filter(status=Booking.Status.CONFIRMED).count(),
            'completed': bookings.filter(status=Booking.Status.COMPLETED).count(),
            'cancelled': bookings.filter(status=Booking.Status.CANCELLED).count(),
            'rejected': bookings.filter(status=Booking.Status.REJECTED).count(),
            'expired': bookings.filter(status=Booking.Status.EXPIRED).count(),
            
            'total_revenue': bookings.filter(
                status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED]
            ).aggregate(total=Sum('total_price'))['total'] or 0,
            
            'average_booking_value': bookings.filter(
                status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED]
            ).aggregate(avg=Avg('total_price'))['avg'] or 0,
        }
        
        # Popular times
        popular_times = bookings.values('start_time').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # Popular tables
        popular_tables = bookings.values(
            'table__table_number', 'branch__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # Popular menu items
        popular_items = BookingMenu.objects.filter(
            booking__in=bookings
        ).values(
            'menu_item__name'
        ).annotate(
            total_ordered=Sum('quantity')
        ).order_by('-total_ordered')[:5]
        
        # Bookings by day
        bookings_by_day = bookings.values('date').annotate(
            count=Count('id'),
            revenue=Sum('total_price')
        ).order_by('date')
        
        stats.update({
            'popular_times': list(popular_times),
            'popular_tables': list(popular_tables),
            'popular_menu_items': list(popular_items),
            'bookings_by_day': list(bookings_by_day),
            'period': {
                'from': from_date,
                'to': to_date
            }
        })
        
        serializer = BookingStatisticsSerializer(data=stats)
        serializer.is_valid()
        return Response(serializer.data)


class BookingMenuViewSet(viewsets.ModelViewSet):
    """
    ViewSet for BookingMenu CRUD operations
    """
    queryset = BookingMenu.objects.select_related('booking', 'menu_item').all()
    serializer_class = BookingMenuSerializer
    permission_classes = [IsAuthenticated, CanManageBookings]
    
    def get_queryset(self):
        """Filter queryset by booking if provided"""
        queryset = super().get_queryset()
        booking_id = self.request.query_params.get('booking')
        if booking_id:
            queryset = queryset.filter(booking_id=booking_id)
        
        # Filter by user permissions
        user = self.request.user
        if user.role == 'USER':
            queryset = queryset.filter(booking__user=user)
        elif user.role == 'MANAGER':
            queryset = queryset.filter(booking__restaurant__manager=user)
        
        return queryset
    
    def perform_destroy(self, instance):
        """Delete menu item and update booking total"""
        with transaction.atomic():
            booking = instance.booking
            super().perform_destroy(instance)
            # Update booking total price
            booking.total_price = booking.menu_items.aggregate(
                total=Sum('subtotal')
            )['total'] or 0
            booking.save(update_fields=['total_price'])


class BookingHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing booking history (read-only)
    """
    queryset = BookingHistory.objects.select_related('booking', 'changed_by').all()
    serializer_class = BookingHistorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['booking', 'new_status', 'changed_by']
    ordering_fields = ['changed_at']
    ordering = ['-changed_at']
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.role == 'ADMIN':
            return queryset
        elif user.role == 'MANAGER':
            return queryset.filter(booking__restaurant__manager=user)
        else:
            return queryset.filter(booking__user=user)


class BookingNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing booking notifications (read-only)
    """
    queryset = BookingNotification.objects.select_related('booking').all()
    serializer_class = BookingNotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['booking', 'notification_type', 'is_successful']
    ordering_fields = ['sent_at']
    ordering = ['-sent_at']
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.role == 'ADMIN':
            return queryset
        elif user.role == 'MANAGER':
            return queryset.filter(booking__restaurant__manager=user)
        else:
            return queryset.filter(booking__user=user)