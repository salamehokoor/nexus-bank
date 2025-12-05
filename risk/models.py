"""
Core risk models for auditing authentication and transactional activity.
"""

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Incident(models.Model):
    """
    Stores security/audit incidents across the platform.
    The flexible `details` JSON captures per-event metadata without schema churn.
    """
    SEVERITY_CHOICES = (
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    )

    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    ip = models.GenericIPAddressField(null=True, blank=True)
    country = models.CharField(max_length=100, blank=True)

    # Email used during the action (may differ from authenticated user).
    attempted_email = models.EmailField(blank=True)

    event = models.CharField(max_length=255)
    severity = models.CharField(
        max_length=10,
        choices=SEVERITY_CHOICES,
        default="low",
    )
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event} ({self.severity})"


class LoginEvent(models.Model):
    """
    Records individual login attempts (success and failure) for analytics
    and anomaly detection.
    """
    SOURCE_CHOICES = (
        ("password", "Password (Djoser/JWT/Admin)"),
        ("google", "Google OAuth"),
        ("other", "Other"),
    )

    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    ip = models.GenericIPAddressField(null=True, blank=True)
    country = models.CharField(max_length=100, blank=True)

    successful = models.BooleanField(default=False)
    attempted_email = models.CharField(max_length=255,
                                       blank=True)  # what user typed
    user_agent = models.TextField(blank=True)
    source = models.CharField(max_length=20,
                              choices=SOURCE_CHOICES,
                              default="password")
    failure_reason = models.CharField(max_length=255, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "OK" if self.successful else "FAIL"
        return f"[{status}] {self.attempted_email or self.user} @ {self.ip}"
