"""
API views exposing business metrics (daily/weekly/monthly, country/currency, active users).
All endpoints require authentication; responses are cache-hinted for dashboards.
"""
from datetime import datetime, timedelta

from django.utils.cache import patch_cache_control
from rest_framework import permissions, status
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    CountryUserMetrics,
    CurrencyMetrics,
    DailyBusinessMetrics,
)
from .serializers import (
    ActiveUsersDailySerializer,
    BusinessOverviewSerializer,
    CountryUserMetricsSerializer,
    CurrencyMetricsSerializer,
    DailyBusinessMetricsSerializer,
    MonthlySummarySerializer,
    WeeklySummarySerializer,
)
from .services import build_monthly_summaries, build_weekly_summaries, summarize_range


def _parse_date_param(value):
    """Parse ISO date string to date; return None on failure."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


class BasePaginatedView(APIView):
    permission_classes = [permissions.IsAdminUser]
    pagination_class = LimitOffsetPagination

    def paginate(self, request, queryset, serializer_class):
        """Apply limit/offset pagination and return serialized page."""
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        # LimitOffsetPagination returns None when page_size is unset; in that
        # case we should return the full queryset instead of crashing.
        if page is not None:
            data = serializer_class(page, many=True).data
            return paginator.get_paginated_response(data)
        data = serializer_class(queryset, many=True).data
        return Response(data)


class DailyMetricsView(APIView):
    permission_classes = [permissions.IsAdminUser]

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


class WeeklySummaryView(BasePaginatedView):

    def get(self, request):
        week_param = _parse_date_param(request.query_params.get("week"))
        dates = DailyBusinessMetrics.objects.values_list(
            "date", flat=True).order_by("-date")
        if not dates:
            return Response([], status=status.HTTP_204_NO_CONTENT)

        week_starts = []
        seen = set()
        for d in dates:
            start = d - timedelta(days=d.weekday())
            if week_param and start != week_param:
                continue
            if start in seen:
                continue
            seen.add(start)
            week_starts.append(start)
            if not week_param and len(week_starts) >= 12:
                break

        payload = list(build_weekly_summaries(week_starts))
        return Response(WeeklySummarySerializer(payload, many=True).data)


class MonthlySummaryView(BasePaginatedView):

    def get(self, request):
        month_param = _parse_date_param(request.query_params.get("month"))
        dates = DailyBusinessMetrics.objects.values_list(
            "date", flat=True).order_by("-date")
        if not dates:
            return Response([], status=status.HTTP_204_NO_CONTENT)
        month_starts = []
        seen = set()
        for d in dates:
            start = d.replace(day=1)
            if month_param and start != month_param:
                continue
            if start in seen:
                continue
            seen.add(start)
            month_starts.append(start)
            if not month_param and len(month_starts) >= 12:
                break

        payload = list(build_monthly_summaries(month_starts))
        return Response(MonthlySummarySerializer(payload, many=True).data)


class CountryMetricsView(BasePaginatedView):

    def get(self, request):
        date_param = _parse_date_param(request.query_params.get("date"))
        qs = CountryUserMetrics.objects.order_by("-date", "country")
        if date_param:
            qs = qs.filter(date=date_param)
        return self.paginate(request, qs, CountryUserMetricsSerializer)


class CurrencyMetricsView(BasePaginatedView):

    def get(self, request):
        date_param = _parse_date_param(request.query_params.get("date"))
        qs = CurrencyMetrics.objects.order_by("-date", "currency")
        if date_param:
            qs = qs.filter(date=date_param)
        return self.paginate(request, qs, CurrencyMetricsSerializer)


class ActiveUsersView(BasePaginatedView):

    def get(self, request):
        date_param = _parse_date_param(request.query_params.get("date"))
        qs = DailyBusinessMetrics.objects.order_by("-date")
        if date_param:
            qs = qs.filter(date=date_param)
        return self.paginate(request, qs, ActiveUsersDailySerializer)


class BusinessOverviewView(APIView):
    """
    Aggregated payload for dashboards with caching hints.
    """

    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        daily_date = _parse_date_param(request.query_params.get("date"))
        daily_obj = (DailyBusinessMetrics.objects.filter(
            date=daily_date).first() if daily_date else
                     DailyBusinessMetrics.objects.order_by("-date").first())
        country_qs = CountryUserMetrics.objects.order_by("-date")
        currency_qs = CurrencyMetrics.objects.order_by("-date")
        active_qs = DailyBusinessMetrics.objects.order_by("-date")

        weekly_data = list(
            build_weekly_summaries({
                d - timedelta(days=d.weekday())
                for d in DailyBusinessMetrics.objects.values_list(
                    "date", flat=True)
            }))
        monthly_data = list(
            build_monthly_summaries({
                d.replace(day=1)
                for d in DailyBusinessMetrics.objects.values_list(
                    "date", flat=True)
            }))

        payload = {
            "daily":
            DailyBusinessMetricsSerializer(daily_obj).data
            if daily_obj else None,
            "weekly":
            WeeklySummarySerializer(weekly_data, many=True).data,
            "monthly":
            MonthlySummarySerializer(monthly_data, many=True).data,
            "country":
            CountryUserMetricsSerializer(country_qs, many=True).data,
            "currency":
            CurrencyMetricsSerializer(currency_qs, many=True).data,
            "active":
            ActiveUsersDailySerializer(active_qs, many=True).data,
        }

        resp = Response(BusinessOverviewSerializer(payload).data)
        patch_cache_control(resp, private=True, max_age=60)
        return resp
