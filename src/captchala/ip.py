"""Best-effort end-user IP extraction for the framework helpers."""

from __future__ import annotations

import ipaddress
from typing import Callable, Optional

HEADER_ORDER = ("CF-Connecting-IP", "X-Forwarded-For", "X-Real-IP")


def _clean(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    ip = value.split(",")[0].strip()
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        return str(addr.ipv4_mapped)
    return str(addr)


def client_ip_from_headers(get_header: Callable[[str], Optional[str]], remote_addr: Optional[str] = None) -> Optional[str]:
    """``CF-Connecting-IP``, the first ``X-Forwarded-For`` entry, ``X-Real-IP``, then ``remote_addr``.

    Anyone can set these headers when your app is not behind a proxy that
    overwrites them. The IP is only an extra risk signal; pass your own IP
    when you know better.
    """
    for name in HEADER_ORDER:
        ip = _clean(get_header(name))
        if ip:
            return ip
    return _clean(remote_addr)
