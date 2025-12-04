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
    Generic admin action logger for critical operations.
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
