from django.urls import path
from .views import IncidentListView, LoginEventsListView, RiskKPIsView

urlpatterns = [
    path("incidents/", IncidentListView.as_view(), name="risk-incidents"),
    path("logins/", LoginEventsListView.as_view(), name="risk-logins"),
    path("kpis/", RiskKPIsView.as_view(), name="risk-kpis"),
]
