"""
URL routes for business metrics APIs.
"""
from django.urls import path

from .views import (
    DailyMetricsView,
    WeeklySummaryView,
    MonthlySummaryView,
    CountryMetricsView,
    CurrencyMetricsView,
    ActiveUsersView,
    BusinessOverviewView,
)
from .views_ai import AIBusinessAdvisorView

urlpatterns = [
    path("daily/", DailyMetricsView.as_view(), name="business-daily"),
    path("weekly/", WeeklySummaryView.as_view(), name="business-weekly"),
    path("monthly/", MonthlySummaryView.as_view(), name="business-monthly"),
    path("countries/", CountryMetricsView.as_view(), name="business-country"),
    path("currencies/",
         CurrencyMetricsView.as_view(),
         name="business-currency"),
    path("active/", ActiveUsersView.as_view(), name="business-active"),
    path("overview/", BusinessOverviewView.as_view(),
         name="business-overview"),
    # AI Business Advisor (admin-only, read-only decision support)
    path("ai/advisor/", AIBusinessAdvisorView.as_view(),
         name="ai-business-advisor"),
]

