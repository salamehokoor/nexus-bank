"""
Utility helpers for IP extraction and country lookup.
Lookups are cached and avoid querying external services for private/local IPs.
"""

import ipaddress
from functools import lru_cache

import requests
from django.conf import settings

# Use env/settings for the IP info token. Leave empty locally to avoid
# external calls slowing down requests during development.
IPINFO_TOKEN = getattr(settings, "IPINFO_TOKEN", "")


def _is_public_ip(ip: str) -> bool:
    """Return True if the IP is valid and not private/loopback/reserved."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (addr.is_private or addr.is_loopback or addr.is_reserved
                or addr.is_multicast)


@lru_cache(maxsize=512)
def _lookup_country(ip: str) -> str:
    """
    Best-effort country lookup with external fallbacks and DB reuse.
    Skips external requests for non-public IPs to reduce leakage/latency.
    """
    if not ip or not _is_public_ip(ip):
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
            resp.raise_for_status()
            data = resp.json()
            country = (data.get("country") or data.get("country_code")
                       or data.get("country_name"))
            if country:
                return country
        except Exception:
            continue

    # Final fallback: reuse the most recent non-empty country we have stored.
    try:
        from .models import Incident, LoginEvent  # local import to avoid cycles

        recent = (Incident.objects.filter(ip=ip).exclude(
            country="").order_by("-timestamp").first())
        if recent and recent.country:
            return recent.country

        recent_login = (LoginEvent.objects.filter(ip=ip).exclude(
            country="").order_by("-timestamp").first())
        if recent_login and recent_login.country:
            return recent_login.country
    except Exception:
        pass

    return ""


def get_country_from_ip(ip: str) -> str:
    """Public API to retrieve country for an IP (best effort)."""
    return _lookup_country(ip)


def _get_ip_from_request(request):
    """Extract client IP from request headers (XFF first) or REMOTE_ADDR."""
    if not request:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
