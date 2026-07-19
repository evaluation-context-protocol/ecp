import asyncio
import inspect
import json
import sys
import threading
from concurrent.futures import Future
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from .decorators import _CURRENT_AGENT_INSTANCE, _HOOKS, Result

JSON_RPC_VERSION = "2.0"
JSON_CONTENT_TYPE = "application/json"


class _AwaitableExecutor:
    """Runs async hooks on one persistent event loop without changing the sync API."""

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def run(self, value: Any) -> Any:
        if not inspect.isawaitable(value):
            return value
        loop = self._ensure_loop()
        future: Future = asyncio.run_coroutine_threadsafe(self._await_value(value), loop)
        return future.result()

    def close(self) -> None:
        with self._lock:
            loop = self._loop
            thread = self._thread
            self._loop = None
            self._thread = None
        if loop is None or thread is None:
            return
        loop.call_soon_threadsafe(loop.stop)
        thread.join()
        loop.close()

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is not None and self._thread is not None and self._thread.is_alive():
                return self._loop

            ready = threading.Event()
            loop = asyncio.new_event_loop()

            def _run_loop() -> None:
                asyncio.set_event_loop(loop)
                ready.set()
                loop.run_forever()

            thread = threading.Thread(target=_run_loop, name="ecp-async-hooks", daemon=True)
            thread.start()
            ready.wait()
            self._loop = loop
            self._thread = thread
            return loop

    @staticmethod
    async def _await_value(value: Any) -> Any:
        return await value


_ASYNC_EXECUTOR = _AwaitableExecutor()


def serve(agent_instance):
    """
    Starts the ECP Server loop. 
    This blocks the process and waits for JSON commands from stdin.
    """
    global _CURRENT_AGENT_INSTANCE
    _CURRENT_AGENT_INSTANCE = agent_instance
    
    # 1. Input Loop (Reads 1 line at a time from the Runtime)
    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            req_id = None

            try:
                request = json.loads(line)
                if isinstance(request, dict):
                    req_id = request.get("id")
                response = _dispatch_json_rpc(request)
                if response is not None:
                    _write_json_rpc(response)

            except Exception as e:
                # If the agent crashes, we must tell the Runtime why
                error_msg = f"{type(e).__name__}: {str(e)}"
                # traceback.print_exc(file=sys.stderr) # Debugging help
                _send_error(req_id if 'req_id' in locals() else None, -32000, error_msg)
    finally:
        _ASYNC_EXECUTOR.close()


def serve_http(
    agent_instance,
    host: str = "127.0.0.1",
    port: int = 8765,
    path: str = "/ecp",
    allowed_origins: Optional[Iterable[str]] = None,
):
    """
    Starts an ECP Streamable HTTP server.

    The server exposes a single endpoint that accepts JSON-RPC over POST.
    It returns JSON responses for requests and HTTP 202 for notifications.
    GET currently returns 405 because ECP does not yet define server-initiated
    messages.
    """
    global _CURRENT_AGENT_INSTANCE
    _CURRENT_AGENT_INSTANCE = agent_instance
    server = _build_http_server(host, port, path, allowed_origins)
    print(f"ECP Streamable HTTP listening on http://{host}:{server.server_port}{_normalize_path(path)}", file=sys.stderr)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        _ASYNC_EXECUTOR.close()


def _build_http_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    path: str = "/ecp",
    allowed_origins: Optional[Iterable[str]] = None,
):
    endpoint_path = _normalize_path(path)
    origins = set(allowed_origins or _default_allowed_origins(host, port))

    class ECPStreamableHTTPRequestHandler(BaseHTTPRequestHandler):
        server_version = "ECPStreamableHTTP/0.1"

        def do_POST(self):
            if not self._is_endpoint():
                self._send_status(HTTPStatus.NOT_FOUND)
                return
            if not self._origin_allowed(origins):
                self._discard_request_body()
                self._send_status(HTTPStatus.FORBIDDEN)
                return

            accept = self.headers.get("Accept", "")
            if not _accepts(accept, JSON_CONTENT_TYPE):
                self._discard_request_body()
                self._send_status(HTTPStatus.NOT_ACCEPTABLE)
                return

            content_type = self.headers.get("Content-Type", "")
            if content_type and JSON_CONTENT_TYPE not in content_type.lower():
                self._discard_request_body()
                self._send_status(HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
                return

            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(length).decode("utf-8")
                payload = json.loads(raw_body) if raw_body else None
                response = _dispatch_http_payload(payload)
            except json.JSONDecodeError:
                self._send_json(_json_rpc_error(None, -32700, "Parse error"), HTTPStatus.BAD_REQUEST)
                return
            except Exception as exc:
                self._send_json(
                    _json_rpc_error(None, -32000, f"{type(exc).__name__}: {exc}"),
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return

            if response is None:
                self._send_status(HTTPStatus.ACCEPTED)
            else:
                self._send_json(response)

        def do_GET(self):
            if not self._is_endpoint():
                self._send_status(HTTPStatus.NOT_FOUND)
                return
            if not self._origin_allowed(origins):
                self._send_status(HTTPStatus.FORBIDDEN)
                return
            self._send_status(HTTPStatus.METHOD_NOT_ALLOWED, allow="POST")

        def do_DELETE(self):
            if not self._is_endpoint():
                self._send_status(HTTPStatus.NOT_FOUND)
                return
            self._send_status(HTTPStatus.METHOD_NOT_ALLOWED, allow="POST")

        def log_message(self, format, *args):
            print(format % args, file=sys.stderr)

        def _is_endpoint(self) -> bool:
            return urlparse(self.path).path == endpoint_path

        def _origin_allowed(self, allowed: set) -> bool:
            origin = self.headers.get("Origin")
            return origin is None or origin in allowed

        def _discard_request_body(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length > 0:
                self.rfile.read(length)

        def _send_status(self, status: HTTPStatus, allow: Optional[str] = None) -> None:
            self.send_response(status)
            if allow:
                self.send_header("Allow", allow)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", f"{JSON_CONTENT_TYPE}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return ThreadingHTTPServer((host, port), ECPStreamableHTTPRequestHandler)


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
    result = _invoke_handler(handler, user_input)
    
    # Ensure it returns a Result object
    if not isinstance(result, Result):
        # Fallback for lazy users who just return a string
        return {"status": "done", "public_output": str(result)}
        
    return {
        "status": result.status,
        "public_output": result.public_output,
        "evaluation_context": result.evaluation_context,
        "private_thought": result.private_thought,
        "tool_calls": result.tool_calls,
        "logs": result.logs,
    }

def _handle_reset():
    method_name = _HOOKS["reset"]
    if method_name:
        handler = getattr(_CURRENT_AGENT_INSTANCE, method_name)
        _invoke_handler(handler)
    return True


def _invoke_handler(handler, *args):
    return _ASYNC_EXECUTOR.run(handler(*args))


def _dispatch_http_payload(payload: Any) -> Optional[Any]:
    if isinstance(payload, list):
        responses: List[Dict[str, Any]] = []
        for item in payload:
            response = _dispatch_json_rpc(item)
            if response is not None:
                responses.append(response)
        return responses or None

    return _dispatch_json_rpc(payload)


def _dispatch_json_rpc(request: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(request, dict):
        return _json_rpc_error(None, -32600, "Invalid Request")

    req_id = request.get("id")
    if request.get("jsonrpc") != JSON_RPC_VERSION:
        return _json_rpc_error(req_id, -32600, "Invalid Request")

    method = request.get("method")
    params = request.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return _json_rpc_error(req_id, -32602, "Invalid params")

    try:
        if method == "agent/initialize":
            response_data = _handle_init(params)
        elif method == "agent/step":
            response_data = _handle_step(params)
        elif method == "agent/reset":
            response_data = _handle_reset()
        else:
            return _json_rpc_error(req_id, -32601, f"Unknown method: {method}")
    except Exception as exc:
        return _json_rpc_error(req_id, -32000, f"{type(exc).__name__}: {exc}")

    if "id" not in request:
        return None
    return _json_rpc_result(req_id, response_data)


# --- Helpers ---

def _send_json_rpc(req_id, result):
    _write_json_rpc(_json_rpc_result(req_id, result))

def _write_json_rpc(response):
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()

def _send_error(req_id, code, message):
    _write_json_rpc(_json_rpc_error(req_id, code, message))

def _json_rpc_result(req_id, result):
    return {
        "jsonrpc": JSON_RPC_VERSION,
        "id": req_id,
        "result": result
    }

def _json_rpc_error(req_id, code, message):
    return {
        "jsonrpc": JSON_RPC_VERSION,
        "id": req_id,
        "error": {"code": code, "message": message}
    }

def _accepts(header: str, media_type: str) -> bool:
    if not header:
        return True
    accepted = [part.split(";", 1)[0].strip().lower() for part in header.split(",")]
    return "*/*" in accepted or media_type in accepted

def _normalize_path(path: str) -> str:
    if not path.startswith("/"):
        return f"/{path}"
    return path

def _default_allowed_origins(host: str, port: int) -> Tuple[str, ...]:
    return (
        f"http://{host}:{port}",
        f"http://localhost:{port}",
        f"http://127.0.0.1:{port}",
    )
