#!/usr/bin/env python3
"""Build the exact text to paste into the Band room for one stage dispatch.

Usage:
  python3 factory/make_dispatch.py --stage 1 --repo /abs/path/result \
      --kickoff /abs/path/sf-buildathon-2026 --checks /abs/path/checks > /tmp/dispatch-1.txt

The output is written to stdout so it never lands in the result repository.
It pastes the stage spec verbatim; nothing from later stages is included.
"""
import argparse
import pathlib

HERE = pathlib.Path(__file__).resolve().parent

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=int, required=True, choices=[1, 2, 3, 4])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--kickoff", required=True)
    ap.add_argument("--checks", required=True)
    a = ap.parse_args()
    spec = pathlib.Path(a.kickoff, "challenges", "dossier", "spec", f"stage-{a.stage}.md").read_text()
    copy_line = ("Start from scratch in stage-1/." if a.stage == 1 else
                 f"First copy the frozen stage-{a.stage - 1}/ folder to stage-{a.stage}/ and extend "
                 f"the copy. stage-{a.stage - 1}/ stays unchanged.")
    text = (HERE / "dispatch-template.md").read_text()
    for k, v in {"{N}": str(a.stage), "{REPO}": a.repo, "{KICKOFF}": a.kickoff,
                 "{CHECKS}": a.checks, "{COPY_LINE}": copy_line, "{SPEC}": spec}.items():
        text = text.replace(k, v)
    print(text)

if __name__ == "__main__":
    main()
