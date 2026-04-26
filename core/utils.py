"""
Core App Utilities (Optimized & Synchronized)
"""

import re
import json
import hmac
import uuid
import hashlib
import secrets
import logging

from decimal import Decimal
from datetime import datetime, timedelta

from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


# =====================================
# 🔹 ID GENERATORS
# =====================================

def _generate_id(prefix, length):
    date_part = timezone.now().strftime('%Y%m%d')
    random_part = uuid.uuid4().hex[:length].upper()
    return f"{prefix}-{date_part}-{random_part}"


def generate_booking_id():
    return _generate_id("RSX", 6)


def generate_transaction_id():
    return _generate_id("TXN", 8)


def generate_receipt_number():
    return _generate_id("RCP", 6)


def generate_qr_code_data(table_id, restaurant_id):
    return json.dumps({
        'type': 'table',
        'table_id': str(table_id),
        'restaurant_id': str(restaurant_id),
        'timestamp': timezone.now().isoformat()
    })


# =====================================
# 🔹 VALIDATION
# =====================================

def validate_phone_number(phone):
    if not phone:
        return False, None

    digits = re.sub(r'\D', '', phone)

    if not (9 <= len(digits) <= 15):
        return False, None

    return True, f"+{digits}"


def validate_email(email):
    return bool(re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email))


def validate_date_range(start_date, end_date, max_days=30):
    if start_date > end_date:
        return False, "Start must be before end"

    if (end_date - start_date).days > max_days:
        return False, f"Max {max_days} days allowed"

    return True, None


def validate_time_slot(start_time, end_time, operating_hours):
    if not operating_hours:
        return True, None

    def to_min(t): return t.hour * 60 + t.minute

    start, end = to_min(start_time), to_min(end_time)
    open_t = datetime.strptime(operating_hours['open'], '%H:%M').time()
    close_t = datetime.strptime(operating_hours['close'], '%H:%M').time()

    if start < to_min(open_t) or end > to_min(close_t):
        return False, "Outside operating hours"

    return True, None


# =====================================
# 🔹 PRICE
# =====================================

def calculate_tax(amount, rate=0.1):
    return amount * Decimal(str(rate))


def calculate_discount(amount, percent):
    return amount * (Decimal(str(percent)) / 100)


def format_currency(amount, currency='USD'):
    return f"{currency} {amount:,.2f}"



def send_html_email(subject, template, context, recipients, from_email=None):
    try:
        html = render_to_string(template, context)
        plain = strip_tags(html)

        send_mail(
            subject,
            plain,
            from_email or settings.DEFAULT_FROM_EMAIL,
            recipients if isinstance(recipients, list) else [recipients],
            html_message=html
        )
        return True
    except Exception as e:
        logger.error(f"Email error: {e}")
        return False


def send_booking_confirmation_email(booking):
    return send_html_email(
        subject=f"Booking Confirmed - {booking.booking_id}",
        template='emails/booking_confirmation.html',
        context={'booking': booking},
        recipients=[booking.user.email]
    )


def send_payment_notification(payment, status='SUCCESS', error=''):
    return send_html_email(
        subject=f"Payment {status} - {payment.transaction_id}",
        template='emails/payment_notification.html',
        context={'payment': payment, 'error': error},
        recipients=[payment.user.email]
    )


# =====================================
# 🔹 REQUEST HELPERS
# =====================================

def get_client_ip(request):
    return request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0] \
        or request.META.get('REMOTE_ADDR')


def get_user_agent(request):
    return request.META.get('HTTP_USER_AGENT', '')


def is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


# =====================================
# 🔹 DATA FORMAT
# =====================================

def serialize_decimal(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def format_datetime(dt, fmt='%Y-%m-%d %H:%M:%S'):
    return dt.strftime(fmt) if dt else None


def parse_datetime(dt_str, fmt='%Y-%m-%d %H:%M:%S'):
    try:
        return datetime.strptime(dt_str, fmt)
    except:
        return None


# =====================================
# 🔹 SECURITY
# =====================================

def generate_secure_token(length=32):
    return secrets.token_urlsafe(length)


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def verify_webhook_signature(payload, signature, secret):
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# =====================================
# 🔹 PAGINATION
# =====================================

def paginate_queryset(queryset, page=1, page_size=10):
    total = queryset.count()
    start = (page - 1) * page_size

    return {
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': (total + page_size - 1) // page_size,
        'results': queryset[start:start + page_size]
    }


# =====================================
# 🔹 CACHE KEYS
# =====================================

def cache_key(prefix, *args):
    return f"{prefix}:{':'.join(map(str, args))}"


def get_restaurant_cache_key(rid):
    return cache_key("restaurant", rid)


def get_menu_cache_key(rid):
    return cache_key("menu", rid)


def get_availability_cache_key(branch_id, date):
    return cache_key("availability", branch_id, date)


# =====================================
# 🔹 BUSINESS LOGIC
# =====================================

def calculate_occupancy_rate(booked, total):
    return (booked / total * 100) if total else 0


def get_time_slots(date, duration=1, interval=30):
    slots = []
    current = datetime.combine(date, datetime.min.time())
    end = current + timedelta(days=1)

    while current + timedelta(hours=duration) <= end:
        slots.append(current.time())
        current += timedelta(minutes=interval)

    return slots


def check_table_availability(table, date, start_time, duration):
    from bookings.models import Booking

    end_time = (datetime.combine(date, start_time) +
                timedelta(hours=duration)).time()

    return not Booking.objects.filter(
        table=table,
        date=date,
        status__in=['PENDING_PAYMENT', 'CONFIRMED'],
        start_time__lt=end_time,
        end_time__gt=start_time
    ).exists()


# =====================================
# 🔹 NOTIFICATION
# =====================================

def create_notification(user, title, message):
    logger.info(f"{user.email}: {title} - {message}")


def send_sms_notification(phone, message):
    logger.info(f"SMS {phone}: {message}")
    return True


# =====================================
# 🔹 FILE
# =====================================

def get_file_extension(filename):
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


def generate_filename(prefix, extension):
    return f"{prefix}_{uuid.uuid4().hex}.{extension}"