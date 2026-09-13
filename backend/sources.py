"""Fetch policy URLs into one plain-text corpus.

Hard limits: 10s timeout, 1MB cap, <=3 redirects, and no private or loopback
addresses — the URLs come from a form, so they are treated as hostile input.
"""
import ipaddress
import os
import re
import socket
from urllib.parse import quote, urlparse

import httpx
from selectolax.parser import HTMLParser

MAX_BYTES = 1024 * 1024
TIMEOUT = 10.0
MAX_REDIRECTS = 3

# Some pages ship a JavaScript shell with no text in the HTTP response (Notion
# is the case we hit). For those we re-fetch through a rendering reader, which
# runs the page and hands back plain text. Set READER_URL="" to disable.
READER_URL = os.environ.get("READER_URL", "https://r.jina.ai/")
# Optional. Without it the reader still works, on a much lower rate limit.
READER_API_KEY = os.environ.get("READER_API_KEY", "") or os.environ.get(
    "JINA_API_KEY", ""
)
READER_TIMEOUT = 45.0

# A 32-hex Notion page id, with or without dashes.
_NOTION_ID = re.compile(r"[0-9a-f]{32}$|[0-9a-f-]{36}$", re.I)

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


def notion_site_url(url: str) -> str:
    """Rewrite a Notion workspace link to its published notion.site address.

    app.notion.com/p/<workspace>/<slug> and notion.so/<workspace>/<slug> are
    private app routes that serve no content to a fetcher. The published
    <workspace>.notion.site/<slug> form is the one a reader can render.
    Anything that does not match that exact shape is returned untouched.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in {"app.notion.com", "www.notion.so", "notion.so"}:
        return url
    segments = [seg for seg in parsed.path.split("/") if seg]
    if segments and segments[0] == "p":
        segments = segments[1:]
    if len(segments) != 2:
        return url
    workspace, slug = segments
    if _NOTION_ID.search(workspace) or not _NOTION_ID.search(slug):
        return url  # already an id-only route, or not a page slug
    return f"https://{workspace}.notion.site/{slug}"


async def fetch_via_reader(client: httpx.AsyncClient, url: str) -> str:
    """Last resort for JS-rendered pages. The URL still passes the SSRF check."""
    if not READER_URL:
        raise SourceError("no reader configured")
    _check_url(url)
    target = READER_URL + quote(url, safe=":/?=&%")
    headers = (
        {"Authorization": f"Bearer {READER_API_KEY}"} if READER_API_KEY else {}
    )
    response = await client.get(
        target, timeout=READER_TIMEOUT, follow_redirects=True, headers=headers
    )
    response.raise_for_status()
    body = response.text[:MAX_BYTES]
    if len(body.strip()) < 200:
        raise SourceError("the reader returned no usable text")
    return body


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
                    raise SourceError(
                        f"exceeded the {MAX_BYTES // 1024}KB cap — if this is a "
                        "single document, the page is probably a JavaScript app "
                        "shell rather than the text itself"
                    )
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
            target = notion_site_url(url)
            text, direct_error = "", ""
            try:
                text = await fetch_one(client, target)
            except (SourceError, httpx.HTTPError) as exc:
                direct_error = str(exc) or type(exc).__name__

            if not text.strip():
                # Either the fetch failed or the response was a JS shell with no
                # text in it. Render it before giving up.
                try:
                    text = await fetch_via_reader(client, target)
                except (SourceError, httpx.HTTPError) as exc:
                    reason = direct_error or (
                        "fetched OK but contains no readable text"
                    )
                    detail = str(exc) or type(exc).__name__
                    errors.append(f"{url}: {reason}; rendering also failed ({detail})")
                    continue

            parts.append(f"--- SOURCE: {url} ---\n{text}")
    return "\n\n".join(parts), errors
