from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from .models import Incident, LoginEvent
from .serializers import IncidentSerializer, LoginEventSerializer


class IncidentListView(ListAPIView):
    queryset = Incident.objects.all().order_by("-timestamp")
    serializer_class = IncidentSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["severity", "country"]
    ordering_fields = ["timestamp", "severity"]
    permission_classes = [IsAdminUser]


class LoginEventsListView(ListAPIView):
    queryset = LoginEvent.objects.all().order_by("-timestamp")
    serializer_class = LoginEventSerializer
    permission_classes = [IsAdminUser]


class RiskKPIsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response({
            "total_incidents":
            Incident.objects.count(),
            "critical_alerts":
            Incident.objects.filter(severity="critical").count(),
            "failed_logins":
            Incident.objects.filter(event__icontains="Failed").count(),
            "unique_attack_ips":
            Incident.objects.values("ip").distinct().count(),
        })
