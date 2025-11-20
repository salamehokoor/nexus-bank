from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions

from .models import DailyBusinessMetrics, CountryUserMetrics, MonthlySummary, WeeklySummary
from .serializers import (DailyBusinessMetricsSerializer,
                          CountryUserMetricsSerializer,
                          MonthlySummarySerializer, WeeklySummarySerializer,
                          BusinessOverviewSerializer)


class DailyMetricsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        obj = DailyBusinessMetrics.objects.order_by("-date").first()
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
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        data = {
            "daily":
            DailyBusinessMetricsSerializer(
                DailyBusinessMetrics.objects.order_by("-date").first()).data,
            "country":
            CountryUserMetricsSerializer(
                CountryUserMetrics.objects.order_by("-date"), many=True).data,
            "weekly":
            WeeklySummarySerializer(
                WeeklySummary.objects.order_by("-week_start"), many=True).data,
            "monthly":
            MonthlySummarySerializer(MonthlySummary.objects.order_by("-month"),
                                     many=True).data,
        }
        return Response(BusinessOverviewSerializer(data).data)
