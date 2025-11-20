from rest_framework import serializers
from .models import Incident, LoginEvent


class UnlockIPSerializer(serializers.Serializer):
    ip = serializers.IPAddressField(required=True)


class IncidentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Incident
        fields = "__all__"


class LoginEventSerializer(serializers.ModelSerializer):

    class Meta:
        model = LoginEvent
        fields = "__all__"
