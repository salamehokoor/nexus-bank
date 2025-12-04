import requests
from django.conf import settings

# Use env/settings for the IP info token. Leave empty locally to avoid
# external calls slowing down requests during development.
IPINFO_TOKEN = getattr(settings, "IPINFO_TOKEN", "")
IS_DEBUG = getattr(settings, "DEBUG", False)


def get_country_from_ip(ip: str) -> str:
    if not ip or IS_DEBUG:
        return ""

    token = IPINFO_TOKEN
    if not token:
        return ""

    try:
        response = requests.get(
            f"https://ipinfo.io/{ip}?token={token}",
            timeout=1,
        )
        data = response.json()
        return data.get("country", "")
    except Exception:
        return ""


def _get_ip_from_request(request):
    if not request:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
