# risk/views.py
from rest_framework.generics import ListAPIView, CreateAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from axes.utils import reset
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView  # 👈 you were missing this

from .models import Incident, LoginEvent
from .serializers import (
    IncidentSerializer,
    LoginEventSerializer,
    UnlockIPSerializer,
)
from .auth_logging import log_auth_event


# -------------------------------------------------------------------
#  JWT login with logging
# -------------------------------------------------------------------
class LoggingTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Wraps the normal SimpleJWT serializer to log *successful* logins.
    Failed logins are still captured by the django_login_failed signal.
    """

    def validate(self, attrs):
        # This calls authenticate() and sets self.user on success
        data = super().validate(attrs)

        request = self.context["request"]

        # Centralised logging helper – this is your function
        log_auth_event(
            request=request,
            user=self.user,
            successful=True,
            source="jwt",  # or "password" / whatever label you prefer
        )

        return data


class LoggingTokenObtainPairView(TokenObtainPairView):
    serializer_class = LoggingTokenObtainPairSerializer


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
