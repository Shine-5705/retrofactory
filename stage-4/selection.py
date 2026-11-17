"""Candidates, page versions and the selection rule.

A candidate is one value for one field, supported by one excerpt of one page.
Each field keeps every value its evidence supports; the fixed stage-2 rule here
picks one of them, deterministically.  Executives and investors run rules of
their own (per title / per member).

Stage 4 adds page origins and the three corroboration keys on every field.
"""

from __future__ import annotations

import json
import math
from datetime import datetime

from dossier_support import (
    EXEC_TITLES,
    FIELDS,
    collapse_ws,
    excerpt_value,
    executive_value,
    investor_names,
    split_sentences,
)
from pages import parse_page_details

ALL_FIELDS = FIELDS + ("executives", "investors")
AUTHORITY = {"own": 2, "filing": 2, "news": 1, "aggregator": 0}
PROVIDER_ORDER = {"nimble": 0, "tavily": 1, "kernel": 2, "browserbase": 3}


def same_value(left: object, right: object) -> bool:
    return _json_key(left) == _json_key(right)


def _json_key(value: object) -> tuple:
    if isinstance(value, bool):
        return (2, str(value))
    if isinstance(value, int):
        return (0, value)
    if isinstance(value, str):
        return (1, value.strip())
    if value is None:
        return (3, "")
    if isinstance(value, (list, dict)):
        return (5, json.dumps(value, sort_keys=True, ensure_ascii=False))
    return (4, repr(value))


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


def citation(candidate: dict) -> dict:
    return {
        "url": candidate.get("url") or "",
        "excerpt": candidate.get("excerpt") or "",
        "provider": candidate.get("provider") or "",
    }


def _blank_corroboration() -> dict:
    return {"origins": [], "corroborated": False, "corroborated_since": None}


def _origins_for(candidates: list[dict]) -> list[str]:
    origins = set()
    for candidate in candidates:
        origin = candidate.get("origin")
        if isinstance(origin, str) and origin:
            origins.add(origin)
    return sorted(origins)


def assemble_field(candidates: list[dict]) -> dict:
    if not candidates:
        return {
            "value": None,
            "status": "unknown",
            "citations": [],
            "candidates": [],
            "true_from": None,
            **_blank_corroboration(),
        }
    ordered = order_candidates(candidates)
    for index, candidate in enumerate(ordered):
        candidate["selected"] = index == 0
    selected = ordered[0]
    value = selected["value"]
    distinct = {_json_key(candidate["value"]) for candidate in ordered}
    status = "known" if len(distinct) == 1 else "contested"
    citations = [
        citation(candidate)
        for candidate in ordered
        if same_json_value(candidate["value"], value)
    ]
    origins = _origins_for([c for c in ordered if same_json_value(c["value"], value)])
    return {
        "value": value,
        "status": status,
        "citations": citations,
        "candidates": ordered,
        "true_from": selected.get("true_from"),
        "origins": origins,
        "corroborated": len(origins) >= 2,
        "corroborated_since": None,
    }


def _member_key(member: dict) -> tuple:
    return (_json_key(member.get("name")),)


def assemble_executives(candidates: list[dict]) -> dict:
    by_title: dict[str, list[dict]] = {title: [] for title in EXEC_TITLES}
    for candidate in candidates:
        title = candidate.get("title")
        if title in by_title:
            by_title[title].append(candidate)

    ordered_all: list[dict] = []
    members: list[dict] = []
    selected_by_title: dict[str, dict] = {}
    for title in EXEC_TITLES:
        group = order_candidates(by_title[title])
        for index, candidate in enumerate(group):
            candidate["selected"] = index == 0
        ordered_all.extend(group)
        if group:
            selected_by_title[title] = group[0]
            members.append({"title": title, "name": group[0]["value"]})

    if not members:
        return {
            "value": None,
            "status": "unknown",
            "citations": [],
            "candidates": [],
            "true_from": None,
            **_blank_corroboration(),
        }

    contested = False
    for title in EXEC_TITLES:
        names = {_json_key(c["value"]) for c in by_title[title]}
        if len(names) >= 2:
            contested = True
            break

    citations: list[dict] = []
    for member in members:
        title = member["title"]
        name_key = _json_key(member["name"])
        matching = [
            c for c in by_title[title] if _json_key(c.get("value")) == name_key
        ]
        citations.extend(citation(c) for c in order_candidates(matching))

    member_dates = [
        selected_by_title[title].get("true_from") for title in EXEC_TITLES
        if title in selected_by_title
    ]
    if any(date is None for date in member_dates):
        true_from = None
    else:
        true_from = max(member_dates)

    member_candidates = [
        c for c in ordered_all
        if c.get("title") in selected_by_title
        and same_json_value(c.get("value"), selected_by_title[c["title"]]["value"])
    ]
    member_origins = {
        title: _origins_for(
            [c for c in by_title[title] if same_json_value(c.get("value"), selected_by_title[title]["value"])]
        )
        for title in selected_by_title
    }
    return {
        "value": members,
        "status": "contested" if contested else "known",
        "citations": citations,
        "candidates": ordered_all,
        "true_from": true_from,
        "origins": _origins_for(member_candidates),
        "corroborated": all(len(origins) >= 2 for origins in member_origins.values()),
        "corroborated_since": None,
    }


def _investor_members(candidates: list[dict]) -> list[dict]:
    """Members by name, with the candidates that support each one."""
    by_name: dict[str, list[dict]] = {}
    for candidate in candidates:
        name = candidate.get("value")
        if isinstance(name, str):
            by_name.setdefault(name.strip(), []).append(candidate)
    members = []
    for name in sorted(by_name):
        group = by_name[name]
        authoritative = any(c.get("kind") in ("own", "filing") for c in group)
        origins = {c.get("origin") for c in group if isinstance(c.get("origin"), str) and c.get("origin")}
        if not authoritative and len(origins) < 2:
            continue
        members.append({"name": name, "candidates": group})
    return members


def assemble_investors(candidates: list[dict]) -> dict:
    ordered = order_candidates(candidates)
    members = _investor_members(ordered)
    if not members:
        for index, candidate in enumerate(ordered):
            candidate["selected"] = False
        return {
            "value": None,
            "status": "unknown",
            "citations": [],
            "candidates": ordered,
            "true_from": None,
            **_blank_corroboration(),
        }

    member_names = {m["name"] for m in members}
    for candidate in ordered:
        name = candidate.get("value")
        candidate["selected"] = isinstance(name, str) and name.strip() in member_names

    value = [m["name"] for m in members]
    citations: list[dict] = []
    member_true_from: dict[str, str | None] = {}
    for member in members:
        group = order_candidates(member["candidates"])
        citations.extend(citation(c) for c in group)
        dates = [c.get("true_from") for c in group if isinstance(c.get("true_from"), str) and c["true_from"]]
        member_true_from[member["name"]] = min(dates) if dates else None

    true_from = None
    if member_true_from and all(date is not None for date in member_true_from.values()):
        true_from = max(member_true_from.values())

    all_origins = _origins_for([c for c in ordered if c.get("selected")])
    member_origins = {
        m["name"]: _origins_for(m["candidates"]) for m in members
    }
    return {
        "value": value,
        "status": "known",
        "citations": citations,
        "candidates": ordered,
        "true_from": true_from,
        "origins": all_origins,
        "corroborated": all(len(o) >= 2 for o in member_origins.values()),
        "corroborated_since": None,
    }


def _candidate_origin(details: dict, domain: str) -> str:
    """Resolve a page's origin from rule 1..4 (no canonical chain fetch here).

    The build resolves canonical chains through the provider and puts the final
    origin in ``details['origin_resolved']``; when absent, fall back to the
    host of the canonical URL (rule 16) or the registrant (rule 4).
    """
    resolved = details.get("origin_resolved")
    if isinstance(resolved, str) and resolved:
        return resolved
    first = details.get("first_published_by")
    if first:
        return first
    canonical = details.get("canonical")
    if canonical:
        from pages import url_host

        host = url_host(canonical)
        if host:
            return host
    if details.get("lookalike"):
        return domain
    registrant = details.get("registrant")
    if registrant:
        return registrant
    from pages import url_host

    return url_host(details.get("url") or "") or domain


def collect_candidates(
    pages: list[dict], domain: str, company: str, retrieved_at: str
) -> dict[str, list[dict]]:
    """Every value that each page supports, once per page, per field and title."""
    collected: dict[str, list[dict]] = {field: [] for field in ALL_FIELDS}
    seen: dict[str, set] = {field: set() for field in ALL_FIELDS}

    for page in pages:
        url = (page.get("url") or "").strip()
        text = page.get("text") or ""
        if not url or not text:
            continue
        provider = page.get("provider") or "nimble"
        details = parse_page_details(text, url, domain)
        if page.get("origin_resolved"):
            details["origin_resolved"] = page["origin_resolved"]
        kind = details["kind"]
        published_at = details["published_at"]
        true_from = details["true_from"]
        origin = _candidate_origin(details, domain)
        for line in details["prose"].splitlines():
            for sentence in split_sentences(line):
                excerpt = collapse_ws(sentence)
                if not (1 <= len(excerpt) <= 500):
                    continue
                for field in FIELDS:
                    value = excerpt_value(excerpt, field, company, domain)
                    if value is None:
                        continue
                    key = (url, _json_key(value))
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
                            "true_from": true_from,
                            "retrieved_at": retrieved_at,
                            "origin": origin,
                            "selected": False,
                        }
                    )
                for title in EXEC_TITLES:
                    name = executive_value(excerpt, title, company, domain)
                    if name is None:
                        continue
                    key = (title, url, _json_key(name))
                    if key in seen["executives"]:
                        continue
                    seen["executives"].add(key)
                    collected["executives"].append(
                        {
                            "title": title,
                            "value": name,
                            "url": url,
                            "excerpt": excerpt,
                            "provider": provider,
                            "kind": kind,
                            "published_at": published_at,
                            "true_from": true_from,
                            "retrieved_at": retrieved_at,
                            "origin": origin,
                            "selected": False,
                        }
                    )
                for name in investor_names(excerpt, company, domain):
                    key = (url, _json_key(name))
                    if key in seen["investors"]:
                        continue
                    seen["investors"].add(key)
                    collected["investors"].append(
                        {
                            "value": name,
                            "url": url,
                            "excerpt": excerpt,
                            "provider": provider,
                            "kind": kind,
                            "published_at": published_at,
                            "true_from": true_from,
                            "retrieved_at": retrieved_at,
                            "origin": origin,
                            "selected": False,
                        }
                    )

    return collected


def imported_field(value: object, citations: list[dict], researched_at: str | None) -> dict:
    """Synthesize a stage-1 field's candidates from its exported citations."""
    if value is None:
        return {
            "value": None,
            "status": "unknown",
            "citations": [],
            "candidates": [],
            "true_from": None,
            **_blank_corroboration(),
        }
    candidates: list[dict] = []
    seen_urls: set[str] = set()
    for item in citations:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        excerpt = item.get("excerpt")
        provider = item.get("provider")
        if not isinstance(url, str) or not isinstance(excerpt, str):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        from pages import url_host

        candidates.append(
            {
                "value": value,
                "url": url,
                "excerpt": excerpt,
                "provider": provider if isinstance(provider, str) else "nimble",
                "kind": None,
                "published_at": None,
                "true_from": None,
                "retrieved_at": researched_at,
                "learned_at": researched_at,
                "origin": item.get("origin") or url_host(url) or "",
                "selected": False,
            }
        )
    if not candidates:
        return {
            "value": None,
            "status": "unknown",
            "citations": [],
            "candidates": [],
            "true_from": None,
            **_blank_corroboration(),
        }
    return assemble_field(candidates)


def rebuild_field_from_candidates(
    value: object, candidates: list[dict], researched_at: str | None = None
) -> dict:
    clean: list[dict] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        learned = candidate.get("learned_at")
        if not isinstance(learned, str):
            learned = candidate.get("retrieved_at")
        if not isinstance(learned, str):
            learned = researched_at
        from pages import url_host

        origin = candidate.get("origin")
        if not isinstance(origin, str) or not origin:
            origin = url_host(candidate.get("url") or "") or ""
        clean.append(
            {
                "value": candidate.get("value"),
                "url": candidate.get("url") or "",
                "excerpt": candidate.get("excerpt") or "",
                "provider": candidate.get("provider") or "",
                "kind": candidate.get("kind"),
                "published_at": candidate.get("published_at"),
                "true_from": candidate.get("true_from"),
                "retrieved_at": candidate.get("retrieved_at"),
                "learned_at": learned,
                "origin": origin,
                "selected": bool(candidate.get("selected")),
            }
        )
    return assemble_field(clean)
