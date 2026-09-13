"""Fetch policy URLs into one plain-text corpus.

Hard limits: 10s timeout, 1MB cap, <=3 redirects, and no private or loopback
addresses — the URLs come from a form, so they are treated as hostile input.
"""
import ipaddress
import socket
from urllib.parse import urlparse

import httpx
from selectolax.parser import HTMLParser

MAX_BYTES = 1024 * 1024
TIMEOUT = 10.0
MAX_REDIRECTS = 3

# Tags whose text is never policy content.
_STRIP = "script, style, noscript, svg, nav, header, footer, form, iframe"


class SourceError(Exception):
    pass


def _assert_public(host: str) -> None:
    """Resolve and reject loopback, private, link-local and reserved targets."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise SourceError(f"could not resolve {host}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise SourceError(f"{host} resolves to a non-public address ({ip})")


def _check_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SourceError("only http and https URLs are allowed")
    if not parsed.hostname:
        raise SourceError("missing hostname")
    _assert_public(parsed.hostname)


def html_to_text(html: str) -> str:
    tree = HTMLParser(html)
    tree.strip_tags(_STRIP.split(", "))
    text = tree.body.text(separator="\n") if tree.body else tree.text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


async def fetch_one(client: httpx.AsyncClient, url: str) -> str:
    """Follow redirects by hand so every hop is validated BEFORE it is fetched.

    httpx's follow_redirects would fetch the next hop first and only let us
    inspect it afterwards, which would leave a redirect to a private address
    or the cloud metadata endpoint already requested.
    """
    for _ in range(MAX_REDIRECTS + 1):
        _check_url(url)
        async with client.stream("GET", url) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise SourceError("redirect without a location header")
                url = str(response.url.join(location))  # resolves relative hops
                continue
            response.raise_for_status()
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise SourceError(f"exceeded the {MAX_BYTES // 1024}KB cap")
                chunks.append(chunk)
            content_type = response.headers.get("content-type", "")
        body = b"".join(chunks).decode("utf-8", errors="replace")
        is_plain = "text/plain" in content_type or url.endswith((".md", ".txt"))
        return body if is_plain else html_to_text(body)
    raise SourceError(f"more than {MAX_REDIRECTS} redirects")


async def build_corpus(urls: list[str]) -> tuple[str, list[str]]:
    """Return (corpus, errors). One bad URL does not sink the run."""
    parts: list[str] = []
    errors: list[str] = []
    limits = httpx.Limits(max_connections=5)
    async with httpx.AsyncClient(
        timeout=TIMEOUT,
        follow_redirects=False,
        limits=limits,
        headers={"User-Agent": "grounded-questionnaire-agent/1.0"},
    ) as client:
        for url in urls:
            try:
                text = await fetch_one(client, url)
            except SourceError as exc:
                errors.append(f"{url}: {exc}")
            except httpx.HTTPError as exc:
                errors.append(f"{url}: {type(exc).__name__}")
            else:
                if text.strip():
                    parts.append(f"--- SOURCE: {url} ---\n{text}")
                else:
                    errors.append(f"{url}: no readable text")
    return "\n\n".join(parts), errors
