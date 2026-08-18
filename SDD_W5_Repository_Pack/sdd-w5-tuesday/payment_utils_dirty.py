"""Exercise 3 starter: working but intentionally difficult-to-read payment utilities."""
from decimal import Decimal

T = Decimal("0.18")
D = Decimal("0.10")


def calc(x):
    s = Decimal("0")
    for i in x:
        s += Decimal(str(i["p"])) * int(i["q"])
    return s


def dsc(x, vip):
    if vip and x >= Decimal("5000"):
        return x * D
    return Decimal("0")


def do_pay(o, x, vip, m, g=True):
    # Everything is mixed together here: calculation, discount, tax, validation and record creation.
    a = calc(x)
    z = dsc(a, vip)
    b = a - z
    tx = (b * T).quantize(Decimal("0.01"))
    f = b + tx
    if not o:
        raise ValueError("missing order id")
    if m not in ("CARD", "UPI", "COD"):
        raise ValueError("bad method")
    if f <= 0:
        raise ValueError("bad amount")
    ok = bool(g)
    r = {"o": o, "amt": f, "m": m, "ok": ok, "disc": z, "tax": tx}
    if not ok:
        r["msg"] = "gateway declined"
    else:
        r["msg"] = "approved"
    return r


def fmt(r):
    return f"{r['o']}|{r['m']}|{r['amt']}|{'OK' if r['ok'] else 'DECLINED'}"
