from typing import Optional, Dict, Any

from django.contrib.auth.models import AbstractBaseUser

from .models import Incident
from .utils import _get_ip_from_request, get_country_from_ip


def _base_details(request):
    ip = _get_ip_from_request(request) if request is not None else None
    return ip, get_country_from_ip(ip)


def log_account_created(request, user: AbstractBaseUser) -> None:
    ip, country = _base_details(request)
    Incident.objects.create(
        user=user,
        ip=ip,
        country=country,
        event="New account created",
        severity="medium",
        details={"email": getattr(user, "email", "")},
    )


def log_account_closure_attempt(
    request,
    user: Optional[AbstractBaseUser],
    reason: str = "",
    allowed: bool = False,
) -> None:
    ip, country = _base_details(request)
    Incident.objects.create(
        user=user if user and user.is_authenticated else None,
        ip=ip,
        country=country,
        event="Account closure attempt",
        severity="high" if not allowed else "medium",
        details={
            "email": getattr(user, "email", "") if user else "",
            "reason": reason,
            "allowed": allowed,
        },
    )


def log_profile_update(
    request,
    user: AbstractBaseUser,
    changes: Optional[Dict[str, Any]] = None,
) -> None:
    ip, country = _base_details(request)
    Incident.objects.create(
        user=user,
        ip=ip,
        country=country,
        event="Profile updated",
        severity="low",
        details=changes or {},
    )


def log_email_change_request(request, user: AbstractBaseUser,
                             new_email: str) -> None:
    ip, country = _base_details(request)
    Incident.objects.create(
        user=user,
        ip=ip,
        country=country,
        event="Email change requested",
        severity="medium",
        details={
            "old_email": getattr(user, "email", ""),
            "new_email": new_email,
        },
    )


def log_phone_change_request(request, user: AbstractBaseUser,
                             new_phone: str) -> None:
    ip, country = _base_details(request)
    Incident.objects.create(
        user=user,
        ip=ip,
        country=country,
        event="Phone number change requested",
        severity="medium",
        details={
            "new_phone": new_phone,
        },
    )


def log_2fa_toggle(request, user: AbstractBaseUser, enabled: bool) -> None:
    ip, country = _base_details(request)
    Incident.objects.create(
        user=user,
        ip=ip,
        country=country,
        event="2FA status changed",
        severity="medium",
        details={
            "enabled": enabled,
        },
    )


def log_new_device_registration(
    request,
    user: AbstractBaseUser,
    device_id: str,
    user_agent: str = "",
) -> None:
    ip, country = _base_details(request)
    Incident.objects.create(
        user=user,
        ip=ip,
        country=country,
        event="New device registered",
        severity="medium",
        details={
            "device_id": device_id,
            "user_agent": user_agent
            or request.META.get("HTTP_USER_AGENT", ""),
        },
    )
