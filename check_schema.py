
import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nexus.settings')
os.environ.setdefault('DJANGO_DEBUG', 'True')
django.setup()

from django.db import connection

def check_table(table_name):
    print(f"\n--- Checking {table_name} ---")
    with connection.cursor() as cursor:
        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            cols = cursor.fetchall()
            for col in cols:
                print(f" - {col[1]} ({col[2]})")
        except Exception as e:
            print(f"ERROR: {e}")

check_table("api_user")
check_table("api_transaction")
check_table("api_account")
