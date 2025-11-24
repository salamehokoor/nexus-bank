from datetime import timedelta

from django.db import transaction
from django.db.models import Sum, Avg, F
from django.utils.timezone import now

from api.models import Transaction, BillPayment, User
from risk.models import Incident, LoginEvent
from .models import (
    DailyBusinessMetrics,
    CountryUserMetrics,
    WeeklySummary,
    MonthlySummary,
)

# =====================================================
# DAILY SUMMARY
# =====================================================


def compute_daily_business_metrics():
    today = now().date()

    with transaction.atomic():
        metrics, _ = DailyBusinessMetrics.objects.get_or_create(date=today)

        # --- Users ---
        metrics.new_users = User.objects.filter(
            date_joined__date=today).count()
        metrics.total_users = User.objects.count()
        metrics.active_users = (LoginEvent.objects.filter(
            successful=True,
            timestamp__date=today,
        ).values("user").distinct().count())

        # --- Transactions ---
        tx = Transaction.objects.filter(created_at__date=today)
        metrics.total_transactions = tx.count()
        metrics.total_transferred_amount = (
            tx.aggregate(total=Sum("amount"))["total"] or 0)
        metrics.avg_transaction_value = (tx.aggregate(avg=Avg("amount"))["avg"]
                                         or 0)
        metrics.fx_volume = (tx.exclude(sender_account__currency=F(
            "receiver_account__currency")).aggregate(
                total=Sum("amount"))["total"] or 0)

        # --- Bill payments ---
        bp = BillPayment.objects.filter(created_at__date=today)
        metrics.bill_payments_count = bp.count()
        metrics.bill_payments_amount = (
            bp.aggregate(total=Sum("amount"))["total"] or 0)

        # --- Profit placeholder (modify later with real fees model) ---
        metrics.profit = metrics.total_transferred_amount

        # --- Security ---
        metrics.failed_logins = LoginEvent.objects.filter(
            successful=False,
            timestamp__date=today,
        ).count()
        metrics.incidents = Incident.objects.filter(
            timestamp__date=today).count()

        metrics.save()


# =====================================================
# WEEKLY SUMMARY
# =====================================================


def compute_weekly_summary():
    today = now().date()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_end = week_start + timedelta(days=6)

    with transaction.atomic():
        summary, _ = WeeklySummary.objects.get_or_create(
            week_start=week_start,
            defaults={"week_end": week_end},
        )

        # if existing row, keep week_end aligned
        summary.week_end = week_end

        users = User.objects.filter(
            date_joined__date__range=[week_start, week_end])
        tx = Transaction.objects.filter(
            created_at__date__range=[week_start, week_end])
        bp = BillPayment.objects.filter(
            created_at__date__range=[week_start, week_end])

        summary.new_users = users.count()
        summary.total_transactions = tx.count()
        summary.total_transferred_amount = (
            tx.aggregate(total=Sum("amount"))["total"] or 0)
        summary.bill_payments_amount = (
            bp.aggregate(total=Sum("amount"))["total"] or 0)
        summary.profit = summary.total_transferred_amount

        summary.save()


# =====================================================
# MONTHLY SUMMARY
# =====================================================


def compute_monthly_summary():
    today = now().date()
    month_start = today.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    month_end = next_month - timedelta(days=1)

    with transaction.atomic():
        summary, _ = MonthlySummary.objects.get_or_create(month=month_start, )

        users = User.objects.filter(
            date_joined__date__range=[month_start, month_end])
        tx = Transaction.objects.filter(
            created_at__date__range=[month_start, month_end])
        bp = BillPayment.objects.filter(
            created_at__date__range=[month_start, month_end])

        summary.new_users = users.count()
        summary.total_transactions = tx.count()
        summary.total_transferred_amount = (
            tx.aggregate(total=Sum("amount"))["total"] or 0)
        summary.bill_payments_amount = (
            bp.aggregate(total=Sum("amount"))["total"] or 0)
        summary.profit = summary.total_transferred_amount

        summary.save()


# =====================================================
# COUNTRY SNAPSHOT
# =====================================================


def compute_country_snapshot():
    """
    TEMP: all users are assumed to be from Jordan until you add
    a real country field to the profile model.
    """
    today = now().date()

    CountryUserMetrics.objects.filter(date=today).delete()

    CountryUserMetrics.objects.create(
        date=today,
        country="Jordan",
        count=User.objects.count(),
    )
