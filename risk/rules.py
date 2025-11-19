# risk/rules.py
from risk.utils import get_country_from_ip, _get_ip_from_request
from .models import Incident


def high_value_transfer(request, transfer, threshold=1000):
    """
    Create an Incident if the transfer amount is higher than `threshold`.
    """
    if transfer.amount <= threshold:
        return

    ip = _get_ip_from_request(request)

    # Safely get related accounts
    sender_acc = getattr(transfer, "sender_account", None)
    receiver_acc = getattr(transfer, "receiver_account", None)

    from_acc_number = getattr(sender_acc, "account_number", None)
    to_acc_number = getattr(receiver_acc, "account_number", None)

    Incident.objects.create(
        user=request.user if request.user.is_authenticated else None,
        ip=ip,
        country=get_country_from_ip(ip),  # fill later when you add IP->country
        event=f"High value transfer: {transfer.amount}",
        severity="high",
        details={
            "from_account": from_acc_number,
            "to_account": to_acc_number,
        },
    )
