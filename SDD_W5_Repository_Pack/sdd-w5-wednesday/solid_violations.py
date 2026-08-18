"""Exercise 4 starter: one intentionally obvious violation of each SOLID principle."""
from decimal import Decimal


# S — SRP violation: pricing/orchestration and notification are mixed.
class OrderService:
    def __init__(self):
        self.sent_emails = []

    def complete_order(self, order_id: str, email: str, amount: Decimal) -> dict:
        result = {"order_id": order_id, "amount": amount, "status": "CONFIRMED"}
        self.sent_emails.append((email, f"Order {order_id} confirmed"))
        return result


# O — OCP violation: every new payment method requires editing this function.
class PaymentProcessor:
    def pay(self, method: str, amount: Decimal) -> str:
        if method == "CARD":
            return f"card:{amount}:approved"
        if method == "UPI":
            return f"upi:{amount}:approved"
        if method == "COD":
            return f"cod:{amount}:pending"
        raise ValueError("unsupported payment method")


# L — LSP violation: a subtype changes the return type/contract of total().
class Order:
    def __init__(self, amount: Decimal):
        self.amount = amount

    def total(self) -> Decimal:
        return self.amount


class DiscountedOrder(Order):
    def total(self) -> str:
        return f"₹{self.amount * Decimal('0.9')}"


# I — ISP violation: implementers are forced to provide unrelated methods.
class OperationsPort:
    def ship(self, order_id: str):
        raise NotImplementedError

    def notify(self, email: str, message: str):
        raise NotImplementedError

    def refund(self, order_id: str):
        raise NotImplementedError


class EmailNotifier(OperationsPort):
    def ship(self, order_id: str):
        raise NotImplementedError("email notifier cannot ship")

    def notify(self, email: str, message: str):
        return f"sent:{email}:{message}"

    def refund(self, order_id: str):
        raise NotImplementedError("email notifier cannot refund")


# D — DIP violation: high-level checkout creates a concrete gateway itself.
class StripeGateway:
    def charge(self, amount: Decimal) -> bool:
        return amount <= Decimal("100000")


class CheckoutService:
    def checkout(self, amount: Decimal) -> bool:
        gateway = StripeGateway()
        return gateway.charge(amount)
