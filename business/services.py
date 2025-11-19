from django.utils.timezone import now
from django.db import transaction
from django.db.models import Count, Sum, Avg, F

from api.models import Transaction, BillPayment, Account, User
from risk.models import Incident, LoginEvent
from .models import DailyBusinessMetrics, CountryUserMetrics

# =====================================================
#  DAILY BUSINESS METRICS (Main KPI Aggregation)
# =====================================================


def compute_daily_business_metrics():
    """Compute daily KPIs and store them in DailyBusinessMetrics."""

    today = now().date()

    with transaction.atomic():
        metrics, created = DailyBusinessMetrics.objects.get_or_create(
            date=today)

        # =====================================================
        # USERS
        # =====================================================

        # New users today (use date_joined, not created_at)
        metrics.new_users = User.objects.filter(
            date_joined__date=today).count()

        metrics.total_users = User.objects.count()

        # Real active users: users who logged in successfully today
        metrics.active_users = LoginEvent.objects.filter(
            successful=True,
            timestamp__date=today).values('user').distinct().count()

        # =====================================================
        # TRANSACTIONS
        # =====================================================

        tx_qs = Transaction.objects.filter(created_at__date=today)

        metrics.total_transactions = tx_qs.count()

        metrics.total_transferred_amount = (
            tx_qs.aggregate(total=Sum("amount"))["total"] or 0)

        metrics.avg_transaction_value = (
            tx_qs.aggregate(avg=Avg("amount"))["avg"] or 0)

        # FX volume = amount where sender and receiver currency differ
        metrics.fx_volume = (tx_qs.exclude(sender_account__currency=F(
            "receiver_account__currency")).aggregate(
                total=Sum("amount"))["total"] or 0)

        # =====================================================
        # BILL PAYMENTS
        # =====================================================

        bp_qs = BillPayment.objects.filter(created_at__date=today)

        metrics.bill_payments_count = bp_qs.count()

        metrics.bill_payments_amount = (
            bp_qs.aggregate(total=Sum("amount"))["total"] or 0)

        # =====================================================
        # PROFIT (placeholder logic)
        # =====================================================

        # Simple version: incoming transfer volume
        # Later: You can replace this with real fee/profit model
        metrics.profit = metrics.total_transferred_amount

        # =====================================================
        # SECURITY
        # =====================================================

        metrics.failed_logins = LoginEvent.objects.filter(
            successful=False, timestamp__date=today).count()

        metrics.incidents = Incident.objects.filter(
            timestamp__date=today).count()

        metrics.save()


# =====================================================
#  USER COUNTRY SNAPSHOT (TEMPORARY DEFAULT)
# =====================================================


def compute_country_snapshot():
    """
    Store user distribution by country.
    TEMP: all users = Jordan until profile.country exists.
    """

    today = now().date()

    # Clear old for today
    CountryUserMetrics.objects.filter(date=today).delete()

    total_users = User.objects.count()

    # Default assumption: All users from Jordan for now
    CountryUserMetrics.objects.create(date=today,
                                      country="Jordan",
                                      count=total_users)
