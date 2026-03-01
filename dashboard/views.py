from django.shortcuts import render

# Create your views here.
"""
Dashboard App Views
Dashboard endpoints for different user roles (USER, MANAGER, ADMIN)
Provides aggregated data and analytics for the frontend
"""

from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Sum, Avg, Max, Min
from django.db.models.functions import TruncDate, TruncMonth, TruncHour
from django.utils import timezone
from django.shortcuts import get_object_or_404
from datetime import timedelta, datetime
import logging

from bookings.models import Booking, BookingMenu
from restaurants.models import Restaurant, Branch, Table, MenuItem
from users.models import User
from users.permissions import IsAdmin, IsManager, IsUser, CanViewDashboard
from payments.models import Payment

logger = logging.getLogger(__name__)


class UserDashboardView(viewsets.GenericViewSet):
    """
    Dashboard endpoints for regular users
    """
    permission_classes = [IsAuthenticated, IsUser]
    
    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """
        Get user dashboard overview
        """
        user = request.user
        today = timezone.now().date()
        
        # Booking statistics
        total_bookings = Booking.objects.filter(user=user).count()
        
        upcoming_bookings = Booking.objects.filter(
            user=user,
            date__gte=today,
            status__in=[Booking.Status.CONFIRMED, Booking.Status.PENDING_PAYMENT]
        ).count()
        
        past_bookings = Booking.objects.filter(
            user=user,
            date__lt=today,
            status=Booking.Status.COMPLETED
        ).count()
        
        cancelled_bookings = Booking.objects.filter(
            user=user,
            status__in=[Booking.Status.CANCELLED, Booking.Status.REJECTED, Booking.Status.EXPIRED]
        ).count()
        
        # Total spent
        total_spent = Payment.objects.filter(
            user=user,
            payment_status='SUCCESS'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Favorite restaurant
        favorite_restaurant = Booking.objects.filter(
            user=user,
            status=Booking.Status.COMPLETED
        ).values('restaurant__name', 'restaurant_id').annotate(
            count=Count('id')
        ).order_by('-count').first()
        
        # Upcoming bookings (next 5)
        upcoming = Booking.objects.filter(
            user=user,
            date__gte=today,
            status__in=[Booking.Status.CONFIRMED, Booking.Status.PENDING_PAYMENT]
        ).select_related('restaurant', 'branch', 'table').order_by('date', 'start_time')[:5]
        
        upcoming_data = [{
            'id': str(b.id),
            'booking_id': b.booking_id,
            'restaurant_name': b.restaurant.name,
            'branch_name': b.branch.name,
            'table_number': b.table.table_number,
            'date': b.date,
            'start_time': b.start_time.strftime('%H:%M'),
            'end_time': b.end_time.strftime('%H:%M'),
            'duration': b.duration,
            'total_guests': b.total_guests,
            'status': b.status,
            'status_display': b.get_status_display()
        } for b in upcoming]
        
        # Recent bookings (last 5)
        recent = Booking.objects.filter(
            user=user
        ).select_related('restaurant', 'branch').order_by('-created_at')[:5]
        
        recent_data = [{
            'id': str(b.id),
            'booking_id': b.booking_id,
            'restaurant_name': b.restaurant.name,
            'date': b.date,
            'start_time': b.start_time.strftime('%H:%M'),
            'total_guests': b.total_guests,
            'status': b.status,
            'status_display': b.get_status_display(),
            'total_price': float(b.total_price),
            'created_at': b.created_at
        } for b in recent]
        
        # Popular cuisine preferences
        preferred_cuisines = Booking.objects.filter(
            user=user,
            status=Booking.Status.COMPLETED
        ).values('restaurant__cuisine_type').annotate(
            count=Count('id')
        ).order_by('-count')[:3]
        
        # Monthly booking trend (last 6 months)
        six_months_ago = timezone.now() - timedelta(days=180)
        monthly_trend = Booking.objects.filter(
            user=user,
            created_at__gte=six_months_ago
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            count=Count('id'),
            total_spent=Sum('total_price')
        ).order_by('month')
        
        response_data = {
            'user': {
                'id': str(user.id),
                'name': user.name,
                'email': user.email,
                'phone': user.phone,
                'member_since': user.date_joined,
                'total_bookings': total_bookings,
                'total_spent': float(total_spent)
            },
            'statistics': {
                'total_bookings': total_bookings,
                'upcoming_bookings': upcoming_bookings,
                'past_bookings': past_bookings,
                'cancelled_bookings': cancelled_bookings
            },
            'favorite_restaurant': favorite_restaurant,
            'upcoming_bookings': upcoming_data,
            'recent_bookings': recent_data,
            'preferred_cuisines': list(preferred_cuisines),
            'monthly_trend': list(monthly_trend)
        }
        
        return Response(response_data)
    
    @action(detail=False, methods=['get'])
    def bookings(self, request):
        """
        Get user's booking history with filters
        """
        bookings = Booking.objects.filter(user=request.user).select_related(
            'restaurant', 'branch', 'table'
        ).prefetch_related('menu_items__menu_item')
        
        # Filter by status
        status = request.query_params.get('status')
        if status:
            bookings = bookings.filter(status=status)
        
        # Filter by date range
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        if from_date:
            bookings = bookings.filter(date__gte=from_date)
        if to_date:
            bookings = bookings.filter(date__lte=to_date)
        
        # Pagination
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('page_size', 10)
        
        start = (int(page) - 1) * int(page_size)
        end = start + int(page_size)
        
        total = bookings.count()
        paginated_bookings = bookings.order_by('-date', '-start_time')[start:end]
        
        bookings_data = []
        for booking in paginated_bookings:
            bookings_data.append({
                'id': str(booking.id),
                'booking_id': booking.booking_id,
                'restaurant': {
                    'id': str(booking.restaurant.id),
                    'name': booking.restaurant.name,
                    'cuisine_type': booking.restaurant.cuisine_type,
                    'logo': booking.restaurant.logo
                },
                'branch': {
                    'id': str(booking.branch.id),
                    'name': booking.branch.name,
                    'address': booking.branch.address,
                    'city': booking.branch.city
                },
                'table': {
                    'id': str(booking.table.id),
                    'number': booking.table.table_number,
                    'capacity': booking.table.capacity,
                    'seat_type': booking.table.seat_type
                },
                'date': booking.date,
                'start_time': booking.start_time.strftime('%H:%M'),
                'end_time': booking.end_time.strftime('%H:%M'),
                'duration': booking.duration,
                'total_guests': booking.total_guests,
                'total_price': float(booking.total_price),
                'status': booking.status,
                'status_display': booking.get_status_display(),
                'menu_items': [{
                    'name': item.menu_item.name,
                    'quantity': item.quantity,
                    'price': float(item.subtotal)
                } for item in booking.menu_items.all()],
                'created_at': booking.created_at,
                'can_cancel': booking.status in [Booking.Status.PENDING_PAYMENT, Booking.Status.CONFIRMED]
            })
        
        return Response({
            'total': total,
            'page': int(page),
            'page_size': int(page_size),
            'total_pages': (total + int(page_size) - 1) // int(page_size),
            'results': bookings_data
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get detailed user statistics
        """
        user = request.user
        
        # Booking by status
        by_status = Booking.objects.filter(user=user).values('status').annotate(
            count=Count('id'),
            total=Sum('total_price')
        )
        
        # Spending by month
        six_months_ago = timezone.now() - timedelta(days=180)
        spending_by_month = Payment.objects.filter(
            user=user,
            payment_status='SUCCESS',
            created_at__gte=six_months_ago
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            total=Sum('amount')
        ).order_by('month')
        
        # Popular restaurants
        popular_restaurants = Booking.objects.filter(
            user=user,
            status=Booking.Status.COMPLETED
        ).values(
            'restaurant__id',
            'restaurant__name',
            'restaurant__cuisine_type'
        ).annotate(
            visits=Count('id'),
            total_spent=Sum('total_price')
        ).order_by('-visits')[:5]
        
        # Average booking value
        avg_booking = Booking.objects.filter(
            user=user,
            status__in=[Booking.Status.COMPLETED, Booking.Status.CONFIRMED]
        ).aggregate(
            avg=Avg('total_price'),
            max=Max('total_price'),
            min=Min('total_price')
        )
        
        # Peak booking times
        peak_times = Booking.objects.filter(
            user=user
        ).annotate(
            hour=TruncHour('start_time')
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('-count')[:3]
        
        return Response({
            'by_status': list(by_status),
            'spending_by_month': list(spending_by_month),
            'popular_restaurants': list(popular_restaurants),
            'average_booking': {
                'average': float(avg_booking['avg'] or 0),
                'maximum': float(avg_booking['max'] or 0),
                'minimum': float(avg_booking['min'] or 0)
            },
            'peak_times': list(peak_times)
        })


class ManagerDashboardView(viewsets.GenericViewSet):
    """
    Dashboard endpoints for restaurant managers
    """
    permission_classes = [IsAuthenticated, IsManager]
    
    def get_managed_restaurants(self, user):
        """Get restaurants managed by the user"""
        return Restaurant.objects.filter(manager=user)
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """
        Get manager dashboard overview
        """
        user = request.user
        managed_restaurants = self.get_managed_restaurants(user)
        restaurant_ids = managed_restaurants.values_list('id', flat=True)
        
        today = timezone.now().date()
        
        # Basic statistics
        total_restaurants = managed_restaurants.count()
        total_branches = Branch.objects.filter(restaurant__in=restaurant_ids).count()
        total_tables = Table.objects.filter(branch__restaurant__in=restaurant_ids).count()
        total_menu_items = MenuItem.objects.filter(restaurant__in=restaurant_ids).count()
        
        # Booking statistics
        bookings_today = Booking.objects.filter(
            restaurant__in=restaurant_ids,
            date=today,
            status__in=[Booking.Status.CONFIRMED, Booking.Status.PENDING_PAYMENT]
        ).count()
        
        pending_approvals = Booking.objects.filter(
            restaurant__in=restaurant_ids,
            status=Booking.Status.PENDING_PAYMENT,
            date__gte=today
        ).count()
        
        total_bookings = Booking.objects.filter(
            restaurant__in=restaurant_ids
        ).count()
        
        # Revenue today
        revenue_today = Payment.objects.filter(
            booking__restaurant__in=restaurant_ids,
            booking__date=today,
            payment_status='SUCCESS'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Revenue this month
        month_start = today.replace(day=1)
        revenue_month = Payment.objects.filter(
            booking__restaurant__in=restaurant_ids,
            booking__date__gte=month_start,
            payment_status='SUCCESS'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Table occupancy
        total_capacity = Table.objects.filter(
            branch__restaurant__in=restaurant_ids
        ).aggregate(total=Sum('capacity'))['total'] or 0
        
        occupied_seats = Booking.objects.filter(
            restaurant__in=restaurant_ids,
            date=today,
            status=Booking.Status.CONFIRMED
        ).aggregate(total=Sum('total_guests'))['total'] or 0
        
        occupancy_rate = (occupied_seats / total_capacity * 100) if total_capacity > 0 else 0
        
        # Recent bookings
        recent_bookings = Booking.objects.filter(
            restaurant__in=restaurant_ids
        ).select_related('restaurant', 'user').order_by('-created_at')[:10]
        
        recent_data = [{
            'id': str(b.id),
            'booking_id': b.booking_id,
            'restaurant_name': b.restaurant.name,
            'customer_name': b.user.name,
            'customer_email': b.user.email,
            'date': b.date,
            'start_time': b.start_time.strftime('%H:%M'),
            'total_guests': b.total_guests,
            'status': b.status,
            'status_display': b.get_status_display(),
            'total_price': float(b.total_price)
        } for b in recent_bookings]
        
        # Popular menu items
        popular_items = BookingMenu.objects.filter(
            booking__restaurant__in=restaurant_ids,
            booking__status=Booking.Status.COMPLETED
        ).values(
            'menu_item__name',
            'menu_item__category'
        ).annotate(
            total_ordered=Sum('quantity'),
            total_revenue=Sum('subtotal')
        ).order_by('-total_ordered')[:5]
        
        response_data = {
            'statistics': {
                'total_restaurants': total_restaurants,
                'total_branches': total_branches,
                'total_tables': total_tables,
                'total_menu_items': total_menu_items,
                'bookings_today': bookings_today,
                'pending_approvals': pending_approvals,
                'total_bookings': total_bookings,
                'revenue_today': float(revenue_today),
                'revenue_month': float(revenue_month),
                'occupancy_rate': round(occupancy_rate, 2)
            },
            'restaurants': [{
                'id': str(r.id),
                'name': r.name,
                'total_branches': r.total_branches,
                'average_rating': float(r.average_rating),
                'total_bookings': r.total_bookings
            } for r in managed_restaurants],
            'recent_bookings': recent_data,
            'popular_menu_items': list(popular_items)
        }
        
        return Response(response_data)
    
    @action(detail=False, methods=['get'])
    def bookings(self, request):
        """
        Get all bookings for managed restaurants with filters
        """
        user = request.user
        restaurant_ids = self.get_managed_restaurants(user).values_list('id', flat=True)
        
        bookings = Booking.objects.filter(
            restaurant__in=restaurant_ids
        ).select_related('user', 'restaurant', 'branch', 'table').order_by('-date', '-start_time')
        
        # Filter by status
        status = request.query_params.get('status')
        if status:
            bookings = bookings.filter(status=status)
        
        # Filter by date range
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        if from_date:
            bookings = bookings.filter(date__gte=from_date)
        if to_date:
            bookings = bookings.filter(date__lte=to_date)
        
        # Filter by restaurant
        restaurant_id = request.query_params.get('restaurant_id')
        if restaurant_id:
            bookings = bookings.filter(restaurant_id=restaurant_id)
        
        # Pagination
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('page_size', 20)
        
        start = (int(page) - 1) * int(page_size)
        end = start + int(page_size)
        
        total = bookings.count()
        paginated_bookings = bookings[start:end]
        
        bookings_data = [{
            'id': str(b.id),
            'booking_id': b.booking_id,
            'customer': {
                'id': str(b.user.id),
                'name': b.user.name,
                'email': b.user.email,
                'phone': b.user.phone
            },
            'restaurant': {
                'id': str(b.restaurant.id),
                'name': b.restaurant.name
            },
            'branch': {
                'id': str(b.branch.id),
                'name': b.branch.name
            },
            'table': {
                'id': str(b.table.id),
                'number': b.table.table_number,
                'capacity': b.table.capacity
            },
            'date': b.date,
            'start_time': b.start_time.strftime('%H:%M'),
            'end_time': b.end_time.strftime('%H:%M'),
            'duration': b.duration,
            'total_guests': b.total_guests,
            'total_price': float(b.total_price),
            'status': b.status,
            'status_display': b.get_status_display(),
            'special_requests': b.special_requests,
            'waiter_name': b.waiter_name,
            'created_at': b.created_at
        } for b in paginated_bookings]
        
        return Response({
            'total': total,
            'page': int(page),
            'page_size': int(page_size),
            'total_pages': (total + int(page_size) - 1) // int(page_size),
            'results': bookings_data
        })
    
    @action(detail=False, methods=['get'])
    def pending_approvals(self, request):
        """
        Get pending booking approvals
        """
        user = request.user
        restaurant_ids = self.get_managed_restaurants(user).values_list('id', flat=True)
        
        pending = Booking.objects.filter(
            restaurant__in=restaurant_ids,
            status=Booking.Status.PENDING_PAYMENT,
            date__gte=timezone.now().date()
        ).select_related('user', 'restaurant', 'branch', 'table').order_by('date', 'start_time')
        
        data = [{
            'id': str(b.id),
            'booking_id': b.booking_id,
            'customer_name': b.user.name,
            'customer_email': b.user.email,
            'customer_phone': b.user.phone,
            'restaurant_name': b.restaurant.name,
            'branch_name': b.branch.name,
            'table_number': b.table.table_number,
            'date': b.date,
            'start_time': b.start_time.strftime('%H:%M'),
            'end_time': b.end_time.strftime('%H:%M'),
            'duration': b.duration,
            'total_guests': b.total_guests,
            'total_price': float(b.total_price),
            'special_requests': b.special_requests,
            'created_at': b.created_at,
            'expires_at': b.expires_at
        } for b in pending]
        
        return Response({
            'total': pending.count(),
            'results': data
        })
    
    @action(detail=False, methods=['get'])
    def restaurant_performance(self, request):
        """
        Get performance metrics for each managed restaurant
        """
        user = request.user
        restaurants = self.get_managed_restaurants(user)
        
        performance_data = []
        for restaurant in restaurants:
            # Bookings by status
            bookings = Booking.objects.filter(restaurant=restaurant)
            total_bookings = bookings.count()
            
            # Revenue
            revenue = Payment.objects.filter(
                booking__restaurant=restaurant,
                payment_status='SUCCESS'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            # Popular times
            popular_times = bookings.filter(
                status=Booking.Status.COMPLETED
            ).values('start_time').annotate(
                count=Count('id')
            ).order_by('-count')[:3]
            
            performance_data.append({
                'restaurant_id': str(restaurant.id),
                'restaurant_name': restaurant.name,
                'total_bookings': total_bookings,
                'total_revenue': float(revenue),
                'average_rating': float(restaurant.average_rating),
                'total_reviews': restaurant.total_reviews,
                'popular_times': list(popular_times),
                'completion_rate': round(
                    bookings.filter(status=Booking.Status.COMPLETED).count() / total_bookings * 100
                    if total_bookings > 0 else 0, 2
                )
            })
        
        return Response(performance_data)


class AdminDashboardView(viewsets.GenericViewSet):
    """
    Dashboard endpoints for administrators
    """
    permission_classes = [IsAuthenticated, IsAdmin]
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """
        Get admin dashboard overview
        """
        today = timezone.now().date()
        month_start = today.replace(day=1)
        
        # User statistics
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        verified_users = User.objects.filter(is_verified=True).count()
        
        users_by_role = User.objects.values('role').annotate(count=Count('id'))
        
        # Restaurant statistics
        total_restaurants = Restaurant.objects.count()
        active_restaurants = Restaurant.objects.filter(is_active=True).count()
        verified_restaurants = Restaurant.objects.filter(is_verified=True).count()
        
        total_branches = Branch.objects.count()
        total_tables = Table.objects.count()
        total_menu_items = MenuItem.objects.count()
        
        # Booking statistics
        total_bookings = Booking.objects.count()
        bookings_today = Booking.objects.filter(date=today).count()
        pending_bookings = Booking.objects.filter(status=Booking.Status.PENDING_PAYMENT).count()
        
        bookings_by_status = Booking.objects.values('status').annotate(count=Count('id'))
        
        # Revenue statistics
        revenue_today = Payment.objects.filter(
            booking__date=today,
            payment_status='SUCCESS'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        revenue_month = Payment.objects.filter(
            booking__date__gte=month_start,
            payment_status='SUCCESS'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        revenue_total = Payment.objects.filter(
            payment_status='SUCCESS'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Platform growth (users over time)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        users_growth = User.objects.filter(
            date_joined__gte=thirty_days_ago
        ).count()
        
        restaurants_growth = Restaurant.objects.filter(
            created_at__gte=thirty_days_ago
        ).count()
        
        bookings_growth = Booking.objects.filter(
            created_at__gte=thirty_days_ago
        ).count()
        
        response_data = {
            'users': {
                'total': total_users,
                'active': active_users,
                'verified': verified_users,
                'by_role': list(users_by_role),
                'growth_30d': users_growth
            },
            'restaurants': {
                'total': total_restaurants,
                'active': active_restaurants,
                'verified': verified_restaurants,
                'total_branches': total_branches,
                'total_tables': total_tables,
                'total_menu_items': total_menu_items,
                'growth_30d': restaurants_growth
            },
            'bookings': {
                'total': total_bookings,
                'today': bookings_today,
                'pending': pending_bookings,
                'by_status': list(bookings_by_status),
                'growth_30d': bookings_growth
            },
            'revenue': {
                'today': float(revenue_today),
                'month': float(revenue_month),
                'total': float(revenue_total)
            }
        }
        
        return Response(response_data)
    
    @action(detail=False, methods=['get'])
    def users(self, request):
        """
        Get user statistics and list
        """
        users = User.objects.all().order_by('-date_joined')
        
        # Filter by role
        role = request.query_params.get('role')
        if role:
            users = users.filter(role=role)
        
        # Filter by verification status
        verified = request.query_params.get('verified')
        if verified:
            users = users.filter(is_verified=verified.lower() == 'true')
        
        # Pagination
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('page_size', 20)
        
        start = (int(page) - 1) * int(page_size)
        end = start + int(page_size)
        
        total = users.count()
        paginated_users = users.select_related().prefetch_related('bookings')[start:end]
        
        users_data = [{
            'id': str(u.id),
            'email': u.email,
            'name': u.name,
            'phone': u.phone,
            'role': u.role,
            'role_display': u.get_role_display(),
            'is_active': u.is_active,
            'is_verified': u.is_verified,
            'date_joined': u.date_joined,
            'last_login': u.last_login,
            'total_bookings': u.bookings.count(),
            'total_spent': float(Payment.objects.filter(
                user=u,
                payment_status='SUCCESS'
            ).aggregate(total=Sum('amount'))['total'] or 0)
        } for u in paginated_users]
        
        return Response({
            'total': total,
            'page': int(page),
            'page_size': int(page_size),
            'total_pages': (total + int(page_size) - 1) // int(page_size),
            'results': users_data
        })
    
    @action(detail=False, methods=['get'])
    def restaurants(self, request):
        """
        Get restaurant statistics and list
        """
        restaurants = Restaurant.objects.all().order_by('-created_at')
        
        # Filter by cuisine
        cuisine = request.query_params.get('cuisine')
        if cuisine:
            restaurants = restaurants.filter(cuisine_type=cuisine)
        
        # Filter by verification status
        verified = request.query_params.get('verified')
        if verified:
            restaurants = restaurants.filter(is_verified=verified.lower() == 'true')
        
        # Pagination
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('page_size', 20)
        
        start = (int(page) - 1) * int(page_size)
        end = start + int(page_size)
        
        total = restaurants.count()
        paginated_restaurants = restaurants.select_related('manager').prefetch_related('branches')[start:end]
        
        restaurants_data = [{
            'id': str(r.id),
            'name': r.name,
            'cuisine_type': r.cuisine_type,
            'cuisine_display': r.get_cuisine_type_display(),
            'price_level': r.price_level,
            'city': r.city,
            'manager': {
                'id': str(r.manager.id) if r.manager else None,
                'name': r.manager.name if r.manager else None,
                'email': r.manager.email if r.manager else None
            } if r.manager else None,
            'is_active': r.is_active,
            'is_verified': r.is_verified,
            'total_branches': r.total_branches,
            'average_rating': float(r.average_rating),
            'total_bookings': r.total_bookings,
            'created_at': r.created_at
        } for r in paginated_restaurants]
        
        return Response({
            'total': total,
            'page': int(page),
            'page_size': int(page_size),
            'total_pages': (total + int(page_size) - 1) // int(page_size),
            'results': restaurants_data
        })
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """
        Get advanced analytics
        """
        # Date range
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=90)  # Last 90 days
        
        from_date = request.query_params.get('from_date', start_date)
        to_date = request.query_params.get('to_date', end_date)
        
        # Bookings over time
        bookings_over_time = Booking.objects.filter(
            date__gte=from_date,
            date__lte=to_date
        ).annotate(
            day=TruncDate('date')
        ).values('day').annotate(
            count=Count('id'),
            revenue=Sum('total_price')
        ).order_by('day')
        
        # Revenue by restaurant
        revenue_by_restaurant = Payment.objects.filter(
            booking__date__gte=from_date,
            booking__date__lte=to_date,
            payment_status='SUCCESS'
        ).values(
            'booking__restaurant__name'
        ).annotate(
            total=Sum('amount'),
            bookings=Count('booking')
        ).order_by('-total')
        
        # User acquisition over time
        user_acquisition = User.objects.filter(
            date_joined__gte=from_date,
            date_joined__lte=to_date
        ).annotate(
            day=TruncDate('date_joined')
        ).values('day').annotate(
            count=Count('id')
        ).order_by('day')
        
        return Response({
            'period': {
                'from': from_date,
                'to': to_date
            },
            'bookings_over_time': list(bookings_over_time),
            'revenue_by_restaurant': list(revenue_by_restaurant),
            'user_acquisition': list(user_acquisition)
        })