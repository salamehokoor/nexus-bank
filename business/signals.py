# business/signals.py
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from api.models import Transaction, BillPayment
from .tasks import task_daily_metrics

User = get_user_model()


def _debounced_schedule(date_key: str, call):
    """
    Prevent task storms by allowing one enqueue per key per minute.
    """
    cache_key = f"business:debounce:{date_key}"
    if cache.add(cache_key, "1", timeout=60):
        transaction.on_commit(call)


@receiver(post_save, sender=Transaction)
def update_metrics_on_transaction(sender, instance, created, **kwargs):
    if not created:
        return
    target_date = getattr(instance, "created_at", None)
    target_date = timezone.localdate(target_date) if target_date else timezone.localdate()
    _debounced_schedule(
        f"tx:{target_date.isoformat()}",
        lambda: task_daily_metrics.delay(date=target_date.isoformat()),
    )


@receiver(post_save, sender=BillPayment)
def update_metrics_on_bill_payment(sender, instance, created, **kwargs):
    if not created:
        return
    target_date = getattr(instance, "created_at", None)
    target_date = timezone.localdate(target_date) if target_date else timezone.localdate()
    _debounced_schedule(
        f"bp:{target_date.isoformat()}",
        lambda: task_daily_metrics.delay(date=target_date.isoformat()),
    )


@receiver(post_save, sender=User)
def update_metrics_on_new_user(sender, instance, created, **kwargs):
    if not created:
        return
    target_date = getattr(instance, "date_joined", None)
    target_date = timezone.localdate(target_date) if target_date else timezone.localdate()
    _debounced_schedule(
        f"user:{target_date.isoformat()}",
        lambda: task_daily_metrics.delay(date=target_date.isoformat()),
    )
