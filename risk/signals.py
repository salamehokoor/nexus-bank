"""
Django signal handlers for authentication lifecycle and admin state changes.
Hooks log events to the risk module for auditing and anomaly detection.
"""
# risk/signals.py
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import (user_logged_in, user_login_failed as
                                         django_login_failed, user_logged_out)
from django.db.models.signals import pre_save, post_save
from axes.signals import user_locked_out

from .auth_logging import log_auth_event
from .account_logging import log_account_created
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
    """Capture failed login attempts and record the attempted email."""
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
    """Mark user offline after logout."""
    if user and user.is_authenticated:
        User.objects.filter(pk=user.pk).update(is_online=False)


@receiver(pre_save, sender=User)
def _cache_user_state(sender, instance, **kwargs):
    """Cache state before save to detect changes on post_save."""
    if not instance.pk:
        return
    try:
        existing = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    instance._old_is_staff = existing.is_staff
    instance._old_is_active = existing.is_active
    instance._old_password = existing.password


@receiver(post_save, sender=User)
def handle_admin_state_changes(sender, instance, created, **kwargs):
    """
    Audit admin role creation, deactivation, and password resets.
    """
    # New account created (non-admin or admin)
    if created:
        log_account_created(request=None, user=instance)

    # Admin role created/granted
    if instance.is_staff or instance.is_superuser:
        if created or not getattr(instance, "_old_is_staff",
                                  instance.is_staff):
            Incident.objects.create(
                user=instance,
                ip=None,
                country="",
                event="Admin role created",
                severity="high",
                details={"email": getattr(instance, "email", "")},
            )

    # Admin deactivated a user (active -> inactive)
    if not created and getattr(instance, "_old_is_active",
                               True) and not instance.is_active:
        Incident.objects.create(
            user=None,
            ip=None,
            country="",
            event="Admin deactivated user",
            severity="high",
            details={"email": getattr(instance, "email", "")},
        )

    # Admin/user password reset (password hash changed)
    if not created and getattr(instance, "_old_password",
                               "") != instance.password:
        Incident.objects.create(
            user=None,
            ip=None,
            country="",
            event="User password reset",
            severity="medium",
            details={"email": getattr(instance, "email", "")},
        )
