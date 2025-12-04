from typing import Optional

from django.contrib.auth.models import AbstractBaseUser

from .models import Incident


def log_admin_action(
    *,
    actor: Optional[AbstractBaseUser],
    event: str,
    details: dict,
    severity: str = "medium",
) -> None:
    """
    Generic admin action logger for critical operations.
    """
    Incident.objects.create(
        user=actor
        if actor and getattr(actor, "is_authenticated", False) else None,
        ip=None,
        country="",
        event=event,
        severity=severity,
        details=details,
    )
