@coordinator — Stage {N} task. This message is the only human input for this stage.

Track: {TRACK}
Result repository (absolute path): {REPO}
Target folder: stage-{N}/
{COPY_LINE}

Specification for stage {N} (read it in full now; it is the complete requirement):
{SPEC_PATH}

Build stage-{N}/ strictly from that specification. Do not open any other stage's
specification, and do not open, list or search anything under the kickoff checkout's
test folders. Stages after {N} are not part of this task.

Deliver one self-contained service in stage-{N}/ with its own Dockerfile, RUN.md and
complete source. The supplied checks are only a partial sample of the judging suite;
behaviour they do not exercise still counts. Run them only through this command, with a
fresh --out directory each time (the harness refuses an existing one), one check at a
time:

    cd {KICKOFF} && . .venv/bin/activate && \
    python -m harness run --track {TRACK} --repo {REPO} --stage {N} --out {CHECKS}/s{N}-$(date +%s)

Handoffs: every delegated handoff carries the complete task text and the specification
pasted verbatim. Send long ones with the part sender from the result repository,
factory/send-parts.py (see your mandate), attaching the specification file with --file
and naming its path in the note. A path alone, a message id or "read the room" is not a
handoff.

Constraints:
- Commit only inside {REPO}, each seat as itself. Never amend, rebase or squash
  reported commits.
- No credentials in the repository or its history. Providers are reached only through
  the base URLs and keys the deployment's environment gives the service.
- Never read earlier runs, task files or other stages' material on disk.
- Resolve every question within the band; never ask the human anything.
- Turn rules: never wait, sleep or poll inside a turn; send, then end the turn. A message
  that needs nothing from you gets no reply. No acknowledgements, status notes or thanks.
- Save wall-clock time: review while checks run, and do not repeat work another seat has
  already verified.

Finish: when the reviewer sends ACCEPT for a revision, freeze stage-{N}/ at that revision
and post one final report to me: the frozen revision, what the reviewer verified, open
risks, rejections and how they changed the work, and the time and spend log ("not
reported" where none exists). After the final report, send nothing further for this
stage.
