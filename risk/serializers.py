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
