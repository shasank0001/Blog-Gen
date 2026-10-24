"""Bounded public HTTP fetches with DNS pinning, including every redirect."""

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin

import httpx

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3


class UnsafeURL(ValueError):
    pass


async def resolve_public_url(value: str) -> tuple[httpx.URL, str]:
    try:
        url = httpx.URL(value)
        if url.scheme not in {"http", "https"} or not url.host or url.userinfo:
            raise UnsafeURL("Only public HTTP(S) URLs without credentials are allowed")
        # Percent-encoded zone identifiers and scoped IPv6 addresses are local.
        if "%" in url.host:
            raise UnsafeURL("Scoped addresses are not allowed")
        addresses = await asyncio.wait_for(
            asyncio.to_thread(socket.getaddrinfo, url.host, url.port or (443 if url.scheme == "https" else 80),
                              type=socket.SOCK_STREAM),
            timeout=5,
        )
        ips = [ipaddress.ip_address(item[4][0]) for item in addresses]
        if not ips:
            raise UnsafeURL("URL has no public destination")
        for ip in ips:
            mapped = getattr(ip, "ipv4_mapped", None)
            if (not ip.is_global or ip.is_multicast or ip.is_reserved
                    or getattr(ip, "sixtofour", None) or getattr(ip, "teredo", None)
                    or (mapped and not mapped.is_global)):
                raise UnsafeURL("Private, loopback and reserved destinations are not allowed")
        return url, str(ips[0])
    except (httpx.InvalidURL, ValueError, OSError, TimeoutError) as exc:
        if isinstance(exc, UnsafeURL):
            raise
        raise UnsafeURL("URL must resolve to a public HTTP(S) destination") from exc


async def fetch_public_bytes(value: str) -> bytes | None:
    for _ in range(MAX_REDIRECTS + 1):
        url, address = await resolve_public_url(value)
        # Pin the vetted IP so a second DNS lookup cannot rebind to a private
        # address. Preserve the original HTTP Host and TLS certificate/SNI name.
        destination = url.copy_with(host=address)
        headers = {"Host": url.netloc.decode("ascii"), "Accept-Encoding": "identity",
                   "User-Agent": "ContentStrategistBot/1.0"}
        # A separate connection per destination also verifies TLS when a redirect
        # changes hostname while sharing an IP. Ignore environment proxy settings.
        async with httpx.AsyncClient(trust_env=False, timeout=10, follow_redirects=False) as client:
            async with client.stream("GET", destination, headers=headers,
                                     extensions={"sni_hostname": url.host}) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        return None
                    value = urljoin(str(url), location)
                    continue
                if response.status_code != 200:
                    return None
                # Reject HTTP compression; .xml.gz bodies are decoded separately
                # with their own output limit by the sitemap parser.
                if response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise UnsafeURL("Compressed HTTP responses are not supported")
                content = bytearray()
                async for chunk in response.aiter_raw():
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise UnsafeURL("Sitemap response exceeds the size limit")
                return bytes(content)
    raise UnsafeURL("Too many redirects")
