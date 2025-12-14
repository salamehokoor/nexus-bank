import csv

from django.contrib import admin
from django.http import HttpResponse

from .models import (DailyBusinessMetrics, CountryUserMetrics, CurrencyMetrics,
                     DailyActiveUser)


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


export_as_csv.short_description = "Export selected to CSV"


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
    actions = [export_as_csv]


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


@admin.register(DailyActiveUser)
class DailyActiveUserAdmin(admin.ModelAdmin):
    list_display = ("date", "user")
    ordering = ("-date", )
    search_fields = ("user__email", )
