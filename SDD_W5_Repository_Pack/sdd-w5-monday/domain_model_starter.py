"""Exercise 1 starter: RetailCo domain modelling.

Complete SPEC.md first. This file intentionally contains only a small skeleton so
learners make the modelling decisions rather than receiving them pre-built.
"""
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class OrderItem:
    sku: str
    quantity: int
    unit_price: Decimal


@dataclass
class Order:
    order_id: str
    customer_id: str
    items: list[OrderItem] = field(default_factory=list)
    status: str = "CREATED"

    def total(self) -> Decimal:
        """TODO: calculate the order total from its items."""
        raise NotImplementedError


# TODO: Add only the entities justified by your SPEC.md.
# Possible domain concepts from the brief include Inventory, Payment, Shipment,
# FulfilmentCentre and Notification. Decide whether each should be a class or a
# plain function and document the rationale before coding it.
