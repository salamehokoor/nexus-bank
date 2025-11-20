from rest_framework import serializers
from .models import DailyBusinessMetrics, CountryUserMetrics, MonthlySummary, WeeklySummary


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


class WeeklySummarySerializer(serializers.ModelSerializer):

    class Meta:
        model = WeeklySummary
        fields = "__all__"


class BusinessOverviewSerializer(serializers.Serializer):
    daily = DailyBusinessMetricsSerializer()
    country = CountryUserMetricsSerializer(many=True)
    weekly = WeeklySummarySerializer(many=True)
    monthly = MonthlySummarySerializer(many=True)
