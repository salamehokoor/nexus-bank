
"""
Celery application bootstrap for Nexus.
Loads settings via the CELERY_ namespace and auto-discovers tasks.
"""
from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nexus.settings")

app = Celery("nexus")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()
