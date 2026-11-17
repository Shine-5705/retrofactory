# Stage 1 Requirement Checklist

Derived from /workspace/band/ref/sf-buildathon-2026/challenges/dossier/spec/stage-1.md

## §1. Scope
1. Every asserted value must cite at least one provider-served excerpt that supports it; no invented, reworded, or mismatched citations. (§1)
2. No dossier build may spend more than 80 units. (§1, §9)
3. Contact data, people search, and fields other than the six in §4 are out of scope. (§1)

## §2. Delivery and deployment
4. Deliver HTTP service with Dockerfile and RUN.md buildable and runnable without manual setup. (§2)
5. Docker image runs standalone with `-e PORT=<port>` and port mapping; `docker-compose.yml` not used to start service. (§2)
6. All runtime dependencies, initialization and seed data work within the single container. (§2)
7. Language/framework/storage unrestricted (TypeScript/JavaScript, Go, Rust, Java, Python, etc. all valid). (§2)
8. Submitted Dockerfile is built and started; only its HTTP behavior is exercised; source not imported/executed on host. (§2)
9. Two providers available: `nimble` (default) and `tavily` (optional). (§2)
10. Nimble research must work alone; tavily absence must not prevent research while nimble answers. (§2)
11. All provider requests go through WebRouter (`web_router` module). (§2)
12. `webrouter>=0.12.0` listed in dependency manifest. (§2)
13. `pip install "webrouter[search,extract,research]>=0.12.0"` used in Docker build. (§2)
14. `PORT` env var: service listens on `0.0.0.0` using `PORT`, default `8080`. (§3.1)

## §3. Runtime contract
### 3.1 Listening
15. Service listens on `0.0.0.0` using `PORT` env var, default `8080`. (§3.1)

### 3.2 Health
16. `GET /health` returns `200 {"status":"ok"}` once service and data store can serve requests, within 60s of container start. (§3.2)
17. `/health` makes no provider call. (§3.2)

### 3.3 Reset and seed
18. `POST /_test/reset` replaces all service state with fixture body. (§3.3)
19. After `reset` returns `204`, subsequent requests see only fixture: no extraneous users, dossiers, or stored idempotent responses. (§3.3)
20. Repeated resets are supported. (§3.3)
21. Build running when `reset` called must not change post-reset state. (§3.3)
22. `/_test/reset` requires no authentication. (§3.3)
23. Fixture with two users sharing an email returns `422 validation_failed`, changing nothing. (§3.3)

### 3.4 Clock
24. Clock only moved by `reset` and `POST /_test/clock`. (§3.4)
25. All timestamps recorded or returned read from this clock. (§3.4)
26. Before first reset, clock follows system time. (§3.4)
27. Clock stands still between calls: two requests with no clock call between them read the same time. (§3.4)
28. `POST /_test/clock` with RFC 3339 `now`; `422 validation_failed` if `now` earlier than current clock, changes nothing. (§3.4)
29. `POST /_test/clock` requires no authentication. (§3.4)

### 3.5 Conventions
30. Requests and responses are `application/json; charset=utf-8`. (§3.5)
31. Timestamps in responses are RFC 3339 with explicit offset, e.g. `2026-09-24T19:00:00+02:00`. (§3.5)
32. Unknown fields in request body ignored, never error. (§3.5)
33. Unknown query parameters ignored. (§3.5)
34. IDs are opaque strings max 64 characters; format arbitrary. (§3.5)

## §4. Model
### Users
35. Users sign up and login (§6); every authenticated user sees the same dossiers. (§4)

### Domains
36. Domain normalisation: surrounding whitespace removed, lowercased, one trailing `.` removed, one leading `www.` removed. (§4)
37. Normalised domain must be valid host name: ≥2 labels of 1-63 chars `[a-z0-9-]`, not starting/ending with `-`, ≤253 chars total. (§4)
38. Invalid domain (URL with scheme/path) returns `422 validation_failed`. (§4)
39. Responses always carry the normalised domain. (§4)

### Fields - six fields
40. Dossier has exactly six fields: `legal_name`, `hq_city`, `ceo`, `founded_year`, `headcount_range`, `funding_total`. (§4)
41. `legal_name`: string, company's registered name. (§4)
42. `hq_city`: string, city without region or country. (§4)
43. `ceo`: string, full name of chief executive. (§4)
44. `founded_year`: integer year founded. (§4)
45. `headcount_range`: one of `1-10`, `11-50`, `51-200`, `201-500`, `501-1000`, `1001-5000`, `5001-10000`, `10001+` as string. (§4)
46. `funding_total`: integer, total equity funding in whole US dollars. (§4)
47. String values written as excerpt writes them, no surrounding whitespace. (§4)
48. Headcount as number/range mapped to containing range as value. (§4)
49. Each field response: `{value, status, citations}` shape. (§4)
50. `status`: `known` when value not null, `unknown` when null. (§4)
51. Known field has one or more citations; unknown has `"value":null, "citations":[]`. (§4)
52. `url` in citation: page URL; `provider`: `nimble` or `tavily`. (§4)

### Evidence and support
53. Evidence: every search-researched page + every nimble research claim for all six fields. (§4)
54. Each build makes exactly one query = normalised domain through chosen provider; other searches use other queries. (§4)
55. Errored provider searches don't count. (§4)
56. Gathered pages: text obtained from provider pages. (§4)
57. Citation: excerpt of text provider served for page at url. (§4)
58. Excerpt copied character-for-character from served text; whitespace runs collapsed to single space. (§4)
59. Excerpt 1-500 characters long. (§4)
60. Excerpt from page prose, not header. (§4)
61. `Fact:` header JSON object; keys are field names; values are what page states; informative only. (§4)
62. Citations from prose; support decision by Appendix A alone. (§4)
63. When evidence supports multiple values, field holds one and cites only supporting excerpts. (§4)

### Pages
64. Every page has URL, title, text. Text may begin with header lines `Name: value`. (§4)
65. Header ends at first empty line; rest is prose. (§4)
66. Text without header line has no header, all prose. (§4)
67. `Fact:` header line carries JSON object on same line; keys are field names. (§4)

## §5. Errors
68. Every 4xx/5xx: `{error: {code, message}}`. (§5)
69. Use specified HTTP status and `code`; human-readable `message` any wording. (§5)
70. `400 malformed_request`: unparseable body or field of wrong JSON type. (§5)
71. `400 missing_idempotency_key`: `Idempotency-Key` header absent or empty. (§5)
72. `401 unauthenticated`: missing, malformed or unknown bearer token. (§5)
73. `404 not_found`: no such resource or not visible to caller. (§5)
74. `409 idempotency_key_reuse`: key already used by same caller with different body. (§5)
75. `422 validation_failed`: required field missing or rule violated with no more specific code. (§5)
76. Integer query params as plain decimal digits; `1e9`, `4.0`, `+4` are `422 validation_failed`. (§5)
77. Reserve `400 malformed_request` for unparseable body or wrong field type. (§5)
78. `Idempotency-Key`: 1-255 chars enforced; else `422 validation_failed`. (§5)
79. `limit`: integer 1-200 enforced; else `422 validation_failed`. (§5)
80. `offset`: integer 0+ enforced; else `422 validation_failed`. (§5)
81. Requests must not produce `5xx` responses, including under concurrent load or provider error. (§5)

## §6. Authentication
82. Authentication supports signup and login; email verification, password reset, refresh tokens, role-management out of scope. (§6)
83. `POST /auth/signup` with `{email, password, display_name}` → `201 {user_id, display_name, token}`. (§6)
84. `POST /auth/login` with `{email, password}` → `200 {user_id, display_name, token}`. (§6)
85. Email already registered → `409 email_taken`. (§6)
86. Password shorter than 8 characters → `422 validation_failed`. (§6)
87. `email` not of form `local@domain` → `422 validation_failed`. (§6)
88. `display_name` empty or longer than 100 characters → `422 validation_failed`. (§6)
89. Wrong password or unknown email on login → `401 unauthenticated`. (§6)
90. Fixture-seeded `user_id` equals fixture's `id`. (§6)
91. Every endpoint except `/health`, `/_test/*` and the two `/auth/*` requires bearer token. (§6)
92. Lacking valid token → `401 unauthenticated`, even without `Idempotency-Key`. (§6)
93. `Authorization: Bearer <token>` header format. (§6)
94. Tokens do not expire; multiple valid tokens per account allowed. (§6)
95. Passwords hashed via bcrypt/scrypt/Argon2 or equivalent; plaintext storage prohibited. (§6)

## §7. Idempotency
96. POST /dossiers and POST /dossiers/{domain}/refresh require Idempotency-Key. (§7)
97. Key scoped to authenticated user; different users may use same key with no interaction. (§7)
98. Replay: same method, same path, same body, same key. (§7)
99. Same key, same body on different path → different request, succeeds normally. (§7)
100. `Acme-Robotics.test` and `acme-robotics.test` are different requests for this rule. (§7)
101. Header absent or empty → `400 missing_idempotency_key`. (§7)
102. First use of key → normal response. (§7)
103. Replay: same key, same body → `200`, body identical to original response as JSON value. (§7)
104. Same key, different body → `409 idempotency_key_reuse`. (§7)
105. Key reused after original request failed with 4x → treated as first use. (§7)
106. "Same body": same JSON value after parsing; key order and whitespace don't matter. (§7)
107. Unknown fields ignored; body differing only in unknown fields is same body/replay. (§7)
108. POST /dossiers/{domain}/refresh takes no body; body ignored in replay decision. (§7)
109. Concurrent identical requests with unused key: exactly one returns normal response; others return 200 same body. (§7)
110. Successful replay returns original response even after dossier changed; starts no build, makes no provider call. (§7)
111. Claimed key resolved before field validation; invalid body with same successful key → `409 idempotency_key_reuse`. (§7)

## §8. API
### Builds
112. Build researches one dossier: calls providers, decides each field, replaces fields when complete. (§8)
113. First build starts with `POST /dossiers`; later with `POST /dossiers/{domain}/refresh`. (§8)
114. Dossier has at most one build running at a time. (§8)
115. Build ends in `ready` (completed) or `failed` (no provider calls succeeded). (§8)
116. Failed build leaves fields as they were. (§8)
117. When build completes `ready`, each field is `known` exactly when evidence supports value. (§8)
118. Build with provider calls each within 1s ends within 10s of request. (§8)
119. Bound not a deadline for slower providers. (§8)
120. Against live providers (`sdk.nimbleway.com`): no give-up <30s wait; no stop <120s run; ends `ready`/`failed` within 300s. (§8)
121. Reading dossier, listing dossiers and other requests except `POST /dossiers` and `POST /dossiers/{domain}/refresh` make no provider call. (§8)

### POST /dossiers
122. Idempotency-Key required; see §7. (§8)
123. No dossier for domain → creates one, starts first build, returns `202`. (§8)
124. Dossier already exists → starts no build, returns `200` with `dossier_id`, `domain`, `state`. (§8)
125. Concurrent same-domain requests create one dossier and one build, whatever their keys. (§8)
126. `domain` missing → `422 validation_failed`. (§8)
127. `domain` invalid after normalisation → `422 validation_failed`. (§8)

### GET /dossiers/{domain}
128. Returns `{dossier_id, domain, state, researched_at, spent_units, fields}`. (§8)
129. `state`: `building` while build runs; otherwise `ready` or `failed` outcome. (§8)
130. `fields` always holds all six fields; before first build `ready`, all `unknown`. (§8)
131. `researched_at`: time of last build that completed `ready`, or `null`. (§8)
132. `spent_units`: total cost of every provider call for this dossier since creation. (§8)
133. Domain in path normalised; no dossier for it is `404 not_found`. (§8)

### POST /dossiers/{domain}/refresh
134. Idempotency-Key required; see §7. No body. (§8)
135. Starts new build, returns `202` with `{dossier_id, domain, state: "building"}`. (§8)
136. Refresh during running build: no second build, returns `202` same body. (§8)
137. Refresh research makes provider calls regardless of changes; spending counts in `spent_units`. (§8)
138. No dossier for domain → `404 not_found`. (§8)

### GET /dossiers
139. `GET /dossiers?q=acme&limit=50&offset=0`. (§8)
140. `q` optional: filters by domain or `legal_name` case-insensitive containment. (§8)
141. Empty `q` lists every dossier. (§8)
142. Dossiers ordered by domain ascending. (§8)
143. `limit` defaults to 50, range 1-200; `offset` defaults to 0. (§8)
144. `has_more` true when items exist beyond last returned. (§8)

## §9. Providers and cost
145. Each provider call has cost in units per table. (§9)
146. Nimble search depth `lite` (title, URL, snippet) → 1 unit. (§9)
147. Nimble search depth `fast` (truncated page body) → 5 units. (§9)
148. Nimble search depth `deep` (full page) → 15 units. (§9)
149. Tavily search depth `lite` (title, URL, snippet) → 8 units. (§9)
150. Tavily search depth `fast` (title, URL, longer snippet) → 16 units. (§9)
151. Tavily search depth `deep` (full page) → 16 units. (§9)
152. Extract through `nimble` → 1 per URL requested, including no-page URLs. (§9)
153. Extract through `tavily` → 2 per URL requested, including no-page URLs. (§9)
154. Research run through `nimble` → 25 when started; checking/collecting costs nothing. (§9)
155. Search depth = WebRouter `search_depth`. (§9)
156. Search returns at most 10 results, whatever number asked for. (§9)
157. Provider error-status call costs nothing. (§9)
158. Timeout/connection-fail call costs its units whether or not provider received it. (§9)
159. Extract with no page: costs its units; not refused. (§9)
160. Nimble extract does not set `render`. (§9)
161. Build stops before spending exceeds 80 units; completes with obtained pages/claims. (§9)
162. Research request names company by domain in query; names fields by §4 names as output schema property names. (§9)

## §10. Export and import
161. Service supports `GET /_test/export` and `POST /_test/import`. (§10)
162. Export unauthenticated control endpoint. (§10)
163. Export returns `200` with JSON: `track:"dossier"`, `format_version:1`, `state`. (§10)
164. State format opaque; must be accepted unchanged by import. (§10)
165. Import replaces service state entirely, returns `204`. (§10)
166. Import accepts unchanged export from this service. (§10)
167. No dependency on source process, files, volume, port or network address. (§10)
168. Import is replacement, not merge; repeat restores state without duplication. (§10)
169. Invalid JSON/missing fields/wrong track/version/invalid state → `422 validation_failed`, no change. (§10)
170. Control calls have 10-second timeout. (§10)
171. Export atomic read-only snapshot; subsequent source writes don't change it. (§10)
172. Preserve accounts, hashed-password login, existing bearer tokens, dossiers with ids/states/fields/citations/researched_at/spent_units. (§10)
173. Identities and timestamps must not be regenerated. (§10)
174. Import makes no provider call; imported dossiers not researched again; citations remain. (§10)
175. Failed request keys remain reusable. (§10)
176. Existing tokens and retries remain valid after import. (§10)
177. Fresh fixture replacement does not satisfy import requirement. (§10)
178. Import removes all previous destination data and credentials. (§10)
179. Reset clears all state including imported state. (§10)
180. State need not survive abrupt container restart. (§10)
181. Export taken during running build holds dossier as before that build; after import, dossier in state of last completed build or failed with all fields `unknown` when no build completed. (§10)

## §11. Concurrency
182. Concurrent requests produce same results as sequential execution in some order. (§11)
183. Requirements above hold at every read. (§11)

## Appendix A. When an excerpt supports a value
### A.1 Sentences
184. Prose split into lines at line breaks; each line into sentences. (§A.1)
185. Sentence ends after `. ! ?` plus any `" "" '' )` directly after when whitespace follows. (§A.1)
186. Legal-form suffix `.` written as whole word does not end sentence. (§A.1)
187. Sentence taken without surrounding whitespace; empty dropped. (§A.1)
188. Excerpt is single sentence when whitespace-normalized splits into exactly one sentence. (§A.1)

### A.2 The rule
189. Excerpt supports value V for field F exactly when all hold: (§A.2)
190. It is a single sentence (A.1). (§A.2.1)
191. It names the company: contains normalised domain or company name. (§A.2.2)
192. It contains a statement phrase for F (A.3). (§A.2.3)
193. It contains none of the negating phrases (A.3). (§A.2.4)
194. It contains at least one value in F's format (A.4), and every such value normalises to V (A.5). (§A.2.5)

### A.3 Phrases
195. Statement phrases per field: `legal_name`, `hq_city`, `ceo`, `founded_year`, `headcount_range`, `funding_total`. (§A.3)
196. Negating phrases: `in talks to`, `plans to`, `planning to`, `wants to`, `expects to`, `hopes to`, `aims to`, `seeking`, `could`, `would`, `might`, `reportedly`, `rumoured`, `formerly`, `will become`, `not`. (§A.3)

### A.4 Value formats
197. Capitalised word: uppercase letter followed by lowercase letters; no letter/digit before/after. (§A.4)
198. Uppercase word: two+ uppercase letters; no letter/digit before/after: `AI`, `USA`. (§A.4)
199. Number: digits with optional `,` before groups of three and decimal part after `.`. (§A.4)
200. `legal_name` format: company name/domain then zero or more cap/uppercase words each after one space, optional `, ` one space and legal-form suffix with no letter/digit after. (§A.4)
201. `hq_city` format: place name after statement phrase and one space; longest run of cap words joined by single spaces or `-`, not part of longer run. (§A.4)
202. `ceo` format: person's name: 2-3 cap words joined by single spaces; not part of longer run; company name and ceo statement phrases taken out first. (§A.4)
203. `founded_year`: exactly four digits 1800-2099, not part of an amount. (§A.4)
204. `headcount_range`: number no decimal part 1+ not part of amount; words like about/roughly don't change it; range like `51-200 employees` holds two numbers. (§A.4)
205. `funding_total`: an amount per below definition. (§A.4)

### A.5 Normalisation
206. `legal_name`, `hq_city`, `ceo`: text as excerpt writes it. (§A.5)
207. `founded_year`: number as integer. (§A.5)
208. `headcount_range`: range of §4 that contains the number. (§A.5)
209. `funding_total`: number times scale in US dollars (k/thousand=1,000; m/mn/million=1,000,000; bn/billion=1,000,000,000); non-whole-dollar amounts not values. (§A.5)

---

# Lessons ledger

Reusable lessons from rejections and failed checks. Each entry: date, revision,
symptom, root cause, and a generic rule that would have prevented it, written to
help a team building a different product. First occurrence of a root cause is
listed here; the second occurrence is promoted to "Standing rules" below. Root
causes shared across a fix and another symptom are listed once.

## Entries

- 2026-11-17 (Stage 2, revision be11ee3): global value-level deduplication of candidates drops per-source evidence.
  - Symptom: when two different pages each support the same value for a field, only
    the first page yields a candidate; the second page's url/excerpt/provider are
    dropped, so the selected field's citations omit a supporting page. Observed:
    two pages each supporting legal_name "Acme Ltd" produced 1 candidate and 1
    citation, expected 2. Reviewer probe `reviewer_logic_probe2.py` and full-build
    `reviewer_fake_router_probe.py` CASE A.
  - Root cause: `selection.candidates_from_pages` deduplicates globally by value
    alone (`key = _json_key(value); if key in seen[field]: continue`,
    selection.py:131-134), conflating "same value" with "same evidence item".
  - Generic rule: when a requirement defines an evidence item by a tuple of
    attributes (here value + source page + excerpt + provider), deduplicate on the
    full identity of that item, never on a single projected attribute such as the
    value. Group by value only for downstream selection/aggregation, after all
    distinct supporting evidence items have been retained; a "one per X" rule
    means one per X, not one per deduplicated value.

- 2026-11-17 (Stage 4, revision b51897c): "first-seen" tracking of gathered
  origins drops later re-gatherings, so corroboration history is lost.
  - Symptom: `corroborated_since` stayed null and `corroborated` false even when a
    selected value/member had two or more standing origins. Scalar case (S4-21/22):
    t1 CEO Dana Ruiz from a.test; t2 Lee Park from b.test; t3 Dana Ruiz again from
    a.test plus c.test — expected origin a.test to count as standing from t3, giving
    corroborated_since 2026-03-03T09:00:00+00:00, but it was filtered out as
    "pre-learned_at". Member case (S4-29/30): cfo Ana Silva from alpha.test (t1) and
    delta.test (t2), cto Cy Park from gamma.test+epsilon.test (t3) — expected both
    members corroborated at t3, but Ana's delta.test was missed and a single
    field-level learned_at was used for every member.
  - Root cause: `_assign_learned` (server.py:739) records only the first time for a
    candidate identity and never updates it when a later ready build gathers that
    candidate again; `_decorate_corroboration` (server.py:846, 874, 883) then filters
    origins as "pre-learned_at" and applies one field-level learned_at to all
    members. This is the same root cause class as the stage-2 be11ee3 REJECT:
    collapsing distinct evidence items (here a gathering at time t3 vs t1) onto a
    single stored representative, losing the items that the requirement keeps.
  - Generic rule: when a value's status depends on the full history of evidence
    gathered over time, record every gathering event (identity + time) and
    recompute from the accumulated set; never keep only a "first seen" timestamp
    and never reuse one aggregate timestamp across distinct sub-items (members).
    Re-gathering an already-known item IS a new standing fact. This is the second
    occurrence of the collapse/lose-evidence root cause (first: be11ee3), so the
    rule is promoted to Standing rules below.

- 2026-11-17 (Stage 4, revision b51897c): new field omitted from one render path.
  - Symptom: `investors` appeared on the dossier, evidence and /contested screens
    and in the history API JSON, but the change-history screen showed no Investors
    section (S4-51).
  - Root cause: `webui.py:1074` kept `order = list(FIELD_ORDER) + ["executives"]`
    from stage 3; `investors` was added to the other render paths but not to
    `history_page`.
  - Generic rule: when adding a new item to a fixed enumerated set (a field list),
    update every consumer of that enumeration, not only the primary ones; derive
    the render order from one shared definition or assert full coverage in a test,
    so a new member cannot be silently dropped from one screen.

## Standing rules

- Retain every distinct evidence item; never collapse items onto a single stored
  representative. When an item is defined by a tuple of attributes (value + source
  page + excerpt + provider, or identity + time), deduplicate only on the full
  identity, group by a projected attribute only downstream, and record every
  occurrence over time rather than just the first. Applies equally to candidate
  deduplication (be11ee3) and to time-based standing-origin tracking (b51897c).
  (Promoted 2026-11-17 after the second occurrence.)
