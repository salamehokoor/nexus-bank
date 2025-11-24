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
from .models import (
    DailyBusinessMetrics,
    CountryUserMetrics,
    WeeklySummary,
    MonthlySummary,
    Incident,
    LoginEvent,
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
admin.site.register(DailyBusinessMetrics)
admin.site.register(CountryUserMetrics)
admin.site.register(WeeklySummary)
admin.site.register(MonthlySummary)
admin.site.register(Incident)
admin.site.register(LoginEvent)
