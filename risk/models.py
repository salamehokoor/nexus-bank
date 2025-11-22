from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Incident(models.Model):
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

    # NEW: what email was used in the attempt (success or fail)
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
    source = models.CharField(max_length=20,
                              choices=SOURCE_CHOICES,
                              default="password")
    failure_reason = models.CharField(max_length=255, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "OK" if self.successful else "FAIL"
        return f"[{status}] {self.attempted_email or self.user} @ {self.ip}"
