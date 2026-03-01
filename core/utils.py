"""
Core App Utilities
Helper functions and utilities used across the application
"""

import random
import string
import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta, date
from decimal import Decimal
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)


# ==================== ID GENERATORS ====================

def generate_booking_id():
    """
    Generate a unique booking ID
    Format: RSX-YYYYMMDD-XXXXXX
    """
    import uuid
    date_part = timezone.now().strftime('%Y%m%d')
    random_part = uuid.uuid4().hex[:6].upper()
    return f"RSX-{date_part}-{random_part}"


def generate_transaction_id():
    """
    Generate a unique transaction ID
    Format: TXN-YYYYMMDD-XXXXXXXX
    """
    import uuid
    date_part = timezone.now().strftime('%Y%m%d')
    random_part = uuid.uuid4().hex[:8].upper()
    return f"TXN-{date_part}-{random_part}"


def generate_receipt_number():
    """
    Generate a receipt number
    Format: RCP-YYYYMMDD-XXXXXX
    """
    import uuid
    date_part = timezone.now().strftime('%Y%m%d')
    random_part = uuid.uuid4().hex[:6].upper()
    return f"RCP-{date_part}-{random_part}"


def generate_qr_code_data(table_id, restaurant_id):
    """
    Generate QR code data for table
    """
    data = {
        'type': 'table',
        'table_id': str(table_id),
        'restaurant_id': str(restaurant_id),
        'timestamp': timezone.now().isoformat()
    }
    return json.dumps(data)


# ==================== VALIDATION FUNCTIONS ====================

def validate_phone_number(phone):
    """
    Validate phone number format
    Returns (is_valid, formatted_number)
    """
    if not phone:
        return False, None
    
    # Remove all non-digit characters
    phone_digits = re.sub(r'\D', '', phone)
    
    # Check length
    if len(phone_digits) < 9 or len(phone_digits) > 15:
        return False, None
    
    # Format with country code if missing
    if len(phone_digits) == 10 and not phone.startswith('+'):
        formatted = f"+1{phone_digits}"  # Assuming US/Canada
    else:
        formatted = f"+{phone_digits}" if not phone_digits.startswith('+') else phone_digits
    
    return True, formatted


def validate_email(email):
    """
    Validate email format
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_date_range(start_date, end_date, max_days=30):
    """
    Validate that date range is valid and within limits
    """
    if start_date > end_date:
        return False, "Start date must be before end date"
    
    if (end_date - start_date).days > max_days:
        return False, f"Date range cannot exceed {max_days} days"
    
    return True, None


def validate_time_slot(start_time, end_time, operating_hours):
    """
    Validate that time slot is within operating hours
    """
    # Convert to minutes since midnight for easier comparison
    def time_to_minutes(t):
        return t.hour * 60 + t.minute
    
    start_mins = time_to_minutes(start_time)
    end_mins = time_to_minutes(end_time)
    
    # Check if within operating hours
    if 'open' in operating_hours and 'close' in operating_hours:
        open_mins = time_to_minutes(datetime.strptime(operating_hours['open'], '%H:%M').time())
        close_mins = time_to_minutes(datetime.strptime(operating_hours['close'], '%H:%M').time())
        
        if start_mins < open_mins or end_mins > close_mins:
            return False, "Time slot is outside operating hours"
    
    return True, None


# ==================== PRICE CALCULATIONS ====================

def calculate_tax(amount, tax_rate=0.1):
    """
    Calculate tax amount
    """
    return amount * Decimal(str(tax_rate))


def calculate_discount(amount, discount_percent):
    """
    Calculate discount amount
    """
    return amount * (Decimal(str(discount_percent)) / 100)


def format_currency(amount, currency='USD'):
    """
    Format amount as currency string
    """
    return f"{currency} {amount:,.2f}"


# ==================== EMAIL FUNCTIONS ====================

def send_html_email(subject, html_template, context, to_emails, from_email=None):
    """
    Send HTML email using template
    """
    try:
        html_message = render_to_string(html_template, context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email or settings.DEFAULT_FROM_EMAIL,
            recipient_list=to_emails if isinstance(to_emails, list) else [to_emails],
            html_message=html_message,
            fail_silently=False
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False


def send_booking_confirmation_email(booking):
    """
    Send booking confirmation email
    """
    context = {
        'user': booking.user,
        'booking': booking,
        'restaurant': booking.restaurant,
        'branch': booking.branch,
        'table': booking.table,
        'menu_items': booking.menu_items.all(),
        'frontend_url': settings.FRONTEND_URL
    }
    
    return send_html_email(
        subject=f"Booking Confirmed - {booking.booking_id}",
        html_template='emails/booking_confirmation.html',
        context=context,
        to_emails=[booking.user.email]
    )


def send_payment_notification(payment, notification_type='SUCCESS', error_message=''):
    """
    Send payment notification email
    """
    subject_map = {
        'SUCCESS': f"Payment Successful - {payment.transaction_id}",
        'FAILED': f"Payment Failed - {payment.transaction_id}",
        'REFUNDED': f"Payment Refunded - {payment.transaction_id}"
    }
    
    context = {
        'user': payment.user,
        'payment': payment,
        'booking': payment.booking,
        'notification_type': notification_type,
        'error_message': error_message,
        'frontend_url': settings.FRONTEND_URL
    }
    
    return send_html_email(
        subject=subject_map.get(notification_type, 'Payment Update'),
        html_template='emails/payment_notification.html',
        context=context,
        to_emails=[payment.user.email]
    )


# ==================== REQUEST UTILITIES ====================

def get_client_ip(request):
    """
    Get client IP address from request
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request):
    """
    Get user agent from request
    """
    return request.META.get('HTTP_USER_AGENT', '')


def is_ajax(request):
    """
    Check if request is AJAX
    """
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


# ==================== DATA FORMATTING ====================

def serialize_decimal(obj):
    """
    Serialize Decimal objects for JSON
    """
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def format_datetime(dt, format='%Y-%m-%d %H:%M:%S'):
    """
    Format datetime object
    """
    if dt:
        return dt.strftime(format)
    return None


def parse_datetime(dt_str, format='%Y-%m-%d %H:%M:%S'):
    """
    Parse datetime string
    """
    try:
        return datetime.strptime(dt_str, format)
    except (ValueError, TypeError):
        return None


# ==================== SECURITY ====================

def generate_secure_token(length=32):
    """
    Generate a secure random token
    """
    import secrets
    return secrets.token_urlsafe(length)


def hash_token(token):
    """
    Hash a token for storage
    """
    return hashlib.sha256(token.encode()).hexdigest()


def verify_webhook_signature(payload, signature, secret):
    """
    Verify webhook signature
    """
    expected = hmac.new(
        key=secret.encode(),
        msg=payload,
        digestmod=hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ==================== PAGINATION ====================

def paginate_queryset(queryset, page, page_size=10):
    """
    Paginate a queryset
    """
    total = queryset.count()
    start = (page - 1) * page_size
    end = start + page_size
    
    return {
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': (total + page_size - 1) // page_size,
        'results': queryset[start:end]
    }


# ==================== CACHE KEYS ====================

def get_restaurant_cache_key(restaurant_id):
    """
    Get cache key for restaurant
    """
    return f"restaurant:{restaurant_id}"


def get_menu_cache_key(restaurant_id):
    """
    Get cache key for menu
    """
    return f"menu:{restaurant_id}"


def get_availability_cache_key(branch_id, date):
    """
    Get cache key for availability
    """
    return f"availability:{branch_id}:{date}"


# ==================== BUSINESS LOGIC ====================

def calculate_occupancy_rate(booked_seats, total_seats):
    """
    Calculate occupancy rate
    """
    if total_seats == 0:
        return 0
    return (booked_seats / total_seats) * 100


def get_time_slots(date, duration=1, interval=30):
    """
    Generate available time slots
    """
    slots = []
    start_time = datetime.combine(date, datetime.min.time())
    end_time = start_time + timedelta(days=1)
    
    current = start_time
    while current + timedelta(minutes=duration*60) <= end_time:
        slots.append(current.time())
        current += timedelta(minutes=interval)
    
    return slots


def check_table_availability(table, date, start_time, duration):
    """
    Check if table is available for given time slot
    """
    from bookings.models import Booking
    
    end_time = (datetime.combine(date, start_time) + 
                timedelta(hours=duration)).time()
    
    # Check for overlapping bookings
    overlapping = Booking.objects.filter(
        table=table,
        date=date,
        status__in=['PENDING_PAYMENT', 'CONFIRMED'],
        start_time__lt=end_time,
        end_time__gt=start_time
    ).exists()
    
    return not overlapping


# ==================== NOTIFICATION HELPERS ====================

def create_notification(user, notification_type, title, message, data=None):
    """
    Create a notification for user
    (Placeholder for future push notification implementation)
    """
    from bookings.models import BookingNotification
    
    # For now, just log
    logger.info(f"Notification for {user.email}: {title} - {message}")
    
    # Create in-app notification if needed
    # This would be implemented with a Notification model


def send_sms_notification(phone, message):
    """
    Send SMS notification
    (Placeholder for SMS integration)
    """
    logger.info(f"SMS to {phone}: {message}")
    # Integrate with Twilio or similar service
    return True


# ==================== FILE HELPERS ====================

def get_file_extension(filename):
    """
    Get file extension from filename
    """
    if '.' in filename:
        return filename.rsplit('.', 1)[1].lower()
    return ''


def generate_filename(prefix, extension):
    """
    Generate a unique filename
    """
    import uuid
    return f"{prefix}_{uuid.uuid4().hex}.{extension}"