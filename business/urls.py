from django.urls import path
from .views import (DailyMetricsView, CountryMetricsView, MonthlySummaryView,
                    BusinessOverviewView, WeeklySummaryView)

urlpatterns = [
    path("business/daily/", DailyMetricsView.as_view()),
    path("business/weekly/", WeeklySummaryView.as_view()),
    path("business/monthly/", MonthlySummaryView.as_view()),
    path("business/country/", CountryMetricsView.as_view()),
    path("business/overview/", BusinessOverviewView.as_view()),
]
