from django.contrib import admin
from .models import DailyBusinessMetrics, WeeklySummary, MonthlySummary, CountryUserMetrics


@admin.register(DailyBusinessMetrics)
class DailyMetricsAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "new_users",
        "total_users",
        "active_users",
        "total_transactions",
        "total_transferred_amount",
        "profit",
    )
    ordering = ("-date", )


@admin.register(WeeklySummary)
class WeeklySummaryAdmin(admin.ModelAdmin):
    list_display = (
        "week_start",
        "week_end",
        "new_users",
        "total_transactions",
        "total_transferred_amount",
        "profit",
    )
    ordering = ("-week_start", )


@admin.register(MonthlySummary)
class MonthlySummaryAdmin(admin.ModelAdmin):
    list_display = (
        "month",
        "new_users",
        "total_transactions",
        "total_transferred_amount",
        "profit",
    )
    ordering = ("-month", )


@admin.register(CountryUserMetrics)
class CountryUserMetricsAdmin(admin.ModelAdmin):
    list_display = ("date", "country", "count")
    ordering = ("-date", )
