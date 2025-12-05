"""
Middleware for logging authorization, API key misuse, and server errors.
Each middleware records incidents without changing response handling.
"""

from typing import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from .models import Incident
from .utils import _get_ip_from_request, get_country_from_ip
from .auth_logging import (log_unauthorized_api_key, log_suspicious_api_usage,
                           log_infrastructure_event)


class AuthorizationLoggingMiddleware:
    """
    Logs authorization/permission incidents such as 401/403 responses and
    admin-area probes.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        status = response.status_code
        path = request.path or ""
        ip = _get_ip_from_request(request)
        country = get_country_from_ip(ip)
        user = getattr(request, "user", None)
        is_authenticated = bool(user
                                and getattr(user, "is_authenticated", False))

        # Unauthorized access attempts (401)
        if status == 401:
            Incident.objects.create(
                user=user if is_authenticated else None,
                ip=ip,
                country=country,
                event="Unauthorized access attempt",
                severity="medium",
                details={
                    "path": path,
                    "method": request.method,
                },
            )

        # Forbidden access (403)
        if status == 403:
            Incident.objects.create(
                user=user if is_authenticated else None,
                ip=ip,
                country=country,
                event="Forbidden access",
                severity="medium",
                details={
                    "path": path,
                    "method": request.method,
                },
            )

        # Admin-only area probes (path contains /admin/) when user lacks staff
        if "/admin" in path.lower() and (not is_authenticated or
                                         not getattr(user, "is_staff", False)):
            Incident.objects.create(
                user=user if is_authenticated else None,
                ip=ip,
                country=country,
                event="Admin area access attempt",
                severity="high",
                details={
                    "path": path,
                    "method": request.method,
                    "status": status,
                },
            )

        return response


class ApiKeyLoggingMiddleware:
    """
    Logs unauthorized API key attempts and suspicious unauthenticated write
    requests to API endpoints.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        path = request.path or ""
        api_key = request.META.get("HTTP_X_API_KEY")
        allowed_keys = [
            k for k in getattr(settings, "RISK_ALLOWED_API_KEYS", []) if k
        ]

        if api_key and (api_key not in allowed_keys):
            log_unauthorized_api_key(request=request, provided_key=api_key)

        response = self.get_response(request)

        # Suspicious API usage: unauthenticated write to /api/
        user = getattr(request, "user", None)
        if path.startswith("/api") and request.method not in ("GET", "HEAD",
                                                              "OPTIONS"):
            if not user or not getattr(user, "is_authenticated", False):
                log_suspicious_api_usage(
                    request=request,
                    reason="Unauthenticated write attempt to API",
                )

        return response


class ErrorLoggingMiddleware:
    """
    Logs unhandled exceptions and 5xx responses as infrastructure incidents.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        try:
            response = self.get_response(request)
        except Exception as exc:
            log_infrastructure_event(
                event="Server error (exception)",
                severity="critical",
                details={
                    "path": getattr(request, "path", ""),
                    "method": getattr(request, "method", ""),
                    "error": repr(exc),
                },
            )
            raise

        if response.status_code >= 500:
            log_infrastructure_event(
                event="Server error (5xx)",
                severity="critical",
                details={
                    "path": getattr(request, "path", ""),
                    "method": getattr(request, "method", ""),
                    "status": response.status_code,
                },
            )

        return response
