"""Appendix A support engine: decide whether an excerpt supports a value."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

FIELDS = (
    "legal_name",
    "hq_city",
    "ceo",
    "founded_year",
    "headcount_range",
    "funding_total",
)

STATEMENT_PHRASES = {
    "legal_name": [
        "legal name",
        "registered name",
        "registered as",
        "registered company",
        "legal entity",
        "name of record",
    ],
    "hq_city": [
        "headquartered in",
        "headquarters in",
        "head office in",
        "based in",
        "registered office in",
        "registered seat in",
    ],
    "ceo": ["chief executive officer", "chief executive", "CEO"],
    "founded_year": ["founded", "founding", "established", "incorporated"],
    "headcount_range": ["employs", "employees", "staff", "people", "headcount", "workforce"],
    "funding_total": ["raised", "funding", "invested", "investment"],
}

NEGATING_PHRASES = [
    "in talks to",
    "plans to",
    "planning to",
    "wants to",
    "expects to",
    "hopes to",
    "aims to",
    "seeking",
    "could",
    "would",
    "might",
    "reportedly",
    "rumoured",
    "former",
    "formerly",
    "will become",
    "not",
]

LEGAL_SUFFIXES = [
    "Inc.",
    "Corp.",
    "LLC",
    "LLP",
    "L.P.",
    "Ltd",
    "Limited",
    "Pty Ltd",
    "plc",
    "PLC",
    "GmbH",
    "AG",
    "KG",
    "SE",
    "AS",
    "A/S",
    "ASA",
    "AB",
    "Oy",
    "Oyj",
    "B.V.",
    "N.V.",
    "S.A.",
    "S.A.S.",
    "S.L.",
    "S.r.l.",
    "S.p.A.",
    "s.r.o.",
    "a.s.",
    "K.K.",
]
_SUFFIXES_LONGEST_FIRST = sorted(LEGAL_SUFFIXES, key=len, reverse=True)
_DOT_SUFFIXES = sorted([s for s in LEGAL_SUFFIXES if s.endswith(".")], key=len, reverse=True)

HEADCOUNT_RANGES = [
    (1, 10, "1-10"),
    (11, 50, "11-50"),
    (51, 200, "51-200"),
    (201, 500, "201-500"),
    (501, 1000, "501-1000"),
    (1001, 5000, "1001-5000"),
    (5001, 10000, "5001-10000"),
    (10001, None, "10001+"),
]

_WS_RE = re.compile(r"\s+")

_NUMBER_CORE = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
# A standalone number: not glued to letters/digits and not part of a malformed
# comma/period grouping.
_NUM_STANDALONE = re.compile(
    r"(?<![\d.,])(?<![^\W_])" + _NUMBER_CORE + r"(?![\d.,][0-9])(?![^\W_])"
)
# A number inside an amount; the scale may follow directly, so no trailing
# letter boundary here (the amount match enforces its own outer boundary).
_NUM_IN_AMOUNT = re.compile(r"(?<![\d.,])" + _NUMBER_CORE + r"(?![\d.,][0-9])")

_AMOUNT_1 = r"(?:US\$|\$|USD) ?" + _NUM_IN_AMOUNT.pattern + r"(?:(?:mn|bn|k|m)| (?:thousand|million|billion))?"
_AMOUNT_2 = (
    _NUM_IN_AMOUNT.pattern
    + r"(?: (?:thousand|million|billion))? (?:US dollars|dollars)"
)
_AMOUNT_RE = re.compile(
    r"(?<![^\W_])(?:" + _AMOUNT_1 + r"|" + _AMOUNT_2 + r")(?![^\W_])",
    re.IGNORECASE,
)


def collapse_ws(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def _is_capitalised_at(text: str, i: int) -> int | None:
    if i >= len(text) or not text[i].isupper():
        return None
    if i > 0 and text[i - 1].isalnum():
        return None
    j = i + 1
    if j >= len(text) or not text[j].islower():
        return None
    j += 1
    while j < len(text) and text[j].islower():
        j += 1
    if j < len(text) and text[j].isalnum():
        return None
    return j


def _is_uppercase_at(text: str, i: int) -> int | None:
    if i >= len(text) or not text[i].isupper():
        return None
    if i > 0 and text[i - 1].isalnum():
        return None
    j = i + 1
    while j < len(text) and text[j].isupper():
        j += 1
    if j - i < 2:
        return None
    if j < len(text) and text[j].isalnum():
        return None
    return j


def _is_header_name(name: str) -> bool:
    if not name:
        return False
    for part in name.split("-"):
        if len(part) < 2 or not part[0].isupper():
            return False
        if not all(ch.islower() for ch in part[1:]):
            return False
    return True


def split_prose(text: str) -> str:
    """Return the prose part of a page text (everything after the header)."""
    lines = text.splitlines()
    if not lines:
        return ""
    first = lines[0]
    colon = first.find(":")
    if colon <= 0 or not _is_header_name(first[:colon]):
        return text
    for index, line in enumerate(lines):
        if line.strip() == "":
            return "\n".join(lines[index + 1 :])
    return ""


def _ends_with_legal_suffix(line: str, end: int) -> bool:
    for suffix in _DOT_SUFFIXES:
        start = end - len(suffix)
        if start < 0:
            continue
        if line[start:end] != suffix:
            continue
        if start > 0 and line[start - 1].isalnum():
            continue
        if end < len(line) and line[end].isalnum():
            continue
        return True
    return False


def split_sentences(line: str) -> list[str]:
    sentences: list[str] = []
    start = 0
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch in ".!?":
            if ch == "." and _ends_with_legal_suffix(line, i + 1):
                i += 1
                continue
            j = i + 1
            while j < n and line[j] in '"”’)':
                j += 1
            if j >= n or line[j].isspace():
                sentence = line[start:j].strip()
                if sentence:
                    sentences.append(sentence)
                start = j
                i = j
                continue
        i += 1
    tail = line[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def is_single_sentence(excerpt: str) -> bool:
    normalised = collapse_ws(excerpt)
    if not normalised:
        return False
    return len(split_sentences(normalised)) == 1


def find_phrase_spans(text: str, phrase: str) -> list[tuple[int, int]]:
    haystack = text.lower()
    needle = phrase.lower()
    if not needle:
        return []
    spans: list[tuple[int, int]] = []
    pos = 0
    while True:
        index = haystack.find(needle, pos)
        if index < 0:
            break
        before_ok = index == 0 or not text[index - 1].isalnum()
        after = index + len(needle)
        after_ok = after >= len(text) or not text[after].isalnum()
        if before_ok and after_ok:
            spans.append((index, after))
        pos = index + 1
    return spans


def has_any_phrase(text: str, phrases: list[str]) -> bool:
    return any(find_phrase_spans(text, phrase) for phrase in phrases)


def _capital_run_end(text: str, start: int) -> int | None:
    end = _is_capitalised_at(text, start)
    if end is None:
        return None
    j = end
    while j < len(text):
        if text[j] == " ":
            nxt = _is_capitalised_at(text, j + 1)
            if nxt is not None:
                j = nxt
                continue
        elif text[j] == "-":
            nxt = _is_capitalised_at(text, j + 1)
            if nxt is not None:
                j = nxt
                continue
        break
    return j


def _suffix_match(text: str, start: int) -> int | None:
    for suffix in _SUFFIXES_LONGEST_FIRST:
        end = start + len(suffix)
        if text[start:end] != suffix:
            continue
        if end < len(text) and text[end].isalnum():
            continue
        return end
    return None


def _legal_name_values(text: str, company: str, domain: str) -> list[tuple[object, int, int]]:
    values: list[tuple[object, int, int]] = []
    anchors = find_phrase_spans(text, company) + find_phrase_spans(text, domain)
    for anchor_start, anchor_end in anchors:
        best_end: int | None = None
        pos = anchor_end
        while True:
            suffix_start: int | None = None
            if text[pos : pos + 1] == " ":
                suffix_start = pos + 1
            if text[pos : pos + 2] == ", ":
                suffix_start = pos + 2
            if suffix_start is not None:
                end = _suffix_match(text, suffix_start)
                if end is not None and (best_end is None or end < best_end):
                    best_end = end
            if text[pos : pos + 1] != " ":
                break
            nxt = _is_capitalised_at(text, pos + 1) or _is_uppercase_at(text, pos + 1)
            if nxt is None:
                break
            pos = nxt
        if best_end is not None:
            values.append((text[anchor_start:best_end], anchor_start, best_end))
    return values


def _hq_values(text: str) -> list[tuple[object, int, int]]:
    values: list[tuple[object, int, int]] = []
    for phrase in STATEMENT_PHRASES["hq_city"]:
        for _, phrase_end in find_phrase_spans(text, phrase):
            if text[phrase_end : phrase_end + 1] != " ":
                continue
            start = phrase_end + 1
            end = _capital_run_end(text, start)
            if end is not None:
                values.append((text[start:end], start, end))
    return values


def _person_values(
    text: str, company: str, domain: str, phrases: list[str]
) -> list[tuple[object, int, int]]:
    chars = list(text)
    for start, end in find_phrase_spans(text, company) + find_phrase_spans(text, domain):
        for i in range(start, end):
            chars[i] = "\x00"
    for phrase in phrases:
        for start, end in find_phrase_spans(text, phrase):
            for i in range(start, end):
                chars[i] = "\x00"
    masked = "".join(chars)

    tokens: list[tuple[int, int]] = []
    i = 0
    while i < len(masked):
        end = _is_capitalised_at(masked, i)
        if end is not None:
            tokens.append((i, end))
            i = end
        else:
            i += 1

    groups: list[tuple[int, int]] = []
    current: list[tuple[int, int]] = []
    for token in tokens:
        if current and token[0] == current[-1][1] + 1 and masked[current[-1][1]] == " ":
            current.append(token)
        else:
            if current:
                groups.append((current[0][0], current[-1][1]))
            current = [token]
    if current:
        groups.append((current[0][0], current[-1][1]))

    values: list[tuple[object, int, int]] = []
    for start, end in groups:
        if end - start == 0:
            continue
        words = [w for w in re.split(r" ", masked[start:end]) if w]
        if len(words) in (2, 3):
            values.append((text[start:end], start, end))
    return values


def _ceo_values(text: str, company: str, domain: str) -> list[tuple[object, int, int]]:
    return _person_values(text, company, domain, STATEMENT_PHRASES["ceo"])


def amount_spans(text: str) -> list[tuple[int, int, object]]:
    spans: list[tuple[int, int, object]] = []
    for match in _AMOUNT_RE.finditer(text):
        raw = match.group(0)
        number_match = _NUM_IN_AMOUNT.search(raw)
        if number_match is None:
            continue
        number_text = number_match.group(0)
        rest = raw[number_match.end() :].lower()
        scale = 1
        if "thousand" in rest:
            scale = 1_000
        elif "million" in rest:
            scale = 1_000_000
        elif "billion" in rest:
            scale = 1_000_000_000
        elif rest.startswith("mn"):
            scale = 1_000_000
        elif rest.startswith("bn"):
            scale = 1_000_000_000
        elif rest.startswith("k"):
            scale = 1_000
        elif rest.startswith("m"):
            scale = 1_000_000
        try:
            number = Decimal(number_text.replace(",", ""))
        except InvalidOperation:
            continue
        total = number * scale
        if total != total.to_integral_value():
            continue
        spans.append((match.start(), match.end(), int(total)))
    return spans


def _number_values(text: str, amount_ranges: list[tuple[int, int, object]]) -> list[tuple[int, int, str]]:
    out: list[tuple[int, int, str]] = []
    for match in _NUM_STANDALONE.finditer(text):
        if any(start <= match.start() and match.end() <= end for start, end, _ in amount_ranges):
            continue
        out.append((match.start(), match.end(), match.group(0)))
    return out


def headcount_range_for(number: int) -> str | None:
    for low, high, label in HEADCOUNT_RANGES:
        if number >= low and (high is None or number <= high):
            return label
    return None


def extract_values(text: str, field: str, company: str, domain: str) -> list[tuple[object, int, int]]:
    if field == "legal_name":
        return _legal_name_values(text, company, domain)
    if field == "hq_city":
        return _hq_values(text)
    if field == "ceo":
        return _ceo_values(text, company, domain)
    if field == "funding_total":
        return [(value, start, end) for start, end, value in amount_spans(text)]
    if field in ("founded_year", "headcount_range"):
        amounts = amount_spans(text)
        values: list[tuple[object, int, int]] = []
        for start, end, raw in _number_values(text, amounts):
            if "." in raw:
                continue
            digits = raw.replace(",", "")
            if not digits.isdigit():
                continue
            number = int(digits)
            if field == "founded_year":
                if len(digits) == 4 and 1800 <= number <= 2099:
                    values.append((number, start, end))
            else:
                if number >= 1:
                    label = headcount_range_for(number)
                    if label is not None:
                        values.append((label, start, end))
        return values
    return []


def excerpt_value(excerpt: str, field: str, company: str, domain: str) -> object | None:
    text = collapse_ws(excerpt)
    if not text:
        return None
    if not is_single_sentence(text):
        return None
    if not (find_phrase_spans(text, domain) or find_phrase_spans(text, company)):
        return None
    if not has_any_phrase(text, STATEMENT_PHRASES[field]):
        return None
    if has_any_phrase(text, NEGATING_PHRASES):
        return None
    values = extract_values(text, field, company, domain)
    if not values:
        return None
    normalised = {value for value, _, _ in values}
    if len(normalised) != 1:
        return None
    return next(iter(normalised))


# --------------------------------------------------------------------------
# Executives: each title is a field with the format and normalisation of ceo.

EXEC_TITLES = ("cfo", "coo", "cto")

EXEC_STATEMENT_PHRASES = {
    "cfo": ["chief financial officer", "CFO"],
    "coo": ["chief operating officer", "COO"],
    "cto": ["chief technology officer", "CTO"],
}


def executive_values(
    excerpt: str, title: str, company: str, domain: str
) -> list[tuple[object, int, int]]:
    text = collapse_ws(excerpt)
    return _person_values(text, company, domain, EXEC_STATEMENT_PHRASES[title])


def executive_value(
    excerpt: str, title: str, company: str, domain: str
) -> object | None:
    text = collapse_ws(excerpt)
    if not text:
        return None
    if not is_single_sentence(text):
        return None
    if not (find_phrase_spans(text, domain) or find_phrase_spans(text, company)):
        return None
    if not has_any_phrase(text, EXEC_STATEMENT_PHRASES[title]):
        return None
    if has_any_phrase(text, NEGATING_PHRASES):
        return None
    values = executive_values(text, title, company, domain)
    if not values:
        return None
    normalised = {str(value) for value, _, _ in values}
    if len(normalised) != 1:
        return None
    return next(iter(normalised))
