"""
Core App Signals (Optimized)
"""

from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
import logging

from users.models import User, UserPreference
from restaurants.models import Restaurant, Branch, Table
from bookings.models import Booking, BookingHistory
from payments.models import Payment

logger = logging.getLogger(__name__)


# ==================== USER SIGNALS ====================

@receiver(post_save, sender=User)
def handle_user_save(sender, instance, created, **kwargs):
    """
    Handle user creation + role change in one place
    """
    if created:
        UserPreference.objects.get_or_create(user=instance)
        logger.info(f"User created: {instance.email}")

    else:
        old = sender.objects.filter(pk=instance.pk).values('role').first()
        if old and old['role'] != instance.role:
            logger.info(f"Role changed: {instance.email} ({old['role']} → {instance.role})")


@receiver(pre_delete, sender=User)
def handle_manager_delete(sender, instance, **kwargs):
    """
    Delete managed restaurants safely
    """
    if instance.role != User.Role.MANAGER:
        return

    restaurants = Restaurant.objects.filter(manager=instance)

    if not restaurants.exists():
        return

    logger.info(f"Deleting {restaurants.count()} restaurants of {instance.email}")

    with transaction.atomic():
        Booking.objects.filter(
            restaurant__in=restaurants,
            status__in=[Booking.Status.PENDING_PAYMENT, Booking.Status.CONFIRMED]
        ).update(
            status=Booking.Status.CANCELLED,
            metadata={'reason': 'Manager deleted'}
        )

        restaurants.delete()


# ==================== RESTAURANT SIGNALS ====================

@receiver(pre_delete, sender=Restaurant)
def handle_restaurant_delete(sender, instance, **kwargs):
    logger.info(
        f"Deleting restaurant {instance.name} "
        f"(branches={instance.branches.count()}, "
        f"bookings={instance.bookings.count()})"
    )


# ==================== BRANCH SIGNALS ====================

@receiver([post_save, post_delete], sender=Branch)
def update_branch_stats(sender, instance, **kwargs):
    instance.restaurant.update_statistics()


# ==================== TABLE SIGNALS ====================

@receiver([post_save, post_delete], sender=Table)
def update_table_capacity(sender, instance, **kwargs):
    instance.branch.update_capacity()


# ==================== BOOKING SIGNALS ====================

@receiver(post_save, sender=Booking)
def handle_booking_save(sender, instance, created, **kwargs):
    if created:
        Restaurant.objects.filter(pk=instance.restaurant_id).update(
            total_bookings=models.F('total_bookings') + 1
        )
        logger.info(f"Booking created: {instance.booking_id}")
        return

    # ⚡ FIX: old value properly fetch before update
    old = sender.objects.filter(pk=instance.pk).values('status').first()

    if old and old['status'] != instance.status:
        BookingHistory.objects.create(
            booking=instance,
            old_status=old['status'],
            new_status=instance.status,
            changed_at=timezone.now()
        )


@receiver(pre_delete, sender=Booking)
def handle_booking_delete(sender, instance, **kwargs):
    Table.objects.filter(
        pk=instance.table_id,
        status=Table.Status.RESERVED
    ).update(status=Table.Status.AVAILABLE)


# ==================== PAYMENT SIGNALS ====================

@receiver(post_save, sender=Payment)
def handle_payment(sender, instance, created, **kwargs):
    if created:
        logger.info(f"Payment created: {instance.transaction_id}")

    booking = instance.booking

    if instance.payment_status == Payment.Status.SUCCESS:
        if booking.status != Booking.Status.CONFIRMED:
            booking.confirm_booking()

    elif instance.payment_status == Payment.Status.REFUNDED:
        if booking.status != Booking.Status.CANCELLED:
            booking.status = Booking.Status.CANCELLED
            booking.save(update_fields=['status'])


# ==================== SCHEDULED TASKS ====================

def cleanup_expired_bookings():
    count = Booking.expire_pending_bookings()
    if count:
        logger.info(f"Expired bookings: {count}")
    return count


def cleanup_incomplete_payments():
    cutoff = timezone.now() - timezone.timedelta(hours=1)

    qs = Payment.objects.filter(
        payment_status=Payment.Status.PENDING,
        created_at__lt=cutoff
    )

    count = qs.count()

    if count:
        qs.update(
            payment_status=Payment.Status.FAILED,
            metadata={'auto_expired': True}
        )
        logger.info(f"Expired payments: {count}")

    return count


def update_restaurant_statistics():
    for r in Restaurant.objects.all().only('id'):
        r.total_branches = r.branches.count()
        r.save(update_fields=['total_branches'])

    return Restaurant.objects.count()