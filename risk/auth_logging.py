# risk/auth_logging.py
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count

from django.contrib.auth import get_user_model

from .models import LoginEvent, Incident
from .utils import _get_ip_from_request, get_country_from_ip
from django.contrib.auth.models import AbstractBaseUser
from typing import Optional

User = get_user_model()


def log_auth_event(
    *,
    request,
    user: Optional[AbstractBaseUser],
    successful: bool,
    source: str = "password",
    attempted_email: str = "",
    failure_reason: str = "",
) -> None:

    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)

    # normalize attempted email
    if not attempted_email and user is not None:
        attempted_email = getattr(user, "email", "") or ""

    # Create login event entry
    event = LoginEvent.objects.create(
        user=user,
        ip=ip,
        country=country,
        successful=successful,
        attempted_email=attempted_email,
        source=source,
        failure_reason=failure_reason,
    )

    # ----------------------------------------------------------------------
    # 🔹 SUCCESS SIDE
    # ----------------------------------------------------------------------
    if successful and user is not None:

        # 🔥 Mark user online
        User.objects.filter(pk=user.pk).update(is_online=True)

        # --- Detect login from new country ---
        previous_login = (LoginEvent.objects.filter(
            user=user,
            successful=True,
        ).exclude(country="").exclude(
            id=event.id).order_by("-timestamp").first())

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

    # ----------------------------------------------------------------------
    # 🔹 FAILURE SIDE: Credential Stuffing
    # ----------------------------------------------------------------------
    if not successful and ip:
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

        # rule: 5 failures & 3+ target accounts
        if total_failures >= 5 and distinct_targets >= 3:
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
