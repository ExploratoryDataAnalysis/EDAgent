"""
Security and Guardrails Utility
Provides SSRF protection, CSV formula injection defense, and input sanitization.
"""

import ipaddress
import re
import socket
from urllib.parse import urlparse
from typing import Tuple


DISALLOWED_IP_RANGES = [
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("10.0.0.0/8"),       # Private class A
    ipaddress.ip_network("172.16.0.0/12"),    # Private class B
    ipaddress.ip_network("192.168.0.0/16"),   # Private class C
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local / AWS metadata
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 private
]


def validate_url_safe(url: str) -> Tuple[bool, str]:
    """
    Validates a URL against SSRF attacks before downloading.
    Rejects private networks, loopbacks, internal IPs, and non-http(s) protocols.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ("http", "https"):
            return False, f"Unsupported protocol '{parsed.scheme}'. Only http and https are allowed."

        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL: missing hostname."

        # Resolve hostname to IP addresses
        ip_addresses = socket.getaddrinfo(hostname, None)
        for family, _, _, _, sockaddr in ip_addresses:
            ip_str = sockaddr[0]
            ip_obj = ipaddress.ip_address(ip_str)
            for disallowed_range in DISALLOWED_IP_RANGES:
                if ip_obj in disallowed_range:
                    return False, f"URL resolves to restricted IP address: {ip_str}."

        return True, ""
    except Exception as e:
        return False, f"Failed to validate URL: {str(e)}"


def sanitize_csv_cell(value: str) -> str:
    """
    Guards against CSV formula injection.
    Prefixes cells starting with '=', '+', '-', or '@' with a single quote.
    """
    if isinstance(value, str) and len(value) > 0:
        if value[0] in ("=", "+", "-", "@", "\t", "\r"):
            return f"'{value}"
    return value


def sanitize_prompt_data(data_representation: str) -> str:
    """
    Sanitizes tabular sample data passed to the AI to prevent prompt injection.
    Enforces that table contents are formatted strictly as structured data context.
    """
    # Strips system role simulation markers from dataset cell text
    cleaned = re.sub(r"(?i)(system\s*:|user\s*:|assistant\s*:)", "[filtered]", data_representation)
    return cleaned
