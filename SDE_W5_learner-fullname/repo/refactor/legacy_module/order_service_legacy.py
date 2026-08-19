"""Thursday lab starter: messy RetailCo order service.

This file is intentionally long and mixes domain rules, persistence, inventory,
payment, shipping, notification, discounts, exports and analytics. Characterize
existing behaviour before changing it.
"""
from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timezone


class LegacyOrderService:
    TAX_RATE = Decimal("0.18")

    def __init__(self, inventory=None):
        self.inventory = dict(inventory or {})
        self.orders = {}
        self.payments = []
        self.shipments = []
        self.notifications = []
        self.events = []
        self.coupons = {"SAVE10": Decimal("0.10"), "FLASH5": Decimal("0.05")}

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def set_inventory(self, sku, quantity):
        if quantity < 0:
            raise ValueError("quantity cannot be negative")
        self.inventory[sku] = int(quantity)
        self.events.append(("INVENTORY_SET", sku, int(quantity)))

    def create_order(self, order_id, customer_email, items, channel="web"):
        if not order_id:
            raise ValueError("missing order id")
        if order_id in self.orders:
            raise ValueError("duplicate order id")
        if not customer_email:
            raise ValueError("missing customer email")
        order = {
            "order_id": order_id,
            "customer_email": customer_email,
            "items": [dict(item) for item in items],
            "channel": channel,
            "status": "CREATED",
            "coupon": None,
            "shipping_address": None,
            "created_at": self._now(),
        }
        self.orders[order_id] = order
        self.events.append(("ORDER_CREATED", order_id))
        return dict(order)

    def calculate_subtotal(self, order_id):
        order = self.orders[order_id]
        subtotal = Decimal("0")
        for item in order["items"]:
            subtotal += Decimal(str(item["unit_price"])) * int(item["quantity"])
        return subtotal

    def apply_coupon(self, order_id, coupon_code):
        if coupon_code not in self.coupons:
            return False
        self.orders[order_id]["coupon"] = coupon_code
        self.events.append(("COUPON_APPLIED", order_id, coupon_code))
        return True

    def calculate_discount(self, order_id):
        order = self.orders[order_id]
        code = order.get("coupon")
        if not code:
            return Decimal("0")
        return (self.calculate_subtotal(order_id) * self.coupons[code]).quantize(Decimal("0.01"))

    def calculate_tax(self, order_id):
        taxable = self.calculate_subtotal(order_id) - self.calculate_discount(order_id)
        return (taxable * self.TAX_RATE).quantize(Decimal("0.01"))

    def calculate_total(self, order_id):
        subtotal = self.calculate_subtotal(order_id)
        discount = self.calculate_discount(order_id)
        tax = self.calculate_tax(order_id)
        return subtotal - discount + tax

    def can_fulfil(self, order_id):
        for item in self.orders[order_id]["items"]:
            if self.inventory.get(str(item["sku"]), 0) < int(item["quantity"]):
                return False
        return True

    def reserve_inventory(self, order_id):
        if not self.can_fulfil(order_id):
            self.orders[order_id]["status"] = "BACK_ORDERED"
            self.events.append(("BACK_ORDERED", order_id))
            return False
        for item in self.orders[order_id]["items"]:
            sku = str(item["sku"])
            self.inventory[sku] -= int(item["quantity"])
        self.orders[order_id]["status"] = "RESERVED"
        self.events.append(("INVENTORY_RESERVED", order_id))
        return True

    def release_inventory(self, order_id):
        for item in self.orders[order_id]["items"]:
            sku = str(item["sku"])
            self.inventory[sku] = self.inventory.get(sku, 0) + int(item["quantity"])
        self.events.append(("INVENTORY_RELEASED", order_id))

    def authorize_payment(self, order_id, method):
        amount = self.calculate_total(order_id)
        if method == "CARD":
            approved = amount <= Decimal("100000")
        elif method == "UPI":
            approved = amount <= Decimal("200000")
        elif method == "COD":
            approved = amount <= Decimal("50000")
        else:
            raise ValueError("unsupported payment method")
        record = {"order_id": order_id, "method": method, "amount": amount, "approved": approved}
        self.payments.append(record)
        self.events.append(("PAYMENT_AUTH", order_id, approved))
        if approved:
            self.orders[order_id]["status"] = "PAID" if method != "COD" else "COD_PENDING"
        else:
            self.orders[order_id]["status"] = "PAYMENT_REJECTED"
        return approved

    def retry_payment(self, order_id, method):
        if self.orders[order_id]["status"] != "PAYMENT_REJECTED":
            return False
        return self.authorize_payment(order_id, method)

    def choose_centre(self, order_id):
        channel = self.orders[order_id]["channel"]
        if channel == "mobile":
            return "BENGALURU"
        if channel == "api":
            return "DELHI"
        return "MUMBAI"

    def create_shipment(self, order_id, centre=None):
        centre = centre or self.choose_centre(order_id)
        shipment_id = f"SHP-{len(self.shipments)+1:05d}"
        record = {"shipment_id": shipment_id, "order_id": order_id, "centre": centre, "status": "CREATED"}
        self.shipments.append(record)
        self.orders[order_id]["shipment_id"] = shipment_id
        self.orders[order_id]["status"] = "READY_TO_SHIP"
        self.events.append(("SHIPMENT_CREATED", order_id, shipment_id))
        return shipment_id

    def mark_shipped(self, order_id):
        shipment_id = self.orders[order_id].get("shipment_id")
        if not shipment_id:
            return False
        for shipment in self.shipments:
            if shipment["shipment_id"] == shipment_id:
                shipment["status"] = "SHIPPED"
                self.orders[order_id]["status"] = "SHIPPED"
                self.events.append(("ORDER_SHIPPED", order_id))
                return True
        return False

    def mark_delivered(self, order_id):
        if self.orders[order_id]["status"] != "SHIPPED":
            return False
        self.orders[order_id]["status"] = "DELIVERED"
        self.events.append(("ORDER_DELIVERED", order_id))
        self.emit_analytics_event(order_id, "DELIVERED")
        return True

    def send_notification(self, order_id, message):
        email = self.orders[order_id]["customer_email"]
        self.notifications.append({"to": email, "message": message})
        self.events.append(("NOTIFIED", order_id))
        return True

    def update_address(self, order_id, address):
        if self.orders[order_id]["status"] in {"SHIPPED", "DELIVERED"}:
            return False
        self.orders[order_id]["shipping_address"] = address
        self.events.append(("ADDRESS_UPDATED", order_id))
        return True

    def cancel_order(self, order_id):
        order = self.orders[order_id]
        if order["status"] in {"SHIPPED", "DELIVERED", "CANCELLED"}:
            return False
        if order["status"] in {"RESERVED", "PAID", "COD_PENDING", "READY_TO_SHIP", "PAYMENT_REJECTED"}:
            self.release_inventory(order_id)
        order["status"] = "CANCELLED"
        self.events.append(("ORDER_CANCELLED", order_id))
        self.send_notification(order_id, f"Order {order_id} cancelled")
        return True

    def get_order_status(self, order_id):
        return self.orders[order_id]["status"]

    def list_open_orders(self):
        closed = {"DELIVERED", "CANCELLED"}
        return [dict(order) for order in self.orders.values() if order["status"] not in closed]

    def emit_analytics_event(self, order_id, event_name):
        event = {"order_id": order_id, "event": event_name, "at": self._now()}
        self.events.append(("ANALYTICS", event))
        return event

    def export_order_summary(self, order_id):
        order = self.orders[order_id]
        return {
            "order_id": order_id,
            "status": order["status"],
            "subtotal": self.calculate_subtotal(order_id),
            "discount": self.calculate_discount(order_id),
            "tax": self.calculate_tax(order_id),
            "total": self.calculate_total(order_id),
            "shipment_id": order.get("shipment_id"),
        }

    def process_order(self, order_id, payment_method):
        order = self.orders[order_id]
        if not order["items"]:
            order["status"] = "REJECTED"
            self.events.append(("EMPTY_ORDER_REJECTED", order_id))
            return {"order_id": order_id, "status": "REJECTED"}
        if not self.reserve_inventory(order_id):
            self.send_notification(order_id, f"Order {order_id} is back-ordered")
            return {"order_id": order_id, "status": "BACK_ORDERED"}
        if not self.authorize_payment(order_id, payment_method):
            self.release_inventory(order_id)
            self.send_notification(order_id, f"Payment failed for order {order_id}")
            return {"order_id": order_id, "status": "PAYMENT_REJECTED", "total": self.calculate_total(order_id)}
        shipment_id = self.create_shipment(order_id)
        self.send_notification(order_id, f"Order {order_id} confirmed; shipment {shipment_id}")
        return {
            "order_id": order_id,
            "status": "CONFIRMED",
            "total": self.calculate_total(order_id),
            "shipment_id": shipment_id,
        }


# ---------------------------------------------------------------------------
# Historical maintenance notes retained in the legacy module.
# Legacy note 001: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 002: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 003: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 004: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 005: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 006: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 007: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 008: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 009: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 010: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 011: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 012: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 013: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 014: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 015: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 016: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 017: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 018: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 019: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 020: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 021: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 022: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 023: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 024: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 025: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 026: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 027: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 028: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 029: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 030: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 031: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 032: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 033: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 034: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 035: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 036: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 037: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 038: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 039: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 040: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 041: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 042: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 043: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 044: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 045: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 046: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 047: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 048: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 049: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 050: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 051: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 052: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 053: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 054: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 055: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 056: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 057: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 058: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 059: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 060: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 061: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 062: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 063: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 064: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 065: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 066: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 067: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 068: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 069: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 070: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 071: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 072: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 073: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 074: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 075: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 076: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 077: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 078: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 079: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 080: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 081: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 082: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 083: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 084: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 085: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 086: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 087: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 088: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 089: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 090: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 091: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 092: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 093: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 094: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 095: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 096: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 097: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 098: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 099: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 100: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 101: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 102: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 103: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 104: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 105: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 106: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 107: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 108: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 109: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 110: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 111: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 112: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 113: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 114: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 115: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 116: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 117: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 118: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 119: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 120: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 121: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 122: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 123: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 124: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 125: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 126: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 127: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 128: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 129: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 130: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 131: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 132: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 133: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 134: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 135: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 136: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 137: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 138: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 139: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 140: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 141: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 142: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 143: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 144: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 145: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 146: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 147: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 148: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 149: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 150: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 151: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 152: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 153: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 154: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 155: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 156: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 157: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 158: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 159: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 160: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 161: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 162: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 163: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 164: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 165: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 166: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 167: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 168: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 169: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 170: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 171: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 172: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 173: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 174: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 175: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 176: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 177: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 178: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 179: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 180: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 181: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 182: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 183: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 184: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 185: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 186: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 187: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 188: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 189: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 190: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 191: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 192: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 193: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 194: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 195: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 196: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 197: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 198: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 199: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 200: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 201: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 202: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 203: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 204: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 205: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 206: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 207: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 208: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 209: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 210: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 211: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 212: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 213: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 214: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 215: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 216: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 217: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 218: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 219: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 220: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 221: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 222: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 223: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 224: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 225: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 226: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 227: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 228: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 229: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 230: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 231: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 232: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 233: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 234: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 235: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 236: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 237: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 238: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 239: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 240: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 241: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 242: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 243: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 244: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 245: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 246: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 247: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 248: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 249: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 250: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 251: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 252: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 253: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 254: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 255: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 256: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 257: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 258: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 259: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 260: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 261: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 262: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 263: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 264: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 265: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 266: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 267: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 268: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 269: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 270: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 271: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 272: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 273: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 274: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 275: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 276: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 277: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 278: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 279: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 280: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 281: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 282: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 283: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 284: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 285: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 286: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 287: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 288: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 289: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 290: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 291: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 292: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 293: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 294: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 295: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 296: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 297: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 298: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 299: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 300: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 301: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 302: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 303: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 304: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 305: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 306: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 307: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 308: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 309: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 310: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 311: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 312: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 313: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 314: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 315: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 316: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 317: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 318: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 319: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 320: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 321: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 322: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 323: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 324: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 325: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 326: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 327: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 328: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 329: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 330: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 331: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 332: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 333: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 334: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 335: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 336: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 337: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 338: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 339: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 340: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 341: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 342: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 343: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 344: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 345: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 346: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 347: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 348: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 349: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 350: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 351: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 352: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 353: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 354: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 355: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 356: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 357: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 358: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 359: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 360: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 361: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 362: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 363: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 364: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 365: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 366: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 367: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 368: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 369: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 370: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 371: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 372: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 373: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 374: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 375: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 376: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 377: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 378: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 379: behaviour retained for backward compatibility; verify with characterization tests before changing.
# Legacy note 380: behaviour retained for backward compatibility; verify with characterization tests before changing.
