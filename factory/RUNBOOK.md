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


## 0b. Shine's box (Debian 13) — prepared 17 Nov

Installed and verified from the shell:
- Docker 29.10.0 (static) + buildx, `hello-world` OK, harness `--mode isolated` toy probe
  gives the documented 2/8 result. After a reboot run `/workspace/band/bin/start-docker.sh`.
- Band Desktop 0.4.18 (`band-desktop`, `band` CLI, `jamd`). Daemon: `band daemon run`.
- OpenCode 1.19.5 with OpenCode Zen free models (no account, $0.00 in `opencode stats`).
  `band agent create --transport opencode --dry-run` passes.
- Kickoff harness venv at `/workspace/band/ref/sf-buildathon-2026/.venv`.

Remaining sign-ins: `band init --device` (Band account), Nimble free-trial key for the live run.
Then: `factory/create_seats.sh /abs/path/result-repo`.
Free models rotate daily: re-check `curl -s https://opencode.ai/zen/v1/models` before the
submitted run and update `Model:` lines if one disappears.

## 0c. Lessons from practice-1 (17 Nov)

- A coordinator that slept/polled inside its turn deadlocked: Band delivers messages only
  between turns. All mandates now carry a "Turn discipline" section.
- The implementer started from room context before any handoff. Non-coordinator mandates
  now say: no work until a handoff addressed to you arrives.
- To change a seat's model, use `band runtime settings --as <owner>/<seat> --model <id>`
  (`band runtime template set --runtime-model` did not change the launched model). Verify
  with `band runtime template show --as <owner>/<seat> --json --reveal` → `thread.model`.
- Only new room sessions pick up instruction/model changes: start a fresh room.
- Keep later-stage specs out of the seats' reach (`/workspace/band/held-specs/`) until the
  earlier folder is frozen; the harness only needs `test/` folders.

## 0d. Lessons from practice-2 (17 Nov) — run layout

Practice-2 passed (stage 1 at 100%, 15 min, $0), but the implementer started before its
handoff and read task files, a later stage's specification and test files it found in its
working directory. The layout is now:

| Path | Who can read it | Holds |
|---|---|---|
| `/workspace/band/runs/<run>/` | seats (working directory) | only the result repository |
| `/workspace/band/checks/<run>/` | seats | harness `--out` folders |
| `/workspace/band/kickoffs/` | root only (`sudo cat`) | stage task messages to paste |
| `/workspace/band/held-specs/` | root only | later-stage specifications |
| `/workspace/band/archive/` | root only | earlier runs and transcripts |
| `/workspace/band/.nimble_key` | root only | the Nimble key |

Root-only is a speed bump, not a sandbox: the box user has passwordless sudo. The
mandates forbid reading outside the result repository.

Other practice-2 lessons:

- With OpenCode, any final text a seat ends its turn with is posted to the room. Mandates
  now say to end with no reply at all and never to post acknowledgements.
- The coordinator kept turns open with no-op commands (`true`), which delays delivery just
  like sleeping. Mandates now ban placeholder commands.
- Un-acknowledged messages from finished rooms are re-delivered when a seat restarts and
  re-open those rooms with the current working directory. Before starting a new room,
  settle them (`factory/drain-old.sh <seat> <seconds> <old room ids>` during
  `band restart`), then `band detach --host-session default-<old room id>` per seat, and
  check `band status` shows only the parked `default` session.

## 0e. Lessons from practice-3 (17 Nov) — acknowledgement loop and quota

Practice-3 passed (stage 1 8/8, $0), but 191 of 221 room messages were acknowledgement
ping-pong and the first 11 minutes were lost to a free-model usage limit.

- Root cause of the loop: Band's owned OpenCode runtime posts the text an agent ends its
  turn with as a reply to the sender (an empty turn is silent), and these models rarely end
  on empty text. Band offers no per-agent switch for this in 0.4.18 (checked `band --help`,
  `band runtime template/settings/defaults`, experiments); the OpenCode transport has no
  disposition tools.
- Fix: seats launch OpenCode through `factory/acp-quiet.py`, a pass-through ACP proxy.
  It holds the agent's message text until the turn ends and drops it only when the whole
  text is a bare acknowledgement/status line (short, matches the patterns, and carries no
  verdict, revision hash or code). Everything else passes unchanged. Decisions are logged
  to `ops/acp-quiet/<seat>-<pid>.jsonl`. It never writes content, so the work in the room
  is still the agents' own; FACTORY.md discloses it.
- Quota: OpenCode free models hit "Free usage limit reached" per model after sustained use
  and recover within roughly an hour; some return upstream errors at times. acp-quiet also
  fails over: on such an error for the turn in flight it cancels, switches the session to
  the seat's next model and re-sends the same prompt. Each seat has a distinct primary and
  two fallbacks (create_seats.sh, mandate Model: lines).
- Polling: the coordinator checked `git log` 33 times inside one turn. Mandates now ban
  repeated checks of the repository, check folders or room; the handoff message is the wake.

## 0f. Lessons from practice-4 (17 Nov) — proxy launch and split handoffs

Practice-4 passed (stage 1 8/8, $0) with 25 room messages in total (practice-3: 269).

- Launch: Band starts the seat command with a minimal PATH and JSON-RPC ids that are UUID
  strings. acp-quiet now resolves the agent binary itself (falling back to `~/.local/bin`)
  and treats ids as opaque, and a relay error can never swallow a line. If a seat shows
  `Failed` with "ACP protocol handshake did not become ready", touch
  `ops/acp-quiet/TRACE` (traces new spawns), `band restart` the seat and read its log.
- Real failover seen: implementer deepseek "Free usage limit" → big-pickle in under a
  second, one turn as far as Band could tell.
- Seats acted on part 1 of a split handoff and the coordinator re-sent parts. Mandates now
  say a split handoff is one handoff (act on the last part) and to resend only on a
  reported send failure.
- Box reboot recovery: a reboot can drop system packages (band/jamd, docker, dnsmasq,
  /etc configs) and reset ownership under /workspace/band. Reinstall Band from
  downloads.band.ai, docker static + buildx, iptables-legacy, dnsmasq config, then
  `bin/start-docker.sh`, and re-lock `kickoffs/ held-specs/ archive/ .nimble_key` to root.

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
3. Make the stage spec readable and later ones unreadable (`held-specs/`), generate the
   dispatch (it names the spec file and must stay under about 4,800 characters) and paste
   it as the **only** message:
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
