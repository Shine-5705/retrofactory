# Submitted run timeline — stages 1–4

All times UTC on 2026-11-17 (IST = UTC+5:30). Sources: `room.json` message timestamps
(R), Git commit times (G), `factory/RUNLOG.md` written by the retro seat (L), and the
operator's monitor notes / proxy logs `ops/acp-quiet/*.jsonl` (O). One room
(`02b38c62…`), one result repository, four seats.

## Stage 1 — dispatch 10:57:04 (R) → final report 11:48:16 (R) · 51 min 12 s

| Time | Event | Src |
|---|---|---|
| 10:57:04 | Human dispatch to @coordinator (2,721 chars; names `stage-1.md`) | R |
| 10:58:02 | Proxy failover, retro: hy4-flash-free → nemotron-3.5-lightning-free (free limit) | O |
| 10:59:34 | Retro checklist delivered (209 items) | L |
| 11:00:31 | Coordinator → implementer handoff (spec + checklist, numbered parts) | L |
| 11:18:27 / 11:19:57 / 11:25:11 | Implementer harness runs: fail / pass / pass | L |
| 11:25:24 | Implementation commit `3dfbf20` (implementer) | G |
| 11:25:57 | Coordinator → reviewer handoff | L |
| 11:28:27 | Reviewer's own harness run finished (122/122) | L |
| 11:34:58 | Reviewer ACCEPT of `3dfbf20` posted (verdict file 11:34:50) | R, L |
| 11:34:59 | Proxy failover, coordinator: glm-5.3-flash-free → longcat-2.5-free | O |
| 11:35:53 | Coordinator freezes stage 1 at `3dfbf20` | R |
| 11:46:32 / 11:46:57 | Retro commits `8f1a733`, `4d7ad17` (unit closed, checklist recorded) | G |
| 11:48:16 | Coordinator final report to the human (frozen `3dfbf20`) | R |

## Stage 2 — dispatch 12:03:38 (R) → final report 13:26:23 (R) · 1 h 22 min 45 s

| Time | Event | Src |
|---|---|---|
| 12:03:38 | Human dispatch (2,935 chars; names `stage-2.md` + earlier `stage-1.md`) | R |
| 12:03:39 | Proxy failover, coordinator: glm → longcat | O |
| 12:10:20 | Proxy failover, coordinator: longcat → hy4 | O |
| 12:15:53 | Baseline commit `c8f6794` (copy of frozen stage-1) | G |
| 12:28:11 / 12:35:41 / 12:44:45 | Implementer commits `b093b62`, `1096230`, `be11ee3` | G |
| 12:48:11 | Implementer report: `be11ee3`, own harness stage 1 122/122, stage 2 12/12 | R |
| 12:50:31 | Proxy failover, implementer: deepseek → big-pickle | O |
| 12:51:52 | Reviewer asks coordinator for authoritative checklist numbering | R |
| 12:58:52 | Coordinator resends checklist with authoritative numbering (21 parts) | R |
| 13:06:59 | **Reviewer REJECT of `be11ee3`**: checklist item 25 — candidates deduplicated by value alone instead of one per supporting page (`selection.py`) | R |
| 13:07:35 | Retro records the REJECT lesson, commit `57b9abf` | G |
| 13:21:04 | Fix commit `2cd5de3` (dedupe key `(url, value)`) | G |
| 13:24:26 | Reviewer re-run: stage 1 122/122, stage 2 12/12 | L |
| 13:25:57 | Reviewer ACCEPT of `2cd5de3` | R |
| 13:26:15 | Coordinator freezes stage 2 at `2cd5de3` | R |
| 13:26:23 | Coordinator final report to the human | R |
| 13:35:35 | Retro closes the unit, commit `8b7ca7f` | G |

## Stage 3 — dispatch 13:46:03 (R) → final report 15:35:01 (R) · 1 h 48 min 58 s

| Time | Event | Src |
|---|---|---|
| 13:46:03 | Human dispatch (3,009 chars; names `stage-3.md` + `stage-1.md`, `stage-2.md`) | R |
| 13:47:15–17 | Coordinator → retro, 17 parts | R |
| 13:48:44–45 | Retro checklist (S3-1…), 4 parts | R |
| 13:49:54 / 13:53:05 | Proxy failovers, coordinator: glm → longcat → hy4 | O |
| 13:51:07–15 | Coordinator → implementer handoff, 26 parts | R |
| 13:51:09–13:53:04 | Implementer: deepseek, glm, longcat all hit free limits; no model left | O |
| 14:08:40 | Baseline commit `63c7d41` (copy of frozen stage-2) | G |
| 14:33:54 | Implementer harness on working tree: claims stage 3 | O |
| 14:54:19 | Implementation commit `437e78b` | G |
| 14:57:05 | Implementer report to reviewer (harness 1/2/3 pass) | R |
| 14:57–15:01 | Reviewer: big-pickle, deepseek, glm all hit free limits | O |
| 14:59:08 | Coordinator → reviewer verification handoff, 27 parts | R |
| 15:04:25 / 15:08:25 | Reviewer harness runs finished | L |
| 15:34:10 | Reviewer ACCEPT of `437e78b` (harness 122/122, 12/12, 9/9; 171 own probe checks; docker kill/start and kill -9 mid-build) | R |
| 15:34:50 | Coordinator → retro close request | R |
| 15:35:01 | Coordinator final report to the human (frozen `437e78b`, no REJECT) | R |
| 15:35:23 | Retro closes the unit, commit `8671b92` | G |

## Stage 4 — dispatch 15:49:07 (R) → final report 18:07:42 (R) · 2 h 18 min 35 s

| Time | Event | Src |
|---|---|---|
| 15:49:07 | Human dispatch (3,083 chars; names `stage-4.md` + stages 1–3 specs) | R |
| 15:49:26 | Baseline commit `d99b58b` (made by the coordinator seat) | G |
| 15:50:50 | Retro checklist (S4-1..S4-85 + A1..A6), lessons, log; commit `b8ccc70` 15:51:05 | R, G |
| 15:52:19 | Coordinator → implementer handoff, 24 parts (about 104K chars) | R |
| 15:57–16:39 | Implementer: models refused the handoff size; interrupt lost the message; operator re-delivery 15:59:50; context limit and fresh-session re-delivery 16:39:01 (FACTORY §8) | O |
| 16:52:13 | Implementer commit `b51897c` (its own harness: stages 1–4 pass) | G |
| 16:57:31 | Operator relays the implementer's unposted handoff text word for word as the implementer (FACTORY §8) | R, O |
| 16:57:55 | Coordinator → reviewer verification handoff, 24 parts | R |
| 16:58–17:13 | Reviewer: all models at free-usage limit; restarts 17:02:55 and 17:13:06; review starts 17:13:45 | O |
| 17:44:44 | **REJECT `b51897c`** (S4-21/22, S4-29/30, S4-51), with reproduction probes | R |
| 17:45:11 | Coordinator forwards REJECT to implementer (2 parts); retro lesson `c1e7b51` 17:45:15 | R, G |
| 17:55:06 | Implementer fix `f000d83` | G |
| 17:56:23 | Reviewer clarifies S4-28 to the implementer | R |
| 17:59:58 | Implementer `cd6208c` (S4-28 correction) | G |
| 18:01:01 | Coordinator → reviewer corrected re-verification handoff for `cd6208c`, 24 parts | R |
| 18:02:19 | **REJECT `f000d83`** (S4-28 regression; already fixed in `cd6208c`); retro `5c67a43`, `cae8481` | R, G |
| 18:07:06 | **ACCEPT `cd6208c`** (harness stages 1–4 + ten reviewer probes) | R |
| 18:07:24 | Freeze commit `15f62c9`, tag `stage-4-frozen` | G |
| 18:07:42 | Coordinator final report | R |
| 18:08:06 | Retro closes the stage in `factory/RUNLOG.md` (`473bbeb`) | G |
| 18:12:47 | Operator live build of frozen `stage-4/` for runway.com finishes; `dossier-runway.com.json` committed `bf36f4f` 18:17:07 | O, G |
| 18:20:09 | `room.json` exported from the Band console (full session) | O |
