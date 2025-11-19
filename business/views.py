from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions

from .models import DailyBusinessMetrics, CountryUserMetrics, MonthlySummary
from .serializers import (DailyBusinessMetricsSerializer,
                          CountryUserMetricsSerializer,
                          MonthlySummarySerializer, BusinessOverviewSerializer)


class DailyMetricsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        obj = DailyBusinessMetrics.objects.order_by("-date").first()
        serializer = DailyBusinessMetricsSerializer(obj)
        return Response(serializer.data)


class CountryMetricsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = CountryUserMetrics.objects.order_by("-date")
        serializer = CountryUserMetricsSerializer(qs, many=True)
        return Response(serializer.data)


class MonthlySummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = MonthlySummary.objects.order_by("-month")
        serializer = MonthlySummarySerializer(qs, many=True)
        return Response(serializer.data)


class BusinessOverviewView(APIView):
    """
    Combines:
    - Daily metrics
    - All country snapshots
    - All monthly summaries

    Front-end calls ONE endpoint → dashboard loads instantly.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        daily = DailyBusinessMetrics.objects.order_by("-date").first()
        country = CountryUserMetrics.objects.order_by("-date")
        monthly = MonthlySummary.objects.order_by("-month")

        data = {
            "daily": DailyBusinessMetricsSerializer(daily).data,
            "country": CountryUserMetricsSerializer(country, many=True).data,
            "monthly": MonthlySummarySerializer(monthly, many=True).data,
        }

        serializer = BusinessOverviewSerializer(data)
        return Response(serializer.data)
