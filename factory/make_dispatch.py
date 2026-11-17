#!/usr/bin/env python3
"""Build the exact text to paste into the Band room for one stage dispatch.

Usage:
  python3 factory/make_dispatch.py --stage 1 --repo /abs/path/result \
      --kickoff /abs/path/sf-buildathon-2026 --checks /abs/path/checks > /tmp/dispatch-1.txt

The output is written to stdout so it never lands in the result repository.
By default it names the stage's spec file (the room caps a message at about 5,000
characters); --paste inlines the spec instead. Nothing from later stages is included.
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
    ap.add_argument("--track", default="dossier", choices=["dossier", "toy"])
    ap.add_argument("--paste", action="store_true",
                    help="paste the spec into the message (only for rooms without a message size limit); "
                         "default names the spec file, as the participant guide's lead-seat example does")
    a = ap.parse_args()
    spec_path = pathlib.Path(a.kickoff, "challenges", a.track, "spec", f"stage-{a.stage}.md")
    spec = spec_path.read_text() if a.paste else ""
    prev = [spec_path.with_name(f"stage-{k}.md") for k in range(1, a.stage)]
    earlier = ("It extends the earlier stage specification(s) below, which still apply where it\n"
               "refers to them and are part of this requirement:\n" + "\n".join(map(str, prev)) + "\n") if prev else ""
    copy_line = ("Build in stage-1/. It may already hold starter files; use or replace them." if a.stage == 1 else
                 f"First copy the frozen stage-{a.stage - 1}/ folder to stage-{a.stage}/ and extend "
                 f"the copy. stage-{a.stage - 1}/ stays unchanged.")
    text = (HERE / ("dispatch-template.md" if a.paste else "dispatch-template-file.md")).read_text()
    for k, v in {"{N}": str(a.stage), "{REPO}": a.repo, "{KICKOFF}": a.kickoff,
                 "{CHECKS}": a.checks, "{TRACK}": a.track, "{COPY_LINE}": copy_line, "{SPEC}": spec,
                 "{SPEC_PATH}": str(spec_path), "{EARLIER}": earlier}.items():
        text = text.replace(k, v)
    if not a.paste and len(text) > 4800:
        raise SystemExit(f"dispatch is {len(text)} characters; the room limit is about 4,800")
    print(text, end="")

if __name__ == "__main__":
    main()
