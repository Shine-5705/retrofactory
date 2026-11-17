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

## Stage 4 — dossier (extended) — CLOSED

- Prerequisite retro checklist (S4-1..S4-85 + 6 ambiguities + lessons + time/spend):
  delivered 2026-11-17 ~15:50 (measured: `/tmp/opencode/s4-retro-reply.md` mtime
  and this turn; 20-part handoff plan file `/tmp/opencode/s4-retro-plan.md` mtime
  15:49). Sent to @coordinator as 5 parts via `factory/send-parts.py`. Lessons
  carried forward: stage-2 REJECT (be11ee3, candidate dedupe key) applicable.
- S4-0a baseline copy stage-3/ -> stage-4/ commit d99b58b at 2026-11-17 15:49:26
  (measured: git commit time); stage-3/ untouched.
- Handoff (coordinator -> implementer): ~15:50-15:51 UTC (measured: checklist
  above and retro log commit b8ccc70 at 15:51:05). Complete task text, checklist
  S4-1..S4-85 + A1..A6, stage-2 rejection lesson and all four specs attached
  verbatim; five ordered units.
- First implementation revision b51897cdc45e37c2b86f893d2193c89b48f74a60 at
  2026-11-17 16:52:13 (measured: git commit time).
- Review round 1 verdict: REJECT of b51897c (measured: reviewer message this turn).
  Basis: clean detached worktree, stage-1/2/3 diff vs d99b58b empty, docker build
  ok, supplied harness all stages pass, 10 independent probes (p1..p10). Failing:
  S4-21/S4-22 (scalar corroborated_since), S4-29/S4-30 (member corroborated_since),
  S4-51 (investors missing from history screen). Root causes supplied by reviewer.
- Fix revision f000d83bcb8e4627ce59b5ae7a763dde0f1bcdaa at 2026-11-17 17:55:06
  (measured: git commit time; b51897c not amended): all 5 original findings fixed;
  implementer reported harness + 10/10 probes pass.
- Review round 2 verdict: REJECT of f000d83 (measured: reviewer message this turn).
  Basis: clean detached worktree, harness stages 1/2/3/4 pass, 10/10 probes pass;
  original 5 findings confirmed fixed. NEW FAIL S4-28 regression: member
  `corroborated` computed from standing origins instead of current-candidate
  origins (server.py:937); also the reported tree was dirty (the uncommitted fix).
- Correction revision cd6208cc44ac7e2ee34cf9c4c25c698f574cc02d at 2026-11-17
  17:59:58 (measured: git commit time; parent f000d83, clean tree; only change is
  stage-4/server.py member `corroborated` reverted to current-candidate origins
  while keeping the per-member `member_since` and all-gather-times fix).
- Review round 3 verdict: ACCEPT of cd6208c (measured: coordinator close message
  this turn); reviewer reported all S4-1..S4-85 + A1..A6 PASS.
- Freeze: coordinator froze stage-4/ at cd6208c, tag `stage-4-frozen`, freeze
  commit 15f62c9 at 2026-11-17 18:07:24 (measured: git commit time and tag).
- Review rounds: 3 (rounds 1 and 2 REJECT, round 3 ACCEPT).
- Ledger: stage-2 collapse/dedupe root cause promoted to Standing rules after its
  second occurrence (b51897c); new root causes recorded as first occurrences —
  b51897c "new field omitted from one render path" (S4-51) and f000d83 "sibling
  field computed from wrong evidence basis / S4-28 regression from the prior fix".
- Open risk (reviewer, carried into ACCEPT): no live Nimble credentials; provider
  429/5xx/all-fail behaviour exercised with the reviewer mock only.
- Spend: not reported (no seat reported model or provider spend figures for stage 4).
  Carried from stages 1–3: not reported.
- Unit closed by coordinator freeze of cd6208c; closed in this log 2026-11-17
  ~18:08 UTC (measured: this turn).
