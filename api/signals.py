"""
Django signals for real-time transaction notifications.
Sends WebSocket notifications AND creates Notification DB records.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import Notification, Transaction


@receiver(post_save, sender=Transaction)
def notify_transaction_participants(sender, instance, created, **kwargs):
    """
    Send real-time notifications to sender and receiver when a successful
    transaction is created.
    
    Actions:
    1. Create Notification DB records for both sender and receiver
    2. Send WebSocket DEBIT notification to sender
    3. Send WebSocket CREDIT notification to receiver
    """
    if not created:
        return
    
    # Only notify for successful transactions
    if instance.status != Transaction.Status.SUCCESS:
        return
    
    timestamp = timezone.now().isoformat()
    
    # Get user IDs
    sender_user_id = instance.sender_account.user_id
    receiver_user_id = instance.receiver_account.user_id
    
    # Build messages
    debit_message_text = f"Sent {instance.amount} {instance.sender_account.currency} to {instance.receiver_account.account_number}"
    credit_message_text = f"Received {instance.amount} {instance.sender_account.currency} from {instance.sender_account.account_number}"
    
    # ---------------------------------------------------------
    # 1. Create Notification DB records
    # ---------------------------------------------------------
    Notification.objects.create(
        user_id=sender_user_id,
        message=debit_message_text,
        notification_type=Notification.NotificationType.TRANSACTION,
        related_transaction=instance,
    )
    
    Notification.objects.create(
        user_id=receiver_user_id,
        message=credit_message_text,
        notification_type=Notification.NotificationType.TRANSACTION,
        related_transaction=instance,
    )
    
    # ---------------------------------------------------------
    # 2. Send WebSocket notifications
    # ---------------------------------------------------------
    channel_layer = get_channel_layer()
    if channel_layer is None:
        # Channel layer not configured (e.g., in tests without channels)
        return
    
    # Notify sender (DEBIT)
    sender_group = f"user_{sender_user_id}"
    debit_message = {
        "type": "user_notification",
        "event": "DEBIT",
        "amount": str(instance.amount),
        "currency": instance.sender_account.currency,
        "account": instance.sender_account.account_number,
        "timestamp": timestamp,
        "message": debit_message_text,
    }
    async_to_sync(channel_layer.group_send)(sender_group, debit_message)
    
    # Notify receiver (CREDIT)
    receiver_group = f"user_{receiver_user_id}"
    credit_message = {
        "type": "user_notification",
        "event": "CREDIT",
        "amount": str(instance.amount),
        "currency": instance.receiver_account.currency,
        "account": instance.receiver_account.account_number,
        "timestamp": timestamp,
        "message": credit_message_text,
    }
    async_to_sync(channel_layer.group_send)(receiver_group, credit_message)
