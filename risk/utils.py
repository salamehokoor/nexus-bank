from functools import lru_cache

import requests
from django.conf import settings

# Use env/settings for the IP info token. Leave empty locally to avoid
# external calls slowing down requests during development.
IPINFO_TOKEN = getattr(settings, "IPINFO_TOKEN", "")


@lru_cache(maxsize=512)
def _lookup_country(ip: str) -> str:
    if not ip:
        return ""

    # Prefer ipinfo if a token is configured; fall back to the public endpoint.
    lookups = []
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

    # Final fallback: reuse the most recent non-empty country we have stored.
    try:
        from .models import Incident, LoginEvent  # local import to avoid cycles

        recent = (
            Incident.objects.filter(ip=ip)
            .exclude(country="")
            .order_by("-timestamp")
            .first()
        )
        if recent and recent.country:
            return recent.country

        recent_login = (
            LoginEvent.objects.filter(ip=ip)
            .exclude(country="")
            .order_by("-timestamp")
            .first()
        )
        if recent_login and recent_login.country:
            return recent_login.country
    except Exception:
        pass

    return ""


def get_country_from_ip(ip: str) -> str:
    return _lookup_country(ip)


def _get_ip_from_request(request):
    if not request:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
