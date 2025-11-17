import requests
from django.conf import settings

IPINFO_TOKEN = "6eb1e5d2d97582"


def get_country_from_ip(ip: str) -> str:
    if not ip:
        return ""

    token = getattr(settings, "IPINFO_TOKEN", None)
    if not token:
        return ""  # no token configured

    try:
        response = requests.get(f"https://ipinfo.io/{ip}?token={token}",
                                timeout=2)
        data = response.json()
        return data.get("country", "")
    except Exception:
        return ""
