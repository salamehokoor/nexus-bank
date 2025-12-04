from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.db.models import Sum, Avg
from django.utils import timezone

from api.models import Transaction
from .models import Incident, LoginEvent
from .utils import _get_ip_from_request, get_country_from_ip


def log_transaction_event(
        *,
        request,
        user,
        transaction: Transaction,
        large_txn_threshold: Decimal = Decimal("10000.00"),
        rapid_transfer_threshold: int = 5,
        velocity_count_threshold: int = 10,
        velocity_amount_threshold: Decimal = Decimal("50000.00"),
) -> None:
    """
    Log transaction anomalies into Incident.
    """
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)

    receiver_account = getattr(transaction, "receiver_account", None)
    txn_hour = timezone.now().hour

    # --- Large transaction above threshold ---
    if transaction.amount >= large_txn_threshold:
        Incident.objects.create(
            user=user,
            ip=ip,
            country=country,
            event="Large transaction above threshold",
            severity="medium",
            details={
                "transaction_id": transaction.id,
                "amount": str(transaction.amount),
                "threshold": str(large_txn_threshold),
            },
        )

    # --- Unusual transaction size vs user history (30d avg * 5x) ---
    thirty_days_ago = timezone.now() - timedelta(days=30)
    avg_amount = Transaction.objects.filter(
        sender_account__user=user,
        created_at__gte=thirty_days_ago,
    ).aggregate(avg=Avg("amount")).get("avg")
    if avg_amount:
        if transaction.amount >= avg_amount * 5:
            Incident.objects.create(
                user=user,
                ip=ip,
                country=country,
                event="Unusual transaction size",
                severity="medium",
                details={
                    "transaction_id": transaction.id,
                    "amount": str(transaction.amount),
                    "average_30d": str(avg_amount),
                },
            )

    # --- First transfer to this beneficiary ---
    if receiver_account:
        has_prior = Transaction.objects.filter(
            sender_account__user=user,
            receiver_account=receiver_account,
        ).exclude(pk=transaction.pk).exists()

        if not has_prior:
            Incident.objects.create(
                user=user,
                ip=ip,
                country=country,
                event="First transfer to new beneficiary",
                severity="medium",
                details={
                    "transaction_id": transaction.id,
                    "receiver_account": str(receiver_account),
                },
            )

    # --- Multiple transfers in short window ---
    window_start = timezone.now() - timedelta(minutes=5)
    recent_count = Transaction.objects.filter(
        sender_account__user=user,
        created_at__gte=window_start,
    ).count()

    if recent_count >= rapid_transfer_threshold:
        if not Incident.objects.filter(
                event="Multiple transfers in short window",
                timestamp__gte=window_start,
                user=user,
        ).exists():
            Incident.objects.create(
                user=user,
                ip=ip,
                country=country,
                event="Multiple transfers in short window",
                severity="medium",
                details={
                    "transaction_id": transaction.id,
                    "count": recent_count,
                    "window_minutes": 5,
                },
            )

    # --- Suspicious velocity pattern (higher volume/count in 15m) ---
    velocity_window = timezone.now() - timedelta(minutes=15)
    velocity_qs = Transaction.objects.filter(
        sender_account__user=user,
        created_at__gte=velocity_window,
    )
    velocity_count = velocity_qs.count()
    velocity_amount = velocity_qs.aggregate(
        total=Sum("amount")).get("total") or Decimal("0")

    if velocity_count >= velocity_count_threshold or velocity_amount >= velocity_amount_threshold:
        if not Incident.objects.filter(
                event="Suspicious transaction velocity",
                timestamp__gte=velocity_window,
                user=user,
        ).exists():
            Incident.objects.create(
                user=user,
                ip=ip,
                country=country,
                event="Suspicious transaction velocity",
                severity="high",
                details={
                    "transaction_id": transaction.id,
                    "count_15m": velocity_count,
                    "amount_15m": str(velocity_amount),
                    "count_threshold": velocity_count_threshold,
                    "amount_threshold": str(velocity_amount_threshold),
                },
            )

    # --- Transactions at unusual hours ---
    if txn_hour < 5:
        Incident.objects.create(
            user=user,
            ip=ip,
            country=country,
            event="Transaction at unusual hour",
            severity="low",
            details={
                "hour": txn_hour,
                "transaction_id": transaction.id,
            },
        )

    # --- Blacklisted IP check ---
    blacklisted_ips = getattr(settings, "RISK_BLACKLISTED_IPS", [])
    if ip and ip in blacklisted_ips:
        Incident.objects.create(
            user=user,
            ip=ip,
            country=country,
            event="Transaction from blacklisted IP",
            severity="high",
            details={
                "transaction_id": transaction.id,
            },
        )

    # --- Tor/VPN heuristic based on headers ---
    via = (request.META.get("HTTP_VIA", "")
           or request.META.get("HTTP_X_FORWARDED_FOR", "")
           or request.META.get("HTTP_TOR_EXIT", "")).lower()
    if "tor" in via or "vpn" in via:
        Incident.objects.create(
            user=user,
            ip=ip,
            country=country,
            event="Transaction via anonymizer (Tor/VPN)",
            severity="medium",
            details={
                "transaction_id": transaction.id,
                "via": via,
            },
        )

    # --- Transaction from new country right after login ---
    last_login = (LoginEvent.objects.filter(
        user=user,
        successful=True).exclude(country="").order_by("-timestamp").first())
    if last_login and last_login.country != country:
        time_since_login = timezone.now() - last_login.timestamp
        if time_since_login <= timedelta(hours=2):
            Incident.objects.create(
                user=user,
                ip=ip,
                country=country,
                event="Transaction from new country after login",
                severity="high",
                details={
                    "transaction_id":
                    transaction.id,
                    "previous_country":
                    last_login.country,
                    "new_country":
                    country,
                    "minutes_since_login":
                    round(time_since_login.total_seconds() / 60),
                },
            )


def log_failed_transfer_attempt(
    *,
    request,
    user,
    errors,
    amount: Optional[Decimal] = None,
    receiver_account: Optional[str] = None,
) -> None:
    """
    Record failed/ rejected transfer attempts (e.g., validation errors).
    """
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)

    details = {
        "errors": errors,
        "amount": str(amount) if amount is not None else None,
        "receiver_account": receiver_account,
    }

    Incident.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        ip=ip,
        country=country,
        event="Failed transfer attempt",
        severity="medium",
        details=details,
    )

    # Balance anomaly: negative/insufficient attempts
    error_text = str(errors).lower()
    if (amount is not None and amount
            < 0) or "insufficient" in error_text or "balance" in error_text:
        Incident.objects.create(
            user=user if getattr(user, "is_authenticated", False) else None,
            ip=ip,
            country=country,
            event="Balance anomaly detected",
            severity="high",
            details=details,
        )

    # Multiple failed transfers in 15 minutes
    window_start = timezone.now() - timedelta(minutes=15)
    failed_count = Incident.objects.filter(
        user=user if getattr(user, "is_authenticated", False) else None,
        event="Failed transfer attempt",
        timestamp__gte=window_start,
    ).count()
    if failed_count >= 3:
        if not Incident.objects.filter(
                event="Multiple failed transfers",
                timestamp__gte=window_start,
                user=user
                if getattr(user, "is_authenticated", False) else None,
        ).exists():
            Incident.objects.create(
                user=user
                if getattr(user, "is_authenticated", False) else None,
                ip=ip,
                country=country,
                event="Multiple failed transfers",
                severity="medium",
                details={
                    "failed_count": failed_count,
                    "window_minutes": 15,
                },
            )


def log_flagged_transaction(
    *,
    request,
    user,
    transaction: Transaction,
    reason: str,
) -> None:
    """
    Record a transaction that was flagged/rejected downstream.
    """
    ip = _get_ip_from_request(request)
    country = get_country_from_ip(ip)

    Incident.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        ip=ip,
        country=country,
        event="Transaction flagged",
        severity="medium",
        details={
            "transaction_id": transaction.id,
            "reason": reason,
            "amount": str(transaction.amount),
            "receiver_account":
            str(getattr(transaction, "receiver_account", "")),
        },
    )
