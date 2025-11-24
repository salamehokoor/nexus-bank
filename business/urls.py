from django.urls import path

from .views import (
    DailyMetricsView,
    WeeklySummaryView,
    MonthlySummaryView,
    CountryMetricsView,
    BusinessOverviewView,
)

urlpatterns = [
    path("daily/", DailyMetricsView.as_view(), name="business-daily"),
    path("weekly/", WeeklySummaryView.as_view(), name="business-weekly"),
    path("monthly/", MonthlySummaryView.as_view(), name="business-monthly"),
    path("countries/", CountryMetricsView.as_view(), name="business-country"),
    path("overview/", BusinessOverviewView.as_view(),
         name="business-overview"),
]
