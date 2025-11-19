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
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    ip = models.GenericIPAddressField(null=True, blank=True)
    country = models.CharField(max_length=100, blank=True)
    successful = models.BooleanField(default=False)

    # NEW: what the client typed as email
    attempted_email = models.EmailField(blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.ip} - {self.timestamp}"
