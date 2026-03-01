from django.shortcuts import render

# # Create your views here.
"""
Restaurants App Views
Handles CRUD operations for Restaurant, Branch, Table, and MenuItem models
"""
import math  
from rest_framework import viewsets, status, filters, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from django.shortcuts import get_object_or_404
from datetime import timedelta, datetime
import logging

from .models import Restaurant, Branch, Table, MenuItem
from .serializers import (
    RestaurantListSerializer, RestaurantDetailSerializer,
    RestaurantCreateSerializer, RestaurantUpdateSerializer,
    BranchSerializer, TableSerializer, TableAvailabilitySerializer,
    MenuItemSerializer, RestaurantStatisticsSerializer,
    BranchStatisticsSerializer
)
from users.permissions import (
    IsAdmin, IsManager, IsAdminOrManager,
    IsAdminOrManagerOrReadOnly, IsManagerOfRestaurant,
    IsAdminOrManagerOfRestaurant
)
from core.utils import get_client_ip

logger = logging.getLogger(__name__)


class RestaurantViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Restaurant CRUD operations
    """
    queryset = Restaurant.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['cuisine_type', 'price_level', 'city', 'is_active', 'is_verified', 'is_featured']
    search_fields = ['name', 'description', 'city', 'address']
    ordering_fields = ['name', 'created_at', 'average_rating', 'total_bookings']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Optimize queryset with select_related and prefetch_related"""
        queryset = Restaurant.objects.select_related('manager').prefetch_related(
            'branches', 'menu_items'
        )
        
        # Filter by city if provided
        city = self.request.query_params.get('city')
        if city:
            queryset = queryset.filter(city__icontains=city)
        
        # Filter by cuisine type
        cuisine = self.request.query_params.get('cuisine')
        if cuisine:
            queryset = queryset.filter(cuisine_type=cuisine)
        
        # Filter by price level
        price = self.request.query_params.get('price')
        if price:
            queryset = queryset.filter(price_level=price)
        
        # Filter by rating
        min_rating = self.request.query_params.get('min_rating')
        if min_rating:
            queryset = queryset.filter(average_rating__gte=min_rating)
        
        # Filter by featured
        featured = self.request.query_params.get('featured')
        if featured and featured.lower() == 'true':
            queryset = queryset.filter(is_featured=True)
        
        # Filter by verified
        verified = self.request.query_params.get('verified')
        if verified and verified.lower() == 'true':
            queryset = queryset.filter(is_verified=True)
        
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return RestaurantListSerializer
        elif self.action == 'create':
            return RestaurantCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return RestaurantUpdateSerializer
        return RestaurantDetailSerializer
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        elif self.action == 'create':
            permission_classes = [IsAuthenticated, IsAdminOrManager]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsAdminOrManagerOfRestaurant]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def branches(self, request, pk=None):
        """Get all branches of a restaurant"""
        restaurant = self.get_object()
        branches = restaurant.branches.select_related('restaurant').prefetch_related('tables').all()
        
        # Filter by city
        city = request.query_params.get('city')
        if city:
            branches = branches.filter(city__icontains=city)
        
        # Filter by status
        status_param = request.query_params.get('status')
        if status_param:
            branches = branches.filter(status=status_param)
        
        serializer = BranchSerializer(branches, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def menu(self, request, pk=None):
        """Get menu items of a restaurant"""
        restaurant = self.get_object()
        menu_items = restaurant.menu_items.filter(is_available=True).select_related('restaurant')
        
        # Filter by category
        category = request.query_params.get('category')
        if category:
            menu_items = menu_items.filter(category=category)
        
        # Filter by dietary type
        dietary = request.query_params.get('dietary')
        if dietary:
            menu_items = menu_items.filter(dietary_types__contains=[dietary])
        
        # Filter by price range
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        if min_price:
            menu_items = menu_items.filter(price__gte=min_price)
        if max_price:
            menu_items = menu_items.filter(price__lte=max_price)
        
        # Filter by popular
        popular = request.query_params.get('popular')
        if popular and popular.lower() == 'true':
            menu_items = menu_items.filter(is_popular=True)
        
        serializer = MenuItemSerializer(menu_items, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def availability(self, request, pk=None):
        """Check table availability across all branches"""
        restaurant = self.get_object()
        
        # Validate request parameters
        serializer = TableAvailabilitySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        date = serializer.validated_data['date']
        time = serializer.validated_data['time']
        duration = serializer.validated_data['duration']
        
        # Get available tables per branch
        branches = restaurant.branches.prefetch_related('tables').all()
        availability = []
        
        for branch in branches:
            # Check if branch is open at this time
            if not branch.is_open_at(date, time):
                continue
            
            available_tables = branch.get_available_tables(date, time, duration)
            
            availability.append({
                'branch_id': branch.id,
                'branch_name': branch.name,
                'branch_address': branch.address,
                'available_tables': TableSerializer(available_tables, many=True).data,
                'total_available': available_tables.count()
            })
        
        return Response({
            'restaurant': restaurant.name,
            'date': date,
            'time': time,
            'duration': duration,
            'branches': availability
        })
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminOrManager])
    def assign_manager(self, request, pk=None):
        """Assign a manager to the restaurant"""
        restaurant = self.get_object()
        manager_id = request.data.get('manager_id')
        
        if not manager_id:
            return Response(
                {'error': 'manager_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from users.models import User
        try:
            manager = User.objects.get(id=manager_id, role='MANAGER')
        except User.DoesNotExist:
            return Response(
                {'error': 'Manager not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        restaurant.manager = manager
        restaurant.save()
        
        logger.info(f"Manager {manager.email} assigned to restaurant {restaurant.name}")
        
        return Response(
            RestaurantDetailSerializer(restaurant, context={'request': request}).data
        )
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def featured(self, request):
        """Get featured restaurants"""
        featured = self.get_queryset().filter(is_featured=True, is_active=True)[:10]
        serializer = RestaurantListSerializer(featured, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def search_by_location(self, request):
        """Search restaurants by location (city or coordinates)"""
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        radius = request.query_params.get('radius', 10)  # Radius in km
        city = request.query_params.get('city')
        
        queryset = self.get_queryset().filter(is_active=True)
        
        if city:
            queryset = queryset.filter(city__icontains=city)
        elif lat and lng:
            # Simple bounding box search (for production, use PostGIS)
            lat = float(lat)
            lng = float(lng)
            radius = float(radius)
            
            # Approximate degree to km conversion
            lat_range = radius / 111.0
            lng_range = radius / (111.0 * abs(math.cos(math.radians(lat))) if abs(math.cos(math.radians(lat))) > 0 else 1)
            
            queryset = queryset.filter(
                latitude__gte=lat - lat_range,
                latitude__lte=lat + lat_range,
                longitude__gte=lng - lng_range,
                longitude__lte=lng + lng_range
            )
        
        serializer = RestaurantListSerializer(queryset[:20], many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated, IsAdminOrManager])
    def statistics(self, request, pk=None):
        """Get detailed statistics for the restaurant"""
        restaurant = self.get_object()
        
        from bookings.models import Booking
        from django.db.models.functions import TruncDate, TruncMonth
        
        # Date ranges
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Basic stats
        total_branches = restaurant.branches.count()
        total_tables = Table.objects.filter(branch__restaurant=restaurant).count()
        total_capacity = Table.objects.filter(branch__restaurant=restaurant).aggregate(
            total=Sum('capacity')
        )['total'] or 0
        total_menu_items = restaurant.menu_items.count()
        
        # Booking stats
        bookings_today = Booking.objects.filter(
            restaurant=restaurant,
            date=today,
            status='CONFIRMED'
        ).count()
        
        bookings_week = Booking.objects.filter(
            restaurant=restaurant,
            date__gte=week_ago,
            status='CONFIRMED'
        ).count()
        
        bookings_month = Booking.objects.filter(
            restaurant=restaurant,
            date__gte=month_ago,
            status='CONFIRMED'
        ).count()
        
        # Revenue stats (assuming payment amount from bookings)
        revenue_today = Booking.objects.filter(
            restaurant=restaurant,
            date=today,
            status='CONFIRMED'
        ).aggregate(total=Sum('total_price'))['total'] or 0
        
        revenue_week = Booking.objects.filter(
            restaurant=restaurant,
            date__gte=week_ago,
            status='CONFIRMED'
        ).aggregate(total=Sum('total_price'))['total'] or 0
        
        revenue_month = Booking.objects.filter(
            restaurant=restaurant,
            date__gte=month_ago,
            status='CONFIRMED'
        ).aggregate(total=Sum('total_price'))['total'] or 0
        
        # Popular times
        popular_times = Booking.objects.filter(
            restaurant=restaurant,
            status='CONFIRMED'
        ).values('start_time').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        stats = {
            'restaurant_name': restaurant.name,
            'total_branches': total_branches,
            'total_tables': total_tables,
            'total_capacity': total_capacity,
            'total_menu_items': total_menu_items,
            'average_rating': float(restaurant.average_rating),
            'total_reviews': restaurant.total_reviews,
            'total_bookings': restaurant.total_bookings,
            'bookings_today': bookings_today,
            'bookings_week': bookings_week,
            'bookings_month': bookings_month,
            'revenue_today': float(revenue_today),
            'revenue_week': float(revenue_week),
            'revenue_month': float(revenue_month),
            'popular_times': list(popular_times),
        }
        
        return Response(stats)


class BranchViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Branch CRUD operations
    """
    queryset = Branch.objects.select_related('restaurant').prefetch_related('tables').all()
    serializer_class = BranchSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['restaurant', 'city', 'status']
    search_fields = ['name', 'address', 'city']
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated, IsAdminOrManagerOfRestaurant]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """Filter queryset by restaurant if provided"""
        queryset = super().get_queryset()
        restaurant_id = self.request.query_params.get('restaurant')
        if restaurant_id:
            queryset = queryset.filter(restaurant_id=restaurant_id)
        return queryset
    
    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def tables(self, request, pk=None):
        """Get all tables in a branch"""
        branch = self.get_object()
        tables = branch.tables.all()
        
        # Filter by seat type
        seat_type = request.query_params.get('seat_type')
        if seat_type:
            tables = tables.filter(seat_type=seat_type)
        
        # Filter by capacity
        min_capacity = request.query_params.get('min_capacity')
        if min_capacity:
            tables = tables.filter(capacity__gte=min_capacity)
        
        # Filter by availability
        available_only = request.query_params.get('available_only')
        if available_only and available_only.lower() == 'true':
            tables = tables.filter(status='AVAILABLE')
        
        serializer = TableSerializer(tables, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def availability(self, request, pk=None):
        """Check table availability in this branch"""
        branch = self.get_object()
        
        serializer = TableAvailabilitySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        date = serializer.validated_data['date']
        time = serializer.validated_data['time']
        duration = serializer.validated_data['duration']
        
        # Check if branch is open
        if not branch.is_open_at(date, time):
            return Response(
                {'error': 'Branch is closed at this time'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        available_tables = branch.get_available_tables(date, time, duration)
        
        return Response({
            'branch_id': branch.id,
            'branch_name': branch.name,
            'date': date,
            'time': time,
            'duration': duration,
            'available_tables': TableSerializer(available_tables, many=True).data,
            'total_available': available_tables.count()
        })
    
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated, IsAdminOrManager])
    def statistics(self, request, pk=None):
        """Get statistics for this branch"""
        branch = self.get_object()
        
        from bookings.models import Booking
        
        today = timezone.now().date()
        
        # Table statistics
        total_tables = branch.tables.count()
        occupied_tables = branch.tables.filter(status='OCCUPIED').count()
        available_tables = branch.tables.filter(status='AVAILABLE').count()
        
        total_seats = branch.tables.aggregate(total=Sum('capacity'))['total'] or 0
        occupied_seats = Booking.objects.filter(
            branch=branch,
            date=today,
            status='CONFIRMED'
        ).aggregate(total=Sum('total_guests'))['total'] or 0
        
        occupancy_rate = (occupied_seats / total_seats * 100) if total_seats > 0 else 0
        
        # Booking statistics
        today_bookings = Booking.objects.filter(
            branch=branch,
            date=today,
            status='CONFIRMED'
        ).count()
        
        upcoming_bookings = Booking.objects.filter(
            branch=branch,
            date__gte=today,
            status='CONFIRMED'
        ).count()
        
        stats = {
            'branch_name': branch.name,
            'total_tables': total_tables,
            'occupied_tables': occupied_tables,
            'available_tables': available_tables,
            'total_seats': total_seats,
            'occupied_seats': occupied_seats,
            'occupancy_rate': round(occupancy_rate, 2),
            'today_bookings': today_bookings,
            'upcoming_bookings': upcoming_bookings,
        }
        
        return Response(stats)


class TableViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Table CRUD operations
    """
    queryset = Table.objects.select_related('branch__restaurant').all()
    serializer_class = TableSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['branch', 'seat_type', 'status', 'capacity', 'is_accessible']
    search_fields = ['table_number', 'branch__name']
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated, IsAdminOrManagerOfRestaurant]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """Filter queryset by branch if provided"""
        queryset = super().get_queryset()
        branch_id = self.request.query_params.get('branch')
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        return queryset
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def reserve(self, request, pk=None):
        """Temporarily reserve a table (used during checkout)"""
        table = self.get_object()
        
        if table.status != 'AVAILABLE':
            return Response(
                {'error': 'Table is not available'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mark table as reserved
        table.status = 'RESERVED'
        table.save()
        
        # Schedule auto-release after 15 minutes (implement with Celery in production)
        # For now, just return success
        
        logger.info(f"Table {table.id} reserved by user {request.user.email}")
        
        return Response({'status': 'Table reserved successfully'})


class MenuItemViewSet(viewsets.ModelViewSet):
    """
    ViewSet for MenuItem CRUD operations
    """
    queryset = MenuItem.objects.select_related('restaurant').all()
    serializer_class = MenuItemSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['restaurant', 'category', 'is_available', 'is_featured', 'is_popular']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'price', 'total_orders', 'average_rating', 'created_at']
    ordering = ['category', 'name']
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated, IsAdminOrManagerOfRestaurant]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """Filter queryset by restaurant if provided"""
        queryset = super().get_queryset()
        restaurant_id = self.request.query_params.get('restaurant')
        if restaurant_id:
            queryset = queryset.filter(restaurant_id=restaurant_id)
        return queryset
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def popular(self, request):
        """Get popular menu items"""
        popular = self.get_queryset().filter(
            is_popular=True,
            is_available=True
        ).order_by('-total_orders')[:20]
        
        serializer = self.get_serializer(popular, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def categories(self, request):
        """Get all menu categories with item counts"""
        from django.db.models import Count
        
        categories = MenuItem.objects.filter(
            is_available=True
        ).values('category').annotate(
            count=Count('id'),
            restaurant_count=Count('restaurant', distinct=True)
        ).order_by('category')
        
        return Response(categories)

