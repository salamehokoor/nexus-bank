# risk/signals.py
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import (
    user_logged_in,
    user_login_failed as django_login_failed,
)
from axes.signals import user_locked_out

from .models import Incident, LoginEvent
from .utils import get_country_from_ip, _get_ip_from_request

User = get_user_model()


# ------------------------------
# LOGIN SUCCESS (Django)
# ------------------------------
@receiver(user_logged_in)
def log_login_success(sender, request, user, **kwargs):
    """
    Fired when a login succeeds (including Djoser / SimpleJWT if they call login).
    """
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)

    LoginEvent.objects.create(
        user=user,
        ip=ip,
        country=country,
        successful=True,
        attempted_email=getattr(user, "email", ""),
    )


# ------------------------------
# LOGIN FAILED (Django) → ONLY LoginEvent
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

    LoginEvent.objects.create(
        user=target_user,  # User instance or None
        ip=ip,
        country=country,
        successful=False,
        attempted_email=attempted,
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
        attempted_email=username or "",
        event=f"User locked out by Axes",
        severity="critical",
        details={
            "email": username,
            "reason": "Too many failed login attempts",
        },
    )
