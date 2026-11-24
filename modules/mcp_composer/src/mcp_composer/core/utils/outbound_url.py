"""Destination guard for server-side fetches of caller-supplied URLs.

Tools such as ``register_agent`` fetch URLs chosen by the MCP caller. Without a
guard, a caller can make the composer reach loopback services, cloud metadata
endpoints, or private networks. Operators opt internal hosts in by listing
hostnames, IPs, or CIDRs in ``MCP_COMPOSER_OUTBOUND_ALLOWLIST``.
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
from urllib.parse import urlsplit

OUTBOUND_ALLOWLIST_ENV = "MCP_COMPOSER_OUTBOUND_ALLOWLIST"
ALLOWED_SCHEMES = frozenset({"http", "https"})

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


def parse_outbound_allowlist(
    raw: str | None = None,
) -> tuple[frozenset[str], tuple[IPNetwork, ...]]:
    """Split the allowlist into lowercase hostnames and IP networks."""
    value = raw if raw is not None else os.getenv(OUTBOUND_ALLOWLIST_ENV, "")
    hosts: set[str] = set()
    networks: list[IPNetwork] = []
    for part in (value or "").split(","):
        item = part.strip().lower()
        if not item:
            continue
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            hosts.add(item)
    return frozenset(hosts), tuple(networks)


async def _resolve(host: str, port: int) -> set[IPAddress]:
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            host, port, type=socket.SOCK_STREAM
        )
    except OSError as exc:
        raise ValueError(f"Outbound URL host could not be resolved: {host}") from exc
    return {ipaddress.ip_address(info[4][0]) for info in infos}


async def assert_outbound_url_allowed(url: str) -> str:
    """
    Refuse ``url`` unless it is http(s) and every address its host resolves to
    is globally routable or listed in ``MCP_COMPOSER_OUTBOUND_ALLOWLIST``.

    Returns ``url`` unchanged. Raises ``ValueError`` with an operator-facing message.
    """
    parts = urlsplit(str(url or "").strip())
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise ValueError(f"Outbound URL must use http or https: {url}")
    host = (parts.hostname or "").lower()
    if not host:
        raise ValueError(f"Outbound URL has no host: {url}")

    allowed_hosts, allowed_networks = parse_outbound_allowlist()
    if host in allowed_hosts:
        return url

    port = parts.port or (443 if parts.scheme.lower() == "https" else 80)
    for address in await _resolve(host, port):
        if address.is_global or any(address in net for net in allowed_networks):
            continue
        raise ValueError(
            f"Refusing to fetch {url}: {host} resolves to non-public address {address}. "
            f"Add it to {OUTBOUND_ALLOWLIST_ENV} to allow it."
        )
    return url


def _member_config_urls(config: dict) -> list[str]:
    """Collect URLs in a member-server config that the composer will connect to."""
    urls: list[str] = []

    def add(value: object) -> None:
        if isinstance(value, str) and value.strip():
            urls.append(value)

    add(config.get("endpoint"))
    for section in ("open_api", "graphql"):
        block = config.get(section)
        if isinstance(block, dict):
            add(block.get("endpoint"))
            add(block.get("spec_url"))
    auth = config.get("auth")
    if isinstance(auth, dict):
        add(auth.get("token_url"))
        add(auth.get("login_url"))
    return urls


async def assert_member_config_destinations_allowed(config: dict) -> None:
    """
    Apply the outbound destination guard to every URL a caller-supplied
    member-server config makes the composer connect to.

    Stdio and local members have no network destination and are skipped.
    Raises ``ValueError`` on the first refused URL.
    """
    for url in _member_config_urls(config):
        await assert_outbound_url_allowed(url)
