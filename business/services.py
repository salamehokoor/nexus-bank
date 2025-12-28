"""
Incremental business metrics services.
Metrics are updated synchronously on core events (transactions, bill payments,
logins, and user creation) and never rely on background workers.
"""
from datetime import timedelta
from decimal import Decimal
from typing import Dict, Iterable

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from api.models import Transaction, BillPayment, User
from risk.models import LoginEvent
from .models import (
    CurrencyMetrics,
    DailyActiveUser,
    DailyBusinessMetrics,
    CountryUserMetrics,
)


def _metrics_defaults() -> Dict:
    return {
        "total_users": User.objects.count(),
        "avg_transaction_value": Decimal("0.00"),
    }


def _get_metrics_row(target_date):
    """Lock and return the metrics row for a date, creating with sane defaults."""
    metrics, created = DailyBusinessMetrics.objects.select_for_update(
    ).get_or_create(date=target_date, defaults=_metrics_defaults())
    return metrics, created


def _refresh_profit(metrics: DailyBusinessMetrics):
    metrics.net_revenue = (
        metrics.fee_revenue + metrics.bill_commission_revenue +
        metrics.fx_spread_revenue - metrics.total_refunded_amount -
        metrics.total_chargeback_amount)
    metrics.profit = metrics.net_revenue


def _get_country_row(target_date, country: str):
    row, created = CountryUserMetrics.objects.select_for_update().get_or_create(
        date=target_date,
        country=country or "Unknown",
        defaults={
            "count": User.objects.filter(country=country).count()
            if country else 0,
        },
    )
    return row, created


def _get_currency_row(target_date, currency: str):
    row, _ = CurrencyMetrics.objects.select_for_update().get_or_create(
        date=target_date, currency=currency or "UNKNOWN")
    return row


def record_transaction(transaction_obj: Transaction):
    """
    Incrementally update daily/country/currency metrics for a transaction.
    """
    target_date = timezone.localdate(getattr(transaction_obj, "created_at",
                                             None) or timezone.now())
    sender_account = transaction_obj.sender_account
    receiver_account = transaction_obj.receiver_account
    sender_country = getattr(getattr(sender_account, "user", None), "country",
                             "") if sender_account else ""
    sender_currency = getattr(sender_account, "currency", None)
    cross_currency = bool(sender_account and receiver_account
                          and sender_account.currency != receiver_account.currency)

    with transaction.atomic():
        metrics, _ = _get_metrics_row(target_date)

        if transaction_obj.status == Transaction.Status.SUCCESS:
            metrics.total_transactions_success += 1
            metrics.total_transferred_amount += transaction_obj.amount
            metrics.fee_revenue += transaction_obj.fee_amount
            if cross_currency:
                metrics.fx_volume += transaction_obj.amount
            # Use exact calculation (sum / count) instead of rolling average
            # to eliminate floating-point drift over many transactions
            metrics.avg_transaction_value = (
                metrics.total_transferred_amount / metrics.total_transactions_success
            ).quantize(Decimal("0.01"))
        elif transaction_obj.status == Transaction.Status.FAILED:
            metrics.total_transactions_failed += 1
        elif transaction_obj.status == Transaction.Status.REVERSED:
            metrics.total_transactions_refunded += 1
            metrics.total_refunded_amount += transaction_obj.amount

        _refresh_profit(metrics)
        metrics.save()

        if sender_country:
            country_row, _ = _get_country_row(target_date, sender_country)
            if transaction_obj.status == Transaction.Status.SUCCESS:
                country_row.tx_count += 1
                country_row.tx_amount += transaction_obj.amount
                country_row.net_revenue += transaction_obj.fee_amount
                country_row.save()

        if sender_currency:
            currency_row = _get_currency_row(target_date, sender_currency)
            if transaction_obj.status == Transaction.Status.SUCCESS:
                currency_row.tx_count += 1
                currency_row.tx_amount += transaction_obj.amount
                if cross_currency:
                    currency_row.fx_volume += transaction_obj.amount
                currency_row.fee_revenue += transaction_obj.fee_amount
                currency_row.save()


def record_bill_payment(bill_payment: BillPayment):
    """Incrementally update bill payment metrics when a bill is paid/failed."""
    if bill_payment.status not in {"PAID", "FAILED"}:
        return
    target_date = timezone.localdate(getattr(bill_payment, "created_at", None)
                                     or timezone.now())
    with transaction.atomic():
        metrics, _ = _get_metrics_row(target_date)
        if bill_payment.status == "PAID":
            metrics.bill_payments_count += 1
            metrics.bill_payments_amount += bill_payment.amount
        elif bill_payment.status == "FAILED":
            metrics.bill_payments_failed += 1
        _refresh_profit(metrics)
        metrics.save()


def record_user_signup(user: User):
    target_date = timezone.localdate(getattr(user, "date_joined", None)
                                     or timezone.now())
    with transaction.atomic():
        metrics, created = _get_metrics_row(target_date)
        metrics.new_users += 1
        if created:
            metrics.total_users = User.objects.count()
        else:
            metrics.total_users += 1
        _refresh_profit(metrics)
        metrics.save()

        if getattr(user, "country", ""):
            country_row, created_row = _get_country_row(target_date,
                                                        user.country)
            if not created_row:
                country_row.count += 1
                country_row.save()


def record_login_event(login_event: LoginEvent):
    target_date = timezone.localdate(getattr(login_event, "timestamp", None)
                                     or timezone.now())
    with transaction.atomic():
        metrics, _ = _get_metrics_row(target_date)

        if login_event.successful and login_event.user:
            _, created = DailyActiveUser.objects.select_for_update().get_or_create(
                date=target_date, user=login_event.user)
            if created:
                metrics.active_users += 1
                if getattr(login_event.user, "country", ""):
                    country_row, _ = _get_country_row(
                        target_date, login_event.user.country)
                    country_row.active_users += 1
                    country_row.save()
        else:
            metrics.failed_logins += 1

        metrics.active_users_7d = DailyActiveUser.objects.filter(
            date__gte=target_date - timedelta(days=6),
            date__lte=target_date).values("user").distinct().count()
        metrics.active_users_30d = DailyActiveUser.objects.filter(
            date__gte=target_date - timedelta(days=29),
            date__lte=target_date).values("user").distinct().count()
        _refresh_profit(metrics)
        metrics.save()


def summarize_range(start_date, end_date) -> Dict[str, Decimal]:
    """
    Aggregate DailyBusinessMetrics for a window (used by weekly/monthly views).
    """
    qs = DailyBusinessMetrics.objects.filter(date__gte=start_date,
                                             date__lte=end_date)
    aggregated = qs.aggregate(
        new_users=Sum("new_users"),
        active_users=Sum("active_users"),
        total_transactions_success=Sum("total_transactions_success"),
        total_transactions_failed=Sum("total_transactions_failed"),
        total_transactions_refunded=Sum("total_transactions_refunded"),
        total_transferred_amount=Sum("total_transferred_amount"),
        total_refunded_amount=Sum("total_refunded_amount"),
        bill_payments_amount=Sum("bill_payments_amount"),
        fee_revenue=Sum("fee_revenue"),
        bill_commission_revenue=Sum("bill_commission_revenue"),
        fx_spread_revenue=Sum("fx_spread_revenue"),
        net_revenue=Sum("net_revenue"),
        profit=Sum("profit"),
    )
    return {k: (v or Decimal("0.00")) for k, v in aggregated.items()}


def build_weekly_summaries(week_starts: Iterable):
    for start in sorted(week_starts, reverse=True):
        end = start + timedelta(days=6)
        yield {"week_start": start, "week_end": end, **summarize_range(start, end)}


def build_monthly_summaries(month_starts: Iterable):
    for start in sorted(month_starts, reverse=True):
        next_month = (start + timedelta(days=32)).replace(day=1)
        end = next_month - timedelta(days=1)
        yield {"month": start, **summarize_range(start, end)}
