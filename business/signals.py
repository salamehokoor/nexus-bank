"""
Signals to update metrics synchronously on core events (no background jobs).
"""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from api.models import Transaction, BillPayment
from risk.models import LoginEvent
from .services import (record_bill_payment, record_login_event,
                       record_transaction, record_user_signup)

User = get_user_model()


@receiver(post_save, sender=Transaction)
def update_metrics_on_transaction(sender, instance, created, **kwargs):
    if not created:
        return
    transaction.on_commit(lambda: record_transaction(instance))


@receiver(pre_save, sender=BillPayment)
def _track_previous_bill_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return
    try:
        existing = sender.objects.get(pk=instance.pk)
        instance._previous_status = existing.status
    except sender.DoesNotExist:
        instance._previous_status = None


@receiver(post_save, sender=BillPayment)
def update_metrics_on_bill_payment(sender, instance, created, **kwargs):
    status_changed = getattr(instance, "_previous_status",
                             None) != instance.status
    if created or status_changed:
        transaction.on_commit(lambda: record_bill_payment(instance))


@receiver(post_save, sender=User)
def update_metrics_on_new_user(sender, instance, created, **kwargs):
    if created:
        transaction.on_commit(lambda: record_user_signup(instance))


@receiver(post_save, sender=LoginEvent)
def update_metrics_on_login(sender, instance, created, **kwargs):
    if created:
        transaction.on_commit(lambda: record_login_event(instance))
