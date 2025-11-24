from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    DailyBusinessMetrics,
    CountryUserMetrics,
    WeeklySummary,
    MonthlySummary,
)
from .serializers import (
    DailyBusinessMetricsSerializer,
    CountryUserMetricsSerializer,
    WeeklySummarySerializer,
    MonthlySummarySerializer,
    BusinessOverviewSerializer,
)


class DailyMetricsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        obj = DailyBusinessMetrics.objects.order_by("-date").first()
        # if no metrics yet, return empty dict
        if not obj:
            return Response({})
        return Response(DailyBusinessMetricsSerializer(obj).data)


class WeeklySummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = WeeklySummary.objects.order_by("-week_start")
        return Response(WeeklySummarySerializer(qs, many=True).data)


class MonthlySummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = MonthlySummary.objects.order_by("-month")
        return Response(MonthlySummarySerializer(qs, many=True).data)


class CountryMetricsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = CountryUserMetrics.objects.order_by("-date")
        return Response(CountryUserMetricsSerializer(qs, many=True).data)


class BusinessOverviewView(APIView):
    """
    Single endpoint for React dashboard.

    Returns:
    {
      "daily": {...} or null,
      "weekly": [...],
      "monthly": [...],
      "country": [...]
    }
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        daily_obj = DailyBusinessMetrics.objects.order_by("-date").first()
        weekly_qs = WeeklySummary.objects.order_by("-week_start")
        monthly_qs = MonthlySummary.objects.order_by("-month")
        country_qs = CountryUserMetrics.objects.order_by("-date")

        payload = {
            "daily":
            DailyBusinessMetricsSerializer(daily_obj).data
            if daily_obj else None,
            "weekly":
            WeeklySummarySerializer(weekly_qs, many=True).data,
            "monthly":
            MonthlySummarySerializer(monthly_qs, many=True).data,
            "country":
            CountryUserMetricsSerializer(country_qs, many=True).data,
        }

        return Response(BusinessOverviewSerializer(payload).data)
