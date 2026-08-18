"""Exercise 5 starter: apply one pattern after documenting a DDR in SPEC.md."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PaymentRequest:
    order_id: str
    amount: Decimal
    method: str


class OrderService:
    def checkout(self, request: PaymentRequest) -> str:
        """TODO: remove method-specific branching by applying a documented pattern."""
        if request.method == "CARD":
            return f"CARD:{request.order_id}:APPROVED"
        if request.method == "UPI":
            return f"UPI:{request.order_id}:APPROVED"
        if request.method == "COD":
            return f"COD:{request.order_id}:PENDING"
        raise ValueError("unsupported payment method")
