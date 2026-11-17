#!/usr/bin/env python3
"""Drive `acp-quiet.py -- opencode acp` like Band does and show what would be posted."""
import json, subprocess, sys, threading, queue, os
MODEL = sys.argv[1] if len(sys.argv) > 1 else "opencode/big-pickle"
env = dict(os.environ, JAM_SESSION="drytest", ACP_QUIET_LOG_DIR="/workspace/band/ops/acp-quiet")
p = subprocess.Popen(["python3", "/workspace/band/retrofactory/factory/acp-quiet.py", "--", "opencode", "acp"],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd="/tmp/acptest", env=env)
q = queue.Queue()
threading.Thread(target=lambda: [q.put(json.loads(l)) for l in p.stdout], daemon=True).start()
nid = [0]
def call(method, params, timeout=240):
    nid[0] += 1; i = nid[0]
    p.stdin.write((json.dumps({"jsonrpc": "2.0", "id": i, "method": method, "params": params}) + "\n").encode()); p.stdin.flush()
    chunks = []
    while True:
        m = q.get(timeout=timeout)
        if m.get("method") == "session/update":
            u = m["params"]["update"]
            if u.get("sessionUpdate") == "agent_message_chunk":
                chunks.append(u.get("content", {}).get("text", ""))
        elif m.get("method") and "id" in m:   # agent->client request (permissions etc.)
            p.stdin.write((json.dumps({"jsonrpc": "2.0", "id": m["id"], "result": {"outcome": {"outcome": "selected", "optionId": "allow"}}}) + "\n").encode()); p.stdin.flush()
        elif m.get("id") == i:
            return m, "".join(chunks)
init, _ = call("initialize", {"protocolVersion": 1, "clientCapabilities": {}})
sess, _ = call("session/new", {"cwd": "/tmp/acptest", "mcpServers": []})
sid = sess["result"]["sessionId"]
models = sess["result"].get("models") or {}
try: call("session/set_model", {"sessionId": sid, "modelId": MODEL})
except Exception as e: pass
RULE = ("You are a seat in a team chat. Your final assistant text is posted to the room as a reply "
        "to the sender. If a message needs nothing from you, end your turn without any text.\n\n")
tests = [
  ("ack", RULE + "[INCOMING MESSAGE] From: @retro\nContent: Receipt notification. Nothing pending. Staying silent."),
  ("real", RULE + "[INCOMING MESSAGE] From: @coordinator\nContent: Reply with the verdict word PASS followed by the number 4."),
]
for name, text in tests:
    r, posted = call("session/prompt", {"sessionId": sid, "prompt": [{"type": "text", "text": text}]})
    print(f"{name}: stopReason={r.get('result',{}).get('stopReason')} would_post={posted!r}")
p.terminate()
