"""Dossier service (stage 4): independent origins, investors and batches.

A small threaded HTTP service.  All state is held in memory and mirrored to the
container filesystem so it survives a container restart.  Background builds
research a domain through WebRouter (Nimble) and decide each field only from
provider-served text using the Appendix A support rules in dossier_support.py.
"""

from __future__ import annotations

import copy
import json
import os
import re
import secrets
import tempfile
import threading
import time
from datetime import datetime, timezone

from flask import Flask, Response, redirect, request
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

from dossier_support import (
    EXEC_TITLES,
    FIELDS,
    collapse_ws,
    excerpt_value,
    split_prose,
    split_sentences,
)
from pages import parse_page_details
from selection import (
    ALL_FIELDS,
    assemble_executives,
    assemble_field,
    assemble_investors,
    collect_candidates,
    imported_field,
    rebuild_field_from_candidates,
    same_json_value,
)
from webui import (
    auth_page,
    contested_page,
    dossier_page,
    evidence_page,
    history_page,
    list_page,
    message_page,
)

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

DEFAULT_PORT = 8080
MAX_UNITS = 80

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+$")
_DOMAIN_LABEL_RE = re.compile(r"^[a-z0-9-]+$")
_INT_QUERY_RE = re.compile(r"^[0-9]+$")
_DATE_ONLY_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")

_STRING_FIELDS = {"legal_name", "hq_city", "ceo", "headcount_range"}
_INT_FIELDS = {"founded_year", "funding_total"}

RESEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        field: {"type": ["integer", "null"] if field in _INT_FIELDS else ["string", "null"]}
        for field in FIELDS
    },
    "required": list(FIELDS),
}


def now_iso(dt: datetime) -> str:
    return dt.isoformat()


def parse_rfc3339(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def parse_date_only(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    match = _DATE_ONLY_RE.match(value.strip())
    if not match:
        return None
    try:
        parsed = datetime.strptime(value.strip(), "%Y-%m-%d")
    except ValueError:
        return None
    return parsed.date().isoformat()


def normalise_domain(raw: object) -> str:
    if not isinstance(raw, str):
        raise ValueError("domain must be a string")
    domain = raw.strip().lower()
    if domain.endswith("."):
        domain = domain[:-1]
    if domain.startswith("www."):
        domain = domain[4:]
    if len(domain) > 253:
        raise ValueError("domain too long")
    labels = domain.split(".")
    if len(labels) < 2:
        raise ValueError("domain needs two labels")
    for label in labels:
        if not (1 <= len(label) <= 63):
            raise ValueError("bad label length")
        if not _DOMAIN_LABEL_RE.match(label):
            raise ValueError("bad label characters")
        if label.startswith("-") or label.endswith("-"):
            raise ValueError("bad label boundary")
    return domain


def company_name(domain: str) -> str:
    return domain.split(".", 1)[0].replace("-", " ")


def empty_field() -> dict:
    return {
        "value": None,
        "status": "unknown",
        "citations": [],
        "candidates": [],
        "true_from": None,
        "learned_at": None,
        "origins": [],
        "corroborated": False,
        "corroborated_since": None,
    }


def empty_fields() -> dict:
    return {field: empty_field() for field in ALL_FIELDS}


# --------------------------------------------------------------------------
# State


class State:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.frozen_clock: datetime | None = None
        self.users: dict[str, dict] = {}
        self.email_index: dict[str, str] = {}
        self.tokens: dict[str, str] = {}
        self.dossiers: dict[str, dict] = {}
        self.idem: dict[tuple, dict] = {}
        self.next_user = 1
        self.next_dossier = 1
        self.next_seq = 1
        self.next_build_seq = 1
        self.next_batch = 1
        self.batches: dict[str, dict] = {}
        self.feed: list[dict] = []

    def now(self) -> datetime:
        if self.frozen_clock is not None:
            return self.frozen_clock
        return datetime.now(timezone.utc)


_GLOBAL_LOCK = threading.RLock()
_STATE = State()


def get_state() -> State:
    return _STATE


# --------------------------------------------------------------------------
# Persistence: the container filesystem is the durable disk row.


def _state_path() -> str:
    explicit = os.environ.get("DOSSIER_STATE_FILE")
    if explicit:
        return explicit
    directory = os.environ.get("DOSSIER_STATE_DIR")
    candidates = []
    if directory:
        candidates.append(directory)
    candidates.append("/app/state")
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "state"))
    for candidate in candidates:
        try:
            os.makedirs(candidate, exist_ok=True)
            if os.access(candidate, os.W_OK):
                return os.path.join(candidate, "state.json")
        except OSError:
            continue
    fallback = os.path.join(tempfile.gettempdir(), "dossier-state")
    os.makedirs(fallback, exist_ok=True)
    return os.path.join(fallback, "state.json")


_STATE_FILE = _state_path()


def _serialise_dossier(dossier: dict, building_as_before: bool = True) -> dict:
    building = bool(dossier.get("building"))
    if building and building_as_before:
        outcome = dossier.get("last_outcome") or "failed"
        spent = dossier.get("base_spent", dossier.get("spent_units", 0))
    else:
        outcome = dossier.get("state")
        spent = dossier.get("spent_units", 0)
    return {
        "id": dossier["id"],
        "domain": dossier["domain"],
        "state": outcome,
        "last_outcome": dossier.get("last_outcome"),
        "researched_at": dossier.get("researched_at"),
        "spent_units": spent,
        "live_spent": dossier.get("spent_units", spent),
        "base_spent": dossier.get("base_spent", spent),
        "fields": copy.deepcopy(dossier["fields"]),
        "builds": copy.deepcopy(dossier.get("builds", [])),
        "history": copy.deepcopy(dossier.get("history", {})),
        "gathered": dict(dossier.get("gathered", {})),
        "has_ready": bool(dossier.get("has_ready")),
        "building": building,
    }


def _serialise_state(state: State) -> dict:
    idempotency = []
    for (user_id, method, path, key), record in state.idem.items():
        idempotency.append(
            {
                "user_id": user_id,
                "method": method,
                "path": path,
                "key": key,
                "body": record["body"],
                "response": copy.deepcopy(record["response"]),
            }
        )
    return {
        "clock": now_iso(state.frozen_clock) if state.frozen_clock is not None else None,
        "users": [
            {
                "id": user["id"],
                "email": user["email"],
                "display_name": user["display_name"],
                "password_hash": user["password_hash"],
            }
            for user in state.users.values()
        ],
        "tokens": dict(state.tokens),
        "dossiers": [_serialise_dossier(d) for d in state.dossiers.values()],
        "idempotency": idempotency,
        "next_user": state.next_user,
        "next_dossier": state.next_dossier,
        "next_batch": state.next_batch,
        "batches": copy.deepcopy(state.batches),
        "stage3": {
            "feed": copy.deepcopy(state.feed),
            "next_seq": state.next_seq,
            "next_build_seq": state.next_build_seq,
        },
    }


def _write_state(data: dict) -> None:
    try:
        directory = os.path.dirname(_STATE_FILE)
        os.makedirs(directory, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=directory, prefix=".state-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, _STATE_FILE)
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
    except OSError:
        pass


def persist_state(state: State | None = None) -> None:
    target = state if state is not None else _STATE
    with target.lock:
        with _GLOBAL_LOCK:
            if target is not _STATE:
                return
            data = _serialise_state(target)
            _write_state(data)


# --------------------------------------------------------------------------
# HTTP helpers


def json_response(payload: object, status: int = 200) -> Response:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    response = Response(body, status=status, mimetype="application/json")
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response


def empty_response(status: int = 204) -> Response:
    response = Response("", status=status, mimetype="application/json")
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response


def error_response(status: int, code: str, message: str = "") -> Response:
    return json_response({"error": {"code": code, "message": message or code}}, status)


def validation_error(message: str = "validation failed") -> Response:
    return error_response(422, "validation_failed", message)


def malformed(message: str = "malformed request") -> Response:
    return error_response(400, "malformed_request", message)


def not_found(message: str = "not found") -> Response:
    return error_response(404, "not_found", message)


def unauthenticated(message: str = "unauthenticated") -> Response:
    return error_response(401, "unauthenticated", message)


def read_json_body():
    raw = request.get_data(cache=True)
    if not raw:
        return None, False
    try:
        return json.loads(raw.decode("utf-8")), True
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, False


def canonical_body(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


SESSION_COOKIE = "dossier_session"


def bearer_token() -> str | None:
    header = request.headers.get("Authorization")
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def auth_user(state: State) -> str | None:
    token = bearer_token()
    if token is None:
        token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    with state.lock:
        return state.tokens.get(token)


def current_user(state: State) -> dict | None:
    user_id = auth_user(state)
    if user_id is None:
        return None
    with state.lock:
        user = state.users.get(user_id)
        if user is None:
            return None
        return {"id": user["id"], "email": user["email"], "display_name": user["display_name"]}


def idempotency_header() -> tuple[str | None, Response | None]:
    raw = request.headers.get("Idempotency-Key")
    if raw is None or raw == "":
        return None, error_response(400, "missing_idempotency_key", "Idempotency-Key is required")
    if len(raw) > 255:
        return None, validation_error("Idempotency-Key is too long")
    return raw, None


def token_for_user(state: State) -> str:
    while True:
        token = secrets.token_urlsafe(32)
        if len(token) <= 64 and token not in state.tokens:
            return token


def integer_query(name: str, default: int | None, minimum: int, maximum: int | None) -> tuple[int | None, Response | None]:
    raw = request.args.get(name)
    if raw is None:
        return default, None
    if not _INT_QUERY_RE.match(raw):
        return None, validation_error(f"{name} must be plain decimal digits")
    value = int(raw)
    if value < minimum or (maximum is not None and value > maximum):
        return None, validation_error(f"{name} is out of range")
    return value, None


# --------------------------------------------------------------------------
# Representation


def dossier_view(dossier: dict) -> dict:
    return {
        "dossier_id": dossier["id"],
        "domain": dossier["domain"],
        "state": dossier["state"],
        "researched_at": dossier["researched_at"],
        "spent_units": dossier["spent_units"],
        "fields": copy.deepcopy(dossier["fields"]),
    }


def dossier_brief(dossier: dict) -> dict:
    return {
        "dossier_id": dossier["id"],
        "domain": dossier["domain"],
        "state": dossier["state"],
    }


def _build_time(build: dict) -> datetime | None:
    return parse_rfc3339(build.get("time"))


def _builds_at(dossier: dict, as_of: datetime, ready_only: bool) -> list[dict]:
    chosen = []
    for build in dossier.get("builds", []):
        when = _build_time(build)
        if when is None:
            continue
        if when <= as_of and (not ready_only or build.get("outcome") == "ready"):
            chosen.append(build)
    chosen.sort(key=lambda b: (b.get("seq", 0)))
    return chosen


def _field_selected_learned(field_entry: dict) -> str | None:
    if not isinstance(field_entry, dict) or field_entry.get("value") is None:
        return None
    return field_entry.get("learned_at")


# --------------------------------------------------------------------------
# Provider access


_router = None
_router_lock = threading.Lock()


def get_router():
    global _router
    if _router is None:
        with _router_lock:
            if _router is None:
                from web_router import WebRouter

                _router = WebRouter("nimble")
    return _router


def _exception_was_refused(exc: Exception) -> bool:
    """True when the provider answered with an error status (such a call costs 0)."""
    try:
        from web_router.exceptions import DeadlineExceededError, ProviderError, WebRouterError
        from web_router.exceptions_typed import AllProvidersFailedError
    except Exception:  # pragma: no cover - web_router always provides these
        return False
    if isinstance(exc, DeadlineExceededError):
        return False
    if isinstance(exc, AllProvidersFailedError):
        return all(
            getattr(inner, "status_code", None) is not None
            for inner in getattr(exc, "failures", {}).values()
        ) and bool(getattr(exc, "failures", {}))
    if isinstance(exc, ProviderError):
        return exc.status_code is not None
    if isinstance(exc, WebRouterError):
        return True  # configuration / unsupported / missing parameter: never sent
    return False


def _reserve(state: State, dossier: dict, cost: int) -> bool:
    with state.lock:
        if dossier["build_spent"] + cost > MAX_UNITS:
            return False
        batch_id = dossier.get("build_batch_id")
        if batch_id is not None:
            batch = state.batches.get(batch_id)
            if batch is not None and batch["spent_units"] + cost > batch["budget_units"]:
                return False
        dossier["build_spent"] += cost
        dossier["spent_units"] += cost
        if batch_id is not None:
            batch = state.batches.get(batch_id)
            if batch is not None:
                batch["spent_units"] += cost
        return True


def _refund(state: State, dossier: dict, cost: int) -> None:
    with state.lock:
        dossier["build_spent"] = max(0, dossier["build_spent"] - cost)
        dossier["spent_units"] = max(0, dossier["spent_units"] - cost)
        batch_id = dossier.get("build_batch_id")
        if batch_id is not None:
            batch = state.batches.get(batch_id)
            if batch is not None:
                batch["spent_units"] = max(0, batch["spent_units"] - cost)


def _timeout_for(deadline: float, cap: float) -> float | None:
    remaining = deadline - time.monotonic()
    if remaining <= 5:
        return None
    return max(1.0, min(cap, remaining - 2.0))


def _is_429(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status == 429:
        return True
    failures = getattr(exc, "failures", None)
    if isinstance(failures, dict) and failures:
        return all(getattr(inner, "status_code", None) == 429 for inner in failures.values())
    return False


class Deadline:
    """A build deadline that 429 back-off waits extend, so they are not charged to it."""

    def __init__(self, seconds: float) -> None:
        self.at = time.monotonic() + seconds

    def remaining(self) -> float:
        return self.at - time.monotonic()

    def extend(self, seconds: float) -> None:
        self.at += seconds


def _with_429(state: State, dossier: dict, cost: int, deadline: Deadline, call):
    """Make one provider call, retrying a 429 after a full second, up to three times."""
    attempts = 0
    while True:
        if not _reserve(state, dossier, cost):
            return None
        if deadline.remaining() <= 5:
            _refund(state, dossier, cost)
            return None
        try:
            result = call(deadline)
            persist_state(state)
            return result
        except Exception as exc:
            if _is_429(exc):
                _refund(state, dossier, cost)
                persist_state(state)
                attempts += 1
                if attempts > 3:
                    return None
                time.sleep(1.05)
                deadline.extend(1.05)
                continue
            if _exception_was_refused(exc):
                _refund(state, dossier, cost)
            persist_state(state)
            return None


def _do_search(state: State, dossier: dict, query: str, cost: int, deadline: Deadline):
    def call(deadline: Deadline):
        timeout = _timeout_for(deadline.at, 60.0)
        if timeout is None:
            raise TimeoutError("no time left")
        return get_router().search(
            query,
            provider="nimble",
            search_depth="lite",
            max_results=10,
            timeout=timeout,
            data_apis=False,
        )

    return _with_429(state, dossier, cost, deadline, call)


def _do_research(state: State, dossier: dict, query: str, cost: int, deadline: Deadline):
    def call(deadline: Deadline):
        timeout = _timeout_for(deadline.at, 200.0)
        if timeout is None:
            raise TimeoutError("no time left")
        return get_router().research(
            query,
            provider="nimble",
            output_schema=RESEARCH_SCHEMA,
            timeout=timeout,
        )

    return _with_429(state, dossier, cost, deadline, call)


def _do_extract(state: State, dossier: dict, url: str, deadline: Deadline):
    """Read one page's browser-rendered text: 3 units per URL requested."""

    def call(deadline: Deadline):
        timeout = _timeout_for(deadline.at, 30.0)
        if timeout is None:
            raise TimeoutError("no time left")
        return get_router().extract(
            [url],
            provider="nimble",
            provider_options={"render": True},
            timeout=timeout,
        )

    return _with_429(state, dossier, 3, deadline, call)


def _search_urls(response, urls: list[str]) -> None:
    if response is None:
        return
    for result in getattr(response, "results", []) or []:
        url = getattr(result, "url", "") or ""
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            urls.append(url)


def _citation_urls(response, urls: list[str]) -> None:
    if response is None:
        return
    for citation in getattr(response, "citations", []) or []:
        url = getattr(citation, "url", "") or ""
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            urls.append(url)


def _extract_text(response, requested_url: str) -> list[dict]:
    pages: list[dict] = []
    if response is None:
        return pages
    provider = getattr(response, "provider", None) or "nimble"
    for document in getattr(response, "documents", []) or []:
        text = getattr(document, "content", "") or ""
        url = getattr(document, "url", "") or requested_url
        title = getattr(document, "title", "") or ""
        if isinstance(text, str) and text.strip():
            pages.append({"url": url, "title": title, "text": text, "provider": provider})
    return pages


def _priority_urls(urls: list[str], citation_urls: set[str], domain: str) -> list[str]:
    from urllib.parse import urlsplit

    def host(url: str) -> str:
        try:
            value = urlsplit(url).hostname or ""
        except ValueError:
            return ""
        value = value.lower()
        while value.endswith("."):
            value = value[:-1]
        if value.startswith("www."):
            value = value[4:]
        return value

    unique: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)

    def key(url: str) -> tuple:
        return (0 if url in citation_urls else 1, 0 if host(url) == domain else 1)

    return sorted(unique, key=key)


_EXTRA_QUERIES = [
    "{company} company profile",
    "{company} headquarters founded CEO funding employees",
    "{company} official website about company",
    "{company} about us founded headquarters chief executive",
]


# --------------------------------------------------------------------------
# Builds, learned_at, history and the change feed


def _identity_value(value: object) -> str:
    if isinstance(value, str):
        return "s:" + value.strip()
    return "j:" + json.dumps(value, sort_keys=True, ensure_ascii=False)


def candidate_identity(field: str, candidate: dict) -> str:
    parts = [field]
    if field == "executives":
        parts.append(str(candidate.get("title") or ""))
    parts.append(_identity_value(candidate.get("value")))
    parts.append(str(candidate.get("url") or ""))
    parts.append(str(candidate.get("provider") or ""))
    return json.dumps(parts, ensure_ascii=False)


def _assign_learned(dossier: dict, raw: dict[str, list[dict]], build_time: str) -> None:
    gathered = dossier.setdefault("gathered", {})
    for field in ALL_FIELDS:
        for candidate in raw.get(field, []):
            key = candidate_identity(field, candidate)
            record = gathered.get(key)
            if isinstance(record, dict):
                candidate["learned_at"] = record.get("at") or build_time
            elif isinstance(record, str):
                candidate["learned_at"] = record
            else:
                gathered[key] = {
                    "at": build_time,
                    "origin": candidate.get("origin"),
                    "value": candidate.get("value"),
                    "field": field,
                }
                candidate["learned_at"] = build_time


def _member_names_of(entry: dict) -> list[tuple[str, object]]:
    """Return (title-or-name, member value) pairs for a member field."""
    pairs: list[tuple[str, object]] = []
    value = entry.get("value")
    if not isinstance(value, list):
        return pairs
    for member in value:
        if isinstance(member, str):
            pairs.append(("", member))
            continue
        if not isinstance(member, dict):
            continue
        title = member.get("title")
        name = member.get("name")
        if isinstance(title, str) and isinstance(name, str):
            pairs.append((title, name))
        elif isinstance(name, str):
            pairs.append(("", name))
    return pairs


def _standing_origins(
    gathered: dict,
    field: str,
    value: object,
    since: str | None,
    member: tuple | None,
    until: str | None = None,
) -> set[str]:
    """Origins of candidates for a value gathered in ``[since, until]``.

    ``since`` is normally the time the value became selected (its ``learned_at``)
    and ``until`` bounds a candidate build for ``corroborated_since``.  Records
    are never removed, so standing origins accumulate across builds even when a
    later build does not re-gather them (S4-22/S4-30).
    """
    origins: set[str] = set()
    try:
        since_dt = parse_rfc3339(since) if since else None
    except Exception:
        since_dt = None
    try:
        until_dt = parse_rfc3339(until) if until else None
    except Exception:
        until_dt = None
    for key, record in gathered.items():
        if not isinstance(record, dict) or record.get("field") != field:
            continue
        if not same_json_value(record.get("value"), value):
            continue
        origin = record.get("origin")
        if not isinstance(origin, str) or not origin:
            continue
        at = parse_rfc3339(record.get("at"))
        if since_dt is not None and (at is None or at < since_dt):
            continue
        if until_dt is not None and (at is None or at > until_dt):
            continue
        if member is not None:
            if not isinstance(key, str):
                continue
            if member[0] and member[0] not in key:
                continue
        origins.add(origin)
    return origins


def _member_current_origins(entry: dict, field: str) -> dict[tuple, set[str]]:
    """Per-member origins from the field's current candidates (S4-27/S4-28)."""
    members = _member_names_of(entry)
    result: dict[tuple, set[str]] = {}
    for m in members:
        origins: set[str] = set()
        for candidate in entry.get("candidates") or []:
            if not isinstance(candidate, dict):
                continue
            if m[0] and candidate.get("title") != m[0]:
                continue
            if not same_json_value(candidate.get("value"), m[1]):
                continue
            origin = candidate.get("origin")
            if isinstance(origin, str) and origin:
                origins.add(origin)
        result[m] = origins
    return result


def _decorate_corroboration(
    dossier: dict, fields: dict[str, dict], build_time: str
) -> None:
    """Fill origins/corroborated/corroborated_since on every field.

    ``origins`` and ``corroborated`` come from the field's current candidates
    (S4-19/S4-20 and S4-27/S4-28); ``corroborated_since`` is the earliest ready
    build after which the selected value has had two or more standing origins,
    counted from the value's ``learned_at`` (S4-21/S4-22/S4-29/S4-30, A3).
    """
    gathered = dossier.get("gathered") or {}
    build_times = sorted(
        dt for dt in (
            [parse_rfc3339(b.get("time")) for b in dossier.get("builds", [])
             if b.get("outcome") == "ready"]
            + [parse_rfc3339(build_time)]
        )
        if dt is not None
    )
    for field in ALL_FIELDS:
        entry = fields.get(field)
        if not isinstance(entry, dict):
            continue
        if entry.get("value") is None:
            entry["origins"] = []
            entry["corroborated"] = False
            entry["corroborated_since"] = None
            continue
        learned_at = entry.get("learned_at")
        if field in ("executives", "investors"):
            current = _member_current_origins(entry, field)
            entry["origins"] = sorted(set().union(*current.values())) if current else []
            entry["corroborated"] = bool(current) and all(len(o) >= 2 for o in current.values())
            since = None
            for stamp in build_times:
                iso = now_iso(stamp)
                if all(
                    len(_standing_origins(gathered, field, m[1], learned_at, m, iso)) >= 2
                    for m in current
                ):
                    since = iso
                    break
            entry["corroborated_since"] = since
        else:
            value = entry.get("value")
            origins = _origins_from_candidates(
                [c for c in entry.get("candidates") or []
                 if isinstance(c, dict) and same_json_value(c.get("value"), value)]
            )
            entry["origins"] = origins
            entry["corroborated"] = len(origins) >= 2
            since = None
            for stamp in build_times:
                iso = now_iso(stamp)
                if len(_standing_origins(gathered, field, value, learned_at, None, iso)) >= 2:
                    since = iso
                    break
            entry["corroborated_since"] = since


def _origins_from_candidates(candidates: list[dict]) -> list[str]:
    origins = set()
    for candidate in candidates:
        origin = candidate.get("origin")
        if isinstance(origin, str) and origin:
            origins.add(origin)
    return sorted(origins)


def _page_versions(pages: list[dict], raw: dict[str, list[dict]], domain: str) -> list[dict]:
    versions: dict[str, dict] = {}
    for page in pages:
        url = (page.get("url") or "").strip()
        text = page.get("text") or ""
        if not url or not text:
            continue
        details = parse_page_details(text, url, domain)
        if url not in versions:
            versions[url] = {
                "url": url,
                "true_from": details["true_from"],
                "candidates": [],
            }
    for field in ALL_FIELDS:
        for candidate in raw.get(field, []):
            url = candidate.get("url") or ""
            version = versions.get(url)
            if version is None:
                version = {"url": url, "true_from": candidate.get("true_from"), "candidates": []}
                versions[url] = version
            version["candidates"].append(
                {
                    "field": field,
                    "title": candidate.get("title"),
                    "value": candidate.get("value"),
                    "url": url,
                    "excerpt": candidate.get("excerpt") or "",
                    "provider": candidate.get("provider") or "",
                    "kind": candidate.get("kind"),
                    "published_at": candidate.get("published_at"),
                    "true_from": candidate.get("true_from"),
                    "retrieved_at": candidate.get("retrieved_at"),
                    "learned_at": candidate.get("learned_at"),
                    "origin": candidate.get("origin"),
                }
            )
    return list(versions.values())


def _selected_members(field_entry: dict) -> dict[str, tuple[object, object]]:
    members: dict[str, tuple[object, object]] = {}
    for candidate in field_entry.get("candidates") or []:
        if not isinstance(candidate, dict) or not candidate.get("selected"):
            continue
        title = candidate.get("title")
        if title in EXEC_TITLES:
            members[title] = (candidate.get("value"), candidate.get("true_from"))
    if not members:
        for member in field_entry.get("value") or []:
            if isinstance(member, dict) and member.get("title") in EXEC_TITLES:
                members[member["title"]] = (member.get("name"), None)
    return members


def _exec_entry_type(earlier: dict, new: dict) -> str:
    old = _selected_members(earlier)
    now = _selected_members(new)
    differing = []
    for title in set(old) | set(now):
        in_old = title in old
        in_new = title in now
        if in_old != in_new:
            differing.append(title)
        elif not same_json_value(old[title][0], now[title][0]):
            differing.append(title)
    if not differing:
        return "change"
    for title in differing:
        if title not in old or title not in now:
            return "change"
        old_date = old[title][1]
        new_date = now[title][1]
        if old_date is None or new_date is None:
            return "change"
        if not (str(new_date) <= str(old_date)):
            return "change"
    return "correction"


def _investor_member_dates(entry: dict) -> dict[str, str | None]:
    """Earliest non-null ``true_from`` per member name (S4-46)."""
    collected: dict[str, list[str]] = {}
    for candidate in entry.get("candidates") or []:
        if not isinstance(candidate, dict) or not candidate.get("selected"):
            continue
        name = candidate.get("value")
        stamp = candidate.get("true_from")
        if isinstance(name, str) and isinstance(stamp, str) and stamp:
            collected.setdefault(name, []).append(stamp)
    dates: dict[str, str | None] = {}
    for member in entry.get("value") or []:
        if isinstance(member, str):
            values = collected.get(member)
            dates[member] = min(values) if values else None
    return dates


def _investor_entry_type(earlier: dict, new: dict) -> str:
    old_names = set(_investor_member_dates(earlier))
    new_names = set(_investor_member_dates(new))
    old_dates = _investor_member_dates(earlier)
    new_dates = _investor_member_dates(new)
    old_field_date = earlier.get("true_from")
    new_field_date = new.get("true_from")
    corrections = []
    for name in new_names - old_names:
        date = new_dates.get(name)
        if date is not None and old_field_date is not None and str(date) <= str(old_field_date):
            corrections.append(name)
    only_new = new_names - old_names
    only_old = old_names - new_names
    if only_new and not only_old and len(corrections) == len(only_new):
        return "correction"
    return "change"


def _entry_type(field: str, earlier: dict, new: dict) -> str:
    if field == "executives":
        return _exec_entry_type(earlier, new)
    if field == "investors":
        return _investor_entry_type(earlier, new)
    old_value = earlier.get("value")
    new_value = new.get("value")
    if old_value is None or new_value is None:
        return "change"
    old_date = earlier.get("true_from")
    new_date = new.get("true_from")
    if old_date is None or new_date is None:
        return "change"
    return "correction" if str(new_date) <= str(old_date) else "change"


def _finish_ready(
    state: State,
    dossier: dict,
    build_time: str,
    raw: dict[str, list[dict]],
    versions: list[dict],
) -> None:
    build_seq = state.next_build_seq
    state.next_build_seq += 1
    previous_fields = dossier["fields"]
    first_ready = not dossier.get("has_ready")

    new_fields: dict[str, dict] = {}
    for field in FIELDS:
        new_fields[field] = assemble_field(raw[field])
    new_fields["executives"] = assemble_executives(raw["executives"])
    new_fields["investors"] = assemble_investors(raw["investors"])

    for field in ALL_FIELDS:
        entry = new_fields[field]
        if entry.get("value") is None:
            entry["true_from"] = None
            entry["learned_at"] = None
            continue
        previous = previous_fields.get(field) or {}
        if (
            first_ready
            or previous.get("value") is None
            or not same_json_value(previous.get("value"), entry.get("value"))
            or previous.get("learned_at") is None
        ):
            entry["learned_at"] = build_time
        else:
            entry["learned_at"] = previous.get("learned_at")

    feed_entries: list[dict] = []
    for field in ALL_FIELDS:
        entry = new_fields[field]
        previous = previous_fields.get(field) or {}
        if first_ready:
            if entry.get("value") is not None:
                dossier["history"].setdefault(field, []).append(
                    {
                        "type": "initial",
                        "value": copy.deepcopy(entry.get("value")),
                        "true_from": entry.get("true_from"),
                        "learned_at": build_time,
                        "citations": copy.deepcopy(entry.get("citations") or []),
                    }
                )
            continue
        if same_json_value(previous.get("value"), entry.get("value")):
            continue
        entry_type = _entry_type(field, previous, entry)
        dossier["history"].setdefault(field, []).append(
            {
                "type": entry_type,
                "value": copy.deepcopy(entry.get("value")),
                "true_from": entry.get("true_from"),
                "learned_at": build_time,
                "citations": copy.deepcopy(entry.get("citations") or []),
            }
        )
        feed_entries.append(
            {
                "domain": dossier["domain"],
                "field": field,
                "type": entry_type,
                "from": copy.deepcopy(previous.get("value")),
                "to": copy.deepcopy(entry.get("value")),
                "true_from": entry.get("true_from"),
                "learned_at": build_time,
            }
        )

    for entry in feed_entries:
        entry["seq"] = state.next_seq
        state.next_seq += 1
        state.feed.append(entry)

    _decorate_corroboration(dossier, new_fields, build_time)

    dossier["fields"] = new_fields
    dossier["researched_at"] = build_time
    dossier["state"] = "ready"
    dossier["last_outcome"] = "ready"
    dossier["has_ready"] = True
    dossier["builds"].append(
        {
            "seq": build_seq,
            "time": build_time,
            "outcome": "ready",
            "spent": dossier["build_spent"],
            "fields": copy.deepcopy(new_fields),
            "versions": versions,
        }
    )


def _resolve_page_origins(
    state: State, dossier: dict, pages: list[dict], deadline: Deadline, domain: str
) -> None:
    """Assign ``origin_resolved`` to each page by origin rules 1..4.

    Rule 2 follows at most three Canonical URLs in a row, fetching each original
    through the provider.  A fourth hop, or a URL no provider serves, falls back
    to that URL's host (S4-15/S4-16, A2).
    """
    from pages import parse_headers, url_host

    by_url: dict[str, dict] = {}
    for page in pages:
        url = (page.get("url") or "").strip()
        if url:
            by_url.setdefault(url, page)

    def resolve(
        text: str, url: str, hops: int, visiting: frozenset[str]
    ) -> str | None:
        headers = parse_headers(text)
        first = None
        raw = headers.get("first-published-by")
        if raw:
            first = pages_normalise_host(raw)
        if first:
            return first
        canonical = headers.get("canonical")
        if isinstance(canonical, str) and canonical.strip():
            target = canonical.strip()
            if target == url:
                canonical = None
        else:
            canonical = None
        if canonical:
            if hops >= 3 or canonical in visiting:
                return url_host(canonical) or None
            already = by_url.get(canonical)
            target_text = (
                already.get("text")
                if already is not None and already.get("text")
                else _fetch_page_text(state, dossier, canonical, deadline)
            )
            if target_text is None:
                return url_host(canonical) or None
            result = resolve(target_text, canonical, hops + 1, visiting | {canonical})
            return result or url_host(canonical) or None
        from pages import normalise_host, is_lookalike

        if is_lookalike(url, headers):
            return domain
        registrant = normalise_host(headers.get("registrant"))
        if registrant:
            return registrant
        return url_host(url) or None

    for page in pages:
        url = (page.get("url") or "").strip()
        text = page.get("text") or ""
        if not url or not text:
            continue
        origin = resolve(text, url, 0, frozenset({url}))
        if origin:
            page["origin_resolved"] = origin


def pages_normalise_host(raw: str) -> str | None:
    from pages import normalise_host

    return normalise_host(raw)


def _fetch_page_text(
    state: State, dossier: dict, url: str, deadline: Deadline
) -> str | None:
    response = _do_extract(state, dossier, url, deadline)
    if response is None:
        return None
    pages = _extract_text(response, url)
    for page in pages:
        if (page.get("url") or "").strip() == url and page.get("text"):
            return page["text"]
    return pages[0]["text"] if pages else None


def _finish_batch_build(state: State, dossier: dict) -> None:
    batch_id = dossier.get("build_batch_id")
    if not batch_id:
        return
    batch = state.batches.get(batch_id)
    if batch is None:
        return
    for item in batch.get("dossiers", []):
        if item.get("domain") == dossier["domain"]:
            item["state"] = dossier["state"]
            break
    batch["state"] = (
        "done"
        if all(item.get("state") in ("ready", "failed") for item in batch.get("dossiers", []))
        else "running"
    )


def _build_worker(state: State, dossier: dict, build_time: datetime, generation: int) -> None:
    deadline = Deadline(288.0)
    urls: list[str] = []
    citation_urls: set[str] = set()
    pages: list[dict] = []
    any_success = False
    domain = dossier["domain"]
    company = company_name(domain)
    build_iso = now_iso(build_time)

    try:
        router_ok = True
        try:
            get_router()
        except Exception:
            router_ok = False

        if router_ok:
            response = _do_search(state, dossier, domain, 1, deadline)
            if response is not None:
                any_success = True
                _search_urls(response, urls)

            research = _do_research(
                state,
                dossier,
                f"Research the company whose domain is {domain} ({company}). "
                f"Report {', '.join(FIELDS)}.",
                25,
                deadline,
            )
            if research is not None:
                any_success = True
                found: list[str] = []
                _citation_urls(research, found)
                for url in found:
                    citation_urls.add(url)
                urls.extend(found)

            for template in _EXTRA_QUERIES:
                if deadline.remaining() < 20:
                    break
                query = template.format(company=company)
                response = _do_search(state, dossier, query, 1, deadline)
                if response is None:
                    continue
                any_success = True
                _search_urls(response, urls)

            for url in _priority_urls(urls, citation_urls, domain):
                if deadline.remaining() < 4:
                    break
                extracted = _do_extract(state, dossier, url, deadline)
                if extracted is None:
                    continue
                any_success = True
                pages.extend(_extract_text(extracted, url))

        _resolve_page_origins(state, dossier, pages, deadline, domain)
        raw = collect_candidates(pages, domain, company, build_iso)
        _assign_learned(dossier, raw, build_iso)
        versions = _page_versions(pages, raw, domain)
    except Exception:
        raw = {field: [] for field in ALL_FIELDS}
        versions = []
        any_success = False

    with state.lock:
        if not dossier.get("building") or dossier.get("build_gen") != generation:
            return
        dossier["building"] = False
        if any_success:
            _finish_ready(state, dossier, build_iso, raw, versions)
        else:
            dossier["state"] = "failed"
            dossier["last_outcome"] = "failed"
            dossier["builds"].append(
                {
                    "seq": state.next_build_seq,
                    "time": build_iso,
                    "outcome": "failed",
                    "spent": dossier["build_spent"],
                    "fields": None,
                    "versions": [],
                }
            )
            state.next_build_seq += 1
        _finish_batch_build(state, dossier)
    persist_state(state)


def start_build(
    state: State, dossier: dict, build_time: datetime, batch_id: str | None = None
) -> None:
    dossier["building"] = True
    dossier["build_gen"] += 1
    dossier["base_spent"] = dossier["spent_units"]
    dossier["build_spent"] = 0
    dossier["build_batch_id"] = batch_id
    dossier["state"] = "building"
    generation = dossier["build_gen"]
    thread = threading.Thread(
        target=_build_worker,
        args=(state, dossier, build_time, generation),
        daemon=True,
    )
    thread.start()


def _new_dossier(dossier_id: str, domain: str) -> dict:
    return {
        "id": dossier_id,
        "domain": domain,
        "state": "building",
        "last_outcome": None,
        "fields": empty_fields(),
        "researched_at": None,
        "spent_units": 0,
        "base_spent": 0,
        "build_spent": 0,
        "building": False,
        "build_gen": 0,
        "builds": [],
        "history": {field: [] for field in ALL_FIELDS},
        "gathered": {},
        "has_ready": False,
    }


# --------------------------------------------------------------------------
# Fixtures and state transfer


def _fixture_state(fixture: object, clock_now: datetime) -> State | None:
    if not isinstance(fixture, dict):
        return None
    users = fixture.get("users", [])
    if not isinstance(users, list):
        return None

    state = State()
    state.frozen_clock = clock_now
    seen_ids = set()
    seen_emails = set()
    for item in users:
        if not isinstance(item, dict):
            return None
        user_id = item.get("id")
        email = item.get("email")
        password = item.get("password")
        display_name = item.get("display_name")
        if not all(isinstance(v, str) for v in (user_id, email, password, display_name)):
            return None
        if not user_id or len(user_id) > 64 or not email:
            return None
        email_key = email.lower()
        if user_id in seen_ids or email_key in seen_emails:
            return None
        seen_ids.add(user_id)
        seen_emails.add(email_key)
        password_hash = generate_password_hash(password)
        state.users[user_id] = {
            "id": user_id,
            "email": email,
            "email_key": email_key,
            "display_name": display_name,
            "password_hash": password_hash,
        }
        state.email_index[email_key] = user_id
    return state


def _export_state(state: State) -> dict:
    with state.lock:
        idempotency = []
        for (user_id, method, path, key), record in state.idem.items():
            idempotency.append(
                {
                    "user_id": user_id,
                    "method": method,
                    "path": path,
                    "key": key,
                    "body": record["body"],
                    "response": copy.deepcopy(record["response"]),
                }
            )
        return {
            "users": [
                {
                    "id": user["id"],
                    "email": user["email"],
                    "display_name": user["display_name"],
                    "password_hash": user["password_hash"],
                }
                for user in state.users.values()
            ],
            "tokens": dict(state.tokens),
            "dossiers": [_serialise_dossier(d) for d in state.dossiers.values()],
            "idempotency": idempotency,
            "next_user": state.next_user,
            "next_dossier": state.next_dossier,
            "next_batch": state.next_batch,
            "batches": copy.deepcopy(state.batches),
            "stage3": {
                "feed": copy.deepcopy(state.feed),
                "next_seq": state.next_seq,
                "next_build_seq": state.next_build_seq,
            },
        }


def _valid_field_entry(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    if entry.get("status") not in ("known", "contested", "unknown"):
        return False
    if "value" not in entry or not isinstance(entry.get("citations"), list):
        return False
    if "candidates" in entry and not isinstance(entry["candidates"], list):
        return False
    if entry["status"] == "unknown":
        return entry.get("value") is None and entry["citations"] == []
    return entry.get("value") is not None and len(entry["citations"]) >= 1


def _published_true_from(candidate: dict) -> str | None:
    explicit = candidate.get("true_from")
    if isinstance(explicit, str) and explicit:
        return explicit
    published = candidate.get("published_at")
    if isinstance(published, str) and published:
        parsed = parse_rfc3339(published)
        if parsed is not None:
            return parsed.astimezone(timezone.utc).date().isoformat()
    return None


def _legacy_stage2_candidates(entry: dict) -> list[dict]:
    result = []
    for candidate in entry.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        cleaned = dict(candidate)
        cleaned["true_from"] = _published_true_from(candidate)
        result.append(cleaned)
    return result


def _legacy_origin(candidate: dict) -> str:
    """S4-25: imported candidates with no origin take their URL's host."""
    from pages import url_host

    return url_host(candidate.get("url") or "") or ""


def _import_gathered(builds: list[dict], old_gathered: dict, researched_at: str | None) -> dict:
    """Rebuild gathered records from imported builds (S4-23/S4-24)."""
    gathered: dict = {}
    for build in builds:
        when = build.get("time")
        if build.get("outcome") != "ready" or not isinstance(when, str):
            continue
        for field in ALL_FIELDS:
            for candidate in (build.get("fields") or {}).get(field, {}).get("candidates") or []:
                if not isinstance(candidate, dict):
                    continue
                key = candidate_identity(field, candidate)
                at = when
                gathered[key] = {
                    "at": at,
                    "origin": candidate.get("origin") or _legacy_origin(candidate),
                    "value": candidate.get("value"),
                    "field": field,
                }
    for key, record in old_gathered.items():
        if key not in gathered:
            if isinstance(record, dict):
                gathered[key] = record
            else:
                gathered[key] = {"at": record, "origin": "", "value": None, "field": ""}
    return gathered


def _decorate_imported_fields(dossier: dict) -> None:
    """Give imported fields (current and per-build) stage-4 corroboration keys."""
    fields = dossier.get("fields") or {}
    _decorate_corroboration(dossier, fields, dossier.get("researched_at") or "")
    for build in dossier.get("builds") or []:
        bf = build.get("fields")
        if isinstance(bf, dict):
            _decorate_corroboration(dossier, bf, build.get("time") or "")


def _restore_stage3_dossier(item: dict, state: State) -> dict | None:
    dossier_id = item.get("id")
    domain = item.get("domain")
    outcome = item.get("state")
    if not isinstance(dossier_id, str) or not isinstance(domain, str):
        return None
    if outcome not in ("ready", "failed"):
        return None
    fields = item.get("fields")
    stage3_fields = set(FIELDS) | {"executives"}
    if not isinstance(fields, dict) or not stage3_fields.issubset(set(fields)):
        return None
    builds = item.get("builds")
    history = item.get("history")
    gathered = item.get("gathered")
    if not isinstance(builds, list) or not isinstance(history, dict):
        return None
    if not isinstance(gathered, dict):
        gathered = {}
    spent = item.get("live_spent", item.get("spent_units"))
    researched_at = item.get("researched_at")
    if not isinstance(spent, int) or spent < 0:
        return None
    if researched_at is not None and not isinstance(researched_at, str):
        return None
    clean_history = {}
    for field in ALL_FIELDS:
        entries = history.get(field)
        if not isinstance(entries, list):
            entries = []
        clean_history[field] = copy.deepcopy(entries)
    clean_history["investors"] = []

    clean_fields = copy.deepcopy(fields)
    for field in ALL_FIELDS:
        if field not in clean_fields:
            clean_fields[field] = empty_field()
    clean_fields["investors"] = empty_field()
    for field in ALL_FIELDS:
        entry = clean_fields.get(field)
        if not isinstance(entry, dict):
            continue
        for candidate in entry.get("candidates") or []:
            if not isinstance(candidate, dict):
                continue
            if not isinstance(candidate.get("origin"), str) or not candidate["origin"]:
                candidate["origin"] = _legacy_origin(candidate)
        if entry.get("value") is not None:
            entry["origins"] = _origins_from_candidates(entry.get("candidates") or [])
            entry["corroborated"] = len(entry["origins"]) >= 2
        else:
            entry["origins"] = []
            entry["corroborated"] = False
        entry["corroborated_since"] = None

    clean_builds = copy.deepcopy(builds)
    for build in clean_builds:
        bf = build.get("fields")
        if isinstance(bf, dict):
            bf["investors"] = empty_field()
            for field in ALL_FIELDS:
                entry = bf.get(field)
                if not isinstance(entry, dict):
                    continue
                for candidate in entry.get("candidates") or []:
                    if isinstance(candidate, dict) and (
                        not isinstance(candidate.get("origin"), str) or not candidate["origin"]
                    ):
                        candidate["origin"] = _legacy_origin(candidate)
        for version in build.get("versions") or []:
            for candidate in version.get("candidates") or []:
                if not isinstance(candidate.get("origin"), str) or not candidate["origin"]:
                    candidate["origin"] = _legacy_origin(candidate)
    dossier = {
        "id": dossier_id,
        "domain": domain,
        "state": outcome,
        "last_outcome": item.get("last_outcome") or outcome,
        "fields": clean_fields,
        "researched_at": researched_at,
        "spent_units": spent,
        "base_spent": spent,
        "build_spent": 0,
        "building": False,
        "build_gen": 0,
        "builds": clean_builds,
        "history": clean_history,
        "gathered": _import_gathered(clean_builds, gathered, researched_at),
        "has_ready": bool(item.get("has_ready")),
    }
    _decorate_imported_fields(dossier)
    return dossier


def _import_legacy_dossier(item: dict, state: State) -> dict | None:
    dossier_id = item.get("id")
    domain = item.get("domain")
    outcome = item.get("state")
    if not isinstance(dossier_id, str) or not isinstance(domain, str):
        return None
    if outcome not in ("ready", "failed"):
        return None
    fields = item.get("fields")
    if not isinstance(fields, dict) or not set(FIELDS).issubset(set(fields)):
        return None
    if not all(_valid_field_entry(fields[field]) for field in FIELDS):
        return None
    spent = item.get("live_spent", item.get("spent_units"))
    researched_at = item.get("researched_at")
    if not isinstance(spent, int) or spent < 0:
        return None
    if researched_at is not None and not isinstance(researched_at, str):
        return None

    is_stage2 = any("candidates" in (fields[field] or {}) for field in FIELDS)
    dossier = _new_dossier(dossier_id, domain)
    dossier["state"] = outcome
    dossier["last_outcome"] = outcome
    dossier["researched_at"] = researched_at
    dossier["spent_units"] = spent
    dossier["base_spent"] = spent

    assembled: dict[str, dict] = {}
    for field in FIELDS:
        entry = fields[field] or {}
        if is_stage2 and isinstance(entry.get("candidates"), list):
            candidates = _legacy_stage2_candidates(entry)
            rebuilt = rebuild_field_from_candidates(entry.get("value"), candidates, researched_at)
            for candidate in rebuilt["candidates"]:
                candidate["learned_at"] = researched_at
                if candidate.get("true_from") is None:
                    candidate["true_from"] = _published_true_from(candidate)
            rebuilt["true_from"] = (
                rebuilt["candidates"][0].get("true_from") if rebuilt["candidates"] else None
            )
        else:
            rebuilt = imported_field(entry.get("value"), entry.get("citations") or [], researched_at)
        if rebuilt.get("value") is not None:
            rebuilt["learned_at"] = researched_at
        else:
            rebuilt["true_from"] = None
            rebuilt["learned_at"] = None
        assembled[field] = rebuilt
    assembled["executives"] = empty_field()
    assembled["investors"] = empty_field()
    for field in ALL_FIELDS:
        entry = assembled.get(field)
        if not isinstance(entry, dict):
            continue
        for candidate in entry.get("candidates") or []:
            if isinstance(candidate, dict) and (
                not isinstance(candidate.get("origin"), str) or not candidate["origin"]
            ):
                candidate["origin"] = _legacy_origin(candidate)
        if entry.get("value") is not None:
            entry["origins"] = _origins_from_candidates(entry.get("candidates") or [])
            entry["corroborated"] = len(entry["origins"]) >= 2
        else:
            entry["origins"] = []
            entry["corroborated"] = False
        entry["corroborated_since"] = None
    dossier["fields"] = assembled

    for field in ALL_FIELDS:
        for candidate in assembled[field].get("candidates") or []:
            key = candidate_identity(field, candidate)
            dossier["gathered"][key] = {
                "at": candidate.get("learned_at") or candidate.get("retrieved_at") or researched_at,
                "origin": candidate.get("origin") or _legacy_origin(candidate),
                "value": candidate.get("value"),
                "field": field,
            }

    for field in FIELDS:
        entry = assembled[field]
        if entry.get("value") is not None:
            dossier["history"][field].append(
                {
                    "type": "initial",
                    "value": copy.deepcopy(entry.get("value")),
                    "true_from": entry.get("true_from"),
                    "learned_at": researched_at,
                    "citations": copy.deepcopy(entry.get("citations") or []),
                }
            )

    if researched_at is not None:
        versions: dict[str, dict] = {}
        for field in FIELDS:
            for candidate in assembled[field].get("candidates") or []:
                url = candidate.get("url") or ""
                version = versions.setdefault(
                    url,
                    {
                        "url": url,
                        "true_from": candidate.get("true_from"),
                        "candidates": [],
                    },
                )
                version["candidates"].append(
                    {
                        "field": field,
                        "title": None,
                        "value": candidate.get("value"),
                        "url": url,
                        "excerpt": candidate.get("excerpt") or "",
                        "provider": candidate.get("provider") or "",
                        "kind": candidate.get("kind"),
                        "published_at": candidate.get("published_at"),
                        "true_from": candidate.get("true_from"),
                        "retrieved_at": candidate.get("retrieved_at"),
                        "learned_at": candidate.get("learned_at"),
                        "origin": candidate.get("origin"),
                    }
                )
        dossier["builds"].append(
            {
                "seq": state.next_build_seq,
                "time": researched_at,
                "outcome": "ready",
                "spent": spent,
                "fields": copy.deepcopy(assembled),
                "versions": list(versions.values()),
            }
        )
        state.next_build_seq += 1
        dossier["has_ready"] = True
    _decorate_imported_fields(dossier)
    return dossier


def _state_from_export(payload: object, clock: datetime | None) -> State | None:
    if not isinstance(payload, dict):
        return None
    users = payload.get("users")
    tokens = payload.get("tokens")
    dossiers = payload.get("dossiers")
    idempotency = payload.get("idempotency")
    if not isinstance(users, list) or not isinstance(tokens, dict):
        return None
    if not isinstance(dossiers, list) or not isinstance(idempotency, list):
        return None

    state = State()
    state.frozen_clock = clock
    for item in users:
        if not isinstance(item, dict):
            return None
        fields = ("id", "email", "display_name", "password_hash")
        if not all(isinstance(item.get(key), str) for key in fields):
            return None
        email_key = item["email"].lower()
        if item["id"] in state.users or email_key in state.email_index:
            return None
        state.users[item["id"]] = {
            "id": item["id"],
            "email": item["email"],
            "email_key": email_key,
            "display_name": item["display_name"],
            "password_hash": item["password_hash"],
        }
        state.email_index[email_key] = item["id"]

    for token, user_id in tokens.items():
        if not isinstance(token, str) or not isinstance(user_id, str) or user_id not in state.users:
            return None
        state.tokens[token] = user_id

    stage3 = payload.get("stage3") if isinstance(payload.get("stage3"), dict) else None

    for item in dossiers:
        if not isinstance(item, dict):
            return None
        if stage3 is not None:
            dossier = _restore_stage3_dossier(item, state)
        else:
            dossier = _import_legacy_dossier(item, state)
        if dossier is None:
            return None
        if dossier["domain"] in state.dossiers:
            return None
        state.dossiers[dossier["domain"]] = dossier

    for record in idempotency:
        if not isinstance(record, dict):
            return None
        user_id = record.get("user_id")
        method = record.get("method")
        path = record.get("path")
        key = record.get("key")
        body = record.get("body")
        response = record.get("response")
        if not all(isinstance(v, str) for v in (user_id, method, path, key, body)):
            return None
        if user_id not in state.users or not isinstance(response, dict):
            return None
        state.idem[(user_id, method, path, key)] = {"body": body, "response": copy.deepcopy(response)}

    next_user = payload.get("next_user", 1)
    next_dossier = payload.get("next_dossier", 1)
    if not isinstance(next_user, int) or next_user < 1:
        next_user = 1
    if not isinstance(next_dossier, int) or next_dossier < 1:
        next_dossier = 1
    state.next_user = next_user
    state.next_dossier = next_dossier

    next_batch = payload.get("next_batch", 1)
    state.next_batch = next_batch if isinstance(next_batch, int) and next_batch >= 1 else 1
    batches = payload.get("batches")
    if isinstance(batches, dict):
        state.batches = copy.deepcopy(batches)
    for batch in state.batches.values():
        for item in batch.get("dossiers", []):
            dossier = state.dossiers.get(item.get("domain"))
            if dossier is not None:
                item["state"] = dossier["state"]
        batch["state"] = (
            "done"
            if all(item.get("state") in ("ready", "failed") for item in batch.get("dossiers", []))
            else "running"
        )

    if stage3 is not None:
        feed = stage3.get("feed")
        next_seq = stage3.get("next_seq")
        next_build_seq = stage3.get("next_build_seq")
        if not isinstance(feed, list):
            return None
        state.feed = copy.deepcopy(feed)
        state.next_seq = next_seq if isinstance(next_seq, int) and next_seq >= 1 else 1
        state.next_build_seq = (
            next_build_seq if isinstance(next_build_seq, int) and next_build_seq >= 1 else 1
        )
    else:
        state.feed = []
        state.next_seq = 1
    return state


def _next_id(prefix: str, current: int, taken: set[str]) -> tuple[str, int]:
    while True:
        candidate = f"{prefix}_{current}"
        current += 1
        if candidate not in taken:
            return candidate, current


# --------------------------------------------------------------------------
# Boot: restore durable state from the container filesystem.


def _restore_from_disk() -> State | None:
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    clock = parse_rfc3339(data.get("clock")) if data.get("clock") else None
    try:
        state = _state_from_export(data, clock)
    except Exception:
        return None
    if state is None:
        return None
    return state


_loaded = _restore_from_disk()
if _loaded is not None:
    _STATE = _loaded


# --------------------------------------------------------------------------
# Routes


@app.after_request
def _content_type(response: Response) -> Response:
    if response.mimetype == "application/json" or response.status_code >= 400:
        response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response


@app.get("/health")
def health():
    return json_response({"status": "ok"})


@app.post("/_test/reset")
def test_reset():
    global _STATE
    body, ok = read_json_body()
    if not ok:
        return malformed("unparseable fixture")
    if not isinstance(body, dict):
        return malformed("fixture must be an object")
    clock_now = parse_rfc3339(body.get("now"))
    if clock_now is None:
        return validation_error("fixture now is required and must be RFC 3339 with an offset")
    new_state = _fixture_state(body, clock_now)
    if new_state is None:
        return validation_error("invalid fixture")
    with _GLOBAL_LOCK:
        _STATE = new_state
    persist_state(new_state)
    return empty_response(204)


@app.post("/_test/clock")
def test_clock():
    body, ok = read_json_body()
    if not ok:
        return malformed("unparseable clock body")
    if not isinstance(body, dict):
        return malformed("clock body must be an object")
    if "now" not in body:
        return validation_error("now is required")
    raw = body.get("now")
    if not isinstance(raw, str):
        return malformed("now must be a string")
    parsed = parse_rfc3339(raw)
    if parsed is None:
        return validation_error("now must be RFC 3339 with an offset")
    state = _STATE
    with state.lock:
        current = state.frozen_clock
        if current is None:
            current = datetime.now(timezone.utc)
        if parsed < current:
            return validation_error("now is earlier than the clock")
        state.frozen_clock = parsed
    persist_state(state)
    return empty_response(204)


@app.get("/_test/export")
def test_export():
    with _GLOBAL_LOCK:
        state = _STATE
    return json_response(
        {"track": "dossier", "format_version": 1, "state": _export_state(state)}
    )


@app.post("/_test/import")
def test_import():
    global _STATE
    body, ok = read_json_body()
    if not ok:
        return malformed("unparseable import body")
    if not isinstance(body, dict):
        return malformed("import body must be an object")
    if body.get("track") != "dossier" or type(body.get("format_version")) is not int or body.get("format_version") != 1:
        return validation_error("wrong track or format_version")
    if "state" not in body:
        return validation_error("state is required")
    current = _STATE
    with current.lock:
        clock = current.frozen_clock
    new_state = _state_from_export(body.get("state"), clock)
    if new_state is None:
        return validation_error("invalid state")
    with _GLOBAL_LOCK:
        _STATE = new_state
    persist_state(new_state)
    return empty_response(204)


def _create_account(payload: dict):
    for key in ("email", "password", "display_name"):
        if key in payload and not isinstance(payload[key], str):
            return malformed(f"{key} must be a string")
    if "email" not in payload or "password" not in payload or "display_name" not in payload:
        return validation_error("email, password and display_name are required")
    email = payload["email"]
    password = payload["password"]
    display_name = payload["display_name"]
    if not _EMAIL_RE.match(email):
        return validation_error("email must be local@domain")
    if len(password) < 8:
        return validation_error("password must be at least 8 characters")
    if len(display_name) < 1 or len(display_name) > 100:
        return validation_error("display_name must be 1 to 100 characters")

    email_key = email.lower()
    password_hash = generate_password_hash(password)
    state = _STATE
    with state.lock:
        if email_key in state.email_index:
            return error_response(409, "email_taken", "email is already registered")
        user_id, state.next_user = _next_id("u", state.next_user, set(state.users))
        token = token_for_user(state)
        state.users[user_id] = {
            "id": user_id,
            "email": email,
            "email_key": email_key,
            "display_name": display_name,
            "password_hash": password_hash,
        }
        state.email_index[email_key] = user_id
        state.tokens[token] = user_id
    persist_state(state)
    return {"user_id": user_id, "display_name": display_name, "token": token}, 201


def _authenticate(payload: dict):
    for key in ("email", "password"):
        if key in payload and not isinstance(payload[key], str):
            return malformed(f"{key} must be a string")
    if "email" not in payload or "password" not in payload:
        return validation_error("email and password are required")
    email_key = payload["email"].lower()
    state = _STATE
    with state.lock:
        user_id = state.email_index.get(email_key)
        user = state.users.get(user_id) if user_id else None
        password_hash = user["password_hash"] if user else None
    if user is None or password_hash is None or not check_password_hash(
        password_hash, payload["password"]
    ):
        return unauthenticated("wrong email or password")
    with state.lock:
        token = token_for_user(state)
        state.tokens[token] = user["id"]
        display_name = user["display_name"]
        user_id = user["id"]
    persist_state(state)
    return {"user_id": user_id, "display_name": display_name, "token": token}, 200


@app.post("/auth/signup")
def signup():
    body, ok = read_json_body()
    if not ok:
        return malformed("unparseable signup body")
    if not isinstance(body, dict):
        return malformed("signup body must be an object")
    result = _create_account(body)
    if isinstance(result, Response):
        return result
    return json_response(result[0], result[1])


@app.post("/auth/login")
def login():
    body, ok = read_json_body()
    if not ok:
        return malformed("unparseable login body")
    if not isinstance(body, dict):
        return malformed("login body must be an object")
    result = _authenticate(body)
    if isinstance(result, Response):
        return result
    return json_response(result[0], result[1])


def _batch_view(state: State, batch: dict) -> dict:
    with state.lock:
        items = []
        for item in batch["dossiers"]:
            dossier = state.dossiers.get(item.get("domain"))
            items.append({"domain": item["domain"], "state": dossier["state"] if dossier else item["state"]})
        batch_state = (
            "done" if all(item["state"] in ("ready", "failed") for item in items) else "running"
        )
        return {
            "batch_id": batch["id"],
            "state": batch_state,
            "budget_units": batch["budget_units"],
            "spent_units": batch["spent_units"],
            "dossiers": items,
        }


@app.post("/batches")
def create_batch():
    state = _STATE
    user_id = auth_user(state)
    if user_id is None:
        return unauthenticated()
    key, key_error = idempotency_header()
    if key_error is not None:
        return key_error
    body, ok = read_json_body()
    if not ok:
        return malformed("unparseable batch body")
    if not isinstance(body, dict):
        return malformed("batch body must be an object")

    domains = body.get("domains")
    budget = body.get("budget_units")
    canonical = canonical_body({"domains": domains, "budget_units": budget})
    idem_key = (user_id, "POST", request.path, key)

    with state.lock:
        record = state.idem.get(idem_key)
        if record is not None:
            if record["body"] == canonical:
                return json_response(copy.deepcopy(record["response"]), 200)
            return error_response(409, "idempotency_key_reuse", "key reused with a different body")

        if "domains" not in body:
            return validation_error("domains is required")
        if "budget_units" in body and type(budget) is not int:
            return validation_error("budget_units must be an integer from 1 to 100000")
        if not isinstance(domains, list):
            return malformed("domains must be an array")
        if len(domains) == 0 or len(domains) > 50:
            return validation_error("domains must have 1 to 50 entries")
        normalised: list[str] = []
        for entry in domains:
            if not isinstance(entry, str):
                return validation_error("each domain must be a string")
            try:
                value = normalise_domain(entry)
            except ValueError:
                return validation_error("invalid domain")
            if value in normalised:
                return validation_error("duplicate domain")
            normalised.append(value)
        if "budget_units" not in body:
            return validation_error("budget_units is required")
        if type(budget) is not int or budget < 1 or budget > 100000:
            return validation_error("budget_units must be an integer from 1 to 100000")

        batch_id, state.next_batch = _next_id(
            "b", state.next_batch, set(state.batches)
        )
        items = []
        for domain in normalised:
            existing = state.dossiers.get(domain)
            if existing is not None:
                item = {"domain": domain, "state": existing["state"]}
            else:
                dossier_id, state.next_dossier = _next_id(
                    "d", state.next_dossier, set(d["id"] for d in state.dossiers.values())
                )
                dossier = _new_dossier(dossier_id, domain)
                state.dossiers[domain] = dossier
                start_build(state, dossier, state.now(), batch_id=batch_id)
                item = {"domain": domain, "state": dossier["state"]}
            items.append(item)
        batch = {
            "id": batch_id,
            "user_id": user_id,
            "state": "done"
            if all(item["state"] in ("ready", "failed") for item in items)
            else "running",
            "budget_units": budget,
            "spent_units": 0,
            "dossiers": items,
        }
        state.batches[batch_id] = batch
        response_body = _batch_view(state, batch)
        state.idem[idem_key] = {"body": canonical, "response": copy.deepcopy(response_body)}
        persist_state(state)
    return json_response(response_body, 202)


@app.get("/batches/<path:batch_id>")
def get_batch(batch_id: str):
    state = _STATE
    user_id = auth_user(state)
    if user_id is None:
        return unauthenticated()
    with state.lock:
        batch = state.batches.get(batch_id)
        if batch is None or batch.get("user_id") != user_id:
            return not_found("no such batch")
        return json_response(_batch_view(state, batch))


@app.post("/dossiers")
def create_dossier():
    state = _STATE
    user_id = auth_user(state)
    if user_id is None:
        return unauthenticated()
    key, key_error = idempotency_header()
    if key_error is not None:
        return key_error
    body, ok = read_json_body()
    if not ok:
        return malformed("unparseable dossier body")
    if not isinstance(body, dict):
        return malformed("dossier body must be an object")

    canonical = canonical_body({"domain": body["domain"]} if "domain" in body else {})
    idem_key = (user_id, "POST", request.path, key)

    with state.lock:
        record = state.idem.get(idem_key)
        if record is not None:
            if record["body"] == canonical:
                return json_response(copy.deepcopy(record["response"]), 200)
            return error_response(409, "idempotency_key_reuse", "key reused with a different body")

        if "domain" not in body:
            return validation_error("domain is required")
        if not isinstance(body["domain"], str):
            return malformed("domain must be a string")
        try:
            domain = normalise_domain(body["domain"])
        except ValueError:
            return validation_error("invalid domain")

        dossier = state.dossiers.get(domain)
        if dossier is not None:
            response_body = dossier_brief(dossier)
            status = 200
        else:
            dossier_id, state.next_dossier = _next_id(
                "d", state.next_dossier, set(d["id"] for d in state.dossiers.values())
            )
            dossier = _new_dossier(dossier_id, domain)
            state.dossiers[domain] = dossier
            start_build(state, dossier, state.now())
            response_body = dossier_brief(dossier)
            status = 202
        state.idem[idem_key] = {"body": canonical, "response": copy.deepcopy(response_body)}
        persist_state(state)
    return json_response(response_body, status)


@app.get("/dossiers")
def list_dossiers():
    state = _STATE
    user_id = auth_user(state)
    if user_id is None:
        return unauthenticated()

    limit, error = integer_query("limit", 50, 1, 200)
    if error is not None:
        return error
    offset, error = integer_query("offset", 0, 0, None)
    if error is not None:
        return error
    query = request.args.get("q")

    with state.lock:
        items = sorted(
            (dossier_view(dossier) for dossier in state.dossiers.values()),
            key=lambda item: item["domain"],
        )
    if query:
        needle = query.lower()
        filtered = []
        for item in items:
            legal_name = item["fields"].get("legal_name", {}).get("value")
            haystacks = [item["domain"].lower()]
            if isinstance(legal_name, str):
                haystacks.append(legal_name.lower())
            if any(needle in haystack for haystack in haystacks):
                filtered.append(item)
        items = filtered

    window = items[offset : offset + limit]
    payload = {
        "dossiers": [
            {
                "dossier_id": item["dossier_id"],
                "domain": item["domain"],
                "state": item["state"],
                "legal_name": item["fields"]["legal_name"]["value"],
                "researched_at": item["researched_at"],
                "spent_units": item["spent_units"],
            }
            for item in window
        ],
        "has_more": offset + len(window) < len(items),
    }
    return json_response(payload)


def wants_html() -> bool:
    return "text/html" in (request.headers.get("Accept") or "")


def html_response(body: str, status: int = 200) -> Response:
    response = Response(body, status=status, mimetype="text/html")
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    return response


def login_redirect():
    return redirect("/login", code=303)


def _error_message(response: Response) -> str:
    try:
        payload = json.loads(response.get_data(as_text=True))
        return payload.get("error", {}).get("message") or payload.get("error", {}).get("code") or ""
    except Exception:
        return ""


def _filtered_dossiers(state: State, query: str | None) -> list[dict]:
    with state.lock:
        items = [
            dossier_view(dossier)
            for dossier in sorted(state.dossiers.values(), key=lambda d: d["domain"])
        ]
    if query:
        needle = query.lower()
        filtered = []
        for item in items:
            legal_name = item["fields"].get("legal_name", {}).get("value")
            haystacks = [item["domain"].lower()]
            if isinstance(legal_name, str):
                haystacks.append(legal_name.lower())
            if any(needle in haystack for haystack in haystacks):
                filtered.append(item)
        items = filtered
    return items


@app.get("/dossiers/<path:domain>/evidence")
def evidence_screen(domain: str):
    state = _STATE
    user = current_user(state)
    if user is None:
        return login_redirect()
    try:
        normalised = normalise_domain(domain)
    except ValueError:
        return html_response(message_page("Invalid domain", "That domain is not valid.", user=user), 422)
    with state.lock:
        dossier = state.dossiers.get(normalised)
        data = dossier_view(dossier) if dossier is not None else None
    if data is None:
        return html_response(dossier_page(None, normalised, user=user, not_found=True))
    return html_response(evidence_page(data, user=user))


@app.get("/dossiers/<path:domain>/history")
def dossier_history(domain: str):
    html = wants_html()
    state = _STATE
    if html:
        user = current_user(state)
        if user is None:
            return login_redirect()
    else:
        if auth_user(state) is None:
            return unauthenticated()
    try:
        normalised = normalise_domain(domain)
    except ValueError:
        if html:
            return html_response(message_page("Invalid domain", "That domain is not valid.", user=user), 422)
        return validation_error("invalid domain")
    with state.lock:
        dossier = state.dossiers.get(normalised)
        if dossier is None:
            if html:
                return html_response(dossier_page(None, normalised, user=user, not_found=True))
            return not_found("no such dossier")
        history = copy.deepcopy(dossier.get("history", {}))
        domain_name = dossier["domain"]
    if html:
        return html_response(history_page(domain_name, history, user=user))
    fields = {field: history.get(field, []) for field in ALL_FIELDS}
    return json_response({"domain": normalised, "fields": fields})


def _as_of_response(state: State, dossier: dict, as_of: datetime) -> Response:
    ready = _builds_at(dossier, as_of, ready_only=True)
    if not ready:
        return not_found("no ready build at or before as_of")
    chosen = max(ready, key=lambda b: (_build_time(b), b.get("seq", 0)))
    spent = sum(
        b.get("spent", 0)
        for b in dossier.get("builds", [])
        if _build_time(b) is not None and _build_time(b) <= as_of
    )
    payload = {
        "dossier_id": dossier["id"],
        "domain": dossier["domain"],
        "state": "ready",
        "researched_at": chosen.get("time"),
        "spent_units": spent,
        "fields": copy.deepcopy(chosen.get("fields") or empty_fields()),
    }
    return json_response(payload)


def _versions_by_url(versions_in_order: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for version in versions_in_order:
        url = version.get("url") or ""
        grouped.setdefault(url, []).append(version)
    return grouped


def _version_at(versions: list[dict], true_at: str) -> dict | None:
    """The version of one URL whose evidence holds on ``true_at``.

    Versions are in build order.  A version with a null ``true_from`` holds
    from no date and replaces every earlier version; a version dated after
    ``true_at`` does not affect that date.  The last version that does affect
    it therefore decides what holds.
    """
    chosen: dict | None = None
    for version in versions:
        stamp = version.get("true_from")
        if stamp is None:
            chosen = version
        elif isinstance(stamp, str) and stamp <= true_at:
            chosen = version
    if chosen is None or chosen.get("true_from") is None:
        return None
    return chosen


def _values_response(state: State, dossier: dict, true_at: str, as_of: datetime, as_of_text: str) -> Response:
    builds = _builds_at(dossier, as_of, ready_only=True)
    if not builds:
        return not_found("no ready build at or before as_of")
    versions_in_order: list[dict] = []
    for build in builds:
        for version in build.get("versions") or []:
            versions_in_order.append(version)
    grouped = _versions_by_url(versions_in_order)

    active_candidates: dict[str, list[dict]] = {field: [] for field in ALL_FIELDS}
    for url, versions in grouped.items():
        version = _version_at(versions, true_at)
        if version is None:
            continue
        for candidate in version.get("candidates") or []:
            field = candidate.get("field")
            if field in active_candidates:
                active_candidates[field].append(candidate)

    fields: dict[str, dict] = {}
    for field in FIELDS:
        assembled = assemble_field(active_candidates[field])
        fields[field] = {
            "value": assembled["value"],
            "true_from": assembled["true_from"],
            "citations": assembled["citations"],
        }
    execs = assemble_executives(active_candidates["executives"])
    fields["executives"] = {
        "value": execs["value"],
        "true_from": execs["true_from"],
        "citations": execs["citations"],
    }
    investors = assemble_investors(active_candidates["investors"])
    fields["investors"] = {
        "value": investors["value"],
        "true_from": investors["true_from"],
        "citations": investors["citations"],
    }
    return json_response(
        {
            "domain": dossier["domain"],
            "true_at": true_at,
            "as_of": as_of_text,
            "fields": fields,
        }
    )


@app.get("/dossiers/<path:domain>/values")
def dossier_values(domain: str):
    state = _STATE
    user_id = auth_user(state)
    if user_id is None:
        return unauthenticated()
    try:
        normalised = normalise_domain(domain)
    except ValueError:
        return validation_error("invalid domain")
    raw_true_at = request.args.get("true_at")
    true_at = parse_date_only(raw_true_at)
    if true_at is None:
        return validation_error("true_at must be a YYYY-MM-DD date")
    raw_as_of = request.args.get("as_of")
    if raw_as_of is None:
        as_of_value = state.now()
        as_of_text = now_iso(as_of_value)
    else:
        as_of_value = parse_rfc3339(raw_as_of)
        if as_of_value is None:
            return validation_error("as_of must be RFC 3339 with an offset")
        as_of_text = now_iso(as_of_value)
    with state.lock:
        dossier = state.dossiers.get(normalised)
        if dossier is None:
            return not_found("no such dossier")
        snapshot = copy.deepcopy(dossier)
    return _values_response(state, snapshot, true_at, as_of_value, as_of_text)


@app.get("/changes")
def changes_feed():
    state = _STATE
    user_id = auth_user(state)
    if user_id is None:
        return unauthenticated()
    since, error = integer_query("since", 0, 0, None)
    if error is not None:
        return error
    limit, error = integer_query("limit", 50, 1, 200)
    if error is not None:
        return error
    with state.lock:
        entries = [copy.deepcopy(e) for e in state.feed if e.get("seq", 0) > since]
    entries.sort(key=lambda e: e.get("seq", 0))
    window = entries[:limit]
    payload = {
        "changes": [
            {
                "seq": entry.get("seq"),
                "domain": entry.get("domain"),
                "field": entry.get("field"),
                "type": entry.get("type"),
                "from": entry.get("from"),
                "to": entry.get("to"),
                "true_from": entry.get("true_from"),
                "learned_at": entry.get("learned_at"),
            }
            for entry in window
        ],
        "has_more": len(entries) > len(window),
    }
    return json_response(payload)


@app.get("/dossiers/<path:domain>")
def get_dossier(domain: str):
    html = wants_html()
    state = _STATE
    user = current_user(state)
    if user is None:
        if html:
            return login_redirect()
        return unauthenticated()
    try:
        normalised = normalise_domain(domain)
    except ValueError:
        return validation_error("invalid domain")
    raw_as_of = request.args.get("as_of")
    as_of = None
    if raw_as_of is not None:
        as_of = parse_rfc3339(raw_as_of)
        if as_of is None:
            return validation_error("as_of must be RFC 3339 with an offset")
    with state.lock:
        dossier = state.dossiers.get(normalised)
        if dossier is None:
            if html:
                return html_response(dossier_page(None, normalised, user=user, not_found=True))
            return not_found("no such dossier")
        snapshot = copy.deepcopy(dossier)
        data = dossier_view(dossier)
    if as_of is not None:
        return _as_of_response(state, snapshot, as_of)
    if html:
        return html_response(dossier_page(data, normalised, user=user))
    return json_response(data)


@app.post("/dossiers/<path:domain>/refresh")
def refresh_dossier(domain: str):
    state = _STATE
    user_id = auth_user(state)
    if user_id is None:
        return unauthenticated()
    key, key_error = idempotency_header()
    if key_error is not None:
        return key_error
    try:
        normalised = normalise_domain(domain)
    except ValueError:
        return validation_error("invalid domain")

    canonical = canonical_body({})
    idem_key = (user_id, "POST", request.path, key)

    with state.lock:
        record = state.idem.get(idem_key)
        if record is not None:
            if record["body"] == canonical:
                return json_response(copy.deepcopy(record["response"]), 200)
            return error_response(409, "idempotency_key_reuse", "key reused with a different body")

        dossier = state.dossiers.get(normalised)
        if dossier is None:
            return not_found("no such dossier")
        if not dossier["building"]:
            start_build(state, dossier, state.now())
        response_body = dossier_brief(dossier)
        state.idem[idem_key] = {"body": canonical, "response": copy.deepcopy(response_body)}
        persist_state(state)
    return json_response(response_body, 202)


@app.get("/")
def home():
    state = _STATE
    user = current_user(state)
    if user is None:
        return login_redirect()
    query = request.args.get("q")
    items = _filtered_dossiers(state, None)
    listing = [
        {
            "domain": item["domain"],
            "legal_name": item["fields"].get("legal_name", {}).get("value"),
            "state": item["state"],
        }
        for item in items
    ]
    return html_response(list_page(listing, query or "", user=user))


@app.get("/contested")
def contested_screen():
    state = _STATE
    user = current_user(state)
    if user is None:
        return login_redirect()
    with state.lock:
        dossiers = [
            dossier_view(dossier)
            for dossier in sorted(state.dossiers.values(), key=lambda d: d["domain"])
        ]
    items = []
    for data in dossiers:
        for field in FIELDS:
            entry = data["fields"].get(field) or {}
            if entry.get("status") == "contested":
                items.append({"domain": data["domain"], "field": field, "field_data": entry})
    return html_response(contested_page(items, user=user))


def _form_payload() -> dict:
    if request.is_json:
        payload = request.get_json(silent=True)
        return payload if isinstance(payload, dict) else {}
    return request.form.to_dict()


@app.route("/signup", methods=["GET", "POST"])
def signup_screen():
    state = _STATE
    user = current_user(state)
    if request.method == "GET":
        if user is not None:
            return redirect("/", code=303)
        return html_response(auth_page("signup"))
    result = _create_account(_form_payload())
    if isinstance(result, Response):
        return html_response(auth_page("signup", error=_error_message(result), user=user))
    body, _status = result
    response = redirect("/", code=303)
    response.set_cookie(SESSION_COOKIE, body["token"], httponly=True, samesite="Lax", path="/")
    return response


@app.route("/login", methods=["GET", "POST"])
def login_screen():
    state = _STATE
    user = current_user(state)
    if request.method == "GET":
        if user is not None:
            return redirect("/", code=303)
        return html_response(auth_page("login"))
    result = _authenticate(_form_payload())
    if isinstance(result, Response):
        return html_response(auth_page("login", error=_error_message(result), user=user))
    body, _status = result
    response = redirect("/", code=303)
    response.set_cookie(SESSION_COOKIE, body["token"], httponly=True, samesite="Lax", path="/")
    return response


@app.post("/logout")
def logout_screen():
    state = _STATE
    token = bearer_token() or request.cookies.get(SESSION_COOKIE)
    if token:
        with state.lock:
            state.tokens.pop(token, None)
        persist_state(state)
    response = redirect("/login", code=303)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@app.errorhandler(HTTPException)
def handle_http_exception(exc: HTTPException):
    if exc.code == 404:
        return not_found("no such resource")
    if exc.code == 405:
        return error_response(405, "not_found", "method not allowed")
    return error_response(exc.code or 400, "malformed_request", exc.description or "request failed")


@app.errorhandler(Exception)
def handle_exception(_exc: Exception):
    return error_response(500, "internal_error", "internal error")


def main() -> None:
    port = int(os.environ.get("PORT", str(DEFAULT_PORT)))
    try:
        from waitress import serve

        serve(app, host="0.0.0.0", port=port, threads=64)
    except ImportError:  # pragma: no cover - fallback for local runs
        app.run(host="0.0.0.0", port=port, threaded=True)


if __name__ == "__main__":
    main()
