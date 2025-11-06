from django.contrib import admin
from . import models

# This "registers" your models with the admin site

admin.site.register(models.User)
admin.site.register(models.Account)
admin.site.register(models.Card)
