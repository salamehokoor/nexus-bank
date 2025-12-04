from datetime import datetime

from django.utils.cache import patch_cache_control
from rest_framework import permissions, status
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    DailyBusinessMetrics,
    CountryUserMetrics,
    WeeklySummary,
    MonthlySummary,
    CurrencyMetrics,
    ActiveUserWindow,
)
from .serializers import (
    DailyBusinessMetricsSerializer,
    CountryUserMetricsSerializer,
    WeeklySummarySerializer,
    MonthlySummarySerializer,
    BusinessOverviewSerializer,
    CurrencyMetricsSerializer,
    ActiveUserWindowSerializer,
)


def _parse_date_param(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


class BasePaginatedView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = LimitOffsetPagination

    def paginate(self, request, queryset, serializer_class):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        data = serializer_class(page, many=True).data
        return paginator.get_paginated_response(data)


class DailyMetricsView(APIView):
    schema = None  # exclude from schema to avoid doc errors
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        target_date = _parse_date_param(request.query_params.get("date"))
        qs = DailyBusinessMetrics.objects
        obj = qs.filter(date=target_date).first(
        ) if target_date else qs.order_by("-date").first()
        if not obj:
            return Response({}, status=status.HTTP_204_NO_CONTENT)
        resp = Response(DailyBusinessMetricsSerializer(obj).data)
        patch_cache_control(resp, private=True, max_age=60)
        return resp


class WeeklySummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        week_param = _parse_date_param(request.query_params.get("week"))
        qs = WeeklySummary.objects.order_by("-week_start")
        if week_param:
            qs = qs.filter(week_start=week_param)
        return self.paginate(request, qs, WeeklySummarySerializer)


class MonthlySummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        month_param = _parse_date_param(request.query_params.get("month"))
        qs = MonthlySummary.objects.order_by("-month")
        return Response(MonthlySummarySerializer(qs, many=True).data)


class CountryMetricsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        date_param = _parse_date_param(request.query_params.get("date"))
        window = request.query_params.get("window")
        qs = ActiveUserWindow.objects.order_by("-date")
        if date_param:
            qs = qs.filter(date=date_param)
        if window:
            qs = qs.filter(window=window)
        return self.paginate(request, qs, ActiveUserWindowSerializer)


class BusinessOverviewView(APIView):
    schema = None
    """
    Aggregated payload for dashboards with caching hints.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        daily_date = _parse_date_param(request.query_params.get("date"))
        daily_obj = (DailyBusinessMetrics.objects.filter(
            date=daily_date).first() if daily_date else
                     DailyBusinessMetrics.objects.order_by("-date").first())
        weekly_qs = WeeklySummary.objects.order_by("-week_start")
        monthly_qs = MonthlySummary.objects.order_by("-month")
        country_qs = CountryUserMetrics.objects.order_by("-date")
        currency_qs = CurrencyMetrics.objects.order_by("-date")
        active_qs = ActiveUserWindow.objects.order_by("-date")

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
            "currency":
            CurrencyMetricsSerializer(currency_qs, many=True).data,
            "active":
            ActiveUserWindowSerializer(active_qs, many=True).data,
        }

        resp = Response(BusinessOverviewSerializer(payload).data)
        patch_cache_control(resp, private=True, max_age=60)
        return resp
