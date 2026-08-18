from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from god_class_starter import OrderManager


def test_confirmed_order_preserves_expected_behaviour():
    manager = OrderManager({"SKU-1": 10})
    result = manager.process_order(
        "ORD-1",
        "learner@example.com",
        [{"sku": "SKU-1", "quantity": 2, "unit_price": "499.50"}],
        "UPI",
    )
    assert result["status"] == "CONFIRMED"
    assert result["total"] == Decimal("999.00")
    assert manager.inventory["SKU-1"] == 8
    assert result["shipment_id"] == "SHP-ORD-1"


def test_back_order_does_not_charge_customer():
    manager = OrderManager({"SKU-1": 1})
    result = manager.process_order(
        "ORD-2",
        "learner@example.com",
        [{"sku": "SKU-1", "quantity": 2, "unit_price": "100"}],
        "CARD",
    )
    assert result["status"] == "BACK_ORDERED"
    assert manager.payments == []
    assert manager.inventory["SKU-1"] == 1


def test_payment_rejection_rolls_inventory_back():
    manager = OrderManager({"SKU-1": 2})
    result = manager.process_order(
        "ORD-3",
        "learner@example.com",
        [{"sku": "SKU-1", "quantity": 1, "unit_price": "100001"}],
        "CARD",
    )
    assert result["status"] == "PAYMENT_REJECTED"
    assert manager.inventory["SKU-1"] == 2
