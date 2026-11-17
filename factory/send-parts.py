#!/usr/bin/env python3
"""send-parts.py: post one long handoff as numbered room messages, each under the room's
per-message limit, so a seat can paste a complete task or specification verbatim.

Usage:
  send-parts.py ROOM_ID --to @owner/handle [--to ...] --title "Unit 1 handoff" \
      [--note "text placed before the files"] --file PATH [--file PATH ...] \
      [--max 4500] [--session S] [--profile P] [--dry-run]

Every part starts with the mentions and "<title> — part k/n"; the last part says
"(last part)". Files are copied verbatim, split on line boundaries (a very long line is
split inside it), each introduced by "BEGIN <path>" and closed by "END <path>". The text is
passed to `jam send` as one argument, so quotes and backticks are never interpreted by a
shell. Exits non-zero, naming the part, if a send fails; earlier parts were delivered.
"""
import argparse, os, shutil, subprocess, sys

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("room")
    ap.add_argument("--to", action="append", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--note", default="")
    ap.add_argument("--file", action="append", default=[])
    ap.add_argument("--max", type=int, default=4500)
    ap.add_argument("--session"); ap.add_argument("--profile")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    mentions = " ".join(t if t.startswith("@") else "@" + t for t in a.to)
    body = (a.note.strip() + "\n\n") if a.note.strip() else ""
    for f in a.file:
        body += f"----- BEGIN {f} -----\n" + open(f, encoding="utf-8").read().rstrip("\n") + f"\n----- END {f} -----\n\n"
    budget = a.max - len(mentions) - len(a.title) - 70   # room for the part header
    if budget < 500:
        sys.exit("--max too small for the header")
    chunks, cur = [], ""
    for line in body.splitlines(keepends=True):
        while len(line) > budget:
            if cur: chunks.append(cur); cur = ""
            chunks.append(line[:budget]); line = line[budget:]
        if len(cur) + len(line) > budget:
            chunks.append(cur); cur = ""
        cur += line
    if cur.strip(): chunks.append(cur)
    n = len(chunks)
    jam = shutil.which("jam") or shutil.which("band") or "jam"
    base = [jam] + (["--profile", a.profile] if a.profile else []) + (["--session", a.session] if a.session else [])
    for k, c in enumerate(chunks, 1):
        head = f"{mentions} {a.title} — part {k}/{n}" + (" (last part)" if k == n else " (more parts follow; act on the last part)")
        msg = head + "\n\n" + c
        if a.dry_run:
            print(f"=== part {k}/{n}: {len(msg)} chars"); continue
        r = subprocess.run(base + ["send", a.room, msg], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"part {k}/{n} failed: {(r.stderr or r.stdout).strip()[:400]}", file=sys.stderr)
            return 1
    if not a.dry_run:
        print(f"sent {n} part(s) to {mentions}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
