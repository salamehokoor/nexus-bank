from django.contrib import admin
from .models import (User, UserProfile, UserAddress, Account, Card,
                     Transaction)

# Register all your models
admin.site.register(User)
admin.site.register(UserProfile)
admin.site.register(UserAddress)
admin.site.register(Account)
admin.site.register(Card)
admin.site.register(Transaction)
