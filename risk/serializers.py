"""
Serializers for exposing Incident and LoginEvent records via the API.
"""
from rest_framework import serializers
from .models import Incident, LoginEvent


class UnlockIPSerializer(serializers.Serializer):
    """Payload for unlocking an IP via Axes."""
    ip = serializers.IPAddressField(required=True)


class IncidentSerializer(serializers.ModelSerializer):
    """Serializer for the Incident audit model."""

    class Meta:
        model = Incident
        fields = "__all__"
        read_only_fields = ["gemini_analysis", "timestamp", "user"]


class LoginEventSerializer(serializers.ModelSerializer):
    """Serializer for LoginEvent audit model."""

    class Meta:
        model = LoginEvent
        fields = "__all__"


class RiskAnalysisRequestSerializer(serializers.Serializer):
    """
    Serializer for triggering AI analysis on a risk event.
    Accepts the standard fields found in Incident/LoginEvent.
    """
    event = serializers.CharField(required=True)
    severity = serializers.CharField(required=False, default="medium")
    ip = serializers.IPAddressField(required=False, allow_blank=True, allow_null=True)
    country = serializers.CharField(required=False, allow_blank=True)
    distinguished_name = serializers.CharField(required=False, allow_blank=True, help_text="User email or identifier")
    details = serializers.JSONField(required=False, default=dict)
