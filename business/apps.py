"""
App config for business metrics; wires signal handlers on ready.
"""
# business/apps.py
from django.apps import AppConfig


class BusinessConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "business"

    def ready(self):
        # Import signals so Django connects them
        import business.signals  # noqa: F401
