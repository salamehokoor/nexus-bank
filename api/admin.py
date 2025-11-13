from django.contrib import admin
from .models import (
    User,
    UserProfile,
    UserAddress,
    Account,
    Card,
    Transaction,
    Biller,
    BillPayment,
)

admin.site.site_header = "Nexus Admin"
admin.site.site_title = "Nexus Admin Portal"
admin.site.index_title = "Dashboard"

admin.site.register(User)
admin.site.register(UserProfile)
admin.site.register(UserAddress)
admin.site.register(Account)
admin.site.register(Card)
admin.site.register(Transaction)
admin.site.register(Biller)
admin.site.register(BillPayment)
