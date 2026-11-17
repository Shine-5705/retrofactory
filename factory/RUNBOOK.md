# Operator runbook — RetroFactory submitted run

Authoritative source: the kickoff package `docs/participant-guide.md`
(https://github.com/band-ai/sf-buildathon-2026). This runbook is only a checklist.
Deadline: **20 Nov 2026, 5:00 PM PST = 21 Nov 2026, 06:30 IST** (HackerSquad: Nov 21 01:00 UTC).

## 0. What you need (all outside this repo)

- [ ] A Band account and Band Desktop (macOS / Windows / Linux x86-64): https://docs.band.ai/band-desktop/install
- [ ] One coding-agent harness signed in to its own model account (Band Desktop provides
      no model access): Claude Code, Codex, GitHub Copilot, OpenCode, Antigravity, or an ACP
      agent such as Gemini CLI or Cursor.
- [ ] Docker daemon running, Python 3.12+, Git.
- [ ] A Nimble API key (free trial: 5,000 pages, no card, per nimbleway.com/pricing) for the
      one live `runway.com` run only. Never paste it into the room or the repo.

## 1. Kickoff package

```sh
git clone https://github.com/band-ai/sf-buildathon-2026 ~/band/kickoff
cd ~/band/kickoff && python3.12 -m venv .venv && . .venv/bin/activate
python -m pip install -r harness/requirements.txt && python -m playwright install chromium
python -m harness --help
```

Spec hygiene: seats can read the filesystem, and no seat may see a later stage's spec
before the earlier folder is frozen. Move `challenges/dossier/spec/stage-2.md` … `stage-4.md`
out of the seats' reach until their turn.

## 2. Rehearse on the toy (development run — not submitted)

Use a scratch repo, the four mandates, and `challenges/toy`. Confirm: seats reply to
`@handle` messages, the reviewer runs checks itself, commits carry seat identities,
`python -m harness check <toy-repo> --track toy` passes after exporting the room.

## 3. Submitted run

1. Fill `Harness:`, `Model:`, `Effort:` in all four `mandates/*.md` with the real values and
   commit (human commit, before the room starts).
2. Fresh room. Add `coordinator`, `implementer`, `reviewer`, `retro`.
3. Generate the dispatch and paste it as the **only** message:
   ```sh
   python3 factory/make_dispatch.py --stage 1 --repo "$PWD" \
     --kickoff ~/band/kickoff --checks ~/band/checks > /tmp/dispatch-1.txt
   ```
4. Do not type anything in the room until the coordinator's final report. No "continue",
   no hints, no reruns.
5. If stage 1 is frozen and time remains, dispatch stage 2 the same way (`--stage 2`).

## 4. After the run

```sh
cd ~/band/kickoff && . .venv/bin/activate
python -m harness run --track dossier --repo <repo> --all --out ~/band/checks/all
```

- Export the room: Band Desktop room ⋮ → Open in Band → console room ⋮ → Download →
  **Download full session** → save unchanged as `room.json` at repo root. Read it for
  secrets; if one appears, rotate it and replace only the value with `[REDACTED]`.
- Live artifact: follow participant guide "dossier-runway.com.json" steps 1–5 exactly with
  your Nimble key; commit the verbatim response.
- Fill FACTORY.md sections marked **[from the run]** with measured numbers only.
- Push, fresh-clone, then:
  ```sh
  python -m harness check /abs/fresh-clone --track dossier
  python -m harness run --track dossier --repo /abs/fresh-clone --all --mode isolated
  ```

## 5. Submit (HackerSquad)

https://hackersquad.io/builders/dashboard/events/cmvjphjn60001mu23sgymnfzn/builder —
name, description, repo link, technologies, roster, judging-partner consent (your call),
save, record and select the demo video, deliver the presentation, **Submit for judging**,
check it shows as submitted, keep the receipt.

Video must show the Band room or console, a seat-to-seat handoff and the produced result.
