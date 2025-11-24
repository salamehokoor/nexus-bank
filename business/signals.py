# business/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from api.models import Transaction, BillPayment
from risk.models import LoginEvent
from .tasks import task_daily_metrics

User = get_user_model()


@receiver(post_save, sender=Transaction)
def update_metrics_on_transaction(sender, instance, created, **kwargs):
    """
    When a new Transaction is created → recompute today's metrics.
    """
    if created:
        task_daily_metrics.delay()


@receiver(post_save, sender=BillPayment)
def update_metrics_on_bill_payment(sender, instance, created, **kwargs):
    """
    When a new BillPayment is created → recompute today's metrics.
    """
    if created:
        task_daily_metrics.delay()


@receiver(post_save, sender=User)
def update_metrics_on_new_user(sender, instance, created, **kwargs):
    """
    When a new User is created → recompute today's metrics.
    """
    if created:
        task_daily_metrics.delay()


@receiver(post_save, sender=LoginEvent)
def update_metrics_on_login(sender, instance, created, **kwargs):
    """
    When a new LoginEvent is logged → recompute today's metrics.
    """
    if created:
        task_daily_metrics.delay()
