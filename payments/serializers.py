"""
Payments App Serializers
Handles serialization and validation for Payment, PaymentMethod, and Refund models
"""

from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

from .models import Payment, PaymentMethod, PaymentLog, Refund
from bookings.serializers import BookingListSerializer
from users.serializers import UserSerializer


class PaymentMethodSerializer(serializers.ModelSerializer):
    """
    Serializer for PaymentMethod model
    """
    method_type_display = serializers.CharField(source='get_method_type_display', read_only=True)
    
    class Meta:
        model = PaymentMethod
        fields = [
            'id', 'method_type', 'method_type_display', 'token',
            'last_four', 'card_brand', 'expiry_month', 'expiry_year',
            'cardholder_name', 'billing_address', 'is_default', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'token', 'created_at', 'updated_at']


class PaymentMethodCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating payment methods
    """
    class Meta:
        model = PaymentMethod
        fields = [
            'method_type', 'token', 'last_four', 'card_brand',
            'expiry_month', 'expiry_year', 'cardholder_name',
            'billing_address', 'is_default'
        ]
    
    def validate(self, data):
        """Validate payment method data"""
        # Validate card details if it's a card
        if data.get('method_type') == 'CARD':
            if not data.get('last_four'):
                raise serializers.ValidationError(
                    {'last_four': 'Last four digits are required for cards.'}
                )
            if not data.get('card_brand'):
                raise serializers.ValidationError(
                    {'card_brand': 'Card brand is required for cards.'}
                )
            
            # Validate expiry date
            if data.get('expiry_month') and data.get('expiry_year'):
                current_year = timezone.now().year
                current_month = timezone.now().month
                
                if data['expiry_year'] < current_year or \
                   (data['expiry_year'] == current_year and data['expiry_month'] < current_month):
                    raise serializers.ValidationError(
                        {'expiry': 'Card has expired.'}
                    )
        
        return data
    
    def create(self, validated_data):
        """Create payment method for current user"""
        user = self.context['request'].user
        return PaymentMethod.objects.create(user=user, **validated_data)


class PaymentLogSerializer(serializers.ModelSerializer):
    """
    Serializer for PaymentLog model
    """
    class Meta:
        model = PaymentLog
        fields = ['id', 'log_level', 'message', 'data', 'ip_address', 'user_agent', 'created_at']
        read_only_fields = fields


class RefundSerializer(serializers.ModelSerializer):
    """
    Serializer for Refund model
    """
    payment_transaction_id = serializers.CharField(source='payment.transaction_id', read_only=True)
    booking_id = serializers.CharField(source='payment.booking.booking_id', read_only=True)
    initiated_by_name = serializers.CharField(source='initiated_by.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Refund
        fields = [
            'id', 'refund_id', 'payment', 'payment_transaction_id', 'booking_id',
            'amount', 'currency', 'reason', 'status', 'status_display',
            'gateway_refund_id', 'gateway_response', 'initiated_by', 'initiated_by_name',
            'metadata', 'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'refund_id', 'gateway_response', 'created_at', 'updated_at', 'completed_at'
        ]


class RefundCreateSerializer(serializers.Serializer):
    """
    Serializer for creating refunds
    """
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate_amount(self, value):
        """Validate refund amount"""
        if value and value <= 0:
            raise serializers.ValidationError("Refund amount must be greater than 0.")
        return value


class PaymentSerializer(serializers.ModelSerializer):
    """
    Basic serializer for Payment list views
    """
    booking_id = serializers.CharField(source='booking.booking_id', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'transaction_id', 'booking', 'booking_id', 'user', 'user_email', 'user_name',
            'amount', 'currency', 'payment_method', 'payment_method_display',
            'payment_status', 'payment_status_display', 'receipt_url', 'receipt_number',
            'refund_amount', 'created_at', 'completed_at'
        ]
        read_only_fields = ['id', 'transaction_id', 'created_at', 'completed_at']


class PaymentDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for Payment detail views
    """
    booking = BookingListSerializer(read_only=True)
    user = UserSerializer(read_only=True)
    logs = PaymentLogSerializer(many=True, read_only=True)
    refunds = RefundSerializer(many=True, read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    remaining_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'transaction_id', 'booking', 'user', 'amount', 'currency',
            'payment_method', 'payment_method_display', 'payment_status', 'payment_status_display',
            'gateway', 'gateway_response', 'receipt_url', 'receipt_number',
            'refund_amount', 'refund_reason', 'refunded_at', 'remaining_amount',
            'logs', 'refunds', 'metadata', 'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'transaction_id', 'gateway_response', 'created_at', 'updated_at', 'completed_at'
        ]


class PaymentCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating payments
    """
    payment_method_id = serializers.UUIDField(required=False, write_only=True)
    
    class Meta:
        model = Payment
        fields = ['booking', 'payment_method', 'payment_method_id', 'metadata']
    
    def validate(self, data):
        """Validate payment creation data"""
        booking = data.get('booking')
        user = self.context['request'].user
        
        # Verify booking belongs to user
        if booking.user != user:
            raise serializers.ValidationError(
                {'booking': 'Booking does not belong to this user.'}
            )
        
        # Verify booking is in pending payment state
        if booking.status != 'PENDING_PAYMENT':
            raise serializers.ValidationError(
                {'booking': f'Booking is in {booking.status} state, not pending payment.'}
            )
        
        # Verify booking hasn't expired
        if booking.expires_at and booking.expires_at < timezone.now():
            raise serializers.ValidationError(
                {'booking': 'Booking has expired. Please create a new booking.'}
            )
        
        # If payment_method_id provided, verify it exists and belongs to user
        payment_method_id = data.get('payment_method_id')
        if payment_method_id:
            try:
                payment_method = PaymentMethod.objects.get(
                    id=payment_method_id,
                    user=user,
                    is_active=True
                )
                data['payment_method'] = payment_method.method_type
            except PaymentMethod.DoesNotExist:
                raise serializers.ValidationError(
                    {'payment_method_id': 'Payment method not found.'}
                )
        
        return data
    
    def create(self, validated_data):
        """Create payment with atomic transaction"""
        validated_data.pop('payment_method_id', None)
        validated_data['user'] = self.context['request'].user
        validated_data['amount'] = validated_data['booking'].total_price
        
        return super().create(validated_data)


class PaymentGatewaySerializer(serializers.Serializer):
    """
    Serializer for payment gateway operations
    """
    payment_id = serializers.UUIDField()
    action = serializers.ChoiceField(choices=['success', 'fail'], default='success')
    error = serializers.CharField(required=False, allow_blank=True)


class PaymentStatisticsSerializer(serializers.Serializer):
    """
    Serializer for payment statistics
    """
    total_payments = serializers.IntegerField()
    total_successful = serializers.IntegerField()
    total_failed = serializers.IntegerField()
    total_pending = serializers.IntegerField()
    total_refunded = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_refunded_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_payment = serializers.DecimalField(max_digits=10, decimal_places=2)
    by_payment_method = serializers.ListField(child=serializers.DictField())
    by_day = serializers.ListField(child=serializers.DictField())
    period = serializers.DictField()