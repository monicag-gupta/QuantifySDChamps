"""
RetailCo exercise starter: a deliberately overgrown God Class.

Exercise:
1. Read this class and identify its responsibilities.
2. Extract each responsibility into its own class/function.
3. Use composition to wire the collaborators together.
4. Update SPEC.md and add tests.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Order:
    order_id: str
    customer_id: str
    items: Dict[str, int]
    total: float
    status: str = "PLACED"
    shipment_id: str | None = None
    payment_id: str | None = None
    backordered: bool = False
    inventory_decremented: bool = False
    events: List[str] = field(default_factory=list)


class OrderManager:
    """Intentionally violates SRP by owning the whole fulfilment workflow."""

    def __init__(self):
        self.inventory = {"LAPTOP": 5, "MOUSE": 10, "KEYBOARD": 3}
        self.orders = {}
        self.payments = {}
        self.shipments = {}
        self.notifications = []
        self.analytics_events = []

    # Responsibility 1: order lifecycle / order persistence
    def place_order(self, customer_id, items, total):
        order_id = f"ORD-{len(self.orders) + 1:04d}"
        order = Order(order_id, customer_id, items, total)
        self.orders[order_id] = order
        self._log_analytics("ORDER_PLACED", order_id)
        return order

    def get_order(self, order_id):
        return self.orders.get(order_id)

    # Responsibility 2: inventory reservation and decrement
    def check_and_reserve_inventory(self, order_id):
        order = self.orders[order_id]
        for sku, quantity in order.items.items():
            if self.inventory.get(sku, 0) < quantity:
                order.backordered = True
                order.status = "BACKORDERED"
                self._log_analytics("BACKORDER_CREATED", order_id)
                return False

        for sku, quantity in order.items.items():
            self.inventory[sku] -= quantity

        order.status = "INVENTORY_RESERVED"
        self._log_analytics("INVENTORY_RESERVED", order_id)
        return True

    def decrement_inventory_on_delivery(self, order_id):
        order = self.orders[order_id]
        if order.inventory_decremented:
            return

        # In the deliberately simplistic starter, reservation is represented
        # by the first inventory reduction. Delivery records the final state.
        order.inventory_decremented = True
        self._log_analytics("INVENTORY_DECREMENTED", order_id)

    # Responsibility 3: payment gateway interaction
    def authorize_payment(self, order_id, payment_method="CARD"):
        order = self.orders[order_id]

        if order.total <= 0:
            order.status = "PAYMENT_REJECTED"
            self._log_analytics("PAYMENT_REJECTED", order_id)
            return False

        payment_id = f"PAY-{len(self.payments) + 1:04d}"
        self.payments[payment_id] = {
            "order_id": order_id,
            "amount": order.total,
            "method": payment_method,
            "status": "AUTHORIZED",
        }
        order.payment_id = payment_id
        order.status = "CONFIRMED"
        self._log_analytics("PAYMENT_AUTHORIZED", order_id)
        return True

    # Responsibility 4: fulfilment / shipment creation
    def create_shipment(self, order_id, address):
        order = self.orders[order_id]

        if order.status != "CONFIRMED":
            raise ValueError("Only confirmed orders can be shipped")

        shipment_id = f"SHIP-{len(self.shipments) + 1:04d}"
        self.shipments[shipment_id] = {
            "shipment_id": shipment_id,
            "order_id": order_id,
            "address": address,
            "status": "SHIPPED",
        }
        order.shipment_id = shipment_id
        order.status = "SHIPPED"
        self._log_analytics("SHIPMENT_CREATED", order_id)
        return self.shipments[shipment_id]

    def mark_delivered(self, order_id):
        order = self.orders[order_id]

        if not order.shipment_id:
            raise ValueError("Order has no shipment")

        self.shipments[order.shipment_id]["status"] = "DELIVERED"
        order.status = "DELIVERED"
        self.decrement_inventory_on_delivery(order_id)
        order.status = "CLOSED"
        self._log_analytics("ORDER_CLOSED", order_id)
        return order

    # Responsibility 5: customer notification
    def send_shipping_notification(self, order_id, channel="email"):
        order = self.orders[order_id]

        if not order.shipment_id:
            raise ValueError("Cannot notify without a shipment")

        message = (
            f"Order {order_id} has shipped. "
            f"Shipment: {order.shipment_id}"
        )
        self.notifications.append({
            "customer_id": order.customer_id,
            "channel": channel,
            "message": message,
        })
        self._log_analytics("SHIPPING_NOTIFICATION_SENT", order_id)

    # Responsibility 6: analytics/event publishing
    def _log_analytics(self, event_type, order_id):
        self.analytics_events.append({
            "type": event_type,
            "order_id": order_id,
        })
