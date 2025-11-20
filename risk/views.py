from rest_framework.generics import ListAPIView, CreateAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from .models import Incident, LoginEvent
from .serializers import IncidentSerializer, LoginEventSerializer, UnlockIPSerializer
from axes.utils import reset


class AxesUnlockIPView(CreateAPIView):
    #permission_classes = [IsAdminUser]
    serializer_class = UnlockIPSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ip = serializer.validated_data["ip"]

        # Correct kwarg = ip
        reset(ip=ip)

        return Response({"detail": f"Lockouts cleared for IP {ip}."})


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
