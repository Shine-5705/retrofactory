"""Page header lines: kind, publication time and prose.

Stage 2 defines a page's text as the text a browser shows once the page has
loaded.  A text may begin with header lines of the form ``Name: value`` and the
header ends at the first empty line; everything after it is prose.
"""

from __future__ import annotations

import re
from datetime import datetime

from dossier_support import split_prose

KINDS = ("own", "filing", "news", "aggregator")

_HEADER_NAME_RE = re.compile(r"^[A-Z][a-z]+(?:-[A-Z][a-z]+)*$")
_RFC3339_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$"
)


def is_header_line(line: str) -> bool:
    colon = line.find(":")
    if colon <= 0:
        return False
    return bool(_HEADER_NAME_RE.match(line[:colon]))


def _header_lines(text: str) -> list[str]:
    lines = text.splitlines()
    if not lines or not is_header_line(lines[0]):
        return []
    header: list[str] = []
    for line in lines:
        if line.strip() == "":
            break
        header.append(line)
    return header


def parse_headers(text: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in _header_lines(text):
        colon = line.find(":")
        if colon <= 0:
            continue
        name = line[:colon].strip().lower()
        if name and name not in headers:
            headers[name] = line[colon + 1 :].strip()
    return headers


def parse_published(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not _RFC3339_RE.match(text):
        return None
    if text[-1] in "Zz":
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _host_matches(url: str, domain: str) -> bool:
    try:
        from urllib.parse import urlsplit

        host = urlsplit(url).hostname
    except (ValueError, AttributeError):
        return False
    if not host:
        return False
    host = host.strip().lower()
    while host.endswith("."):
        host = host[:-1]
    if host.startswith("www."):
        host = host[4:]
    return host == domain


def page_kind(url: str, headers: dict[str, str], domain: str) -> str:
    kind = headers.get("kind")
    if kind in KINDS:
        return kind
    return "own" if _host_matches(url, domain) else "aggregator"


def page_published(headers: dict[str, str]) -> datetime | None:
    return parse_published(headers.get("published"))


def parse_page(text: str, url: str, domain: str) -> tuple[str, datetime | None, str]:
    """Return ``(kind, published_at, prose)`` for one page text."""
    headers = parse_headers(text)
    return page_kind(url, headers, domain), page_published(headers), split_prose(text)


def published_iso(published: datetime | None) -> str | None:
    return published.isoformat() if published is not None else None
