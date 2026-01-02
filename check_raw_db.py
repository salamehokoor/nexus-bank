
import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nexus.settings')
os.environ.setdefault('DJANGO_DEBUG', 'True')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    try:
        cursor.execute("SELECT email, is_staff, is_superuser FROM api_user")
        rows = cursor.fetchall()
        print(f"FOUND {len(rows)} USERS IN api_user TABLE:")
        for row in rows:
            print(f" - {row[0]} (Staff: {row[1]}, Super: {row[2]})")
    except Exception as e:
        print(f"ERROR reading api_user: {e}")

    try:
        cursor.execute("PRAGMA table_info(api_user)")
        cols = cursor.fetchall()
        print("\nCOLUMNS IN api_user:")
        for col in cols:
            print(f" - {col[1]} ({col[2]})")
    except Exception as e:
        print(f"ERROR reading table info: {e}")
