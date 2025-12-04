import csv

from django.contrib import admin
from django.http import HttpResponse

from .models import (
    DailyBusinessMetrics,
    WeeklySummary,
    MonthlySummary,
    CountryUserMetrics,
    CurrencyMetrics,
    ActiveUserWindow,
)
from .services import compute_daily_business_metrics, compute_weekly_summary, compute_monthly_summary


def export_as_csv(modeladmin, request, queryset):
    meta = modeladmin.model._meta
    field_names = [field.name for field in meta.fields]
    response = HttpResponse(content_type="text/csv")
    response[
        "Content-Disposition"] = f'attachment; filename={meta.model_name}.csv'
    writer = csv.writer(response)
    writer.writerow(field_names)
    for obj in queryset:
        writer.writerow([getattr(obj, field) for field in field_names])
    return response


def recompute_daily(modeladmin, request, queryset):
    for obj in queryset:
        compute_daily_business_metrics(obj.date)


def recompute_weekly(modeladmin, request, queryset):
    for obj in queryset:
        compute_weekly_summary(obj.week_start)


def recompute_monthly(modeladmin, request, queryset):
    for obj in queryset:
        compute_monthly_summary(obj.month)


export_as_csv.short_description = "Export selected to CSV"
recompute_daily.short_description = "Recompute selected days"
recompute_weekly.short_description = "Recompute selected weeks"
recompute_monthly.short_description = "Recompute selected months"


@admin.register(DailyBusinessMetrics)
class DailyMetricsAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "new_users",
        "active_users",
        "total_transactions_success",
        "total_transferred_amount",
        "net_revenue",
        "profit",
    )
    ordering = ("-date", )
    list_filter = ("date", )
    search_fields = ("date", )
    date_hierarchy = "date"
    readonly_fields = ("created_at", "updated_at")
    actions = [export_as_csv, recompute_daily]


@admin.register(WeeklySummary)
class WeeklySummaryAdmin(admin.ModelAdmin):
    list_display = (
        "week_start",
        "week_end",
        "new_users",
        "total_transactions_success",
        "total_transferred_amount",
        "net_revenue",
    )
    ordering = ("-week_start", )
    list_filter = ("week_start", )
    search_fields = ("week_start", "week_end")
    date_hierarchy = "week_start"
    readonly_fields = ("created_at", "updated_at")
    actions = [export_as_csv, recompute_weekly]


@admin.register(MonthlySummary)
class MonthlySummaryAdmin(admin.ModelAdmin):
    list_display = (
        "month",
        "new_users",
        "total_transactions_success",
        "total_transferred_amount",
        "net_revenue",
    )
    ordering = ("-month", )
    list_filter = ("month", )
    search_fields = ("month", )
    date_hierarchy = "month"
    readonly_fields = ("created_at", "updated_at")
    actions = [export_as_csv, recompute_monthly]


@admin.register(CountryUserMetrics)
class CountryUserMetricsAdmin(admin.ModelAdmin):
    list_display = ("date", "country", "count", "active_users", "tx_amount",
                    "net_revenue")
    ordering = ("-date", "country")
    list_filter = ("date", "country")
    search_fields = ("country", )
    date_hierarchy = "date"
    readonly_fields = ("created_at", "updated_at")
    actions = [export_as_csv]


@admin.register(CurrencyMetrics)
class CurrencyMetricsAdmin(admin.ModelAdmin):
    list_display = ("date", "currency", "tx_count", "tx_amount", "fx_volume",
                    "fee_revenue")
    ordering = ("-date", "currency")
    list_filter = ("date", "currency")
    search_fields = ("currency", )
    date_hierarchy = "date"
    readonly_fields = ("created_at", "updated_at")
    actions = [export_as_csv]


@admin.register(ActiveUserWindow)
class ActiveUserWindowAdmin(admin.ModelAdmin):
    list_display = ("date", "window", "active_users")
    ordering = ("-date", )
    list_filter = ("window", )
    search_fields = ("window", )
    date_hierarchy = "date"
    readonly_fields = ("created_at", "updated_at")
    actions = [export_as_csv]
