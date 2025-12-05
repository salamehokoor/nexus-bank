"""
URL routes exposing risk monitoring endpoints (incidents, logins, KPIs).
"""
from django.urls import path
from .views import IncidentListView, LoginEventsListView, RiskKPIsView, AxesUnlockIPView

urlpatterns = [
    path("incidents/", IncidentListView.as_view(), name="risk-incidents"),
    path("logins/", LoginEventsListView.as_view(), name="risk-logins"),
    path("kpis/", RiskKPIsView.as_view(), name="risk-kpis"),
    path("axes/unlock-ip/",
         AxesUnlockIPView.as_view(),
         name="risk-axes-unlock-ip"),
]
