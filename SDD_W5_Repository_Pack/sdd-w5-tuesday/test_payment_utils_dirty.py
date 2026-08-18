from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from payment_utils_dirty import calc, do_pay, fmt


def test_calc_current_behaviour():
    assert calc([{"p": "100", "q": 2}, {"p": "50", "q": 1}]) == Decimal("250")


def test_vip_payment_current_behaviour():
    result = do_pay(
        "ORD-10",
        [{"p": "5000", "q": 1}],
        True,
        "UPI",
        True,
    )
    assert result["disc"] == Decimal("500.00")
    assert result["tax"] == Decimal("810.00")
    assert result["amt"] == Decimal("5310.00")
    assert fmt(result) == "ORD-10|UPI|5310.00|OK"


def test_declined_payment_current_behaviour():
    result = do_pay("ORD-11", [{"p": "100", "q": 1}], False, "CARD", False)
    assert result["ok"] is False
    assert result["msg"] == "gateway declined"
