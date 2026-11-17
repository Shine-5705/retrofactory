@coordinator — Stage {N} task. This message is the only human input for this stage.

Result repository (absolute path): {REPO}
Target folder: stage-{N}/
{COPY_LINE}

Deliver one self-contained service in stage-{N}/ with its own Dockerfile, RUN.md and
complete source, built strictly from the specification below (not from any visible test
file). Shipped checks live in the kickoff package at {KICKOFF}/challenges/dossier/test/
and are only a partial sample of the judging suite. The reviewer runs them with:

    cd {KICKOFF} && . .venv/bin/activate && \
    python -m harness run --track dossier --repo {REPO} --stage {N} --out {CHECKS}/s{N}

Constraints that apply to every stage:
- Commit only inside {REPO}. Never amend, rebase or squash reported commits.
- Never read or forward any other stage's specification.
- No credentials in the repository or its history.
- When the reviewer accepts, freeze stage-{N}/ and post the final report with the frozen
  revision, verification results, rejections and the time and spend log.

The complete specification for stage {N} follows, verbatim.

----- BEGIN SPECIFICATION stage-{N}.md -----
{SPEC}
----- END SPECIFICATION stage-{N}.md -----
