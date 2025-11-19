import requests

IPINFO_TOKEN = "6eb1e5d2d97582"  # DEV ONLY – later put in env/settings


def get_country_from_ip(ip: str) -> str:
    if not ip:
        return ""

    token = IPINFO_TOKEN  # <-- USE THIS, not settings

    if not token:
        return ""

    try:
        response = requests.get(
            f"https://ipinfo.io/{ip}?token={token}",
            timeout=2,
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
