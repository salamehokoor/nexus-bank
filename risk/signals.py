# risk/signals.py
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from .models import LoginEvent, Incident


def _get_ip_from_request(request):
    if not request:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@receiver(user_logged_in)
def log_login_success(sender, request, user, **kwargs):
    ip = _get_ip_from_request(request)

    LoginEvent.objects.create(
        user=user,
        ip=ip,
        country="",  # you can fill this later with IP→country
        successful=True,
    )


@receiver(user_login_failed)
def log_login_failed(sender, credentials, request, **kwargs):
    ip = _get_ip_from_request(request)

    LoginEvent.objects.create(
        user=None,
        ip=ip,
        country="",
        successful=False,
    )

    # optional: also create an Incident
    Incident.objects.create(
        user=None,
        ip=ip,
        country="",
        event="Failed login attempt",
        severity="low",
    )
