"""Candidates and the stage-2 selection rule.

A candidate is one value for one field, supported by one excerpt of one page.
Each field keeps every value its evidence supports; the fixed rule here picks
one of them, deterministically.
"""

from __future__ import annotations

import math
from datetime import datetime

from dossier_support import FIELDS, collapse_ws, excerpt_value, split_sentences
from pages import parse_page

AUTHORITY = {"own": 2, "filing": 2, "news": 1, "aggregator": 0}
PROVIDER_ORDER = {"nimble": 0, "tavily": 1, "kernel": 2, "browserbase": 3}


def same_value(left: object, right: object) -> bool:
    if isinstance(left, str) and isinstance(right, str):
        return left.strip() == right.strip()
    return left == right


def _json_key(value: object) -> tuple:
    if isinstance(value, bool):
        return (1, str(value))
    if isinstance(value, int):
        return (0, value)
    if isinstance(value, str):
        return (1, value.strip())
    return (2, repr(value))


def _published_timestamp(value: object) -> float | None:
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, str) and value:
        try:
            text = value
            if text[-1] in "Zz":
                text = text[:-1] + "+00:00"
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                return None
            return parsed.timestamp()
        except ValueError:
            return None
    return None


def _recency_key(published: object) -> float:
    timestamp = _published_timestamp(published)
    if timestamp is None:
        return math.inf
    return -timestamp


def rank_key(candidate: dict) -> tuple:
    kind = candidate.get("kind")
    authority = AUTHORITY.get(kind, 0)
    provider = candidate.get("provider")
    return (
        -authority,
        _recency_key(candidate.get("published_at")),
        candidate.get("url") or "",
        PROVIDER_ORDER.get(provider, len(PROVIDER_ORDER)),
        _json_key(candidate.get("value")),
        candidate.get("excerpt") or "",
    )


def order_candidates(candidates: list[dict]) -> list[dict]:
    return sorted(candidates, key=rank_key)


def same_json_value(left: object, right: object) -> bool:
    return _json_key(left) == _json_key(right)


def assemble_field(candidates: list[dict]) -> dict:
    if not candidates:
        return {"value": None, "status": "unknown", "citations": [], "candidates": []}
    ordered = order_candidates(candidates)
    for index, candidate in enumerate(ordered):
        candidate["selected"] = index == 0
    selected = ordered[0]
    value = selected["value"]
    distinct = {_json_key(candidate["value"]) for candidate in ordered}
    status = "known" if len(distinct) == 1 else "contested"
    citations = [
        {
            "url": candidate.get("url") or "",
            "excerpt": candidate.get("excerpt") or "",
            "provider": candidate.get("provider") or "",
        }
        for candidate in ordered
        if same_json_value(candidate["value"], value)
    ]
    return {
        "value": value,
        "status": status,
        "citations": citations,
        "candidates": ordered,
    }


def candidates_from_pages(pages: list[dict], domain: str, company: str, retrieved_at: str) -> dict:
    """Every value that each page supports for each field, once per page."""
    collected: dict[str, list[dict]] = {field: [] for field in FIELDS}
    seen: dict[str, set] = {field: set() for field in FIELDS}

    for page in pages:
        url = (page.get("url") or "").strip()
        text = page.get("text") or ""
        if not url or not text:
            continue
        provider = page.get("provider") or "nimble"
        kind, published, prose = parse_page(text, url, domain)
        published_at = published.isoformat() if published is not None else None
        for line in prose.splitlines():
            for sentence in split_sentences(line):
                excerpt = collapse_ws(sentence)
                if not (1 <= len(excerpt) <= 500):
                    continue
                for field in FIELDS:
                    value = excerpt_value(excerpt, field, company, domain)
                    if value is None:
                        continue
                    key = _json_key(value)
                    if key in seen[field]:
                        continue
                    seen[field].add(key)
                    collected[field].append(
                        {
                            "value": value,
                            "url": url,
                            "excerpt": excerpt,
                            "provider": provider,
                            "kind": kind,
                            "published_at": published_at,
                            "retrieved_at": retrieved_at,
                            "selected": False,
                        }
                    )

    return {field: assemble_field(collected[field]) for field in FIELDS}


def imported_field(value: object, citations: list[dict], researched_at: str | None) -> dict:
    """Synthesize a stage-1 field's candidates from its exported citations."""
    if value is None:
        return {"value": None, "status": "unknown", "citations": [], "candidates": []}
    candidates: list[dict] = []
    seen_urls: set[str] = set()
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        url = citation.get("url")
        excerpt = citation.get("excerpt")
        provider = citation.get("provider")
        if not isinstance(url, str) or not isinstance(excerpt, str):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        candidates.append(
            {
                "value": value,
                "url": url,
                "excerpt": excerpt,
                "provider": provider if isinstance(provider, str) else "nimble",
                "kind": None,
                "published_at": None,
                "retrieved_at": researched_at,
                "selected": False,
            }
        )
    if not candidates:
        return {"value": None, "status": "unknown", "citations": [], "candidates": []}
    return assemble_field(candidates)


def rebuild_field_from_candidates(value: object, candidates: list[dict]) -> dict:
    clean: list[dict] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        clean.append(
            {
                "value": candidate.get("value"),
                "url": candidate.get("url") or "",
                "excerpt": candidate.get("excerpt") or "",
                "provider": candidate.get("provider") or "",
                "kind": candidate.get("kind"),
                "published_at": candidate.get("published_at"),
                "retrieved_at": candidate.get("retrieved_at"),
                "selected": bool(candidate.get("selected")),
            }
        )
    return assemble_field(clean)
