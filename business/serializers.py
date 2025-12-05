"""
Serializers for business reporting models and overview payload.
"""
from rest_framework import serializers
from .models import (
    DailyBusinessMetrics,
    CountryUserMetrics,
    WeeklySummary,
    MonthlySummary,
    CurrencyMetrics,
    ActiveUserWindow,
)


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


class WeeklySummarySerializer(serializers.ModelSerializer):
    """Serializer for weekly summary metrics."""

    class Meta:
        model = WeeklySummary
        fields = "__all__"


class MonthlySummarySerializer(serializers.ModelSerializer):
    """Serializer for monthly summary metrics."""

    class Meta:
        model = MonthlySummary
        fields = "__all__"


class ActiveUserWindowSerializer(serializers.ModelSerializer):
    """Serializer for active user window metrics."""

    class Meta:
        model = ActiveUserWindow
        fields = "__all__"


class BusinessOverviewSerializer(serializers.Serializer):
    """
    Wrapper serializer used for the combined /overview endpoint.
    """
    daily = DailyBusinessMetricsSerializer(allow_null=True)
    weekly = WeeklySummarySerializer(many=True)
    monthly = MonthlySummarySerializer(many=True)
    country = CountryUserMetricsSerializer(many=True)
    currency = CurrencyMetricsSerializer(many=True)
    active = ActiveUserWindowSerializer(many=True)
