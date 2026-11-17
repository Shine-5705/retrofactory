import json, subprocess, threading, queue, os, time
LOG="/tmp/acptest/fake-agent.log"; open(LOG,"w").close()
env=dict(os.environ, JAM_SESSION="fotest", ACP_QUIET_AGENT_LOG=LOG)
p=subprocess.Popen(["python3","/workspace/band/retrofactory/factory/acp-quiet.py","--seat","fotest2","--models","opencode/deepseek-v4.1-flash-free,opencode/big-pickle","--","opencode","acp"],stdin=subprocess.PIPE,stdout=subprocess.PIPE,cwd="/tmp/acptest",env=env)
q=queue.Queue(); threading.Thread(target=lambda:[q.put(json.loads(l)) for l in p.stdout],daemon=True).start()
def send(o): p.stdin.write((json.dumps(o)+"\n").encode()); p.stdin.flush()
def wait(i,timeout=200):
    chunks=[]; tools=0
    while True:
        m=q.get(timeout=timeout)
        if m.get("method")=="session/update":
            u=m["params"]["update"]
            if u.get("sessionUpdate")=="agent_message_chunk": chunks.append(u["content"].get("text",""))
            if u.get("sessionUpdate")=="tool_call": tools+=1
        elif m.get("method") and "id" in m: send({"jsonrpc":"2.0","id":m["id"],"result":{"outcome":{"outcome":"selected","optionId":"once"}}})
        elif m.get("id")==i: return m,"".join(chunks),tools
send({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1,"clientCapabilities":{}}}); wait(1)
send({"jsonrpc":"2.0","id":2,"method":"session/new","params":{"cwd":"/tmp/acptest","mcpServers":[]}}); sid=wait(2)[0]["result"]["sessionId"]
send({"jsonrpc":"2.0","id":3,"method":"session/set_model","params":{"sessionId":sid,"modelId":"opencode/deepseek-v4.1-flash-free"}}); wait(3)
send({"jsonrpc":"2.0","id":4,"method":"session/prompt","params":{"sessionId":sid,"prompt":[{"type":"text","text":"Use the bash tool to run exactly: sleep 12 && echo slept . Then reply with the word FINISHED and nothing else."}]}})
def inject():
    time.sleep(4)
    open(LOG,"a").write(f'timestamp=x level=ERROR message="stream error" modelID=deepseek-v4.1-flash-free session.id={sid} error.error="AI_APICallError: Free usage limit reached."\n')
threading.Thread(target=inject).start()
r,text,tools=wait(4)
print("final:",r.get("result"),"text:",repr(text),"tool_calls:",tools)
p.terminate()
