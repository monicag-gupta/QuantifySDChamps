"""Exercise 2 starter: deliberately over-responsible OrderManager.

The class works, but it violates SRP and is difficult to extend. Refactor without
breaking its observable behaviour.
"""
from __future__ import annotations
from decimal import Decimal


class OrderManager:
    def __init__(self, inventory: dict[str, int] | None = None) -> None:
        self.inventory = dict(inventory or {})
        self.notifications: list[dict[str, str]] = []
        self.shipments: list[dict[str, str]] = []
        self.payments: list[dict[str, object]] = []

    def calculate_total(self, items: list[dict[str, object]]) -> Decimal:
        total = Decimal("0")
        for item in items:
            total += Decimal(str(item["unit_price"])) * int(item["quantity"])
        return total

    def reserve_inventory(self, items: list[dict[str, object]]) -> bool:
        for item in items:
            sku = str(item["sku"])
            if self.inventory.get(sku, 0) < int(item["quantity"]):
                return False
        for item in items:
            sku = str(item["sku"])
            self.inventory[sku] -= int(item["quantity"])
        return True

    def authorize_payment(self, order_id: str, amount: Decimal, payment_method: str) -> bool:
        # A simplified legacy rule: the mock gateway declines transactions above ₹100,000.
        approved = amount <= Decimal("100000") and payment_method in {"CARD", "UPI", "COD"}
        self.payments.append({
            "order_id": order_id,
            "amount": amount,
            "method": payment_method,
            "approved": approved,
        })
        return approved

    def create_shipment(self, order_id: str, fulfilment_centre: str) -> str:
        shipment_id = f"SHP-{order_id}"
        self.shipments.append({
            "shipment_id": shipment_id,
            "order_id": order_id,
            "fulfilment_centre": fulfilment_centre,
        })
        return shipment_id

    def send_notification(self, customer_email: str, message: str) -> None:
        self.notifications.append({"to": customer_email, "message": message})

    def process_order(
        self,
        order_id: str,
        customer_email: str,
        items: list[dict[str, object]],
        payment_method: str,
        fulfilment_centre: str = "MUMBAI",
    ) -> dict[str, object]:
        if not items:
            return {"order_id": order_id, "status": "REJECTED", "reason": "EMPTY_ORDER"}

        if not self.reserve_inventory(items):
            self.send_notification(customer_email, f"Order {order_id} is back-ordered")
            return {"order_id": order_id, "status": "BACK_ORDERED"}

        total = self.calculate_total(items)
        if not self.authorize_payment(order_id, total, payment_method):
            # Roll inventory back because payment failed.
            for item in items:
                sku = str(item["sku"])
                self.inventory[sku] = self.inventory.get(sku, 0) + int(item["quantity"])
            self.send_notification(customer_email, f"Payment failed for order {order_id}")
            return {"order_id": order_id, "status": "PAYMENT_REJECTED", "total": total}

        shipment_id = self.create_shipment(order_id, fulfilment_centre)
        self.send_notification(customer_email, f"Order {order_id} confirmed; shipment {shipment_id}")
        return {
            "order_id": order_id,
            "status": "CONFIRMED",
            "total": total,
            "shipment_id": shipment_id,
        }
