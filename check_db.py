
import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nexus.settings')
django.setup()

from api.models import User
from django.db import connection

print(f"DATABASE FILE: {settings.DATABASES['default']['NAME']}")
print(f"TOTAL USERS: {User.objects.count()}")

for user in User.objects.all():
    print(f" - {user.email} (Staff: {user.is_staff}, Super: {user.is_superuser}, Active: {user.is_active}, Password Set: {user.has_usable_password()})")

print(f"Current DB Connection: {connection.settings_dict['NAME']}")
