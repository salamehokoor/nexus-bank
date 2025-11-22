# risk/signals.py
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import (user_logged_in, user_login_failed as
                                         django_login_failed, user_logged_out)
from axes.signals import user_locked_out

from .auth_logging import log_auth_event
from .models import Incident
from .utils import _get_ip_from_request, get_country_from_ip

User = get_user_model()


# ------------------------------
# LOGIN SUCCESS (Django / admin / allauth)
# ------------------------------
@receiver(user_logged_in)
def handle_user_logged_in(sender, request, user, **kwargs):
    """
    Fired for Django login() calls:
    - Admin login
    - allauth account login
    - any view that uses django.contrib.auth.login
    """
    log_auth_event(
        request=request,
        user=user,
        successful=True,
        source="password",  # or "google" if you want to branch later
    )


# ------------------------------
# LOGIN FAILED (Django) – any auth backend that calls authenticate()
# ------------------------------
@receiver(django_login_failed)
def handle_login_failed(sender, credentials, request, **kwargs):
    attempted = (credentials.get("email") or credentials.get("username") or "")

    # Try to map attempted email to a real user (for context)
    user = User.objects.filter(email=attempted).first() if attempted else None

    log_auth_event(
        request=request,
        user=user,
        successful=False,
        source="password",
        attempted_email=attempted,
        failure_reason="invalid_credentials",
    )


# ------------------------------
# LOCKOUT (Axes) → Incident only
# ------------------------------
@receiver(user_locked_out)
def handle_user_locked_out(sender, request, username, **kwargs):
    """
    Axes lockout; we don't need a LoginEvent here, just a high-severity Incident.
    username == email in your setup.
    """
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)

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


@receiver(user_logged_out)
def mark_user_offline(sender, request, user, **kwargs):
    if user and user.is_authenticated:
        User.objects.filter(pk=user.pk).update(is_online=False)
