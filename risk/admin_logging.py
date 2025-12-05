"""
Utilities for auditing privileged/admin actions.
Keeps admin activity in the shared Incident table for traceability.
"""

from typing import Optional

from django.contrib.auth.models import AbstractBaseUser

from .models import Incident
from .utils import _get_ip_from_request, get_country_from_ip


def log_admin_action(
    *,
    request=None,
    actor: Optional[AbstractBaseUser],
    event: str,
    details: dict,
    severity: str = "medium",
) -> None:
    """
    Log an admin/privileged action to Incident.

    Args:
        request: Django request for IP/context (may be None for system tasks).
        actor: Authenticated admin performing the action.
        event: Short event label.
        details: Structured metadata describing the action (avoid secrets).
        severity: One of the Incident severity levels.
    """
    ip = _get_ip_from_request(request) if request is not None else None
    country = get_country_from_ip(ip) if ip else ""

    Incident.objects.create(
        user=actor
        if actor and getattr(actor, "is_authenticated", False) else None,
        ip=ip,
        country=country,
        event=event,
        severity=severity,
        details=details,
    )
