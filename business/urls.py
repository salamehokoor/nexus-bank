from django.urls import path
from .views import (
    DailyMetricsView,
    CountryMetricsView,
    MonthlySummaryView,
    BusinessOverviewView,
)

urlpatterns = [
    path("daily/", DailyMetricsView.as_view(), name="daily-metrics"),
    path("country/", CountryMetricsView.as_view(), name="country-metrics"),
    path("monthly/", MonthlySummaryView.as_view(), name="monthly-metrics"),
    path("overview/", BusinessOverviewView.as_view(),
         name="business-overview"),
]
