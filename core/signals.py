"""
Core App Signals
Django signals for automatic cleanup and business rule enforcement
"""

from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
import logging

from users.models import User
from restaurants.models import Restaurant, Branch, Table
from bookings.models import Booking, BookingHistory
from payments.models import Payment

logger = logging.getLogger(__name__)


# ==================== USER SIGNALS ====================

@receiver(pre_delete, sender=User)
def handle_user_deletion(sender, instance, **kwargs):
    """
    Handle user deletion - cleanup related data
    """
    logger.info(f"User {instance.email} is being deleted")
    
    # For managers, check if they manage any restaurants
    if instance.role == User.Role.MANAGER:
        managed_restaurants = Restaurant.objects.filter(manager=instance)
        for restaurant in managed_restaurants:
            logger.info(f"Restaurant {restaurant.name} will be deleted due to manager deletion")
            # Restaurant will be auto-deleted via pre_delete signal


@receiver(post_save, sender=User)
def handle_user_created(sender, instance, created, **kwargs):
    """
    Handle user creation - create default preferences
    """
    if created:
        from users.models import UserPreference
        UserPreference.objects.get_or_create(user=instance)
        logger.info(f"Created default preferences for user {instance.email}")


@receiver(post_save, sender=User)
def handle_user_role_change(sender, instance, **kwargs):
    """
    Handle user role changes - update related permissions
    """
    if not kwargs.get('created', False):
        # Check if role has changed
        try:
            old_instance = User.objects.get(pk=instance.pk)
            if old_instance.role != instance.role:
                logger.info(f"User {instance.email} role changed from {old_instance.role} to {instance.role}")
                
                # If user was a manager and is no longer, handle restaurant cleanup
                if old_instance.role == User.Role.MANAGER and instance.role != User.Role.MANAGER:
                    # Restaurants will be auto-deleted via manager_pre_delete signal
                    pass
        except User.DoesNotExist:
            pass


# ==================== RESTAURANT SIGNALS ====================

@receiver(pre_delete, sender=Restaurant)
def handle_restaurant_deletion(sender, instance, **kwargs):
    """
    Handle restaurant deletion - cleanup all related data
    """
    logger.info(f"Restaurant {instance.name} is being deleted")
    
    # Log all related objects that will be cascade deleted
    branches_count = instance.branches.count()
    menu_items_count = instance.menu_items.count()
    bookings_count = instance.bookings.count()
    
    logger.info(f"Restaurant deletion will affect: {branches_count} branches, "
                f"{menu_items_count} menu items, {bookings_count} bookings")


@receiver(post_save, sender=Restaurant)
def handle_restaurant_save(sender, instance, created, **kwargs):
    """
    Handle restaurant save - update statistics
    """
    if not created:
        # Check if manager has changed
        try:
            old_instance = Restaurant.objects.get(pk=instance.pk)
            if old_instance.manager != instance.manager:
                logger.info(f"Restaurant {instance.name} manager changed from "
                           f"{old_instance.manager.email if old_instance.manager else 'None'} "
                           f"to {instance.manager.email if instance.manager else 'None'}")
                
                # If new manager is assigned, make sure they have manager role
                if instance.manager and instance.manager.role != User.Role.MANAGER:
                    logger.warning(f"User {instance.manager.email} assigned as manager "
                                  f"but has role {instance.manager.role}")
        except Restaurant.DoesNotExist:
            pass


@receiver(pre_delete, sender=User)
def manager_pre_delete(sender, instance, **kwargs):
    """
    Auto-delete restaurants when their manager is deleted
    """
    if instance.role == User.Role.MANAGER:
        # Get all restaurants managed by this user
        restaurants = Restaurant.objects.filter(manager=instance)
        
        if restaurants.exists():
            logger.info(f"Auto-deleting {restaurants.count()} restaurants managed by {instance.email}")
            
            # Delete all managed restaurants
            # This will cascade to branches, tables, bookings, etc.
            with transaction.atomic():
                for restaurant in restaurants:
                    # Archive any pending bookings before deletion
                    Booking.objects.filter(
                        restaurant=restaurant,
                        status__in=['PENDING_PAYMENT', 'CONFIRMED']
                    ).update(
                        status='CANCELLED',
                        metadata={'cancellation_reason': 'Restaurant manager deleted'}
                    )
                    
                    restaurant.delete()


# ==================== BRANCH SIGNALS ====================

@receiver(post_save, sender=Branch)
def handle_branch_save(sender, instance, created, **kwargs):
    """
    Handle branch save - update restaurant statistics
    """
    if created:
        instance.restaurant.update_statistics()
        logger.info(f"New branch {instance.name} created for restaurant {instance.restaurant.name}")


@receiver(post_delete, sender=Branch)
def handle_branch_delete(sender, instance, **kwargs):
    """
    Handle branch deletion - update restaurant statistics
    """
    instance.restaurant.update_statistics()
    logger.info(f"Branch {instance.name} deleted from restaurant {instance.restaurant.name}")


# ==================== TABLE SIGNALS ====================

@receiver(post_save, sender=Table)
def handle_table_save(sender, instance, created, **kwargs):
    """
    Handle table save - update branch capacity
    """
    if created or kwargs.get('update_fields') != {'capacity'}:
        instance.branch.update_capacity()
        logger.debug(f"Table {instance.table_number} created/updated in branch {instance.branch.name}")


@receiver(post_delete, sender=Table)
def handle_table_delete(sender, instance, **kwargs):
    """
    Handle table deletion - update branch capacity
    """
    instance.branch.update_capacity()
    logger.info(f"Table {instance.table_number} deleted from branch {instance.branch.name}")


# ==================== BOOKING SIGNALS ====================

@receiver(post_save, sender=Booking)
def handle_booking_save(sender, instance, created, **kwargs):
    """
    Handle booking save - update restaurant statistics and table status
    """
    if created:
        # Update restaurant booking count
        instance.restaurant.total_bookings += 1
        instance.restaurant.save(update_fields=['total_bookings'])
        
        logger.info(f"New booking {instance.booking_id} created by {instance.user.email}")
    
    # Create history entry if status changed
    if not created:
        try:
            old_instance = Booking.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                BookingHistory.objects.create(
                    booking=instance,
                    old_status=old_instance.status,
                    new_status=instance.status,
                    changed_at=timezone.now()
                )
                logger.info(f"Booking {instance.booking_id} status changed from "
                           f"{old_instance.status} to {instance.status}")
        except Booking.DoesNotExist:
            pass


@receiver(pre_delete, sender=Booking)
def handle_booking_delete(sender, instance, **kwargs):
    """
    Handle booking deletion - free up table
    """
    # Free up the table
    if instance.table.status == 'RESERVED':
        instance.table.status = 'AVAILABLE'
        instance.table.save()
    
    logger.info(f"Booking {instance.booking_id} deleted")


# ==================== PAYMENT SIGNALS ====================

@receiver(post_save, sender=Payment)
def handle_payment_save(sender, instance, created, **kwargs):
    """
    Handle payment save - update booking status on successful payment
    """
    if created:
        logger.info(f"New payment {instance.transaction_id} created for booking {instance.booking.booking_id}")
    
    # If payment becomes successful, ensure booking is confirmed
    if instance.payment_status == 'SUCCESS' and instance.booking.status != 'CONFIRMED':
        instance.booking.confirm_booking()
        logger.info(f"Booking {instance.booking.booking_id} confirmed via payment {instance.transaction_id}")
    
    # If payment is refunded, update booking status
    if instance.payment_status in ['REFUNDED', 'PARTIALLY_REFUNDED']:
        if instance.booking.status != 'CANCELLED' and instance.payment_status == 'REFUNDED':
            instance.booking.status = 'CANCELLED'
            instance.booking.save()
            logger.info(f"Booking {instance.booking.booking_id} cancelled due to refund")


# ==================== SCHEDULED TASKS ====================

def cleanup_expired_bookings():
    """
    Scheduled task to expire pending bookings
    This should be called by a cron job or Celery beat
    """
    expired_count = Booking.expire_pending_bookings()
    if expired_count > 0:
        logger.info(f"Auto-expired {expired_count} pending bookings")
    return expired_count


def cleanup_incomplete_payments():
    """
    Scheduled task to clean up incomplete payments
    """
    from payments.models import Payment
    
    # Expire payments older than 1 hour
    cutoff = timezone.now() - timezone.timedelta(hours=1)
    expired_payments = Payment.objects.filter(
        payment_status='PENDING',
        created_at__lt=cutoff
    )
    
    count = expired_payments.count()
    if count > 0:
        expired_payments.update(
            payment_status='FAILED',
            metadata={'auto_expired': True, 'expired_at': timezone.now().isoformat()}
        )
        logger.info(f"Auto-expired {count} incomplete payments")
    
    return count


def update_restaurant_statistics():
    """
    Scheduled task to update restaurant statistics
    """
    from django.db.models import Count, Sum
    
    restaurants = Restaurant.objects.all()
    for restaurant in restaurants:
        # Update average rating from reviews (if implemented)
        # For now, just update branch counts
        restaurant.total_branches = restaurant.branches.count()
        restaurant.save(update_fields=['total_branches'])
    
    logger.info(f"Updated statistics for {restaurants.count()} restaurants")
    return restaurants.count()