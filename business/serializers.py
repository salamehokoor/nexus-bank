from rest_framework import serializers
from .models import DailyBusinessMetrics, CountryUserMetrics, MonthlySummary


class DailyBusinessMetricsSerializer(serializers.ModelSerializer):

    class Meta:
        model = DailyBusinessMetrics
        fields = "__all__"


class CountryUserMetricsSerializer(serializers.ModelSerializer):

    class Meta:
        model = CountryUserMetrics
        fields = "__all__"


class MonthlySummarySerializer(serializers.ModelSerializer):

    class Meta:
        model = MonthlySummary
        fields = "__all__"


class BusinessOverviewSerializer(serializers.Serializer):
    """Combined backend → one endpoint for dashboard."""
    daily = DailyBusinessMetricsSerializer()
    country = CountryUserMetricsSerializer(many=True)
    monthly = MonthlySummarySerializer(many=True)
