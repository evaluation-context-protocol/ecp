import sys
import json
import traceback
from .decorators import _HOOKS, _CURRENT_AGENT_INSTANCE, Result

def serve(agent_instance):
    """
    Starts the ECP Server loop. 
    This blocks the process and waits for JSON commands from stdin.
    """
    global _CURRENT_AGENT_INSTANCE
    _CURRENT_AGENT_INSTANCE = agent_instance
    
    # 1. Input Loop (Reads 1 line at a time from the Runtime)
    for line in sys.stdin:
        if not line.strip():
            continue
            
        try:
            request = json.loads(line)
            method = request.get("method")
            params = request.get("params", {})
            req_id = request.get("id")

            # 2. Router
            response_data = None
            
            if method == "agent/initialize":
                response_data = _handle_init(params)
            elif method == "agent/step":
                response_data = _handle_step(params)
            elif method == "agent/reset":
                response_data = _handle_reset()
            else:
                raise ValueError(f"Unknown method: {method}")

            # 3. Response
            _send_json_rpc(req_id, response_data)

        except Exception as e:
            # If the agent crashes, we must tell the Runtime why
            error_msg = f"{type(e).__name__}: {str(e)}"
            # traceback.print_exc(file=sys.stderr) # Debugging help
            _send_error(req_id if 'req_id' in locals() else None, -32000, error_msg)

# --- Handlers ---

def _handle_init(params):
    name = getattr(_CURRENT_AGENT_INSTANCE, "_ecp_meta", {}).get("name", "Unknown")
    return {"name": name, "capabilities": {}}

def _handle_step(params):
    method_name = _HOOKS["step"]
    if not method_name:
        raise NotImplementedError("Agent has no @on_step method")
    
    # Call the user's function
    handler = getattr(_CURRENT_AGENT_INSTANCE, method_name)
    user_input = params.get("input")
    
    # Execute User Logic
    result = handler(user_input)
    
    # Ensure it returns a Result object
    if not isinstance(result, Result):
        # Fallback for lazy users who just return a string
        return {"status": "done", "public_output": str(result)}
        
    return {
        "status": result.status,
        "public_output": result.public_output,
        "private_thought": result.private_thought,
        "tool_calls": result.tool_calls
    }

def _handle_reset():
    method_name = _HOOKS["reset"]
    if method_name:
        handler = getattr(_CURRENT_AGENT_INSTANCE, method_name)
        handler()
    return True

# --- Helpers ---

def _send_json_rpc(req_id, result):
    response = {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result
    }
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()

def _send_error(req_id, code, message):
    response = {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message}
    }
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()