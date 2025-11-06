from django.contrib import admin
from .models import (User, UserProfile, UserAddress, Account, Card,
                     Transaction)


class CardAdmin(admin.ModelAdmin):
    """
    Customizes the Admin view for the Card model.
    """
    # This controls what you see in the main list view
    list_display = ('__str__', 'account', 'card_type', 'is_active')

    # This makes the generated fields visible (but not editable)
    # on the "Change" page for an existing card.
    readonly_fields = ('card_number', 'cvv', 'expiration_date')

    # This is the fix. We override the admin's "save" button logic.
    def save_model(self, request, obj, form, change):
        """
        'change' is False when adding a new object.
        'change' is True when updating an existing object.
        """
        if not change:
            # This is a new card being added.
            # Get the data from the admin form.
            account = form.cleaned_data['account']
            card_type = form.cleaned_data['card_type']

            # Use our custom manager to create the card.
            # This correctly sets the card_number, cvv, and expiration_date.
            Card.objects.create_card(account=account, card_type=card_type)

            # We DON'T call obj.save() because the manager already saved it.
        else:
            # This is an *update* (e.g., deactivating the card).
            # We just let the admin do its normal save.
            super().save_model(request, obj, form, change)


# Register all your models
admin.site.register(User)
admin.site.register(UserProfile)
admin.site.register(UserAddress)
admin.site.register(Account)
admin.site.register(Card, CardAdmin)  # <-- Register Card with its custom admin
admin.site.register(Transaction)
