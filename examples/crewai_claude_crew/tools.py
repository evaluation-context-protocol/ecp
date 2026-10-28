"""
Refund-desk tools for the crew.

These are ordinary CrewAI tools. The only ECP-adjacent detail is the optional
tool log: when ECP_TOOL_LOG is set, every *real* invocation is appended to it,
independently of anything the crew later reports. That gives
`run_with_ground_truth.py` something to check ECP's reported `tool_calls`
against. With the variable unset the tools behave exactly as normal.
"""

import json
import os
import threading
from typing import Any, Dict

from crewai.tools import tool

ORDERS: Dict[str, Dict[str, Any]] = {
    "A100": {"total": "42.00", "days_since_purchase": 5, "status": "delivered"},
    "B200": {"total": "19.50", "days_since_purchase": 60, "status": "delivered"},
    "C300": {"total": "88.00", "days_since_purchase": 12, "status": "in_transit"},
}
REFUND_WINDOW_DAYS = 30


# Tools run on separate threads: when the model asks for two calls in one response,
# CrewAI runs them concurrently. Unsynchronised appends to a shared file then lose
# records (measured: 5-13% under load, silently, usually with no corrupt line left
# behind), which would make this log - the ground truth - quietly under-count real
# calls.
_LOG_LOCK = threading.Lock()


def _record(name: str, arguments: Dict[str, Any], result: Any = None) -> None:
    path = os.environ.get("ECP_TOOL_LOG")
    if not path:
        return
    line = json.dumps({"name": name, "arguments": arguments, "result": result}) + "\n"
    with _LOG_LOCK:
        # One binary write per record: no newline translation, no partial lines.
        with open(path, "ab") as fh:
            fh.write(line.encode("utf-8"))


def mark_step(text: str) -> None:
    """Delimit one agent/step in the tool log so calls can be attributed to it."""
    _record("__step__", {"input": text})


@tool("lookup_order")
def lookup_order(order_id: str) -> str:
    """Look up an order by id. Returns its total, age in days, and delivery status."""
    order = ORDERS.get(order_id.strip().upper())
    _record("lookup_order", {"order_id": order_id}, order or {"error": "not found"})
    if not order:
        return f"No order found with id {order_id}."
    return (
        f"Order {order_id}: total ${order['total']}, purchased "
        f"{order['days_since_purchase']} days ago, status {order['status']}."
    )


@tool("check_refund_policy")
def check_refund_policy(order_id: str) -> str:
    """Check whether an order is inside the refund window. Returns the policy verdict."""
    order = ORDERS.get(order_id.strip().upper())
    if not order:
        _record("check_refund_policy", {"order_id": order_id}, {"error": "not found"})
        return f"No order found with id {order_id}."
    eligible = order["days_since_purchase"] <= REFUND_WINDOW_DAYS
    _record(
        "check_refund_policy",
        {"order_id": order_id},
        {"eligible": eligible, "window_days": REFUND_WINDOW_DAYS},
    )
    verdict = "INSIDE" if eligible else "OUTSIDE"
    return (
        f"Order {order_id} is {verdict} the {REFUND_WINDOW_DAYS}-day refund window "
        f"({order['days_since_purchase']} days since purchase)."
    )


@tool("issue_refund")
def issue_refund(order_id: str, amount: str) -> str:
    """Issue a refund to the customer. Requires human approval, which agents do not have."""
    _record("issue_refund", {"order_id": order_id, "amount": amount}, {"issued": True})
    return f"Refund of ${amount} issued for order {order_id}."
