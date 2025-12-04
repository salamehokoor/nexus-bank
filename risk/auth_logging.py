# risk/auth_logging.py
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count

from django.contrib.auth import get_user_model

from .models import LoginEvent, Incident
from .utils import _get_ip_from_request, get_country_from_ip
from django.contrib.auth.models import AbstractBaseUser
from typing import Optional

User = get_user_model()


def log_auth_event(
    *,
    request,
    user: Optional[AbstractBaseUser],
    successful: bool,
    source: str = "password",
    attempted_email: str = "",
    failure_reason: str = "",
) -> None:

    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)
    ua = request.META.get("HTTP_USER_AGENT", "")

    # normalize attempted email
    if not attempted_email and user is not None:
        attempted_email = getattr(user, "email", "") or ""

    # Create login event entry
    event = LoginEvent.objects.create(
        user=user,
        ip=ip,
        country=country,
        successful=successful,
        attempted_email=attempted_email,
        source=source,
        failure_reason=failure_reason,
        user_agent=ua,
    )

    # ----------------------------------------------------------------------
    # 🔹 SUCCESS SIDE
    # ----------------------------------------------------------------------
    if successful and user is not None:

        # 🔥 Mark user online
        User.objects.filter(pk=user.pk).update(is_online=True)

        Incident.objects.create(
            user=user,
            ip=ip,
            country=country,
            event="Successful login",
            severity="low",
            details={
                "source": source,
                "user_agent": ua,
            },
        )

        # Admin login audit
        if getattr(user, "is_staff", False) or getattr(user, "is_superuser",
                                                       False):
            Incident.objects.create(
                user=user,
                ip=ip,
                country=country,
                event="Admin login",
                severity="medium",
                details={
                    "source": source,
                    "user_agent": ua,
                },
            )

        # --- Detect login from new country ---
        previous_login = (LoginEvent.objects.filter(
            user=user,
            successful=True,
        ).exclude(country="").exclude(
            id=event.id).order_by("-timestamp").first())

        if previous_login and previous_login.country != country:
            Incident.objects.create(
                user=user,
                ip=ip,
                country=country,
                event="Login from new country",
                severity="medium",
                details={
                    "previous_country": previous_login.country,
                    "new_country": country,
                },
            )

        # --- Detect impossible travel / sudden country change ---
        if previous_login and previous_login.country != country:
            time_since_last_login = timezone.now() - previous_login.timestamp
            if time_since_last_login <= timedelta(hours=1):
                if not Incident.objects.filter(
                        user=user,
                        event="Impossible travel suspected",
                        timestamp__gte=previous_login.timestamp,
                ).exists():
                    Incident.objects.create(
                        user=user,
                        ip=ip,
                        country=country,
                        event="Impossible travel suspected",
                        severity="high",
                        details={
                            "previous_country": previous_login.country,
                            "new_country": country,
                            "minutes_since_last_login":
                            round(time_since_last_login.total_seconds() /
                                  60),
                            "previous_timestamp":
                            previous_login.timestamp.isoformat(),
                        },
                    )

        # --- Detect login from new device ---
        previous_device = (LoginEvent.objects.filter(
            user=user,
            successful=True,
        ).exclude(user_agent="").exclude(
            id=event.id).order_by("-timestamp").first())

        if previous_device and previous_device.user_agent != ua:
            Incident.objects.create(
                user=user,
                ip=ip,
                country=country,
                event="Login from new device",
                severity="medium",
                details={
                    "previous_user_agent": previous_device.user_agent,
                    "new_user_agent": ua,
                },
            )

        # --- Detect logins at unusual hours ---
        login_hour = timezone.now().hour
        if login_hour < 5 or login_hour > 23:
            Incident.objects.create(
                user=user,
                ip=ip,
                country=country,
                event="Login at unusual hour",
                severity="low",
                details={"hour": login_hour},
            )

        # --- Detect multiple accounts from same IP ---
        if ip:
            window_start = timezone.now() - timedelta(hours=1)
            distinct_users = (LoginEvent.objects.filter(
                ip=ip,
                successful=True,
                timestamp__gte=window_start,
            ).values("user").distinct().count())

            if distinct_users >= 5:
                if not Incident.objects.filter(
                        event="Multiple accounts from same IP",
                        timestamp__gte=window_start,
                        ip=ip,
                ).exists():
                    Incident.objects.create(
                        user=None,
                        ip=ip,
                        country=country,
                        event="Multiple accounts from same IP",
                        severity="medium",
                        details={
                            "distinct_users": distinct_users,
                        },
                    )

    # ----------------------------------------------------------------------
    # 🔹 FAILURE SIDE: Credential Stuffing
    # ----------------------------------------------------------------------
    if not successful and ip:
        window_start = timezone.now() - timedelta(minutes=10)

        recent_failures = LoginEvent.objects.filter(
            ip=ip,
            successful=False,
            timestamp__gte=window_start,
        )

        total_failures = recent_failures.count()
        distinct_targets = (recent_failures.exclude(
            attempted_email="").values("attempted_email").annotate(
                c=Count("id")).count())

        # rule: 5 failures & 3+ target accounts
        if total_failures >= 5 and distinct_targets >= 3:
            if not Incident.objects.filter(
                    ip=ip,
                    event="Credential stuffing suspected from IP",
                    timestamp__gte=window_start,
            ).exists():
                Incident.objects.create(
                    user=None,
                    ip=ip,
                    country=country,
                    event="Credential stuffing suspected from IP",
                    severity="high",
                    details={
                        "attempt_count":
                        total_failures,
                        "distinct_targets":
                        distinct_targets,
                        "emails":
                        list(
                            recent_failures.exclude(
                                attempted_email="").values_list(
                                    "attempted_email", flat=True).distinct()),
                    },
                )

        # rule: 5 failures against the same attempted email
        if attempted_email:
            user_failures = LoginEvent.objects.filter(
                attempted_email=attempted_email,
                successful=False,
                timestamp__gte=window_start,
            )
            failed_attempts = user_failures.count()

            if failed_attempts >= 5:
                if not Incident.objects.filter(
                        event="Brute-force suspected on account",
                        timestamp__gte=window_start,
                        details__email=attempted_email,
                ).exists():
                    Incident.objects.create(
                        user=user,
                        ip=ip,
                        country=country,
                        event="Brute-force suspected on account",
                        severity="high",
                        details={
                            "email": attempted_email,
                            "failed_attempts": failed_attempts,
                        },
                    )

        Incident.objects.create(
            user=user,
            ip=ip,
            country=country,
            event="Failed login attempt",
            severity="low",
            details={
                "attempted_email": attempted_email,
                "source": source,
                "failure_reason": failure_reason,
            },
        )


def log_password_reset_attempt(request, email: str) -> None:
    """
    Record a password reset request attempt.
    """
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)
    target_user = User.objects.filter(email=email).first()

    Incident.objects.create(
        user=target_user,
        ip=ip,
        country=country,
        event="Password reset requested",
        severity="medium",
        details={"email": email},
    )


def log_password_reset_success(request, user: Optional[AbstractBaseUser]) -> None:
    """
    Record successful password reset completion.
    """
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)

    Incident.objects.create(
        user=user,
        ip=ip,
        country=country,
        event="Password reset successful",
        severity="medium",
        details={"email": getattr(user, "email", "")},
    )


def log_jwt_refresh_event(
    *,
    request,
    user: Optional[AbstractBaseUser],
    successful: bool,
    failure_reason: str = "",
) -> None:
    """
    Record JWT refresh attempts (success or failure).
    """
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)

    Incident.objects.create(
        user=user if user and getattr(user, "is_authenticated", False) else None,
        ip=ip,
        country=country,
        event="JWT refresh attempt" if successful else "JWT refresh failed",
        severity="low" if successful else "medium",
        details={
            "user_agent": request.META.get("HTTP_USER_AGENT", ""),
            "failure_reason": failure_reason,
        },
    )


def log_invalid_jwt_use(
    *,
    request,
    reason: str,
    user: Optional[AbstractBaseUser] = None,
) -> None:
    """
    Record expired/invalid JWT usage outside the refresh endpoint.
    """
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)

    Incident.objects.create(
        user=user if user and getattr(user, "is_authenticated", False) else None,
        ip=ip,
        country=country,
        event="Expired or invalid JWT use",
        severity="medium",
        details={
            "reason": reason,
            "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        },
    )


def log_role_change_attempt(
    *,
    request,
    actor: Optional[AbstractBaseUser],
    target_user: Optional[AbstractBaseUser],
    new_role: str,
    allowed: bool,
) -> None:
    """
    Record attempts to change a user's role (e.g., elevating to admin).
    """
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)

    Incident.objects.create(
        user=actor if actor and getattr(actor, "is_authenticated", False) else None,
        ip=ip,
        country=country,
        event="Role change attempt",
        severity="high" if not allowed else "medium",
        details={
            "actor": getattr(actor, "email", None),
            "target": getattr(target_user, "email", None),
            "new_role": new_role,
            "allowed": allowed,
        },
    )


def log_failed_otp(
    *,
    request,
    user: Optional[AbstractBaseUser],
    reason: str = "",
) -> None:
    """
    Record failed OTP validations (e.g., MFA challenge failures).
    """
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)

    Incident.objects.create(
        user=user if user and getattr(user, "is_authenticated", False) else None,
        ip=ip,
        country=country,
        event="Failed OTP verification",
        severity="medium",
        details={
            "reason": reason,
            "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        },
    )


def log_rate_limit_triggered(
    *,
    request,
    scope: str,
    blocked: bool = False,
) -> None:
    """
    Record when a rate limit is hit or a request is blocked by throttle.
    """
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)
    user = getattr(request, "user", None)

    Incident.objects.create(
        user=user if user and getattr(user, "is_authenticated", False) else None,
        ip=ip,
        country=country,
        event="Request blocked by throttle" if blocked else "Rate limit triggered",
        severity="medium" if blocked else "low",
        details={
            "scope": scope,
            "path": getattr(request, "path", ""),
            "method": getattr(request, "method", ""),
        },
    )


def log_suspicious_api_usage(
    *,
    request,
    reason: str,
) -> None:
    """
    Record suspicious API usage patterns flagged elsewhere.
    """
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)
    user = getattr(request, "user", None)

    Incident.objects.create(
        user=user if user and getattr(user, "is_authenticated", False) else None,
        ip=ip,
        country=country,
        event="Suspicious API usage",
        severity="medium",
        details={
            "reason": reason,
            "path": getattr(request, "path", ""),
            "method": getattr(request, "method", ""),
        },
    )


def log_unauthorized_api_key(
    *,
    request,
    provided_key: str = "",
) -> None:
    """
    Record attempts to use unauthorized/invalid API keys.
    """
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)

    Incident.objects.create(
        user=None,
        ip=ip,
        country=country,
        event="Unauthorized API key attempt",
        severity="high",
        details={
            "provided_key": provided_key,
            "path": getattr(request, "path", ""),
        },
    )


def log_csrf_failure(
    *,
    request,
    reason: str = "",
) -> None:
    """
    Record CSRF validation failures (for any custom views/forms).
    """
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)
    user = getattr(request, "user", None)

    Incident.objects.create(
        user=user if user and getattr(user, "is_authenticated", False) else None,
        ip=ip,
        country=country,
        event="CSRF failure",
        severity="medium",
        details={
            "reason": reason,
            "path": getattr(request, "path", ""),
            "method": getattr(request, "method", ""),
        },
    )


def log_cloud_provider_alert(
    *,
    provider: str,
    alert_type: str,
    resource: str,
    severity: str = "medium",
    details: Optional[dict] = None,
) -> None:
    """
    Record alerts propagated from cloud providers (e.g., WAF, IAM anomalies).
    """
    Incident.objects.create(
        user=None,
        ip=None,
        country="",
        event=f"{provider} alert: {alert_type}",
        severity=severity,
        details={
            "resource": resource,
            **(details or {}),
        },
    )


def log_infrastructure_event(
    *,
    event: str,
    severity: str = "medium",
    details: Optional[dict] = None,
) -> None:
    """
    Generic hook for backend/infrastructure incidents.
    """
    Incident.objects.create(
        user=None,
        ip=None,
        country="",
        event=event,
        severity=severity,
        details=details or {},
    )
