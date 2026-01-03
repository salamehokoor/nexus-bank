"""
Comprehensive tests for the Risk module.

Tests cover:
- Middleware (authorization, API key, error logging)
- Signals (authentication events, admin alerts)
- Models (Incident, LoginEvent)
- Utility functions (IP extraction, country lookup)
- Throttling mechanisms
"""

from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase, RequestFactory, override_settings
from django.http import HttpResponse
from rest_framework.test import APIClient, APITestCase
from rest_framework import status

from .models import Incident, LoginEvent
from .utils import _get_ip_from_request, _is_public_ip, get_country_from_ip
from .middleware import AuthorizationLoggingMiddleware, ApiKeyLoggingMiddleware, ErrorLoggingMiddleware

User = get_user_model()


# =============================================================================
# MODEL TESTS
# =============================================================================

class IncidentModelTests(TestCase):
    """Tests for the Incident model."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="testuser@example.com",
            password="testpass123"
        )

    def test_create_incident_with_all_fields(self):
        """Test creating an incident with all fields populated."""
        incident = Incident.objects.create(
            user=self.user,
            ip="192.168.1.1",
            country="Jordan",
            attempted_email="test@example.com",
            event="Unauthorized access attempt",
            severity="high",
            details={"path": "/admin/", "method": "GET"}
        )
        
        self.assertIsNotNone(incident.pk)
        self.assertEqual(incident.user, self.user)
        self.assertEqual(incident.ip, "192.168.1.1")
        self.assertEqual(incident.country, "Jordan")
        self.assertEqual(incident.event, "Unauthorized access attempt")
        self.assertEqual(incident.severity, "high")
        self.assertEqual(incident.details["path"], "/admin/")

    def test_create_incident_without_user(self):
        """Test creating an incident for anonymous users."""
        incident = Incident.objects.create(
            user=None,
            ip="8.8.8.8",
            event="Anonymous probe",
            severity="low"
        )
        
        self.assertIsNone(incident.user)
        self.assertIsNotNone(incident.pk)

    def test_incident_str_representation(self):
        """Test the string representation of an incident."""
        incident = Incident.objects.create(
            event="Test event",
            severity="medium"
        )
        
        self.assertEqual(str(incident), "Test event (medium)")

    def test_incident_severity_choices(self):
        """Test all severity levels are valid."""
        severities = ["low", "medium", "high", "critical"]
        
        for severity in severities:
            incident = Incident.objects.create(
                event=f"Event with {severity} severity",
                severity=severity
            )
            self.assertEqual(incident.severity, severity)

    def test_incident_gemini_analysis_field(self):
        """Test that gemini_analysis field can be set."""
        incident = Incident.objects.create(
            event="Security breach",
            severity="critical",
            gemini_analysis="AI suggests blocking IP immediately."
        )
        
        self.assertEqual(incident.gemini_analysis, "AI suggests blocking IP immediately.")


class LoginEventModelTests(TestCase):
    """Tests for the LoginEvent model."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="loginuser@example.com",
            password="testpass123"
        )

    def test_create_successful_login_event(self):
        """Test recording a successful login."""
        event = LoginEvent.objects.create(
            user=self.user,
            ip="10.0.0.1",
            country="USA",
            successful=True,
            attempted_email="loginuser@example.com",
            source="password"
        )
        
        self.assertTrue(event.successful)
        self.assertEqual(event.source, "password")
        self.assertEqual(event.user, self.user)

    def test_create_failed_login_event(self):
        """Test recording a failed login."""
        event = LoginEvent.objects.create(
            user=None,
            ip="192.168.1.100",
            successful=False,
            attempted_email="nonexistent@example.com",
            failure_reason="invalid_credentials",
            source="password"
        )
        
        self.assertFalse(event.successful)
        self.assertEqual(event.failure_reason, "invalid_credentials")
        self.assertIsNone(event.user)

    def test_login_event_str_representation_success(self):
        """Test string representation for successful login."""
        event = LoginEvent.objects.create(
            user=self.user,
            ip="10.0.0.1",
            successful=True,
            attempted_email="loginuser@example.com"
        )
        
        self.assertIn("[OK]", str(event))
        self.assertIn("10.0.0.1", str(event))

    def test_login_event_str_representation_failure(self):
        """Test string representation for failed login."""
        event = LoginEvent.objects.create(
            ip="10.0.0.1",
            successful=False,
            attempted_email="failed@example.com"
        )
        
        self.assertIn("[FAIL]", str(event))

    def test_login_event_sources(self):
        """Test all login sources are valid."""
        sources = ["password", "google", "other"]
        
        for source in sources:
            event = LoginEvent.objects.create(
                successful=True,
                source=source
            )
            self.assertEqual(event.source, source)

    def test_login_event_with_user_agent(self):
        """Test storing user agent information."""
        event = LoginEvent.objects.create(
            user=self.user,
            successful=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        self.assertIn("Mozilla", event.user_agent)


# =============================================================================
# UTILITY FUNCTION TESTS
# =============================================================================

class UtilityFunctionTests(TestCase):
    """Tests for risk utility functions."""

    def test_get_ip_from_request_xff_header(self):
        """Test IP extraction from X-Forwarded-For header."""
        factory = RequestFactory()
        request = factory.get("/", HTTP_X_FORWARDED_FOR="203.0.113.1, 198.51.100.1")
        
        ip = _get_ip_from_request(request)
        
        self.assertEqual(ip, "203.0.113.1")

    def test_get_ip_from_request_remote_addr(self):
        """Test IP extraction from REMOTE_ADDR."""
        factory = RequestFactory()
        request = factory.get("/")
        request.META["REMOTE_ADDR"] = "192.0.2.1"
        
        ip = _get_ip_from_request(request)
        
        self.assertEqual(ip, "192.0.2.1")

    def test_get_ip_from_request_none(self):
        """Test IP extraction with None request."""
        ip = _get_ip_from_request(None)
        
        self.assertIsNone(ip)

    def test_is_public_ip_private(self):
        """Test that private IPs are identified correctly."""
        private_ips = [
            "192.168.1.1",
            "10.0.0.1",
            "172.16.0.1",
            "127.0.0.1"
        ]
        
        for ip in private_ips:
            self.assertFalse(_is_public_ip(ip), f"{ip} should be private")

    def test_is_public_ip_public(self):
        """Test that public IPs are identified correctly."""
        # Use truly global IPs (not reserved/documentation ranges like 203.0.113.0/24 TEST-NET-3)
        public_ips = [
            "8.8.8.8",       # Google DNS
            "1.1.1.1",       # Cloudflare DNS
            "142.250.80.46"  # google.com
        ]
        
        for ip in public_ips:
            self.assertTrue(_is_public_ip(ip), f"{ip} should be public")

    def test_is_public_ip_invalid(self):
        """Test that invalid IPs return False."""
        invalid_ips = [
            "not-an-ip",
            "256.256.256.256",
            "",
            "192.168.1.999"
        ]
        
        for ip in invalid_ips:
            self.assertFalse(_is_public_ip(ip), f"{ip} should be invalid")

    def test_get_country_from_ip_private(self):
        """Test that private IPs return empty country."""
        country = get_country_from_ip("192.168.1.1")
        
        self.assertEqual(country, "")

    def test_get_country_from_ip_empty(self):
        """Test that empty IP returns empty country."""
        country = get_country_from_ip("")
        
        self.assertEqual(country, "")


# =============================================================================
# MIDDLEWARE TESTS
# =============================================================================

class AuthorizationLoggingMiddlewareTests(TestCase):
    """Tests for AuthorizationLoggingMiddleware."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="middleware@example.com",
            password="testpass123"
        )
        
    def _get_middleware(self, response_status=200):
        """Create middleware with a mock response."""
        def get_response(request):
            response = HttpResponse()
            response.status_code = response_status
            return response
        return AuthorizationLoggingMiddleware(get_response)

    def test_middleware_logs_401_unauthorized(self):
        """Test that 401 responses are logged as incidents."""
        middleware = self._get_middleware(response_status=401)
        request = self.factory.get("/api/accounts")
        request.user = None
        
        initial_count = Incident.objects.count()
        middleware(request)
        
        self.assertEqual(Incident.objects.count(), initial_count + 1)
        incident = Incident.objects.latest("timestamp")
        self.assertEqual(incident.event, "Unauthorized access attempt")
        self.assertEqual(incident.severity, "medium")

    def test_middleware_logs_403_forbidden(self):
        """Test that 403 responses are logged as incidents."""
        middleware = self._get_middleware(response_status=403)
        # Use a path that doesn't contain /admin to avoid triggering both
        # "Forbidden access" AND "Admin area access attempt"
        request = self.factory.get("/api/accounts/")
        request.user = self.user
        
        initial_count = Incident.objects.count()
        middleware(request)
        
        # At least one new incident should be created
        self.assertGreater(Incident.objects.count(), initial_count)
        incident = Incident.objects.latest("timestamp")
        self.assertEqual(incident.event, "Forbidden access")

    def test_middleware_skips_admin_urls(self):
        """Test that admin URLs are skipped to prevent loops."""
        middleware = self._get_middleware(response_status=401)
        request = self.factory.get("/admin/login/")
        request.user = None
        
        initial_count = Incident.objects.count()
        middleware(request)
        
        # Should not create additional incidents for admin paths
        self.assertEqual(Incident.objects.count(), initial_count)

    def test_middleware_logs_admin_area_probe(self):
        """Test that non-staff accessing admin-like paths is logged."""
        middleware = self._get_middleware(response_status=200)
        request = self.factory.get("/api/admin/users/1/block/")
        request.user = self.user  # Regular user, not staff
        
        middleware(request)
        
        # Check for admin area access attempt
        incidents = Incident.objects.filter(event="Admin area access attempt")
        self.assertTrue(incidents.exists())


class ApiKeyLoggingMiddlewareTests(TestCase):
    """Tests for ApiKeyLoggingMiddleware."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="apikey@example.com",
            password="testpass123"
        )

    def _get_middleware(self, response_status=200):
        """Create middleware with a mock response."""
        def get_response(request):
            response = HttpResponse()
            response.status_code = response_status
            return response
        return ApiKeyLoggingMiddleware(get_response)

    @override_settings(RISK_ALLOWED_API_KEYS=["valid-key-123"])
    def test_middleware_logs_invalid_api_key(self):
        """Test that invalid API keys are logged."""
        middleware = self._get_middleware()
        request = self.factory.get("/api/accounts", HTTP_X_API_KEY="invalid-key")
        request.user = None
        
        initial_count = Incident.objects.count()
        middleware(request)
        
        # Should log the unauthorized API key
        self.assertGreater(Incident.objects.count(), initial_count)

    def test_middleware_skips_admin_urls(self):
        """Test that admin URLs are skipped."""
        middleware = self._get_middleware()
        request = self.factory.get("/admin/", HTTP_X_API_KEY="some-key")
        request.user = None
        
        initial_count = Incident.objects.count()
        middleware(request)
        
        self.assertEqual(Incident.objects.count(), initial_count)


class ErrorLoggingMiddlewareTests(TestCase):
    """Tests for ErrorLoggingMiddleware."""

    def setUp(self):
        self.factory = RequestFactory()

    def _get_middleware(self, response_status=200, raise_exception=False):
        """Create middleware with a mock response."""
        def get_response(request):
            if raise_exception:
                raise ValueError("Test exception")
            response = HttpResponse()
            response.status_code = response_status
            return response
        return ErrorLoggingMiddleware(get_response)

    def test_middleware_logs_5xx_errors(self):
        """Test that 5xx errors are logged."""
        middleware = self._get_middleware(response_status=500)
        request = self.factory.get("/api/test")
        
        initial_count = Incident.objects.count()
        middleware(request)
        
        self.assertGreater(Incident.objects.count(), initial_count)
        incident = Incident.objects.latest("timestamp")
        self.assertEqual(incident.event, "Server error (5xx)")
        self.assertEqual(incident.severity, "critical")

    def test_middleware_logs_exceptions(self):
        """Test that unhandled exceptions are logged."""
        middleware = self._get_middleware(raise_exception=True)
        request = self.factory.get("/api/test")
        
        initial_count = Incident.objects.count()
        
        with self.assertRaises(ValueError):
            middleware(request)
        
        self.assertGreater(Incident.objects.count(), initial_count)
        incident = Incident.objects.latest("timestamp")
        self.assertEqual(incident.event, "Server error (exception)")
        self.assertEqual(incident.severity, "critical")

    def test_middleware_skips_admin_urls(self):
        """Test that admin URLs are skipped."""
        middleware = self._get_middleware(response_status=500)
        request = self.factory.get("/admin/some-error/")
        
        initial_count = Incident.objects.count()
        middleware(request)
        
        self.assertEqual(Incident.objects.count(), initial_count)


# =============================================================================
# SIGNAL TESTS
# =============================================================================

class AuthenticationSignalTests(TransactionTestCase):
    """Tests for authentication-related signals."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="signal@example.com",
            password="testpass123"
        )

    def test_user_locked_out_creates_incident(self):
        """Test that Axes lockout creates a critical incident."""
        from axes.signals import user_locked_out
        from django.test import RequestFactory
        
        factory = RequestFactory()
        request = factory.post("/auth/login/init/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        
        initial_count = Incident.objects.filter(
            event="User locked out by Axes"
        ).count()
        
        # Manually trigger the signal
        user_locked_out.send(
            sender=None,
            request=request,
            username=self.user.email
        )
        
        self.assertGreater(
            Incident.objects.filter(event="User locked out by Axes").count(),
            initial_count
        )


class IncidentNotificationSignalTests(TransactionTestCase):
    """Tests for incident notification signals."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="adminpass",
            is_staff=True
        )
        self.regular_user = User.objects.create_user(
            email="user@example.com",
            password="userpass"
        )

    def test_high_severity_incident_creates_admin_notification(self):
        """Test that high severity incidents notify admins."""
        from api.models import Notification
        
        initial_count = Notification.objects.filter(
            user=self.admin_user,
            notification_type="ADMIN_ALERT"
        ).count()
        
        Incident.objects.create(
            event="High severity test event",
            severity="high"
        )
        
        self.assertGreater(
            Notification.objects.filter(
                user=self.admin_user,
                notification_type="ADMIN_ALERT"
            ).count(),
            initial_count
        )

    def test_low_severity_incident_does_not_notify(self):
        """Test that low severity incidents don't trigger notifications."""
        from api.models import Notification
        
        initial_count = Notification.objects.filter(
            notification_type="ADMIN_ALERT"
        ).count()
        
        Incident.objects.create(
            event="Low severity test event",
            severity="low"
        )
        
        # Low severity should not create admin alerts
        self.assertEqual(
            Notification.objects.filter(
                notification_type="ADMIN_ALERT"
            ).count(),
            initial_count
        )


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class RiskIntegrationTests(APITestCase):
    """Integration tests for risk module endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            email="risk_admin@example.com",
            password="adminpass",
            is_staff=True,
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            email="risk_user@example.com",
            password="userpass"
        )

    def test_unauthorized_api_access_logged(self):
        """Test that unauthorized API access is logged."""
        initial_count = Incident.objects.count()
        
        # Make unauthenticated request to protected endpoint
        response = self.client.get("/accounts")
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        # Incident should be created by middleware
        self.assertGreater(Incident.objects.count(), initial_count)

    def test_failed_login_creates_login_event(self):
        """Test that failed login attempts are recorded."""
        initial_count = LoginEvent.objects.count()
        
        # Attempt login with wrong password
        response = self.client.post("/auth/login/init/", {
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        })
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        # LoginEvent should be created
        self.assertGreater(LoginEvent.objects.count(), initial_count)
