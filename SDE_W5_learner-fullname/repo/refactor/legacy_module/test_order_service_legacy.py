"""Learner characterization-test starter.

Two examples are supplied so `pytest` starts green. Add tests for the remaining
public methods before refactoring and drive coverage above the lab target.
"""
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from order_service_legacy import LegacyOrderService


def test_create_order_current_behaviour():
    service = LegacyOrderService({"SKU-1": 5})
    result = service.create_order(
        "ORD-100", "buyer@example.com", [{"sku": "SKU-1", "quantity": 1, "unit_price": "100"}]
    )
    assert result["status"] == "CREATED"
    assert service.get_order_status("ORD-100") == "CREATED"


def test_process_order_current_happy_path():
    service = LegacyOrderService({"SKU-1": 5})
    service.create_order(
        "ORD-101", "buyer@example.com", [{"sku": "SKU-1", "quantity": 2, "unit_price": "100"}]
    )
    result = service.process_order("ORD-101", "UPI")
    assert result["status"] == "CONFIRMED"
    assert result["total"] == Decimal("236.00")
    assert service.inventory["SKU-1"] == 3
