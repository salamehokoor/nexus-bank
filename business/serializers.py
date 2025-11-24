from rest_framework import serializers
from .models import (
    DailyBusinessMetrics,
    CountryUserMetrics,
    WeeklySummary,
    MonthlySummary,
)


class DailyBusinessMetricsSerializer(serializers.ModelSerializer):

    class Meta:
        model = DailyBusinessMetrics
        fields = "__all__"


class CountryUserMetricsSerializer(serializers.ModelSerializer):

    class Meta:
        model = CountryUserMetrics
        fields = "__all__"


class WeeklySummarySerializer(serializers.ModelSerializer):

    class Meta:
        model = WeeklySummary
        fields = "__all__"


class MonthlySummarySerializer(serializers.ModelSerializer):

    class Meta:
        model = MonthlySummary
        fields = "__all__"


class BusinessOverviewSerializer(serializers.Serializer):
    """
    Simple wrapper serializer used for the combined /overview endpoint.
    """

    daily = DailyBusinessMetricsSerializer(allow_null=True)
    weekly = WeeklySummarySerializer(many=True)
    monthly = MonthlySummarySerializer(many=True)
    country = CountryUserMetricsSerializer(many=True)
