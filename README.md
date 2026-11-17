# RetroFactory

**Team:** Shine Gupta (solo human) · **Track:** Dossier · **Event:** BAND Dark Factory Buildathon (San Francisco & Remote), HackerSquad × BAND, November 2026

RetroFactory is a four-seat software factory for Band Desktop. Its distinguishing seat,
**retro**, turns every reviewer rejection into a reusable lesson and carries those lessons
into the next handoff, so the band stops repeating the same mistake inside a run. That is
the idea behind Adaply, the company I am building: coding agents that learn from repeated
corrections.

> **Status:** the submitted run reached stage 4, each stage passing the event's shipped
> checks in its own folder (`stage-1/` to `stage-4/`).
> One room, one result repository, four seats, one human dispatch per stage. Total model
> spend $0.00 (OpenCode free-tier models). Every operator action outside the room is listed
> with timestamps in `FACTORY.md` §8; none carried task content. Where the models actually run
> differ from the mandates' `Model:` lines is in `FACTORY.md` §10. The live runway.com dossier
> (`dossier-runway.com.json`) came back with only `funding_total` known.

| Stage | Wall time (dispatch → final report) | Review rounds | Result on shipped checks |
|---|---|---|---|
| 1 | 51 min 12 s | 1 | stage-1/ claims stage 1 |
| 2 | 1 h 22 min 45 s | 2 (1 REJECT caught by the reviewer's own probe) | stage-2/ claims stage 2 |
| 3 | 1 h 48 min 58 s | 1 | stage-3/ claims stage 3 |
| 4 | 2 h 18 min 35 s | 3 (2 REJECTs caught by the reviewer's own probes) | stage-4/ claims stage 4 |

## Read this repository

| Path | What it is | Written by |
|---|---|---|
| `FACTORY.md` | How to stand the factory up, why it is shaped this way, cost and time, failure handling | human |
| `mandates/` | One generic mandate per seat: coordinator, implementer, reviewer, retro | human |
| `factory/send-parts.py` | Posts a long handoff (task + verbatim spec) as numbered room messages under the size limit | seats |
| `factory/dispatch-template.md`, `factory/make_dispatch.py` | Builds the single per-stage dispatch message (names the stage spec file; fits the room limit) | human |
| `factory/RUNBOOK.md` | Step-by-step operator checklist for the submitted run, export and checks | human |
| `factory/LESSONS.md`, `factory/RUNLOG.md` | Lessons ledger and time/spend log | retro seat, during the run |
| `factory/TIMELINE.md` | Stage-by-stage timeline of the submitted run from room, Git and RUNLOG | human, from measured sources |
| `factory/acp-quiet.py` | Seat proxy: drops bare acknowledgements, model failover, assembles numbered handoff parts | human |
| `stage-N/` | Dossier service for stage N | band seats only |
| `room.json` | Unchanged Band "Download full session" export of the submitted room | Band |
| `dossier-runway.com.json` | Verbatim live response from the highest completed stage | the service |

## License

MIT. See `LICENSE`.
