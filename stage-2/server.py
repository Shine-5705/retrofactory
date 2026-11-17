"""Dossier stage 1 service.

A small threaded HTTP service.  All state lives in memory; reset, export and
import replace it atomically.  Background builds research a domain through
WebRouter (Nimble) and decide each field only from provider-served text using
the Appendix A support rules in dossier_support.py.
"""

from __future__ import annotations

import copy
import json
import os
import re
import secrets
import threading
import time
from datetime import datetime, timezone

from flask import Flask, Response, request
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

from dossier_support import (
    FIELDS,
    collapse_ws,
    excerpt_value,
    split_prose,
    split_sentences,
)

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

DEFAULT_PORT = 8080
MAX_UNITS = 80

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+$")
_DOMAIN_LABEL_RE = re.compile(r"^[a-z0-9-]+$")
_INT_QUERY_RE = re.compile(r"^[0-9]+$")

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


def parse_rfc3339(value: str) -> datetime | None:
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


def empty_fields() -> dict:
    return {
        field: {"value": None, "status": "unknown", "citations": []}
        for field in FIELDS
    }


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

    def now(self) -> datetime:
        if self.frozen_clock is not None:
            return self.frozen_clock
        return datetime.now(timezone.utc)


_GLOBAL_LOCK = threading.RLock()
_STATE = State()


def get_state() -> State:
    return _STATE


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


def auth_user(state: State) -> str | None:
    header = request.headers.get("Authorization")
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    if not token:
        return None
    with state.lock:
        return state.tokens.get(token)


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


def request_payload(dossier: dict, status: int) -> Response:
    return json_response(dossier_brief(dossier), status)


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
        dossier["build_spent"] += cost
        dossier["spent_units"] += cost
        return True


def _refund(state: State, dossier: dict, cost: int) -> None:
    with state.lock:
        dossier["build_spent"] = max(0, dossier["build_spent"] - cost)
        dossier["spent_units"] = max(0, dossier["spent_units"] - cost)


def _timeout_for(deadline: float, cap: float) -> float | None:
    remaining = deadline - time.monotonic()
    if remaining <= 5:
        return None
    return max(1.0, min(cap, remaining - 2.0))


def _do_search(state: State, dossier: dict, query: str, cost: int, deadline: float):
    if not _reserve(state, dossier, cost):
        return None
    timeout = _timeout_for(deadline, 60.0)
    if timeout is None:
        _refund(state, dossier, cost)
        return None
    try:
        response = get_router().search(
            query,
            provider="nimble",
            search_depth="deep",
            max_results=10,
            timeout=timeout,
            data_apis=False,
        )
        return response
    except Exception as exc:
        if _exception_was_refused(exc):
            _refund(state, dossier, cost)
        return None


def _do_research(state: State, dossier: dict, query: str, cost: int, deadline: float):
    if not _reserve(state, dossier, cost):
        return None
    timeout = _timeout_for(deadline, 200.0)
    if timeout is None:
        _refund(state, dossier, cost)
        return None
    try:
        return get_router().research(
            query,
            provider="nimble",
            output_schema=RESEARCH_SCHEMA,
            timeout=timeout,
        )
    except Exception as exc:
        if _exception_was_refused(exc):
            _refund(state, dossier, cost)
        return None


def _search_pages(response, pages: list[dict]) -> None:
    if response is None:
        return
    provider = getattr(response, "provider", None) or "nimble"
    for result in getattr(response, "results", []) or []:
        text = getattr(result, "content", "") or getattr(result, "description", "")
        url = getattr(result, "url", "") or ""
        title = getattr(result, "title", "") or ""
        if isinstance(text, str) and text.strip():
            pages.append({"url": url, "title": title, "text": text, "provider": provider})


def _research_pages(response, pages: list[dict]) -> None:
    if response is None:
        return
    provider = getattr(response, "provider", None) or "nimble"
    for citation in getattr(response, "citations", []) or []:
        snippet = getattr(citation, "snippet", "") or ""
        if isinstance(snippet, str) and snippet.strip():
            pages.append(
                {
                    "url": getattr(citation, "url", "") or "",
                    "title": getattr(citation, "title", "") or "",
                    "text": snippet,
                    "provider": provider,
                }
            )


def decide_fields(pages: list[dict], domain: str) -> dict:
    company = company_name(domain)
    candidates: dict[str, dict] = {field: {} for field in FIELDS}

    for page in pages:
        url = page.get("url") or ""
        provider = page.get("provider") or "nimble"
        prose = split_prose(page.get("text") or "")
        for line in prose.splitlines():
            for sentence in split_sentences(line):
                excerpt = collapse_ws(sentence)
                if not (1 <= len(excerpt) <= 500):
                    continue
                for field in FIELDS:
                    value = excerpt_value(excerpt, field, company, domain)
                    if value is None:
                        continue
                    bucket = candidates[field].setdefault(value, [])
                    citation = {"url": url, "excerpt": excerpt, "provider": provider}
                    if citation not in bucket:
                        bucket.append(citation)

    fields: dict[str, dict] = {}
    for field in FIELDS:
        bucket = candidates[field]
        if not bucket:
            fields[field] = {"value": None, "status": "unknown", "citations": []}
            continue
        best_value = None
        best_citations: list[dict] = []
        for value, citations in bucket.items():
            if len(citations) > len(best_citations):
                best_value = value
                best_citations = citations
        fields[field] = {
            "value": best_value,
            "status": "known",
            "citations": list(best_citations),
        }
    return fields


_EXTRA_QUERIES = [
    "{company} company profile",
    "{company} headquarters founded CEO funding employees",
    "{company} official website about company",
    "{company} annual revenue funding headcount leadership",
    "{company} about us founded headquarters chief executive",
]


def _build_worker(state: State, dossier: dict, build_time: datetime, generation: int) -> None:
    deadline = time.monotonic() + 288.0
    pages: list[dict] = []
    any_success = False
    domain = dossier["domain"]
    company = company_name(domain)

    try:
        router_ok = True
        try:
            get_router()
        except Exception:
            router_ok = False

        if router_ok:
            # Exactly one successful search whose query is the normalised domain.
            response = _do_search(state, dossier, domain, 15, deadline)
            if response is not None:
                any_success = True
                _search_pages(response, pages)

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
                _research_pages(research, pages)

            for template in _EXTRA_QUERIES:
                if deadline - time.monotonic() < 20:
                    break
                query = template.format(company=company)
                response = _do_search(state, dossier, query, 15, deadline)
                if response is None:
                    continue
                any_success = True
                _search_pages(response, pages)

        fields = decide_fields(pages, domain)
    except Exception:
        fields = empty_fields()
        any_success = False

    with state.lock:
        if not dossier.get("building") or dossier.get("build_gen") != generation:
            return
        dossier["building"] = False
        if any_success:
            dossier["fields"] = fields
            dossier["researched_at"] = now_iso(build_time)
            dossier["state"] = "ready"
            dossier["last_outcome"] = "ready"
        else:
            dossier["state"] = "failed"
            dossier["last_outcome"] = "failed"


def start_build(state: State, dossier: dict, build_time: datetime) -> None:
    dossier["building"] = True
    dossier["build_gen"] += 1
    dossier["base_spent"] = dossier["spent_units"]
    dossier["build_spent"] = 0
    dossier["state"] = "building"
    generation = dossier["build_gen"]
    thread = threading.Thread(
        target=_build_worker,
        args=(state, dossier, build_time, generation),
        daemon=True,
    )
    thread.start()


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
        dossiers = []
        for dossier in state.dossiers.values():
            if dossier["building"]:
                exported_state = dossier["last_outcome"] or "failed"
                spent = dossier["base_spent"]
            else:
                exported_state = dossier["state"]
                spent = dossier["spent_units"]
            dossiers.append(
                {
                    "id": dossier["id"],
                    "domain": dossier["domain"],
                    "state": exported_state,
                    "researched_at": dossier["researched_at"],
                    "spent_units": spent,
                    "fields": copy.deepcopy(dossier["fields"]),
                }
            )
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
            "dossiers": dossiers,
            "idempotency": idempotency,
            "next_user": state.next_user,
            "next_dossier": state.next_dossier,
        }


def _valid_field_entry(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    if entry.get("status") not in ("known", "unknown"):
        return False
    if "value" not in entry or not isinstance(entry.get("citations"), list):
        return False
    if entry["status"] == "unknown":
        return entry.get("value") is None and entry["citations"] == []
    return entry.get("value") is not None and len(entry["citations"]) >= 1


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

    for item in dossiers:
        if not isinstance(item, dict):
            return None
        dossier_id = item.get("id")
        domain = item.get("domain")
        outcome = item.get("state")
        if not isinstance(dossier_id, str) or not isinstance(domain, str):
            return None
        if outcome not in ("ready", "failed"):
            return None
        fields = item.get("fields")
        if not isinstance(fields, dict) or set(fields) != set(FIELDS):
            return None
        if not all(_valid_field_entry(entry) for entry in fields.values()):
            return None
        spent = item.get("spent_units")
        researched_at = item.get("researched_at")
        if not isinstance(spent, int) or spent < 0:
            return None
        if researched_at is not None and not isinstance(researched_at, str):
            return None
        if domain in state.dossiers:
            return None
        state.dossiers[domain] = {
            "id": dossier_id,
            "domain": domain,
            "state": outcome,
            "last_outcome": outcome,
            "fields": copy.deepcopy(fields),
            "researched_at": researched_at,
            "spent_units": spent,
            "base_spent": spent,
            "build_spent": 0,
            "building": False,
            "build_gen": 0,
        }

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
    return state


def _next_id(prefix: str, current: int, taken: set[str]) -> tuple[str, int]:
    while True:
        candidate = f"{prefix}_{current}"
        current += 1
        if candidate not in taken:
            return candidate, current


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
    with _GLOBAL_LOCK:
        state = _STATE
        with state.lock:
            current = state.frozen_clock
            if current is None:
                current = datetime.now(timezone.utc)
            if parsed < current:
                return validation_error("now is earlier than the clock")
            state.frozen_clock = parsed
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
    with _GLOBAL_LOCK:
        current = _STATE
        with current.lock:
            clock = current.frozen_clock
        new_state = _state_from_export(body.get("state"), clock)
        if new_state is None:
            return validation_error("invalid state")
        _STATE = new_state
    return empty_response(204)


@app.post("/auth/signup")
def signup():
    body, ok = read_json_body()
    if not ok:
        return malformed("unparseable signup body")
    if not isinstance(body, dict):
        return malformed("signup body must be an object")
    for key in ("email", "password", "display_name"):
        if key in body and not isinstance(body[key], str):
            return malformed(f"{key} must be a string")
    if "email" not in body or "password" not in body or "display_name" not in body:
        return validation_error("email, password and display_name are required")
    email = body["email"]
    password = body["password"]
    display_name = body["display_name"]
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
    return json_response(
        {"user_id": user_id, "display_name": display_name, "token": token}, 201
    )


@app.post("/auth/login")
def login():
    body, ok = read_json_body()
    if not ok:
        return malformed("unparseable login body")
    if not isinstance(body, dict):
        return malformed("login body must be an object")
    for key in ("email", "password"):
        if key in body and not isinstance(body[key], str):
            return malformed(f"{key} must be a string")
    if "email" not in body or "password" not in body:
        return validation_error("email and password are required")
    email_key = body["email"].lower()
    state = _STATE
    with state.lock:
        user_id = state.email_index.get(email_key)
        user = state.users.get(user_id) if user_id else None
        password_hash = user["password_hash"] if user else None
    if user is None or password_hash is None or not check_password_hash(password_hash, body["password"]):
        return unauthenticated("wrong email or password")
    with state.lock:
        token = token_for_user(state)
        state.tokens[token] = user["id"]
        display_name = user["display_name"]
        user_id = user["id"]
    return json_response({"user_id": user_id, "display_name": display_name, "token": token})


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
            dossier = {
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
            }
            state.dossiers[domain] = dossier
            start_build(state, dossier, state.now())
            response_body = dossier_brief(dossier)
            status = 202
        state.idem[idem_key] = {"body": canonical, "response": copy.deepcopy(response_body)}
    return json_response(response_body, status)


@app.get("/dossiers")
def list_dossiers():
    state = _STATE
    user_id = auth_user(state)
    if user_id is None:
        return unauthenticated()

    raw_limit = request.args.get("limit")
    raw_offset = request.args.get("offset")
    if raw_limit is not None:
        if not _INT_QUERY_RE.match(raw_limit):
            return validation_error("limit must be plain decimal digits")
        limit = int(raw_limit)
        if limit < 1 or limit > 200:
            return validation_error("limit must be between 1 and 200")
    else:
        limit = 50
    if raw_offset is not None:
        if not _INT_QUERY_RE.match(raw_offset):
            return validation_error("offset must be plain decimal digits")
        offset = int(raw_offset)
    else:
        offset = 0
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


@app.get("/dossiers/<path:domain>")
def get_dossier(domain: str):
    state = _STATE
    user_id = auth_user(state)
    if user_id is None:
        return unauthenticated()
    try:
        normalised = normalise_domain(domain)
    except ValueError:
        return validation_error("invalid domain")
    with state.lock:
        dossier = state.dossiers.get(normalised)
        if dossier is None:
            return not_found("no such dossier")
        return json_response(dossier_view(dossier))


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
    return json_response(response_body, 202)


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
