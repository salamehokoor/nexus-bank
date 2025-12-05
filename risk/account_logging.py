"""
Account lifecycle logging (creation, profile updates, contact changes).
Writes events to the shared Incident table for audit and anomaly detection.
"""

from typing import Optional, Dict, Any

from django.contrib.auth.models import AbstractBaseUser

from .models import Incident
from .utils import _get_ip_from_request, get_country_from_ip


def _base_details(request):
    """Return IP and country tuple derived from request (may be None)."""
    ip = _get_ip_from_request(request) if request is not None else None
    return ip, get_country_from_ip(ip)


def log_account_created(request, user: AbstractBaseUser) -> None:
    """
    Record creation of a new account for audit purposes.

    Args:
        request: Django request (optional) for IP context.
        user: Newly created user.
    """
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
    """
    Record an attempt to close an account, including whether it was allowed.

    Args:
        request: Django request for IP context.
        user: User requesting closure (may be unauthenticated).
        reason: Freeform reason for closure.
        allowed: Whether the closure was permitted.
    """
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
    """
    Record profile updates.

    Args:
        request: Django request for IP context.
        user: User performing the update.
        changes: Dict of updated fields (avoid including secrets).
    """
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
    """
    Record a request to change email.

    Args:
        request: Django request for IP context.
        user: User requesting the change.
        new_email: Target email address.
    """
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
    """
    Record a request to change phone number.

    Args:
        request: Django request for IP context.
        user: User requesting the change.
        new_phone: Target phone number (avoid storing OTPs/secrets).
    """
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
    """
    Record enabling/disabling of 2FA.

    Args:
        request: Django request for IP context.
        user: User performing the change.
        enabled: Whether 2FA is now on.
    """
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
    """
    Record registration of a new device for a user.

    Args:
        request: Django request to derive IP and user agent.
        user: User adding the device.
        device_id: Device identifier (do not include secrets).
        user_agent: Optional user agent override.
    """
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
