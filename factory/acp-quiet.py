#!/usr/bin/env python3
"""acp-quiet: a pass-through ACP (Agent Client Protocol) proxy for a seat's coding agent.

Band's owned OpenCode runtime posts whatever text the agent ends a turn with as a room
reply addressed to the sender, and an empty turn counts as a silent completion. Many
models cannot end a turn on empty text, so "nothing to do here" replies wake the sender,
which answers in kind: an acknowledgement loop.

This proxy sits between Band and the agent (`acp-quiet.py -- opencode acp`). It forwards
every message unchanged, except that the agent's message text for a prompt turn is held
until the turn ends. If the whole held text is a bare acknowledgement or status line
(short, and matching ACK_PATTERNS) it is dropped, so the turn ends silently; otherwise it is
released unchanged, in order, before the turn's final response. Tool calls, thoughts,
plans and all other traffic pass straight through. It never writes or edits content.

Model failover: if ACP_QUIET_MODELS lists models ("primary,fallback1,..."), the proxy watches
the agent's log for a usage-limit or upstream failure on the session of the turn in flight.
On one, it cancels that attempt, switches the session to the next model with
`session/set_model`, and re-sends the same prompt, so Band sees a single turn. The model
list rotates; a model that failed is retried after ACP_QUIET_COOLDOWN seconds.

Every decision is logged as one JSON line to $ACP_QUIET_LOG_DIR/<seat>-<pid>.jsonl.
"""
import json, os, re, shutil, subprocess, sys, threading, time

MAX_ACK_CHARS = int(os.environ.get("ACP_QUIET_MAX_CHARS", "280"))
ACK_PATTERNS = [
    r"\bsilent(ly)?\b", r"\bsilence\b", r"\bno (action|reply|response|further action)\b",
    r"\bnothing (requiring|required|needed|to do|pending|further|for me)\b", r"\breceipt\b",
    r"\b(acknowledg\w*|noted|received|got it|understood|thanks?|thank you)\b",
    r"^\W*(ok(ay)?|done|ack|yes|sure|roger)\W*$", r"\b(standing by|stand by|awaiting|waiting)\b",
    r"\bending (the |my )?turn\b", r"\bno (work|task) (for me|remains?)\b", r"\bnot addressed to me\b",
    r"^[\W_]*$", r"(收到|已静默|无操作|好的|明白)",
    r"\b(not|isn't) the (last|final) part\b", r"\bwait(ing)? for the (last|final|remaining) parts?\b",
    r"\bend(ing|s)? (the|my|this) turn\b", r"\bno tool calls?\b", r"\bsilent turn\b",
]
ACK_RE = re.compile("|".join(ACK_PATTERNS), re.I | re.M)
PART_RE = re.compile(r"^(?:@\S+\s+)+(?P<title>[^\n]*?) \u2014 part (?P<i>\d+)/(?P<n>\d+) \((more parts follow; act on the last part|last part)\)", re.M)
MENTION_RE = re.compile(r"@\[\[[^\]]*\]\]|@[\w.-]+(/[\w.-]+)?")

# Anything that carries a decision or evidence is always released.
KEEP_RE = re.compile(r"\b(PASS|ACCEPT\w*|REJECT\w*|FAIL\w*|BLOCK\w*|error|verdict|frozen|"
                     r"final report|[0-9a-f]{7,40})\b|```", re.I)

SILENT_RE = re.compile(r"\bend(ing|s)?( (the|my|this))?( turn)? silently\b|\bno tool calls?\b|\bnothing (more |further )?(is )?needed\b", re.I)

def is_ack(text: str) -> bool:
    core = MENTION_RE.sub("", text)
    core = re.sub(r"<system-reminder>.*?</system-reminder>", "", core, flags=re.S)   # harness notes the model echoed
    core = re.sub(r"</?[A-Za-z][^>]*>|<\|[^|<>]{0,40}\|>", "", core).strip()   # placeholder markup such as <void /> or <|eot|>
    if not core:
        return True
    # A short turn that says it is ending silently is never meant for the room, whatever words it quotes
    if len(core) <= MAX_ACK_CHARS and SILENT_RE.search(core):
        return True
    # The same ack sentence repeated many times (a looping model) is still an ack
    sents = {x.strip().lower() for x in re.split(r"(?<=[.!?])\s+|\n+", core) if x.strip()}
    if len(core) > MAX_ACK_CHARS and len(sents) <= 3 and ACK_RE.search(core):
        return True
    # "waiting on the verdict" is status, not a verdict: drop that phrase before the keep check
    if KEEP_RE.search(re.sub(r"\b(awaiting|waiting (on|for))\b[^.;\n]{0,40}\bverdict\b", "", core, flags=re.I)):
        return False
    return len(core) <= MAX_ACK_CHARS and bool(ACK_RE.search(core))

def main() -> int:
    # Usage: acp-quiet.py [--seat NAME] [--models a,b,c] [--log-dir DIR] -- <agent command...>
    # (arguments, because the runtime may not pass environment variables through)
    argv = sys.argv[1:]
    opts = {}
    while argv and argv[0].startswith("--") and argv[0] != "--":
        opts[argv[0][2:]] = argv[1]; argv = argv[2:]
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        argv = ["opencode", "acp"]
    if "models" in opts: os.environ["ACP_QUIET_MODELS"] = opts["models"]
    if "log-dir" in opts: os.environ["ACP_QUIET_LOG_DIR"] = opts["log-dir"]
    seat = opts.get("seat") or os.environ.get("JAM_SESSION") or os.path.basename(os.getcwd())
    logdir = os.environ.get("ACP_QUIET_LOG_DIR", "/workspace/band/ops/acp-quiet")
    os.makedirs(logdir, exist_ok=True)
    log = open(os.path.join(logdir, f"{seat}-{os.getpid()}.jsonl"), "a", buffering=1)
    trace = os.environ.get("ACP_QUIET_TRACE") == "1" or os.path.exists(os.path.join(logdir, "TRACE"))

    def note(**kw):
        kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        log.write(json.dumps(kw, ensure_ascii=False) + "\n")

    models = [m for m in os.environ.get("ACP_QUIET_MODELS", "").split(",") if m]
    cooldown = int(os.environ.get("ACP_QUIET_COOLDOWN", "900"))
    agent_log = os.environ.get("ACP_QUIET_AGENT_LOG", os.path.expanduser("~/.local/share/opencode/log/opencode.log"))
    FAIL_RE = re.compile(r"Free usage limit|rate.?limit|Upstream request failed|inference service|"
                         r"Endpoint is unavailable|overloaded|AI_RetryError|status(Code)?[=: ]*(429|5\d\d)", re.I)
    # The runtime may launch us with a minimal PATH: resolve the agent binary explicitly.
    import shutil
    exe = shutil.which(argv[0]) or shutil.which(argv[0], path=os.path.expanduser("~/.local/bin"))
    if not exe:
        note(event="agent_not_found", argv=argv, path=os.environ.get("PATH", ""))
        return 127
    argv = [exe] + argv[1:]
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(exe) + os.pathsep + env.get("PATH", "")
    note(event="start", argv=argv, cwd=os.getcwd(), models=models)
    child = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env)
    out_lock = threading.Lock()
    pending = {}   # prompt request id -> sessionId
    prompts = {}   # prompt request id -> raw request line (for re-send on failover)
    retrying = {}  # prompt request id -> True while a cancelled attempt's response is awaited
    failed_at = {} # model -> time it last failed
    current = {}   # sessionId -> model in use
    own_id = [10**9]
    last_fo = {}   # (prompt request id, failing model) -> time of last failover
    held = {}      # sessionId -> list of raw lines (agent_message_chunk updates)
    texts = {}     # sessionId -> accumulated text

    def emit(raw: bytes):
        with out_lock:
            sys.stdout.buffer.write(raw)
            sys.stdout.buffer.flush()

    parts = {}     # sessionId -> {"key": (room, sender, title, n), "got": {i: text}}

    def fetch_parts(room, sender, title, n, need):
        """Missing parts of a numbered message, read back from the room (read-only)."""
        found, cur = {}, None
        import shutil; band = shutil.which("band") or "/usr/bin/band"
        for _ in range(4):
            cmd = [band, "room", "messages", room, "--json", "--type", "text"] + (["--cursor", cur] if cur else [])
            try:
                d = json.loads(subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout)
            except Exception as e:
                note(event="parts_fetch_error", err=repr(e)[:160]); break
            for m in d.get("messages", []):
                if (m.get("sender_name") or "") != sender.split("/")[-1]: continue
                mm = PART_RE.search(m.get("content") or "")
                if not mm or int(mm.group("n")) != n or mm.group("title").strip() != title: continue
                i = int(mm.group("i"))
                if i in need and i not in found:
                    found[i] = (m.get("content") or "")
            if all(i in found for i in need) or not d.get("has_more") or not d.get("next_cursor"): break
            cur = d["next_cursor"]
        return found

    def assemble(msg, sid):
        """Hold non-last parts of a numbered message (answer them as silent turns) and give the
        agent the whole message, in order, with the last part, so it acts once on all of it."""
        pr = (msg.get("params") or {}).get("prompt") or []
        text = "\n".join(b.get("text", "") for b in pr if isinstance(b, dict))
        mm = PART_RE.search(text)
        if not mm:
            return None
        i, n, title = int(mm.group("i")), int(mm.group("n")), mm.group("title").strip()
        room = (re.search(r"^Room: (\S+)", text, re.M) or [None, ""])[1]
        sender = (re.search(r"^From: (\S+)", text, re.M) or [None, ""])[1]
        key = (room, sender, title, n)
        st = parts.get(sid)
        if not st or st["key"] != key:
            st = parts[sid] = {"key": key, "got": {}}
        body = text.split("\nContent:\n", 1)[-1]
        bm = PART_RE.search(body)
        piece = body[bm.start():] if bm else body
        st["got"][i] = piece.split("\n\n\n[ACP TURN SETTLEMENT]", 1)[0]   # Band's per-turn footer stays on the final prompt only
        if i < n and "more parts follow" in mm.group(0):
            note(event="part_held", session=sid, part=i, of=n, title=title[:80])
            return "held"
        need = [k for k in range(1, n + 1) if k not in st["got"]]
        if need and room and sender:
            got = fetch_parts(room, sender, title, n, need)
            st["got"].update(got)
            note(event="parts_fetched", session=sid, need=need, got=sorted(got))
        missing = [k for k in range(1, n + 1) if k not in st["got"]]
        whole = "\n\n".join(f"===== part {k}/{n} =====\n" + st["got"][k] for k in range(1, n + 1) if k in st["got"])
        parts.pop(sid, None)
        intro = (f"[All {n} parts of this numbered message from {sender}, assembled in order by the seat proxy"
                 + (f"; parts {missing} could not be recovered, ask the sender for exactly those" if missing else "")
                 + ". The earlier parts were held, so this is the first time you see them. Act on the whole message now.]\n\n")
        footer = ("\n\n\n[ACP TURN SETTLEMENT]" + text.split("\n\n\n[ACP TURN SETTLEMENT]", 1)[1]) if "\n\n\n[ACP TURN SETTLEMENT]" in text else ""
        msg["params"]["prompt"] = [{"type": "text", "text": text.split("\nContent:\n", 1)[0] + "\nContent:\n" + intro + whole + footer}] + \
                                  [b for b in pr if isinstance(b, dict) and b.get("type") != "text"]
        note(event="parts_assembled", session=sid, of=n, missing=missing, chars=len(whole))
        return "assembled"

    def client_to_agent():
        for raw in sys.stdin.buffer:
            try:
                msg = json.loads(raw)
                if isinstance(msg, dict) and msg.get("method") == "session/prompt":
                    sid0 = (msg.get("params") or {}).get("sessionId")
                    try:
                        r = assemble(msg, sid0)
                    except Exception as e:
                        r = None; note(event="assemble_error", err=repr(e)[:200])
                    if r == "held":
                        emit((json.dumps({"jsonrpc": "2.0", "id": msg.get("id"),
                                          "result": {"stopReason": "end_turn"}}) + "\n").encode())
                        continue
                    if r == "assembled":
                        raw = (json.dumps(msg) + "\n").encode()
                    sid = (msg.get("params") or {}).get("sessionId")
                    pending[msg.get("id")] = sid
                    prompts[msg.get("id")] = raw
                    held[sid] = []; texts[sid] = ""
                if isinstance(msg, dict) and msg.get("method") == "session/set_model":
                    pr = msg.get("params") or {}
                    current[pr.get("sessionId")] = pr.get("modelId")
                if isinstance(msg, dict) and msg.get("method") == "session/set_config_option":
                    pr = msg.get("params") or {}
                    if pr.get("configId") == "model":
                        current[pr.get("sessionId")] = pr.get("value")
                        note(event="model_set_by_client", session=pr.get("sessionId"), model=pr.get("value"))
                if trace:
                    note(dir="in", msg=str(msg)[:400])
            except Exception:
                pass
            child.stdin.write(raw); child.stdin.flush()
        child.stdin.close()

    def agent_to_client():
        for raw in child.stdout:
            try:
                handle_out(raw)
            except Exception as e:
                note(event="relay_error", err=repr(e)[:200])
                emit(raw)

    def handle_out(raw):
            try:
                msg = json.loads(raw)
            except Exception:
                emit(raw); return
            if trace:
                note(dir="out", msg=str(msg)[:400])
            if isinstance(msg, dict) and msg.get("method") == "session/update":
                p = msg.get("params") or {}
                sid = p.get("sessionId"); upd = p.get("update") or {}
                if upd.get("sessionUpdate") == "agent_message_chunk" and sid in held:
                    held[sid].append(raw)
                    c = upd.get("content") or {}
                    if c.get("type") == "text":
                        texts[sid] += c.get("text", "")
                    return
            if isinstance(msg, dict) and msg.get("id") in injected and "method" not in msg and msg.get("id") not in retrying:
                sid = pending.pop(msg["id"], None); prompts.pop(msg["id"], None); injected.discard(msg["id"])
                text = texts.pop(sid, ""); held.pop(sid, None)
                note(event="inject_done", session=sid, chars=len(text), text=text[:2000], result=str(msg.get("result") or msg.get("error"))[:200])
                req = inject_req.pop(msg["id"], {})
                if text.strip() and not is_ack(text) and req.get("room") and req.get("as"):
                    # Post the closing text as this seat, as Band does after a normal delivery.
                    try:
                        name = f".acp-quiet-reply-{seat}-{msg['id']}.txt"
                        with open(name, "w") as fh:
                            fh.write(text)
                        band = shutil.which("band") or "/usr/bin/band"
                        r = subprocess.run([band, "send", "--as", req["as"], "--body-file", name, req["room"]],
                                           capture_output=True, text=True, timeout=60)
                        os.remove(name)
                        note(event="inject_reply_posted", session=sid, chars=len(text), rc=r.returncode,
                             out=(r.stdout + r.stderr)[-300:])
                    except Exception as e:
                        note(event="inject_reply_error", err=repr(e)[:300])
                return
            if isinstance(msg, dict) and isinstance(msg.get("id"), int) and msg["id"] >= 10**9 and "method" not in msg:
                return   # responses to the proxy's own set_model/cancel requests
            if isinstance(msg, dict) and "id" in msg and msg.get("id") in retrying and "method" not in msg:
                retrying.pop(msg["id"])   # the cancelled attempt ended; the re-sent prompt follows
                return
            if isinstance(msg, dict) and "id" in msg and msg.get("id") in pending and "method" not in msg:
                sid = pending.pop(msg["id"]); prompts.pop(msg["id"], None)
                lines, text = held.pop(sid, []), texts.pop(sid, "")
                if lines and is_ack(text):
                    note(event="suppressed", session=sid, chars=len(text), text=text[:300])
                else:
                    if lines:
                        note(event="released", session=sid, chars=len(text), text=text[:120])
                    for l in lines:
                        emit(l)
            emit(raw)

    def send_agent(obj):
        child.stdin.write((json.dumps(obj) + "\n").encode()); child.stdin.flush()

    def failover(rid, sid, reason):
        now = time.time()
        cur = current.get(sid) or (models[0] if models else "")
        failed_at[cur] = now
        nxt = next((m for m in models[models.index(cur) + 1:] + models[:models.index(cur) + 1]
                    if m != cur and now - failed_at.get(m, 0) > cooldown), None) if cur in models else \
              next((m for m in models if now - failed_at.get(m, 0) > cooldown), None)
        if not nxt:
            others = [m for m in models if m != cur]
            if not others:
                note(event="failover_exhausted", session=sid, model=cur, reason=reason[:160]); return
            nxt = min(others, key=lambda m: failed_at.get(m, 0))
            note(event="failover_all_cooling", session=sid, model=cur, pick=nxt)
            time.sleep(45)   # every model is limited: back off before trying again
        note(event="failover", session=sid, frm=cur, to=nxt, reason=reason[:160])
        last_fo.pop((rid, nxt.split("/")[-1]), None)   # the model we move to may fail over again
        retrying[rid] = True
        held[sid] = []; texts[sid] = ""
        send_agent({"jsonrpc": "2.0", "method": "session/cancel", "params": {"sessionId": sid}})
        for _ in range(100):
            if rid not in retrying: break
            time.sleep(0.1)
        retrying.pop(rid, None)
        own_id[0] += 1
        send_agent({"jsonrpc": "2.0", "id": own_id[0], "method": "session/set_model",
                    "params": {"sessionId": sid, "modelId": nxt}})
        current[sid] = nxt
        time.sleep(0.5)
        raw = prompts.get(rid)
        if raw:
            pending[rid] = sid
            child.stdin.write(raw); child.stdin.flush()

    def watch_agent_log():
        if not models: return
        try:
            f = open(agent_log, "r", errors="replace"); f.seek(0, 2)
        except OSError:
            return
        while child.poll() is None:
            line = f.readline()
            if not line:
                time.sleep(0.5); continue
            if "stream error" not in line and "AI_RetryError" not in line: continue
            if not FAIL_RE.search(line): continue
            for rid, sid in list(pending.items()):
                mm = re.search(r"modelID=(\S+)", line)
                key = (rid, mm.group(1) if mm else "")   # guard per model: a fresh model failing still fails over
                if sid and sid in line and rid not in retrying and time.time() - last_fo.get(key, 0) > 20:
                    last_fo[key] = time.time()
                    threading.Thread(target=failover, args=(rid, sid, line), daemon=True).start()

    injected = set()
    inject_req = {}   # injected request id -> {room, as}

    def watch_inject():
        """Operator re-delivery: if <log-dir>/inject-<seat>.json names a room message
        ({"room": ..., "message_id": ...}) that the seat lost (for example a turn cancelled
        by an interrupt marks it processed), give the agent that whole numbered message as a
        prompt. The agent's closing text is then posted as this seat (`band send --as`), exactly as
        Band posts it after a normal delivery, unless it is a bare acknowledgement."""
        path = os.path.join(logdir, f"inject-{seat}.json")
        while child.poll() is None:
            time.sleep(2)
            if not os.path.exists(path) or not current:
                continue
            try:
                req = json.load(open(path)); os.remove(path)
                sid = list(current)[-1]
                band = shutil.which("band") or "/usr/bin/band"
                d = json.loads(subprocess.run([band, "room", "messages", req["room"], "--json", "--type", "text"],
                                              capture_output=True, text=True, timeout=60).stdout)
                m = next(x for x in d.get("messages", []) if x.get("id") == req["message_id"])
                sender = req.get("sender") or ("guptashine5002/" + m.get("sender_name", ""))
                text = (f"[INCOMING BAND MESSAGE]\nFrom: {sender} (Agent)\nRoom: {req['room']}\nMessage: {m['id']}\n\n"
                        "Re-delivered by the operator: " + req.get("why", "an earlier delivery of this message was cancelled before you saw it.") + " "
                        "Your closing text for this turn is posted to the room as your reply, as usual."
                        "\n\nContent:\n" + (m.get("content") or ""))
                own_id[0] += 1; rid = own_id[0]
                msg = {"jsonrpc": "2.0", "id": rid, "method": "session/prompt",
                       "params": {"sessionId": sid, "prompt": [{"type": "text", "text": text}]}}
                r = assemble(msg, sid)
                held[sid] = []; texts[sid] = ""
                raw = (json.dumps(msg) + "\n").encode()
                injected.add(rid); pending[rid] = sid; prompts[rid] = raw
                inject_req[rid] = {"room": req["room"], "as": req.get("as") or (sender.split("/")[0] + "/" + seat)}
                note(event="inject", session=sid, message=m["id"], assembled=r)
                child.stdin.write(raw); child.stdin.flush()
            except Exception as e:
                note(event="inject_error", err=repr(e)[:300])

    threading.Thread(target=watch_agent_log, daemon=True).start()
    threading.Thread(target=watch_inject, daemon=True).start()
    a = threading.Thread(target=client_to_agent, daemon=True); a.start()
    b = threading.Thread(target=agent_to_client, daemon=True); b.start()
    rc = child.wait(); b.join(timeout=5)
    return rc

if __name__ == "__main__":
    sys.exit(main())
