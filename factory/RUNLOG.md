# Run log

Maintained by the `retro` seat during runs: per unit, handoff and verdict times, review
rounds and reported spend. Empty until the factory runs.

Times are UTC. Where a figure was not stated in a room message, it is marked
"measured" with its source file mtime.

## Stage 1 — dossier (full stage) — CLOSED

- Handoff (coordinator -> implementer): 2026-11-17 11:00:31 (measured: dispatch
  text `/tmp/opencode/s1/handoff.md`). Prerequisite retro checklist delivered
  2026-11-17 10:59:34 (measured: `factory/LESSONS.md` mtime, content = 209-item
  stage-1 checklist referenced by the handoff).
- Implementation commit: `3dfbf20ff29ac44f4478e369955f38a1e3f4e501` at
  2026-11-17 11:25:24 (measured: git commit time). Implementer harness runs:
  11:18:27 fail, 11:19:57 pass, 11:25:11 pass (measured: check `report.json`
  finish times; first run on pre-commit working tree).
- Review handoff (coordinator -> reviewer): 2026-11-17 11:25:57 (measured:
  `/tmp/opencode/s1/review-handoff.md`). Reviewer harness run finished
  11:28:27 (measured: `checks/stage-1-real/reviewer-1794914841/report.json`).
- Verdict: ACCEPT of revision 3dfbf20 at 2026-11-17 11:34:50 (measured:
  `/tmp/opencode/reviewer-verdict.txt` mtime); stage-1 checks 122/122 pass.
  Item 120 (live-provider patience vs `sdk.nimbleway.com`) not verifiable in
  this environment (no live Nimble key); recorded as not-verifiable, not a
  failure.
- Review rounds: 1 (first review accepted; no REJECT recorded for this stage).
- Unit closed by coordinator freeze of 3dfbf20; closed in this log
  2026-11-17 11:44.
- Spend: not reported (no seat reported model or provider spend figures).

## Stage 2 — dossier — CLOSED

- Prerequisite retro checklist (123 items + coverage gaps + lessons): delivered
  2026-11-17 (measured: this turn; 6 parts via `factory/send-parts.py`). Lessons
  note: stage 1 had no REJECT, so no rejection-derived lessons existed at start.
- Handoff (coordinator -> implementer): coordinator sent 19-part handoff with both
  specs verbatim + checklist + coverage/lessons; time not reported in room.
- Implementer revision under review: be11ee3a2ea64e2ffda7b4b359a8b252ed8442dd
  (short be11ee3).
- Review verdict: REJECT of be11ee3, delivered in room 2026-11-17 (measured: this
  turn). Reviewer harness: stage 1 pass 122/122, stage 2 pass 12/12, stage 3 probe
  fail (out of scope); report
  `/workspace/band/checks/stage-1-real/s2-reviewer-1794919777/report.json`.
- Review rounds so far: 1 (REJECT). One evidence-backed deviation: checklist item
  25 — candidates deduplicated by value alone instead of one per supporting page.
  Root cause supplied by reviewer (selection.py:131-134); no need to ask implementer.
- Ledger: REJECT entry added to `factory/LESSONS.md` at 2026-11-17; not promoted to
  Standing rules (first occurrence of this root cause).
- Fix commit: `2cd5de39effbb8b584147cfb75d8c41e129106e8` at 2026-11-17 13:21:04
  (measured: git commit time); one-line product change in `stage-2/selection.py`
  dedupe key `(url, _json_key(value))`. Intervening commits were retro ledger/RUNLOG
  only.
- Re-review harness: fresh run finished 2026-11-17 13:24:26 (measured: check report
  `checks/stage-1-real/s2-reviewer-2cd5de3-1794921750/report.json`): stage 1 pass
  122/122, stage 2 pass 12/12, stage 3 fail (out of scope), fabrication 0.
- Verdict: ACCEPT of revision 2cd5de3, delivered in room 2026-11-17 (measured:
  `/tmp/opencode/reviewer_accept_stage2_2cd5de3.txt` mtime 13:25:45). Former item 25
  failure now passes; reviewer caveats (live-provider/vendor behaviour without
  credentials, provider-side 429 rules beyond client retry, subjective UX) are
  caveats, not failures.
- Review rounds: 2 (round 1 REJECT at be11ee3; round 2 ACCEPT at 2cd5de3).
- Unit closed by coordinator freeze of 2cd5de3; closed in this log 2026-11-17 13:29.
- Spend: not reported (no seat reported model or provider spend figures).
