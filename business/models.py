"""
Reporting models for business KPIs (daily/weekly/monthly, country, currency).
Snapshots are populated by business.services via Celery tasks or signals.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class TimeStampedModel(models.Model):
    """Abstract base with created/updated timestamps."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class DailyBusinessMetrics(TimeStampedModel):
    """Daily aggregates of user activity, transactions, and revenue."""
    date = models.DateField(unique=True)

    # User metrics
    new_users = models.IntegerField(default=0)
    total_users = models.IntegerField(default=0)
    active_users = models.IntegerField(default=0)  # DAU
    active_users_7d = models.IntegerField(default=0)  # WAU
    active_users_30d = models.IntegerField(default=0)  # MAU

    # Transaction metrics
    total_transactions_success = models.IntegerField(default=0)
    total_transactions_failed = models.IntegerField(default=0)
    total_transactions_refunded = models.IntegerField(default=0)
    total_transferred_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_refunded_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_chargeback_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    avg_transaction_value = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    fx_volume = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    # Bill payments
    bill_payments_count = models.IntegerField(default=0)
    bill_payments_failed = models.IntegerField(default=0)
    bill_payments_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    # Revenue / profit
    fee_revenue = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    bill_commission_revenue = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    fx_spread_revenue = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    net_revenue = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    profit = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    # Security / risk
    failed_logins = models.IntegerField(default=0)
    incidents = models.IntegerField(default=0)

    class Meta:
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["-date"]),
        ]

    def __str__(self) -> str:
        return f"Metrics for {self.date}"


class CountryUserMetrics(TimeStampedModel):
    """Per-country breakdown of users, activity, transactions, and revenue."""
    date = models.DateField()
    country = models.CharField(max_length=50)
    count = models.IntegerField(default=0)
    active_users = models.IntegerField(default=0)
    tx_count = models.IntegerField(default=0)
    tx_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    net_revenue = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    class Meta:
        unique_together = ("date", "country")
        ordering = ["-date", "country"]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["country"]),
            models.Index(fields=["date", "country"]),
        ]

    def __str__(self) -> str:
        return f"{self.country}: {self.count} on {self.date}"


class CurrencyMetrics(TimeStampedModel):
    """Per-currency aggregation of counts, volume, and revenue."""
    date = models.DateField()
    currency = models.CharField(max_length=16)
    tx_count = models.IntegerField(default=0)
    tx_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    fx_volume = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    fee_revenue = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    fx_spread_revenue = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    class Meta:
        unique_together = ("date", "currency")
        ordering = ["-date", "currency"]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["currency"]),
            models.Index(fields=["date", "currency"]),
        ]

    def __str__(self) -> str:
        return f"{self.currency} on {self.date}"


class WeeklySummary(TimeStampedModel):
    """Weekly aggregates of core metrics (Monday-start week)."""
    week_start = models.DateField(unique=True)
    week_end = models.DateField()

    new_users = models.IntegerField(default=0)
    active_users = models.IntegerField(default=0)
    total_transactions_success = models.IntegerField(default=0)
    total_transactions_failed = models.IntegerField(default=0)
    total_transactions_refunded = models.IntegerField(default=0)
    total_transferred_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_refunded_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    bill_payments_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    fee_revenue = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    bill_commission_revenue = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    fx_spread_revenue = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    net_revenue = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    profit = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    class Meta:
        ordering = ["-week_start"]
        indexes = [
            models.Index(fields=["week_start"]),
            models.Index(fields=["-week_start"]),
        ]

    def __str__(self) -> str:
        return f"Weekly Summary {self.week_start} -> {self.week_end}"


class MonthlySummary(TimeStampedModel):
    """Monthly aggregates keyed by the first day of the month."""
    month = models.DateField(unique=True)  # first day of month

    new_users = models.IntegerField(default=0)
    active_users = models.IntegerField(default=0)
    total_transactions_success = models.IntegerField(default=0)
    total_transactions_failed = models.IntegerField(default=0)
    total_transactions_refunded = models.IntegerField(default=0)
    total_transferred_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_refunded_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    bill_payments_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    fee_revenue = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    bill_commission_revenue = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    fx_spread_revenue = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    net_revenue = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    profit = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    class Meta:
        ordering = ["-month"]
        indexes = [
            models.Index(fields=["month"]),
            models.Index(fields=["-month"]),
        ]

    def __str__(self) -> str:
        return f"Monthly Summary {self.month}"


class ActiveUserWindow(TimeStampedModel):
    """Rolling active-user windows for DAU/WAU/MAU by date."""
    date = models.DateField()
    window = models.CharField(
        max_length=8,
        choices=(
            ("dau", "DAU"),
            ("wau", "WAU"),
            ("mau", "MAU"),
        ),
    )
    active_users = models.IntegerField(default=0)

    class Meta:
        unique_together = ("date", "window")
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["window"]),
            models.Index(fields=["date", "window"]),
        ]

    def __str__(self) -> str:
        return f"{self.window.upper()} on {self.date}: {self.active_users}"


class DailyActiveUser(models.Model):
    """Tracks unique successful logins per user per day for active-user counts."""
    date = models.DateField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("date", "user")
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["user"]),
            models.Index(fields=["date", "user"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} on {self.date}"
