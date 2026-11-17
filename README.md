# RetroFactory

**Team:** Shine Gupta (solo human) · **Track:** Dossier · **Event:** BAND Dark Factory Buildathon (San Francisco & Remote), HackerSquad × BAND, November 2026

RetroFactory is a four-seat software factory for Band Desktop. Its distinguishing seat,
**retro**, turns every reviewer rejection into a reusable lesson and carries those lessons
into the next handoff, so the band stops repeating the same mistake inside a run. That is
the idea behind Adaply, the company I am building: coding agents that learn from repeated
corrections.

> **Status (honest):** the factory design, mandates and dispatch tooling are written. The
> submitted run has **not** happened yet. There is no `stage-1/`, `room.json` or
> `dossier-runway.com.json` in this repository until the band produces them. No results are
> claimed here until then.

## Read this repository

| Path | What it is | Written by |
|---|---|---|
| `FACTORY.md` | How to stand the factory up, why it is shaped this way, cost and time, failure handling | human |
| `mandates/` | One generic mandate per seat: coordinator, implementer, reviewer, retro | human |
| `factory/dispatch-template.md`, `factory/make_dispatch.py` | Builds the single per-stage dispatch message (spec pasted verbatim) | human |
| `factory/RUNBOOK.md` | Step-by-step operator checklist for the submitted run, export and checks | human |
| `factory/LESSONS.md`, `factory/RUNLOG.md` | Lessons ledger and time/spend log | retro seat, during the run |
| `stage-N/` | Dossier service for stage N | band seats only |
| `room.json` | Unchanged Band "Download full session" export of the submitted room | Band |
| `dossier-runway.com.json` | Verbatim live response from the highest completed stage | the service |

## License

MIT. See `LICENSE`.
