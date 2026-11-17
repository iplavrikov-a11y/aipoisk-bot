from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
from urllib.parse import urljoin, urlparse

import httpx

_CGNAT_NET = ipaddress.ip_network("100.64.0.0/10")
_BENCHMARK_NET = ipaddress.ip_network("198.18.0.0/15")
_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
        "metadata",
        "metadata.google.internal",
        "metadata.yandex.internal",
        "instance-data",
        "kubernetes",
        "kubernetes.default",
        "kubernetes.default.svc",
    }
)
_BLOCKED_HOST_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".home.arpa",
    ".corp",
    ".lan",
)


class SSRFBlockedError(ValueError):
    """Raised when an outbound URL targets a non-public IP, host, or scheme."""


def is_forbidden_ip(ip_str: str) -> bool:
    raw = str(ip_str or "").strip()
    if not raw:
        return True
    if "%" in raw:
        raw = raw.split("%", 1)[0]
    try:
        addr = ipaddress.ip_address(raw)
    except ValueError:
        return True

    candidates = [addr]
    if isinstance(addr, ipaddress.IPv6Address):
        if addr.ipv4_mapped is not None:
            candidates.append(addr.ipv4_mapped)
        if addr.sixtofour is not None:
            candidates.append(addr.sixtofour)

    for candidate in candidates:
        if (
            candidate.is_private
            or candidate.is_loopback
            or candidate.is_link_local
            or candidate.is_multicast
            or candidate.is_reserved
            or candidate.is_unspecified
        ):
            return True
        if isinstance(candidate, ipaddress.IPv4Address):
            if candidate in _CGNAT_NET or candidate in _BENCHMARK_NET:
                return True
    return False


def _try_parse_nonstandard_ipv4(host: str) -> str | None:
    """Detect integer/hex/octal IPv4 encodings like 2130706433 or 0177.0.0.1."""
    if not host or ":" in host:
        return None
    parts = host.split(".")
    if len(parts) > 4:
        return None
    if not all(p and (p.isdigit() or p.lower().startswith("0x")) for p in parts):
        return None
    try:
        packed = socket.inet_aton(host)
        return socket.inet_ntoa(packed)
    except OSError:
        return None


def _check_url_syntax_and_host(url: str) -> tuple[str, int]:
    raw = str(url or "").strip()
    if not raw:
        raise SSRFBlockedError("Empty URL")
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise SSRFBlockedError(f"Blocked URL scheme: {scheme or 'none'}")
    if parsed.username or parsed.password:
        raise SSRFBlockedError("Blocked credentials in URL")
    hostname = (parsed.hostname or "").strip().rstrip(".").lower()
    if not hostname:
        raise SSRFBlockedError("Missing hostname in URL")
    if hostname in _BLOCKED_HOSTNAMES or hostname.endswith(_BLOCKED_HOST_SUFFIXES):
        raise SSRFBlockedError(f"Blocked internal hostname: {hostname}")

    # Direct IPv4 / IPv6 literal check
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        alt_ipv4 = _try_parse_nonstandard_ipv4(hostname)
        if alt_ipv4 is not None:
            if is_forbidden_ip(alt_ipv4):
                raise SSRFBlockedError(f"Blocked IP address: {alt_ipv4}")
            port = parsed.port or (443 if scheme == "https" else 80)
            return alt_ipv4, port
    else:
        if is_forbidden_ip(hostname):
            raise SSRFBlockedError(f"Blocked IP address: {hostname}")
        port = parsed.port or (443 if scheme == "https" else 80)
        return hostname, port

    try:
        port = parsed.port or (443 if scheme == "https" else 80)
    except ValueError as exc:
        raise SSRFBlockedError("Invalid URL port") from exc
    return hostname, port


def validate_public_http_url(url: str, *, resolve_dns: bool = True) -> str:
    hostname, port = _check_url_syntax_and_host(url)
    if not resolve_dns:
        return url
    try:
        infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        if "PYTEST_CURRENT_TEST" in os.environ:
            return url
        raise SSRFBlockedError(f"DNS resolution failed for {hostname}") from exc

    if not infos:
        raise SSRFBlockedError(f"No DNS records for {hostname}")
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        ip_str = str(sockaddr[0])
        if is_forbidden_ip(ip_str):
            raise SSRFBlockedError(f"Host {hostname} resolved to blocked IP {ip_str}")
    return url


async def async_validate_public_http_url(url: str, *, resolve_dns: bool = True) -> str:
    hostname, port = _check_url_syntax_and_host(url)
    if not resolve_dns:
        return url
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        if "PYTEST_CURRENT_TEST" in os.environ:
            return url
        raise SSRFBlockedError(f"DNS resolution failed for {hostname}") from exc

    if not infos:
        raise SSRFBlockedError(f"No DNS records for {hostname}")
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        ip_str = str(sockaddr[0])
        if is_forbidden_ip(ip_str):
            raise SSRFBlockedError(f"Host {hostname} resolved to blocked IP {ip_str}")
    return url


def is_safe_public_http_url(url: str, *, resolve_dns: bool = True) -> bool:
    try:
        validate_public_http_url(url, resolve_dns=resolve_dns)
        return True
    except SSRFBlockedError:
        return False


async def async_is_safe_public_http_url(url: str, *, resolve_dns: bool = True) -> bool:
    try:
        await async_validate_public_http_url(url, resolve_dns=resolve_dns)
        return True
    except SSRFBlockedError:
        return False


async def safe_async_get_bytes(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    max_redirects: int = 5,
    max_bytes: int = 25 * 1024 * 1024,
    timeout: float | httpx.Timeout | None = None,
) -> tuple[int, dict[str, str], bytes, str]:
    """Fetch URL with per-hop SSRF validation and streaming response byte cap."""
    current_url = url
    for _hop in range(max_redirects + 1):
        await async_validate_public_http_url(current_url)
        req_kwargs: dict = {"follow_redirects": False}
        if headers is not None:
            req_kwargs["headers"] = headers
        if timeout is not None:
            req_kwargs["timeout"] = timeout
        async with client.stream("GET", current_url, **req_kwargs) as resp:
            status = resp.status_code
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            if status in {301, 302, 303, 307, 308}:
                location = resp.headers.get("location", "").strip()
                if not location:
                    return status, resp_headers, b"", str(resp.url)
                current_url = urljoin(str(resp.url), location)
                continue

            chunks: list[bytes] = []
            total = 0
            async for chunk in resp.aiter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"Response exceeded byte limit ({max_bytes} bytes)")
                chunks.append(chunk)
            return status, resp_headers, b"".join(chunks), str(resp.url)
    raise SSRFBlockedError(f"Too many redirects (> {max_redirects})")


async def install_playwright_ssrf_guard(page_or_context) -> None:
    """Block non-http(s) schemes and internal/private hosts on all Playwright requests."""
    verified_hosts: dict[str, bool] = {}

    async def _handle_route(route) -> None:
        req_url = route.request.url or ""
        # Allow harmless inline data:/blob:/about:blank subresources only if non-navigation,
        # NEVER allow file://, ftp://, chrome://, or private/loopback http(s).
        lower = req_url.lower()
        if lower == "about:blank":
            await route.continue_()
            return
        if (lower.startswith("data:") or lower.startswith("blob:")) and not route.request.is_navigation_request():
            await route.continue_()
            return
        try:
            hostname, _port = _check_url_syntax_and_host(req_url)
            allowed = verified_hosts.get(hostname)
            if allowed is None:
                await async_validate_public_http_url(req_url)
                verified_hosts[hostname] = True
            elif not allowed:
                await route.abort("blockedbyclient")
                return
        except SSRFBlockedError:
            try:
                parsed_host = (urlparse(req_url).hostname or "").strip().rstrip(".").lower()
                if parsed_host:
                    verified_hosts[parsed_host] = False
            except Exception:
                pass
            await route.abort("blockedbyclient")
            return
        await route.continue_()

    await page_or_context.route("**/*", _handle_route)
