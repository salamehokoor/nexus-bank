import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nexus.settings')
django.setup()

from api.models import Biller, Account, User, Card

def run():
    print("Seeding data...")
    
    # System User for Billers
    sys_user, _ = User.objects.get_or_create(email="system@nexus.com")
    if not sys_user.password:
        sys_user.set_password("system123")
        sys_user.save()

    # Create Billers
    if not Biller.objects.filter(name="Electric Co").exists():
        acc_elec = Account.objects.create(user=sys_user, type=Account.AccountTypes.BASIC, currency="JOD")
        Biller.objects.create(
            name="Electric Co", 
            category="Electricity", 
            fixed_amount=Decimal("50.00"),
            system_account=acc_elec
        )
        print("Created Electric Co Biller")

    if not Biller.objects.filter(name="Water Co").exists():
        acc_water = Account.objects.create(user=sys_user, type=Account.AccountTypes.BASIC, currency="JOD")
        Biller.objects.create(
            name="Water Co", 
            category="Water", 
            fixed_amount=Decimal("20.00"),
            system_account=acc_water
        )
        print("Created Water Co Biller")

    # Main User
    try:
        u1 = User.objects.get(email="anas@gmail.com")
        u1.set_password("test")
        u1.save()
        print("Reset password for anas@gmail.com")
        if not u1.accounts.exists():
            Account.objects.create(user=u1, type=Account.AccountTypes.SAVINGS, currency="JOD", balance=Decimal("5000.00"))
            print("Created Account for anas@gmail.com")
        else:
            # Top up
            a = u1.accounts.first()
            a.balance = Decimal("5000.00")
            a.save()
            print("Updated balance for anas@gmail.com")
    except User.DoesNotExist:
        print("User anas@gmail.com does not exist! Please create it or provide valid creds.")

    # Recipient User
    u2, created = User.objects.get_or_create(email="recipient@test.com")
    if created:
        u2.set_password("test")
        u2.save()
        print("Created recipient@test.com")
    
    if not u2.accounts.exists():
        Account.objects.create(user=u2, type=Account.AccountTypes.SAVINGS, currency="JOD", balance=Decimal("0.00"))
        print("Created Account for recipient@test.com")

    # Staff User
    admin, created = User.objects.get_or_create(email="staff@nexus.com")
    if created:
        admin.set_password("staff")
        admin.is_staff = True
        admin.save()
        print("Created staff@nexus.com")
    elif not admin.is_staff:
        admin.is_staff = True
        admin.save()
        print("Updated staff@nexus.com permissions")

    print("Seeding complete.")

if __name__ == "__main__":
    run()
