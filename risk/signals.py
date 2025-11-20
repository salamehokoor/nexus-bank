# risk/signals.py
from datetime import timedelta, timezone
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import (
    user_logged_in,
    user_login_failed as django_login_failed,
)
from axes.signals import user_locked_out
from django.db.models import Count
from .models import Incident, LoginEvent
from .utils import get_country_from_ip, _get_ip_from_request

User = get_user_model()


# ------------------------------
# LOGIN SUCCESS (Django)
# ------------------------------
def log_login_success(sender, request, user, **kwargs):
    """
    Fired when a login succeeds.
    """
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)

    # Previous successful login (for "new country" detection)
    previous_login = (LoginEvent.objects.filter(
        user=user,
        successful=True).exclude(country="").order_by("-timestamp").first())

    # Log the successful login
    LoginEvent.objects.create(
        user=user,
        ip=ip,
        country=country,
        successful=True,
        attempted_email=getattr(user, "email", ""),
    )

    # ---- New Incident: login from new country ----
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


# ------------------------------
# LOGIN FAILED (Django) → LoginEvent + “credential stuffing”
# ------------------------------
@receiver(django_login_failed)
def log_login_failed(sender, credentials, request, **kwargs):
    """
    Fired when authentication fails (e.g. /auth/jwt/create/ with wrong password).
    Signature MUST be (sender, credentials, request, **kwargs).
    """
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)

    # What the client actually typed; you use email as login field
    attempted = credentials.get("email") or ""

    # Try to resolve it to a real user, if that email exists
    target_user = User.objects.filter(
        email=attempted).first() if attempted else None

    # Log the failed login attempt
    LoginEvent.objects.create(
        user=target_user,  # User instance or None
        ip=ip,
        country=country,
        successful=False,
        attempted_email=attempted,
    )

    # ---- New Incident: Credential stuffing suspected from IP ----
    #
    # Look back over last 10 minutes for failures from this IP
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

    # Heuristic: at least 5 failures and 3+ different emails in 10 minutes
    if total_failures >= 5 and distinct_targets >= 3:
        # Avoid spamming: only create one incident per IP per window
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


# ------------------------------
# LOCKOUT (Axes) → Incident
# ------------------------------
@receiver(user_locked_out)
def handle_user_locked_out(sender, request, username, **kwargs):
    """
    Fired when Axes locks an account (too many failed attempts).
    Here we create a high-severity Incident.
    `username` here is your login identifier (email).
    """
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)

    # username in Axes = email in your setup
    target_user = User.objects.filter(
        email=username).first() if username else None

    Incident.objects.create(
        user=target_user,
        ip=ip,
        country=country,
        event="User locked out by Axes",
        severity="critical",
        details={
            "email": username,
            "reason": "Too many failed login attempts",
        },
    )
