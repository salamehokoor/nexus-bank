from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class DailyBusinessMetrics(models.Model):
    date = models.DateField(unique=True)

    new_users = models.IntegerField(default=0)
    total_users = models.IntegerField(default=0)
    active_users = models.IntegerField(default=0)

    total_transactions = models.IntegerField(default=0)
    total_transferred_amount = models.DecimalField(max_digits=14,
                                                   decimal_places=2,
                                                   default=0)
    avg_transaction_value = models.DecimalField(max_digits=14,
                                                decimal_places=2,
                                                default=0)

    bill_payments_count = models.IntegerField(default=0)
    bill_payments_amount = models.DecimalField(max_digits=14,
                                               decimal_places=2,
                                               default=0)

    profit = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    failed_logins = models.IntegerField(default=0)
    incidents = models.IntegerField(default=0)

    fx_volume = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Metrics for {self.date}"


class CountryUserMetrics(models.Model):
    date = models.DateField()
    country = models.CharField(max_length=50)
    count = models.IntegerField(default=0)

    class Meta:
        unique_together = ("date", "country")

    def __str__(self):
        return f"{self.country}: {self.count} on {self.date}"


class WeeklySummary(models.Model):
    week_start = models.DateField(unique=True)
    week_end = models.DateField()

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
        return f"Weekly Summary {self.week_start} → {self.week_end}"


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
