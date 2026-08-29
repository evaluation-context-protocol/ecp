from ecp import Result, agent, on_reset, on_step, serve


ORDERS = {
    "A100": {"status": "delivered", "days_since_delivery": 12, "amount": "$49.00"},
    "B200": {"status": "delivered", "days_since_delivery": 45, "amount": "$79.00"},
}


def lookup_order(order_id: str):
    return ORDERS.get(order_id)


def check_refund_policy(order):
    if order is None:
        return {"eligible": False, "reason": "order was not found"}
    if order["status"] != "delivered":
        return {"eligible": False, "reason": "order has not been delivered"}
    if order["days_since_delivery"] > 30:
        return {"eligible": False, "reason": "delivery was more than 30 days ago"}
    return {"eligible": True, "reason": "delivery was within the 30-day refund window"}


@agent(name="CustomerSupportRefundAgent")
class CustomerSupportRefundAgent:
    def __init__(self):
        self.history = []

    @on_step
    def step(self, user_input: str):
        order_id = "A100" if "A100" in user_input else "B200" if "B200" in user_input else ""
        order = lookup_order(order_id)
        policy = check_refund_policy(order)

        tool_calls = [
            {"name": "lookup_order", "arguments": {"order_id": order_id}},
            {"name": "check_refund_policy", "arguments": {"order_id": order_id}},
        ]

        if policy["eligible"]:
            output = f"Order {order_id} is eligible for a refund. I can start the refund for {order['amount']}."
        else:
            output = f"Order {order_id} is not eligible for a refund because {policy['reason']}."

        self.history.append({"input": user_input, "order_id": order_id, "eligible": policy["eligible"]})
        return Result(
            public_output=output,
            evaluation_context=(
                f"Checked order {order_id}; status={order['status'] if order else 'missing'}; "
                f"days_since_delivery={order['days_since_delivery'] if order else 'unknown'}; "
                f"refund_eligible={policy['eligible']}; reason={policy['reason']}."
            ),
            tool_calls=tool_calls,
        )

    @on_reset
    def reset(self):
        self.history.clear()


if __name__ == "__main__":
    serve(CustomerSupportRefundAgent())
