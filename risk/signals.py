# risk/signals.py
from django.dispatch import receiver
from axes.signals import user_locked_out, user_login_failed as axes_login_failed
from django.contrib.auth.signals import user_logged_in, user_login_failed as django_login_failed

from .models import Incident, LoginEvent
from .utils import get_country_from_ip


def _get_ip_from_request(request):
    if not request:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


# ------------------------------
# LOGIN SUCCESS
# ------------------------------
@receiver(user_logged_in)
def log_login_success(sender, request, user, **kwargs):
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)

    LoginEvent.objects.create(
        user=user,
        ip=ip,
        country=country,
        successful=True,
    )


# ------------------------------
# DJANGO LOGIN FAILED
# ------------------------------
@receiver(django_login_failed)
def log_login_failed(sender, credentials, request, **kwargs):
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)

    LoginEvent.objects.create(
        user=None,
        ip=ip,
        country=country,
        successful=False,
    )

    Incident.objects.create(
        user=None,
        ip=ip,
        country=country,
        event="Failed login attempt",
        severity="low",
    )


# ------------------------------
# AXES: LOCKED OUT
# ------------------------------
@receiver(user_locked_out)
def handle_user_locked_out(sender, request, username, **kwargs):
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)

    Incident.objects.create(
        user=None,
        ip=ip,
        country=country,
        event=f"User locked out by Axes (username={username})",
        severity="critical",
        details={
            "username": username,
            "reason": "Too many failed login attempts",
        },
    )


# ------------------------------
# AXES: LOGIN FAILED
# ------------------------------
@receiver(axes_login_failed)
def handle_axes_login_failed(sender, request, username, **kwargs):
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)

    Incident.objects.create(
        user=None,
        ip=ip,
        country=country,
        event="Axes detected failed login",
        severity="medium",
        details={"username": username},
    )
