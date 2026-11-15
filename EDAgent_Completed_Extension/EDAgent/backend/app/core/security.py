"""
Security and Guardrails Utility

Covers password hashing, JWT issuing/verification, SSRF protection for URL import,
spreadsheet formula-injection defence and prompt-injection hygiene for dataset text.
"""

import ipaddress
import re
import socket
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple
from urllib.parse import urlparse

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

JWT_ALGORITHM = "HS256"

# ---------------------------------------------------------------------------
# Passwords & tokens
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """bcrypt-hash a password. bcrypt only reads the first 72 bytes, so we pre-trim
    explicitly (rather than letting the library raise) and enforce length in the schema."""
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        # Malformed hash in the database must never crash a login request.
        return False


def create_access_token(subject: str, expires_minutes: Optional[int] = None, *, guest: bool = False) -> Tuple[str, int]:
    """Returns (jwt, expires_in_seconds). `sub` is the user id; nothing else sensitive is embedded."""
    minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    claims = {"sub": subject, "exp": expire, "session_version": 2}
    if guest:
        claims["guest"] = True
    token = jwt.encode(claims, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token, minutes * 60


def token_claims(token: str, *, allow_expired: bool = False) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM],
                             options={"verify_exp": not allow_expired, "require_exp": True, "require_sub": True})
    except JWTError:
        return {}
    # Old tokens could be issued by guest login for any stored account.
    return payload if payload.get("session_version") == 2 else {}


def decode_access_token(token: str) -> Optional[str]:
    """Returns the user id (`sub`) for a valid, unexpired token; otherwise None."""
    sub = token_claims(token).get("sub")
    return str(sub) if sub else None


def assert_production_secret() -> None:
    """Refuses to boot in production with the publicly known development key."""
    from app.core.config import INSECURE_DEFAULT_SECRET

    if settings.ENVIRONMENT.lower() == "production" and (
        settings.SECRET_KEY == INSECURE_DEFAULT_SECRET or len(settings.SECRET_KEY) < 32
    ):
        raise RuntimeError("SECRET_KEY must be set to a unique random value (>= 32 chars) in production.")


# ---------------------------------------------------------------------------
# SSRF protection
# ---------------------------------------------------------------------------

DISALLOWED_IP_RANGES = [
    ipaddress.ip_network("0.0.0.0/8"),        # "this network"
    ipaddress.ip_network("127.0.0.0/8"),      # loopback
    ipaddress.ip_network("10.0.0.0/8"),       # private class A
    ipaddress.ip_network("100.64.0.0/10"),    # carrier-grade NAT
    ipaddress.ip_network("172.16.0.0/12"),    # private class B
    ipaddress.ip_network("192.168.0.0/16"),   # private class C
    ipaddress.ip_network("169.254.0.0/16"),   # link-local / cloud metadata
    ipaddress.ip_network("224.0.0.0/4"),      # multicast
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 unique-local
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]


def is_ip_blocked(ip_str: str) -> bool:
    """True when an address is internal/non-public. IPv4-mapped IPv6 is unwrapped first so
    `::ffff:127.0.0.1` cannot slip past the IPv4 rules."""
    ip_obj = ipaddress.ip_address(ip_str.split("%")[0])
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
        ip_obj = ip_obj.ipv4_mapped
    if any(ip_obj in net for net in DISALLOWED_IP_RANGES):
        return True
    return bool(
        ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local
        or ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_unspecified
    )


def validate_url_safe(url: str) -> Tuple[bool, str]:
    """
    Validates a URL against SSRF before any request is made: scheme, credentials in the
    URL, and every IP the hostname resolves to. Called again for each redirect hop.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ("http", "https"):
            return False, f"Unsupported protocol '{parsed.scheme}'. Only http and https are allowed."
        if parsed.username or parsed.password:
            return False, "URLs containing credentials are not allowed."
        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL: missing hostname."

        infos = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        if not infos:
            return False, "Hostname did not resolve."
        for _family, _, _, _, sockaddr in infos:
            if is_ip_blocked(sockaddr[0]):
                return False, f"URL resolves to a restricted IP address: {sockaddr[0]}."
        return True, ""
    except Exception as e:  # DNS failure, malformed URL, ...
        return False, f"Failed to validate URL: {e}"


# ---------------------------------------------------------------------------
# Output / prompt hygiene
# ---------------------------------------------------------------------------

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_cell(value: Any) -> Any:
    """
    Guards CSV/XLSX exports against formula injection: a cell starting with =, +, - or @
    would be executed by Excel/Sheets when the file is opened. Prefixing a single quote
    forces it to be treated as text. Genuine negative numbers are left alone because they
    are numeric types (not strings) by the time they are exported.
    """
    if isinstance(value, str) and value and value[0] in _FORMULA_PREFIXES:
        return f"'{value}"
    return value


_ROLE_MARKER = re.compile(r"(?i)\b(system|assistant|user|developer)\s*:")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_prompt_data(text: str, max_len: int = 120) -> str:
    """
    Cleans a dataset-derived string (column name, category label, sample value) before it is
    placed in an LLM prompt. Dataset text is *data*, never instructions, so we neutralise
    role markers, strip control characters/newlines and cap the length. The prompt also wraps
    all such text in a clearly labelled data block (see ai/context.py).
    """
    cleaned = _CONTROL_CHARS.sub("", str(text)).replace("\r", " ").replace("\n", " ")
    cleaned = _ROLE_MARKER.sub("[role-marker-removed]:", cleaned)
    cleaned = cleaned.replace("```", "'''").replace("<", "‹").replace(">", "›")
    return cleaned[:max_len]


def safe_filename(name: str, default: str = "file") -> str:
    """Reduces any user-controlled string to a safe single path component."""
    base = re.sub(r"[^\w.\-]", "_", name.replace("\\", "/").split("/")[-1]).strip("._")
    return (base or default)[:120]
