"""
Security helpers for path and outbound URL validation.
"""
import ipaddress
import os
import re
import socket
from pathlib import Path
from typing import Optional, Union
from urllib.parse import unquote, urlparse

LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}
SAFE_UPLOAD_FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,255}$")
CGNAT_RANGE = ipaddress.ip_network("100.64.0.0/10")
IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]


def _default_port(scheme: str) -> int:
    return 443 if scheme == "https" else 80


def resolve_upload_file_path(upload_dir: str, filename: str) -> Path:
    """Resolve an upload filename to a safe path inside upload_dir."""
    raw_name = unquote((filename or "").strip())
    if not raw_name:
        raise ValueError("Filename is empty")
    if os.path.isabs(raw_name):
        raise ValueError("Absolute paths are not allowed")
    if "/" in raw_name or "\\" in raw_name:
        raise ValueError("Nested paths are not allowed")
    if raw_name in {".", ".."}:
        raise ValueError("Invalid filename")
    if not SAFE_UPLOAD_FILENAME_RE.fullmatch(raw_name):
        raise ValueError("Filename contains unsupported characters")

    base_path = Path(upload_dir).resolve()
    candidate = (base_path / raw_name).resolve()
    try:
        candidate.relative_to(base_path)
    except ValueError as exc:
        raise ValueError("Path escapes uploads directory") from exc

    return candidate


def extract_local_upload_filename(url_or_path: str) -> Optional[str]:
    """
    Return filename if URL/path points to /uploads/<filename> on local backend.
    """
    if not url_or_path:
        return None

    parsed = urlparse(url_or_path)
    path = parsed.path if parsed.scheme else url_or_path

    if parsed.scheme:
        host = (parsed.hostname or "").lower()
        if host not in LOCAL_HOSTNAMES:
            return None

    if not path.startswith("/uploads/"):
        return None

    filename = unquote(path[len("/uploads/"):]).strip()
    if not filename or "/" in filename or "\\" in filename:
        return None

    return filename


def is_internal_backend_asset_url(
    url: str,
    backend_url: Optional[str],
    allowed_prefixes: tuple[str, ...] = ("/uploads/", "/static/"),
) -> bool:
    """Allow local/private fetches only for known backend asset paths."""
    parsed = urlparse(url or "")
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.hostname:
        return False
    if not any((parsed.path or "").startswith(prefix) for prefix in allowed_prefixes):
        return False

    host = parsed.hostname.lower()
    if host in LOCAL_HOSTNAMES:
        return True

    if not backend_url:
        return False

    backend_parsed = urlparse(backend_url)
    if not backend_parsed.hostname:
        return False

    backend_host = backend_parsed.hostname.lower()
    target_port = parsed.port or _default_port(parsed.scheme)
    backend_port = backend_parsed.port or _default_port(backend_parsed.scheme or "http")
    return host == backend_host and target_port == backend_port


def _is_non_public_ip(ip: IPAddress) -> bool:
    """Return True if the IP should not be reachable via user-controlled URLs."""
    addr = ip.ipv4_mapped if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped else ip

    if addr.is_private or addr.is_loopback or addr.is_link_local:
        return True
    if addr.is_multicast or addr.is_reserved or addr.is_unspecified:
        return True
    if isinstance(addr, ipaddress.IPv4Address) and addr in CGNAT_RANGE:
        return True
    return False


def is_safe_outbound_url(url: str, allow_private: bool = False) -> bool:
    """
    Validate outbound URL to reduce SSRF risk.

    - Allows only http/https
    - Requires hostname
    - Blocks userinfo in URL
    - Resolves host and blocks private/local/reserved ranges unless allow_private=True
    """
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False

    hostname = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    try:
        direct_ip = ipaddress.ip_address(hostname)
        resolved_ips = {direct_ip}
    except ValueError:
        try:
            infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        except socket.gaierror:
            return False

        resolved_ips = set()
        for info in infos:
            ip_raw = info[4][0]
            try:
                resolved_ips.add(ipaddress.ip_address(ip_raw))
            except ValueError:
                continue

        if not resolved_ips:
            return False

    if allow_private:
        return True

    for ip in resolved_ips:
        if _is_non_public_ip(ip):
            return False

    return True
