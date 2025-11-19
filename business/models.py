from django.db import models
from django.contrib.auth import get_user_model
from api.models import Transaction, BillPayment, Account
from risk.models import Incident, LoginEvent

User = get_user_model()


class DailyBusinessMetrics(models.Model):
    """Aggregated analytics per day for fast dashboard performance."""

    date = models.DateField(unique=True)

    # --- User Metrics ---
    new_users = models.IntegerField(default=0)
    total_users = models.IntegerField(default=0)
    active_users = models.IntegerField(default=0)

    # --- Transactions Metrics ---
    total_transactions = models.IntegerField(default=0)
    total_transferred_amount = models.DecimalField(max_digits=14,
                                                   decimal_places=2,
                                                   default=0)
    avg_transaction_value = models.DecimalField(max_digits=14,
                                                decimal_places=2,
                                                default=0)

    # --- Bill Payments ---
    bill_payments_count = models.IntegerField(default=0)
    bill_payments_amount = models.DecimalField(max_digits=14,
                                               decimal_places=2,
                                               default=0)

    # --- Profit Metrics ---
    profit = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # --- Risk / Security Metrics ---
    failed_logins = models.IntegerField(default=0)
    incidents = models.IntegerField(default=0)

    # --- Currency Conversion Metrics ---
    fx_volume = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Metrics for {self.date}"


class CountryUserMetrics(models.Model):
    """Snapshot of user distribution by country."""
    date = models.DateField()
    country = models.CharField(max_length=50)
    count = models.IntegerField(default=0)

    class Meta:
        unique_together = ('date', 'country')

    def __str__(self):
        return f"{self.country}: {self.count} on {self.date}"


class MonthlySummary(models.Model):
    month = models.DateField(unique=True)

    new_users = models.IntegerField(default=0)
    total_transactions = models.IntegerField(default=0)
    total_transferred_amount = models.DecimalField(max_digits=14,
                                                   decimal_places=2,
                                                   default=0)
    bill_payments_amount = models.DecimalField(max_digits=14,
                                               decimal_places=2,
                                               default=0)
    profit = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Monthly Summary {self.month}"
