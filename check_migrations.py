
import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nexus.settings')
os.environ.setdefault('DJANGO_DEBUG', 'True')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    try:
        cursor.execute("SELECT app, name FROM django_migrations WHERE app='api'")
        rows = cursor.fetchall()
        print(f"APPLIED MIGRATIONS FOR 'api':")
        for row in rows:
            print(f" - {row[1]}")
    except Exception as e:
        print(f"ERROR reading django_migrations: {e}")
