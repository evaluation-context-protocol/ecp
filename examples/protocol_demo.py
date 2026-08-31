"""
ECP Protocol Demonstration (Zero-YAML, Zero-CLI)

This script demonstrates how an evaluation client (e.g. LangSmith, Promptfoo)
can communicate with an ECP Server (an AI Agent) using nothing but raw JSON-RPC
over standard input/output. 

It does NOT use `ecp_runtime`, YAML files, or the `ecp run` CLI. 
It proves that ECP is a language-agnostic protocol.
"""

import json
import subprocess
import sys
import threading
from typing import Any, Dict

# We'll use the existing customer support demo agent as our server
AGENT_CMD = [sys.executable, "examples/customer_support_demo/agent.py"]

def send_rpc(process: subprocess.Popen, method: str, params: Dict[str, Any], msg_id: int) -> None:
    """Send a JSON-RPC 2.0 message to the agent's stdin."""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": msg_id
    }
    raw = json.dumps(payload) + "\n"
    print(f"\n---> [CLIENT SENDS]: {raw.strip()}")
    
    if process.stdin:
        process.stdin.write(raw)
        process.stdin.flush()

def read_rpc(process: subprocess.Popen) -> None:
    """Continuously read JSON-RPC 2.0 responses from the agent's stdout."""
    if not process.stdout:
        return
        
    for line in process.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            # We just print the raw response to demonstrate the protocol shape
            response = json.loads(line)
            formatted = json.dumps(response, indent=2)
            print(f"<--- [AGENT RESPONDS]:\n{formatted}")
        except json.JSONDecodeError:
            print(f"<--- [AGENT STDOUT]: {line}")

def main() -> None:
    print(f"Starting ECP Protocol Demo...")
    print(f"Launching Agent Server: {' '.join(AGENT_CMD)}")
    
    # 1. Start the Agent Process
    process = subprocess.Popen(
        AGENT_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,  # Pipe stderr straight through
        text=True,
        bufsize=1 # Line-buffered
    )
    
    # 2. Start a background thread to read responses
    reader_thread = threading.Thread(target=read_rpc, args=(process,), daemon=True)
    reader_thread.start()
    
    try:
        # 3. Send the Initialization message
        send_rpc(
            process,
            "agent/initialize",
            {"protocol_version": "1.0", "config": {}},
            msg_id=1,
        )
        
        # 4. Wait a moment, then send the Step message (the actual evaluation task)
        import time
        time.sleep(1)
        
        send_rpc(
            process, 
            "agent/step", 
            {"input": "Hi, I'd like to return order #A100 because it arrived damaged."}, 
            msg_id=2
        )
        
        time.sleep(4)
        
        # 5. Send the Reset message to clear state
        send_rpc(process, "agent/reset", {}, msg_id=3)
        time.sleep(1)
        
    finally:
        print("\nShutting down Agent Server...")
        process.terminate()
        process.wait()

if __name__ == "__main__":
    main()
