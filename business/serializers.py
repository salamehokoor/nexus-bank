"""
Serializers for business reporting models and overview payload.
"""
from rest_framework import serializers
from .models import (CurrencyMetrics, DailyBusinessMetrics,
                     CountryUserMetrics)


class DailyBusinessMetricsSerializer(serializers.ModelSerializer):
    """Serializer for daily business metrics snapshot."""

    class Meta:
        model = DailyBusinessMetrics
        fields = "__all__"


class CountryUserMetricsSerializer(serializers.ModelSerializer):
    """Serializer for per-country metrics."""

    class Meta:
        model = CountryUserMetrics
        fields = "__all__"


class CurrencyMetricsSerializer(serializers.ModelSerializer):
    """Serializer for per-currency metrics."""

    class Meta:
        model = CurrencyMetrics
        fields = "__all__"


class WeeklySummarySerializer(serializers.Serializer):
    """Serializer for aggregated weekly metrics derived from daily rows."""
    week_start = serializers.DateField()
    week_end = serializers.DateField()
    new_users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    total_transactions_success = serializers.IntegerField()
    total_transactions_failed = serializers.IntegerField()
    total_transactions_refunded = serializers.IntegerField()
    total_transferred_amount = serializers.DecimalField(max_digits=18,
                                                        decimal_places=2)
    total_refunded_amount = serializers.DecimalField(max_digits=18,
                                                     decimal_places=2)
    bill_payments_amount = serializers.DecimalField(max_digits=18,
                                                    decimal_places=2)
    fee_revenue = serializers.DecimalField(max_digits=18, decimal_places=2)
    bill_commission_revenue = serializers.DecimalField(max_digits=18,
                                                       decimal_places=2)
    fx_spread_revenue = serializers.DecimalField(max_digits=18,
                                                 decimal_places=2)
    net_revenue = serializers.DecimalField(max_digits=18, decimal_places=2)
    profit = serializers.DecimalField(max_digits=18, decimal_places=2)


class MonthlySummarySerializer(serializers.Serializer):
    """Serializer for aggregated monthly metrics derived from daily rows."""
    month = serializers.DateField()
    new_users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    total_transactions_success = serializers.IntegerField()
    total_transactions_failed = serializers.IntegerField()
    total_transactions_refunded = serializers.IntegerField()
    total_transferred_amount = serializers.DecimalField(max_digits=18,
                                                        decimal_places=2)
    total_refunded_amount = serializers.DecimalField(max_digits=18,
                                                     decimal_places=2)
    bill_payments_amount = serializers.DecimalField(max_digits=18,
                                                    decimal_places=2)
    fee_revenue = serializers.DecimalField(max_digits=18, decimal_places=2)
    bill_commission_revenue = serializers.DecimalField(max_digits=18,
                                                       decimal_places=2)
    fx_spread_revenue = serializers.DecimalField(max_digits=18,
                                                 decimal_places=2)
    net_revenue = serializers.DecimalField(max_digits=18, decimal_places=2)
    profit = serializers.DecimalField(max_digits=18, decimal_places=2)


class ActiveUsersDailySerializer(serializers.ModelSerializer):
    """Expose daily active user counts straight from daily metrics rows."""

    class Meta:
        model = DailyBusinessMetrics
        fields = ("date", "active_users", "active_users_7d",
                  "active_users_30d")


class BusinessOverviewSerializer(serializers.Serializer):
    """
    Wrapper serializer used for the combined /overview endpoint.
    """
    daily = DailyBusinessMetricsSerializer(allow_null=True)
    weekly = WeeklySummarySerializer(many=True)
    monthly = MonthlySummarySerializer(many=True)
    country = CountryUserMetricsSerializer(many=True)
    currency = CurrencyMetricsSerializer(many=True)
    active = ActiveUsersDailySerializer(many=True)
