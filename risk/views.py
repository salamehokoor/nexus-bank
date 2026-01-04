"""
API endpoints for risk monitoring, authentication logging, and KPI dashboards.
"""
# risk/views.py
from rest_framework.generics import ListAPIView, CreateAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from axes.utils import reset
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework import status

from .models import Incident, LoginEvent
from .serializers import (
    IncidentSerializer,
    LoginEventSerializer,
    UnlockIPSerializer,
    RiskAnalysisRequestSerializer,
)
from .auth_logging import (
    log_auth_event,
    log_jwt_refresh_event,
    log_csrf_failure,
)
from .ai import analyze_incident
from .models import Incident, LoginEvent


# -------------------------------------------------------------------
#  JWT login with logging
# -------------------------------------------------------------------
class LoggingTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Wraps the SimpleJWT serializer to log successful logins.
    Failed logins are still captured by the django_login_failed signal.
    """

    def validate(self, attrs):
        """Authenticate and log the successful login event."""
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


class LoggingTokenRefreshView(TokenRefreshView):
    """
    Wraps SimpleJWT refresh to log successful and failed refresh attempts.
    """

    def post(self, request, *args, **kwargs):
        try:
            response = super().post(request, *args, **kwargs)
        except (InvalidToken, TokenError) as exc:
            log_jwt_refresh_event(
                request=request,
                user=getattr(request, "user", None),
                successful=False,
                failure_reason=str(exc),
            )
            raise

        user = getattr(request, "user", None)
        if response.status_code == status.HTTP_200_OK:
            log_jwt_refresh_event(
                request=request,
                user=user,
                successful=True,
            )
        else:
            log_jwt_refresh_event(
                request=request,
                user=user,
                successful=False,
                failure_reason=f"status_{response.status_code}",
            )

        return response


class AxesUnlockIPView(CreateAPIView):
    """
    Admin-only endpoint to unlock a blocked IP through django-axes.
    """
    permission_classes = [IsAdminUser]
    serializer_class = UnlockIPSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ip = serializer.validated_data["ip"]

        # Correct kwarg = ip
        reset(ip=ip)

        return Response({"detail": f"Lockouts cleared for IP {ip}."})


class IncidentListView(ListAPIView):
    """List incidents for admin review with filtering and ordering."""
    queryset = Incident.objects.all().order_by("-timestamp")
    serializer_class = IncidentSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["severity", "country"]
    ordering_fields = ["timestamp", "severity"]
    permission_classes = [IsAdminUser]


class LoginEventsListView(ListAPIView):
    """List login events for admin review."""
    queryset = LoginEvent.objects.all().order_by("-timestamp")
    serializer_class = LoginEventSerializer
    permission_classes = [IsAdminUser]


class RiskKPIsView(APIView):
    """Return basic risk/security KPIs for dashboards."""
    schema = None
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response({
            "total_incidents": Incident.objects.count(),
            "critical_alerts": Incident.objects.filter(severity="critical").count(),
            "failed_logins": Incident.objects.filter(event__icontains="Failed").count(),
            "unique_attack_ips": Incident.objects.values("ip").distinct().count(),
        })


class RiskAnalysisView(APIView):
    """
    POST /risk/analyze/
    
    Ad-hoc analysis of risk events using Gemini.
    Accepts an Incident-like payload and returns the AI analysis text.
    Does NOT persist the result to the DB (read-only analysis).
    """
    # APIView defaults are sufficient (JWT usually default in settings)
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = RiskAnalysisRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Construct a temporary object to satisfy analyze_incident interface
        # analyze_incident expects an object with attributes: event, severity, ip, country, attempted_email/user, details
        class MockIncident:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)
                self.id = "adhoc"
                self.attempted_email = kwargs.get("distinguished_name")
                self.user = kwargs.get("distinguished_name")

        mock_incident = MockIncident(**data)
        
        analysis = analyze_incident(mock_incident)
        
        return Response({
            "gemini_analysis": analysis or "Analysis unavailable."
        })


def csrf_failure_view(request, reason=""):
    """
    Custom CSRF failure handler that logs and returns 403.
    
    NOTE: This is called by Django's CSRF middleware, NOT by DRF.
    We must use Django's JsonResponse, not DRF Response.
    """
    from django.http import JsonResponse
    
    log_csrf_failure(request=request, reason=reason)
    return JsonResponse(
        {
            "detail": "CSRF verification failed.",
            "reason": reason
        },
        status=403,
    )
