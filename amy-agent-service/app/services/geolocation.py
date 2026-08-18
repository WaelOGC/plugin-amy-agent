"""IP → country/city lookup via ip-api.com (free, no API key).

Failures never raise: callers always get (None, None) so event ingestion
cannot be blocked by a geo outage, rate limit, or private/local IP.
"""

from __future__ import annotations

import ipaddress
import logging

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(2.0, connect=1.0)
_CACHE: dict[str, tuple[str | None, str | None]] = {}


def lookup_ip(ip: str | None) -> tuple[str | None, str | None]:
    """Return (country, city) for a public IP, or (None, None) on any failure.

    Successful (and private-IP) lookups are cached in-process for the life of
    the worker so a burst of events from the same visitor does not repeat the
    HTTP call. Transient failures are not cached so a later event can retry.
    """
    if not ip:
        return None, None
    ip = ip.strip()
    if not ip or ip.lower() in {"unknown", "none", "null"}:
        return None, None

    cached = _CACHE.get(ip)
    if cached is not None:
        return cached

    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None, None

    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_reserved
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_unspecified
    ):
        _CACHE[ip] = (None, None)
        return None, None

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "status,country,city"},
            )
        data = response.json()
        if not isinstance(data, dict) or data.get("status") != "success":
            return None, None
        country = data.get("country") or None
        city = data.get("city") or None
        if country is not None:
            country = str(country)
        if city is not None:
            city = str(city)
        result = (country, city)
        _CACHE[ip] = result
        return result
    except Exception:
        logger.debug("IP geolocation lookup failed for %s", ip, exc_info=True)
        return None, None
