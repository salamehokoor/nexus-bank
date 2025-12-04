import requests
from django.conf import settings

# Use env/settings for the IP info token. Leave empty locally to avoid
# external calls slowing down requests during development.
IPINFO_TOKEN = getattr(settings, "IPINFO_TOKEN", "")


def get_country_from_ip(ip: str) -> str:
    if not ip:
        return ""

    lookups = []

    # Prefer ipinfo if a token is configured; fall back to the public endpoint.
    if IPINFO_TOKEN:
        lookups.append(f"https://ipinfo.io/{ip}?token={IPINFO_TOKEN}")
    lookups.append(f"https://ipinfo.io/{ip}")

    # Secondary fallback (no token required).
    lookups.append(f"https://ipapi.co/{ip}/json/")

    for url in lookups:
        try:
            resp = requests.get(url, timeout=1)
            data = resp.json()
            country = (
                data.get("country")
                or data.get("country_code")
                or data.get("country_name")
            )
            if country:
                return country
        except Exception:
            continue

    return ""


def _get_ip_from_request(request):
    if not request:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
