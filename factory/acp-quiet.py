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
import json, os, re, subprocess, sys, threading, time

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
MENTION_RE = re.compile(r"@\[\[[^\]]*\]\]|@[\w.-]+(/[\w.-]+)?")

# Anything that carries a decision or evidence is always released.
KEEP_RE = re.compile(r"\b(PASS|ACCEPT\w*|REJECT\w*|FAIL\w*|BLOCK\w*|error|verdict|frozen|"
                     r"final report|[0-9a-f]{7,40})\b|```", re.I)

def is_ack(text: str) -> bool:
    core = MENTION_RE.sub("", text)
    core = re.sub(r"</?[A-Za-z][^>]*>", "", core).strip()   # placeholder markup such as <void />
    if not core:
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
    last_fo = {}   # prompt request id -> time of last failover
    held = {}      # sessionId -> list of raw lines (agent_message_chunk updates)
    texts = {}     # sessionId -> accumulated text

    def emit(raw: bytes):
        with out_lock:
            sys.stdout.buffer.write(raw)
            sys.stdout.buffer.flush()

    def client_to_agent():
        for raw in sys.stdin.buffer:
            try:
                msg = json.loads(raw)
                if isinstance(msg, dict) and msg.get("method") == "session/prompt":
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
            note(event="failover_exhausted", session=sid, model=cur, reason=reason[:160]); return
        note(event="failover", session=sid, frm=cur, to=nxt, reason=reason[:160])
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
                if sid and sid in line and rid not in retrying and time.time() - last_fo.get(rid, 0) > 20:
                    last_fo[rid] = time.time()
                    threading.Thread(target=failover, args=(rid, sid, line), daemon=True).start()

    threading.Thread(target=watch_agent_log, daemon=True).start()
    a = threading.Thread(target=client_to_agent, daemon=True); a.start()
    b = threading.Thread(target=agent_to_client, daemon=True); b.start()
    rc = child.wait(); b.join(timeout=5)
    return rc

if __name__ == "__main__":
    sys.exit(main())
