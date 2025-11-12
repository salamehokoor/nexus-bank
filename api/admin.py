from django.contrib import admin
from .models import *

admin.site.site_header = "Nexus Admin"
admin.site.site_title = "Nexus Admin"
admin.site.index_title = "Dashboard"
# Register all your models
admin.site.register(User)
admin.site.register(UserProfile)
admin.site.register(UserAddress)
admin.site.register(Account)
admin.site.register(Card)
admin.site.register(Transaction)
admin.site.register(Biller)
admin.site.register(BillPayment)
