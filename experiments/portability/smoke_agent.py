"""
One live step against one framework's agent, over ECP's real JSON-RPC.

Shows what the agent answered, what its adapter reported, and what the tools really
did, so a framework that does not start, or whose adapter drops tool calls, is found
before a long run rather than during it.

Usage: smoke_agent.py <framework> [prompt]
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_manifests  # noqa: E402

framework = sys.argv[1]
prompt = sys.argv[2] if len(sys.argv) > 2 else "Hi, order A100 arrived damaged. I bought it 5 days ago - can I get a refund?"

python = make_manifests.interpreter(framework)
agent = HERE / "agents" / f"agent_{framework}.py"
log = Path(tempfile.mkdtemp()) / "tools.jsonl"
env = dict(os.environ, ECP_TOOL_LOG=str(log))

requests = [
    {"jsonrpc": "2.0", "id": 1, "method": "agent/initialize", "params": {"protocol_version": "1.0", "config": {}}},
    {"jsonrpc": "2.0", "id": 2, "method": "agent/step", "params": {"input": prompt}},
]
proc = subprocess.run(
    [str(python), str(agent)],
    input="\n".join(json.dumps(r) for r in requests) + "\n",
    capture_output=True,
    text=True,
    env=env,
    timeout=240,
    cwd=make_manifests.REPO,
)

init = step = None
for line in proc.stdout.splitlines():
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        continue
    if msg.get("id") == 1:
        init = msg
    if msg.get("id") == 2:
        step = msg

actual = []
if log.exists():
    actual = [json.loads(ln)["name"] for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    actual = [n for n in actual if n != "__step__"]

print(f"== {framework} ==")
if init and "result" in init:
    print("initialize   :", init["result"]["name"], "| protocol", init["result"].get("protocol_version"),
          "| capabilities", list(init["result"].get("capabilities", {})))
else:
    print("initialize   : FAILED", (init or {}).get("error") or proc.stderr[-400:])
if step and "result" in step:
    r = step["result"]
    reported = [c["name"] for c in (r.get("tool_calls") or [])]
    print("reply        :", (r.get("public_output") or "")[:200])
    print("tools (real) :", actual)
    print("tools (ECP)  :", reported, "->", "MATCH" if sorted(actual) == sorted(reported) else "MISMATCH")
    print("usage        :", r.get("usage"))
    print("eval_context :", len(r.get("evaluation_context") or ""), "chars")
else:
    print("step         : FAILED", ((step or {}).get("error") or {}).get("message", proc.stderr[-500:])[:500])
