"""Page header lines: kind, publication time, effective date, lineage and prose.

A page's text is the text a browser shows once the page has loaded.  A text may
begin with header lines of the form ``Name: value`` and the header ends at the
first empty line; everything after it is prose.  ``Effective: <YYYY-MM-DD>``
states the date from which the page's evidence holds; a page without a valid
``Effective`` line takes the date part, in UTC, of its ``Published`` time.

Stage 4 adds three header lines: ``Registrant``, ``Canonical`` and
``First-Published-By``.  From them a page's registrant, lookalike status and
origin are derived (see ``resolve_origin``).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

from dossier_support import split_prose

KINDS = ("own", "filing", "news", "aggregator")

_HEADER_NAME_RE = re.compile(r"^[A-Z][a-z]+(?:-[A-Z][a-z]+)*$")
_RFC3339_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$"
)
_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_DOMAIN_LABEL_RE = re.compile(r"^[a-z0-9-]+$")


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


def parse_effective_date(value: str | None) -> str | None:
    """A valid ``Effective`` header line carries a bare ``YYYY-MM-DD`` date."""
    if not value:
        return None
    text = value.strip()
    if not _DATE_RE.match(text):
        return None
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return None
    return parsed.date().isoformat()


def normalise_host(value: object) -> str | None:
    """Apply stage-1 §4 domain normalisation to a domain or a URL's host.

    Returns the normalised domain, or ``None`` when the value is not a valid
    host name.  A value with a scheme or a path is not a domain; callers that
    need a URL's host should use ``url_host`` first.
    """
    if not isinstance(value, str):
        return None
    domain = value.strip().lower()
    if not domain or "/" in domain or "?" in domain or "#" in domain or " " in domain:
        return None
    if domain.endswith("."):
        domain = domain[:-1]
    if domain.startswith("www."):
        domain = domain[4:]
    if not domain or len(domain) > 253:
        return None
    labels = domain.split(".")
    if len(labels) < 2:
        return None
    for label in labels:
        if not (1 <= len(label) <= 63) or not _DOMAIN_LABEL_RE.match(label):
            return None
        if label.startswith("-") or label.endswith("-"):
            return None
    return domain


def url_host(url: str) -> str | None:
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return None
    return normalise_host(host) if host else None


def _host_matches(url: str, domain: str) -> bool:
    return url_host(url) == domain


def page_registrant(url: str, headers: dict[str, str]) -> str | None:
    """The page's registrant: a valid Registrant line, else its own host."""
    registrant = normalise_host(headers.get("registrant"))
    if registrant is not None:
        return registrant
    return url_host(url)


def is_lookalike(url: str, headers: dict[str, str]) -> bool:
    """A Kind: own page whose registrant is not the host of its own URL."""
    if headers.get("kind") != "own":
        return False
    own_host = url_host(url)
    registrant = normalise_host(headers.get("registrant"))
    return registrant is not None and own_host is not None and registrant != own_host


def page_kind(url: str, headers: dict[str, str], domain: str) -> str:
    declared = headers.get("kind")
    if declared in KINDS:
        if declared == "own":
            registrant = page_registrant(url, headers)
            if registrant is not None and registrant != domain:
                return "aggregator"
        return declared
    return "own" if _host_matches(url, domain) else "aggregator"


def canonical_url(headers: dict[str, str]) -> str | None:
    raw = headers.get("canonical")
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if text.startswith(("http://", "https://")):
        return text
    return None


def first_published_by(headers: dict[str, str]) -> str | None:
    return normalise_host(headers.get("first-published-by"))


def page_published(headers: dict[str, str]) -> datetime | None:
    return parse_published(headers.get("published"))


def published_utc_date(published: datetime | None) -> str | None:
    if published is None:
        return None
    return published.astimezone(timezone.utc).date().isoformat()


def page_true_from(headers: dict[str, str], published: datetime | None) -> str | None:
    effective = parse_effective_date(headers.get("effective"))
    if effective is not None:
        return effective
    return published_utc_date(published)


def parse_page_details(text: str, url: str, domain: str) -> dict:
    """Return page properties: kind, publication time, true_from, lineage and prose."""
    headers = parse_headers(text)
    published = page_published(headers)
    registrant = page_registrant(url, headers)
    return {
        "kind": page_kind(url, headers, domain),
        "published": published,
        "published_at": published.isoformat() if published is not None else None,
        "true_from": page_true_from(headers, published),
        "headers": headers,
        "url": url,
        "registrant": registrant,
        "canonical": canonical_url(headers),
        "first_published_by": first_published_by(headers),
        "lookalike": is_lookalike(url, headers),
        "prose": split_prose(text),
    }


def parse_page(text: str, url: str, domain: str) -> tuple[str, datetime | None, str]:
    """Backwards-compatible ``(kind, published_at, prose)`` for one page text."""
    details = parse_page_details(text, url, domain)
    return details["kind"], details["published"], details["prose"]


def published_iso(published: datetime | None) -> str | None:
    return published.isoformat() if published is not None else None
