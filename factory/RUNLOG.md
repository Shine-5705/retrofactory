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

## Stage 3 — dossier (extended) — CLOSED

- Prerequisite retro checklist (209 items + coverage gaps + lessons): delivered
  2026-11-17 13:48 (measured: `/tmp/opencode/s3-retro-reply.md` mtime). Lessons
  carried forward: no new Standing rules; stage-2 REJECT lesson (candidate
  dedupe key) applicable.
- Handoff (coordinator -> implementer): 2026-11-17 (measured: handoff text
  `/tmp/opencode/s3-implementer-handoff.md` mtime 13:50). Target stage-3/, copied
  from frozen stage-2/ baseline.
- Implementation commits: baseline copy `63c7d41` at 2026-11-17 14:08:40; final
  revision `437e78bd3338b3945af96063fc0839b572cf24c6` at 2026-11-17 14:54:19
  (measured: git commit time). Implementer harness runs finished 14:33:54,
  14:51:45, 14:56:30 (measured: `checks/stage-1-real/s3-*`/`s3-1794927*/report.json`
  mtimes).
- Review handoff (coordinator -> reviewer): 2026-11-17 14:56 (measured:
  `/tmp/opencode/s3-reviewer-handoff.md` mtime 14:58). Reviewer harness runs
  finished 15:04:25 and 15:08:25 (measured: `checks/stage-1-real/s3-rev-*`/`s3-rev2-*`
  report mtimes).
- Verdict: ACCEPT of revision 437e78b, delivered in room 2026-11-17 (measured:
  coordinator close message `/tmp/opencode/s3-close.md` mtime 15:34). Reviewer
  reported harness stage 1 122/122, stage 2 12/12, stage 3 9/9; 171 independent
  probe checks; live docker restart and mid-build kill -9 probes passed.
- Review rounds: 1 (first review accepted; no REJECT recorded for this stage).
- Ledger: no stage-3 REJECT to record (none occurred).
- Unit closed by coordinator freeze of 437e78b; closed in this log 2026-11-17 15:34.
- Spend: not reported (no seat reported model or provider spend figures).

## Stage 4 — dossier (in progress)

- Prerequisite retro checklist (S4-1..S4-85 + 6 ambiguities + lessons + time/spend):
  delivered 2026-11-17 ~15:50 (measured: `/tmp/opencode/s4-retro-reply.md` mtime
  and this turn; 20-part handoff plan file `/tmp/opencode/s4-retro-plan.md` mtime
  15:49). Sent to @coordinator as 5 parts via `factory/send-parts.py`. Lessons
  carried forward: stage-2 REJECT (be11ee3, candidate dedupe key) applicable;
  Standing rules still empty (no second occurrence).
- S4-0a baseline copy stage-3/ -> stage-4/ commit d99b58b already exists;
  stage-3/ untouched.
- Implementation commit and review verdicts: not yet occurred. Review rounds:
  0 so far.
- Spend: STAGE 4 not reported. Carried from stages 1–3: not reported.
- Review verdict: REJECT of revision b51897cdc45e37c2b86f893d2193c89b48f74a60,
  delivered in room 2026-11-17 (measured: reviewer message this turn). Reviewer
  basis: clean detached worktree, stage-1/2/3 diff vs d99b58b empty, docker build
  ok, supplied harness all stages pass, 10 independent probes. Failing items:
  S4-21, S4-22 (scalar corroborated_since), S4-29, S4-30 (member-field
  corroborated_since), S4-51 (investors missing from history screen). Root causes
  supplied by reviewer; no need to ask implementer.
- Review rounds: 1 (REJECT). Ledger: added stage-4 REJECT entries; promoted the
  collapse/lose-evidence root cause to Standing rules (second occurrence, first
  be11ee3). New S4-51 root cause (new field omitted from one render path) recorded.
- Implementer fix revision f000d83bcb8e4627ce59b5ae7a763dde0f1bcdaa (b51897c not
  amended): all 5 original findings fixed; implementer reported harness + 10/10
  probes pass.
- Review verdict: REJECT of f000d83 (measured: reviewer message this turn). Basis:
  clean detached worktree, harness stages 1/2/3/4 pass, 10/10 probes pass. Original
  5 findings confirmed fixed. NEW FAIL S4-28 regression: member `corroborated`
  computed from standing origins instead of current-candidate origins (server.py:937),
  false at p3 t3 where Ana has one current origin. Also: reported tree was dirty
  (uncommitted fix of that line); handoff claimed clean.
- Review rounds: 2 (both REJECT). Ledger: added f000d83 REJECT entry; root cause
  (sibling field using wrong evidence basis) is a first occurrence, not promoted.
  Standing rules still the single collapsed-evidence rule. Coordinator clarified
  S4-28 was a regression from the b51897c fix, corrected in clean revision
  cd6208cc44ac7e2ee34cf9c4c25c698f574cc02d (parent f000d83; only change is
  stage-4/server.py member `corroborated` back to current-candidate origins),
  now under re-review.
- Open risk (reviewer): no live Nimble credentials; provider 429/5xx/all-fail
  exercised with reviewer mock only.
- Spend: STAGE 4 not reported (no seat reported figures).
- Unit remains open; close it here on the final ACCEPT and forward the frozen
  revision's figures.
