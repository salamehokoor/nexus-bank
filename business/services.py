"""
Business metrics computation services.
Aggregate transaction, bill payment, login, and incident data into reporting tables.
All functions are idempotent and safe to run concurrently.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Tuple

from django.core.exceptions import FieldDoesNotExist
from django.db import transaction
from django.db.models import F, Sum, Avg, Count, Q
from django.utils import timezone

from api.models import Transaction, BillPayment, User
from risk.models import Incident, LoginEvent
from .models import (
    ActiveUserWindow,
    CurrencyMetrics,
    DailyBusinessMetrics,
    CountryUserMetrics,
    WeeklySummary,
    MonthlySummary,
)

SUCCESS_STATUSES = {"success", "succeeded", "completed", "settled"}
FAILED_STATUSES = {"failed", "cancelled", "rejected"}
REFUND_STATUSES = {"refunded", "reversed", "chargeback"}


def _has_field(model, field_name: str) -> bool:
    """Return True if the model defines the given field."""
    try:
        model._meta.get_field(field_name)
        return True
    except FieldDoesNotExist:
        return False


def _date_bounds(target_date) -> Tuple[datetime, datetime]:
    """Return [start, end) datetimes for a given date in default timezone."""
    tz = timezone.get_default_timezone()
    start = timezone.make_aware(
        datetime.combine(target_date, datetime.min.time()), tz)
    end = start + timedelta(days=1)
    return start, end


def _week_bounds(week_start) -> Tuple[datetime, datetime]:
    """Return [start, end) datetimes for a Monday-start week."""
    tz = timezone.get_default_timezone()
    start = timezone.make_aware(
        datetime.combine(week_start, datetime.min.time()), tz)
    end = start + timedelta(days=7)
    return start, end


def _month_bounds(month_start) -> Tuple[datetime, datetime]:
    """Return [start, end) datetimes for a first-of-month date."""
    tz = timezone.get_default_timezone()
    start = timezone.make_aware(
        datetime.combine(month_start, datetime.min.time()), tz)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    end = timezone.make_aware(
        datetime.combine(next_month, datetime.min.time()), tz)
    return start, end


def _filter_success_tx(qs):
    """Filter successful transactions if status exists; otherwise return qs."""
    if _has_field(Transaction, "status"):
        return qs.filter(status__in=SUCCESS_STATUSES)
    return qs


def _filter_failed_tx(qs):
    """Filter failed transactions if status exists; otherwise return empty qs."""
    if _has_field(Transaction, "status"):
        return qs.filter(status__in=FAILED_STATUSES)
    return qs.none()


def _filter_refund_tx(qs):
    """Filter refund/chargeback transactions based on available fields."""
    if _has_field(Transaction, "status"):
        return qs.filter(status__in=REFUND_STATUSES)
    if _has_field(Transaction, "is_refund"):
        return qs.filter(is_refund=True)
    return qs.none()


def _sum_field(qs, field_name: str) -> Decimal:
    """Sum a field if present; otherwise return zero."""
    if not _has_field(qs.model, field_name):
        return Decimal("0.00")
    return qs.aggregate(total=Sum(field_name))["total"] or Decimal("0.00")


def _count_distinct_users_login(start_dt, end_dt, success_only: bool = True) -> int:
    """Count distinct users in LoginEvent within window, optionally success only."""
    qs = LoginEvent.objects.filter(timestamp__gte=start_dt,
                                   timestamp__lt=end_dt)
    if _has_field(LoginEvent, "successful"):
        qs = qs.filter(successful=success_only)
    return qs.values("user").distinct().count()


def _currency_field():
    """Pick currency source field from Transaction or related accounts."""
    if _has_field(Transaction, "currency"):
        return "currency"
    if _has_field(Transaction, "sender_account__currency"):
        return "sender_account__currency"
    return None


def compute_daily_business_metrics(target_date=None):
    """
    Idempotent, concurrency-safe daily metrics recomputation for a specific date.
    Uses [start, end) datetime bounds and filters only successful records.
    """
    target_date = target_date or timezone.localdate()
    start_dt, end_dt = _date_bounds(target_date)

    tx_qs_base = Transaction.objects.filter(created_at__gte=start_dt,
                                            created_at__lt=end_dt)
    tx_success = _filter_success_tx(tx_qs_base)
    tx_failed = _filter_failed_tx(tx_qs_base)
    tx_refund = _filter_refund_tx(tx_qs_base)

    bill_qs_base = BillPayment.objects.filter(created_at__gte=start_dt,
                                              created_at__lt=end_dt)
    bill_success = _filter_success_tx(bill_qs_base)
    bill_failed = _filter_failed_tx(bill_qs_base)

    country_rows = _compute_country_rows(target_date, start_dt, end_dt)
    currency_rows = _compute_currency_rows(target_date, start_dt, end_dt,
                                           tx_success)

    fee_revenue = _sum_field(tx_success, "fee_amount") + _sum_field(
        tx_success, "fee")
    bill_commission_revenue = _sum_field(bill_success,
                                         "commission_amount") + _sum_field(
                                             bill_success, "commission")
    fx_spread_revenue = _sum_field(tx_success, "fx_spread_amount")

    total_refunded_amount = _sum_field(tx_refund, "amount")
    total_chargeback_amount = _sum_field(tx_refund, "chargeback_amount")
    net_revenue = (
        fee_revenue + bill_commission_revenue + fx_spread_revenue -
        total_refunded_amount - total_chargeback_amount)

    with transaction.atomic():
        metrics, _ = DailyBusinessMetrics.objects.select_for_update(
        ).get_or_create(date=target_date)

        metrics.new_users = User.objects.filter(
            date_joined__gte=start_dt, date_joined__lt=end_dt).count()
        metrics.total_users = User.objects.filter(
            date_joined__lte=end_dt).count()
        metrics.active_users = _count_distinct_users_login(start_dt, end_dt)
        metrics.active_users_7d = _count_distinct_users_login(
            start_dt - timedelta(days=6), end_dt)
        metrics.active_users_30d = _count_distinct_users_login(
            start_dt - timedelta(days=29), end_dt)

        metrics.total_transactions_success = tx_success.count()
        metrics.total_transactions_failed = tx_failed.count()
        metrics.total_transactions_refunded = tx_refund.count()
        metrics.total_transferred_amount = _sum_field(tx_success, "amount")
        metrics.total_refunded_amount = total_refunded_amount
        metrics.total_chargeback_amount = total_chargeback_amount
        metrics.avg_transaction_value = (
            tx_success.aggregate(avg=Avg("amount"))["avg"]
            or Decimal("0.00"))
        metrics.fx_volume = _cross_currency_volume(tx_success)

        metrics.bill_payments_count = bill_success.count()
        metrics.bill_payments_failed = bill_failed.count()
        metrics.bill_payments_amount = _sum_field(bill_success, "amount")

        metrics.fee_revenue = fee_revenue
        metrics.bill_commission_revenue = bill_commission_revenue
        metrics.fx_spread_revenue = fx_spread_revenue
        metrics.net_revenue = net_revenue
        metrics.profit = net_revenue

        metrics.failed_logins = LoginEvent.objects.filter(
            timestamp__gte=start_dt, timestamp__lt=end_dt,
            successful=False).count() if _has_field(LoginEvent,
                                                    "successful") else 0
        metrics.incidents = Incident.objects.filter(
            timestamp__gte=start_dt, timestamp__lt=end_dt).count()

        metrics.save()

    _upsert_country_metrics(target_date, country_rows)
    _upsert_currency_metrics(target_date, currency_rows)
    _update_active_windows(target_date, metrics.active_users,
                           metrics.active_users_7d, metrics.active_users_30d)


def compute_weekly_summary(week_start=None):
    """
    Recompute weekly summary for a given Monday (week_start).
    Idempotent and concurrency-safe. Uses [start, end) bounds.
    """
    today = timezone.localdate()
    week_start = week_start or (today - timedelta(days=today.weekday()))
    start_dt, end_dt = _week_bounds(week_start)

    tx_base = Transaction.objects.filter(created_at__gte=start_dt,
                                         created_at__lt=end_dt)
    tx_success = _filter_success_tx(tx_base)
    tx_failed = _filter_failed_tx(tx_base)
    tx_refund = _filter_refund_tx(tx_base)

    bill_base = BillPayment.objects.filter(created_at__gte=start_dt,
                                           created_at__lt=end_dt)
    bill_success = _filter_success_tx(bill_base)

    fee_revenue = _sum_field(tx_success, "fee_amount") + _sum_field(
        tx_success, "fee")
    bill_commission_revenue = _sum_field(bill_success,
                                         "commission_amount") + _sum_field(
                                             bill_success, "commission")
    fx_spread_revenue = _sum_field(tx_success, "fx_spread_amount")

    total_refunded_amount = _sum_field(tx_refund, "amount")
    total_chargeback_amount = _sum_field(tx_refund, "chargeback_amount")
    net_revenue = (
        fee_revenue + bill_commission_revenue + fx_spread_revenue -
        total_refunded_amount - total_chargeback_amount)

    with transaction.atomic():
        summary, _ = WeeklySummary.objects.select_for_update().get_or_create(
            week_start=week_start,
            defaults={"week_end": week_start + timedelta(days=6)},
        )
        summary.week_end = week_start + timedelta(days=6)

        summary.new_users = User.objects.filter(
            date_joined__gte=start_dt, date_joined__lt=end_dt).count()
        summary.active_users = _count_distinct_users_login(start_dt, end_dt)
        summary.total_transactions_success = tx_success.count()
        summary.total_transactions_failed = tx_failed.count()
        summary.total_transactions_refunded = tx_refund.count()
        summary.total_transferred_amount = _sum_field(tx_success, "amount")
        summary.total_refunded_amount = total_refunded_amount
        summary.bill_payments_amount = _sum_field(bill_success, "amount")
        summary.fee_revenue = fee_revenue
        summary.bill_commission_revenue = bill_commission_revenue
        summary.fx_spread_revenue = fx_spread_revenue
        summary.net_revenue = net_revenue
        summary.profit = net_revenue
        summary.save()


def compute_monthly_summary(month_start=None):
    """
    Recompute monthly summary for a given first-of-month date.
    Idempotent and concurrency-safe. Uses [start, end) bounds.
    """
    today = timezone.localdate()
    month_start = month_start or today.replace(day=1)
    start_dt, end_dt = _month_bounds(month_start)

    tx_base = Transaction.objects.filter(created_at__gte=start_dt,
                                         created_at__lt=end_dt)
    tx_success = _filter_success_tx(tx_base)
    tx_failed = _filter_failed_tx(tx_base)
    tx_refund = _filter_refund_tx(tx_base)

    bill_base = BillPayment.objects.filter(created_at__gte=start_dt,
                                           created_at__lt=end_dt)
    bill_success = _filter_success_tx(bill_base)

    fee_revenue = _sum_field(tx_success, "fee_amount") + _sum_field(
        tx_success, "fee")
    bill_commission_revenue = _sum_field(bill_success,
                                         "commission_amount") + _sum_field(
                                             bill_success, "commission")
    fx_spread_revenue = _sum_field(tx_success, "fx_spread_amount")

    total_refunded_amount = _sum_field(tx_refund, "amount")
    total_chargeback_amount = _sum_field(tx_refund, "chargeback_amount")
    net_revenue = (
        fee_revenue + bill_commission_revenue + fx_spread_revenue -
        total_refunded_amount - total_chargeback_amount)

    with transaction.atomic():
        summary, _ = MonthlySummary.objects.select_for_update().get_or_create(
            month=month_start)
        summary.new_users = User.objects.filter(
            date_joined__gte=start_dt, date_joined__lt=end_dt).count()
        summary.active_users = _count_distinct_users_login(start_dt, end_dt)
        summary.total_transactions_success = tx_success.count()
        summary.total_transactions_failed = tx_failed.count()
        summary.total_transactions_refunded = tx_refund.count()
        summary.total_transferred_amount = _sum_field(tx_success, "amount")
        summary.total_refunded_amount = total_refunded_amount
        summary.bill_payments_amount = _sum_field(bill_success, "amount")
        summary.fee_revenue = fee_revenue
        summary.bill_commission_revenue = bill_commission_revenue
        summary.fx_spread_revenue = fx_spread_revenue
        summary.net_revenue = net_revenue
        summary.profit = net_revenue
        summary.save()


def compute_country_snapshot(target_date=None):
    target_date = target_date or timezone.localdate()
    start_dt, end_dt = _date_bounds(target_date)

    rows = _compute_country_rows(target_date, start_dt, end_dt)
    _upsert_country_metrics(target_date, rows)


def _compute_country_rows(target_date, start_dt, end_dt):
    """Build country-level aggregates for the target date."""
    country_field = "country" if _has_field(User, "country") else None
    if not country_field:
        return [("Unknown", 0, 0, 0, Decimal("0.00"), Decimal("0.00"))]

    tx_base = _filter_success_tx(
        Transaction.objects.filter(created_at__gte=start_dt,
                                   created_at__lt=end_dt))
    rows = []
    for row in User.objects.filter(
            date_joined__lte=end_dt).values(country_field).annotate(
                total=Count("id")):
        country = row[country_field] or "Unknown"
        active = LoginEvent.objects.filter(
            timestamp__gte=start_dt,
            timestamp__lt=end_dt,
            successful=True,
            user__country=country if country_field == "country" else None,
        ).values("user").distinct().count() if country_field else 0
        tx_filterable = country_field and _has_field(Transaction, "user")
        tx_qs_for_country = (tx_base.filter(
            **{f"user__{country_field}": country}) if tx_filterable else
                             tx_base.none())
        tx_count = tx_qs_for_country.count() if tx_filterable else 0
        tx_amount = _sum_field(tx_qs_for_country, "amount")
        net_revenue = _sum_field(tx_qs_for_country, "fee_amount")
        rows.append(
            (country, row["total"], active, tx_count, tx_amount, net_revenue))
    if not rows:
        rows.append(("Unknown", 0, 0, 0, Decimal("0.00"), Decimal("0.00")))
    return rows


def _compute_currency_rows(target_date, start_dt, end_dt, tx_success):
    """Build currency-level aggregates for the target date."""
    currency_field = _currency_field()
    if not currency_field:
        return []
    return list(
        tx_success.values(currency_field).annotate(
            tx_count=Count("id"),
            tx_amount=Sum("amount"),
            fx_volume=Sum(
                "amount",
                filter=~Q(sender_account__currency=F("receiver_account__currency"))
                if _has_field(Transaction, "receiver_account") else None),
            fee_revenue=Sum("fee_amount") if _has_field(
                Transaction, "fee_amount") else Sum("fee") if _has_field(
                    Transaction, "fee") else None,
            fx_spread_revenue=Sum("fx_spread_amount")
            if _has_field(Transaction, "fx_spread_amount") else None,
        ))


def _cross_currency_volume(qs) -> Decimal:
    """Sum volume for cross-currency transfers."""
    if not _has_field(Transaction, "receiver_account"):
        return Decimal("0.00")
    value = qs.exclude(sender_account__currency=F(
        "receiver_account__currency")).aggregate(total=Sum("amount"))["total"]
    return value or Decimal("0.00")


def _upsert_country_metrics(target_date, rows):
    """Replace country metrics for a date with the provided rows."""
    with transaction.atomic():
        CountryUserMetrics.objects.filter(date=target_date).delete()
        for country, count, active, tx_count, tx_amount, net_revenue in rows:
            CountryUserMetrics.objects.create(
                date=target_date,
                country=country or "Unknown",
                count=count,
                active_users=active,
                tx_count=tx_count,
                tx_amount=tx_amount or Decimal("0.00"),
                net_revenue=net_revenue or Decimal("0.00"),
            )


def _upsert_currency_metrics(target_date, rows):
    """Replace currency metrics for a date with the provided rows."""
    if not rows:
        return
    with transaction.atomic():
        CurrencyMetrics.objects.filter(date=target_date).delete()
        for row in rows:
            currency = row.get(_currency_field()) or "UNKNOWN"
            CurrencyMetrics.objects.create(
                date=target_date,
                currency=currency,
                tx_count=row.get("tx_count") or 0,
                tx_amount=row.get("tx_amount") or Decimal("0.00"),
                fx_volume=row.get("fx_volume") or Decimal("0.00"),
                fee_revenue=row.get("fee_revenue") or Decimal("0.00"),
                fx_spread_revenue=row.get("fx_spread_revenue")
                or Decimal("0.00"),
            )


def _update_active_windows(target_date, dau, wau, mau):
    """Upsert active-user windows (DAU/WAU/MAU) for the date."""
    with transaction.atomic():
        ActiveUserWindow.objects.update_or_create(
            date=target_date, window="dau", defaults={"active_users": dau})
        ActiveUserWindow.objects.update_or_create(
            date=target_date, window="wau", defaults={"active_users": wau})
        ActiveUserWindow.objects.update_or_create(
            date=target_date, window="mau", defaults={"active_users": mau})


def backfill_metrics(start_date, end_date):
    """
    Recompute daily, weekly, and monthly metrics for an inclusive date range.
    """
    if start_date > end_date:
        raise ValueError("start_date must be before end_date")

    current = start_date
    seen_weeks = set()
    seen_months = set()
    while current <= end_date:
        compute_daily_business_metrics(current)

        week_start = current - timedelta(days=current.weekday())
        month_start = current.replace(day=1)
        seen_weeks.add(week_start)
        seen_months.add(month_start)

        current += timedelta(days=1)

    for week in sorted(seen_weeks):
        compute_weekly_summary(week)

    for month in sorted(seen_months):
        compute_monthly_summary(month)
