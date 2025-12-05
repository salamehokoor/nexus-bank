"""
Admin registrations for risk monitoring models.
Provides searchable, filterable listings for incidents and login events.
"""

from django.contrib import admin

from .models import Incident, LoginEvent


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    """Read-only-oriented view of incidents with search and filters."""
    list_display = (
        "id",
        "event",
        "severity",
        "attempted_email",
        "user",
        "ip",
        "country",
        "timestamp",
    )
    list_filter = ("severity", "country", "event", "timestamp")
    search_fields = (
        "event",
        "attempted_email",
        "user__email",
        "ip",
        "details",
    )
    ordering = ("-timestamp",)
    readonly_fields = ("timestamp",)


@admin.register(LoginEvent)
class LoginEventAdmin(admin.ModelAdmin):
    """Admin listing for login attempts with filtering and search."""
    list_display = (
        "id",
        "attempted_email",
        "user",
        "successful",
        "source",
        "ip",
        "country",
        "timestamp",
    )
    list_filter = ("successful", "source", "country", "timestamp")
    search_fields = (
        "attempted_email",
        "user__email",
        "ip",
        "user_agent",
        "failure_reason",
    )
    ordering = ("-timestamp",)
    readonly_fields = ("timestamp",)
