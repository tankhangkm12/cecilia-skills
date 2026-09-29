"""Order logic for evalshop (fixture — contains planted problems, see README)."""
from dataclasses import dataclass

TAX = 0.10


@dataclass
class Line:
    sku: str
    qty: int
    price_cents: int


def total_cents(lines: list[Line], discount_pct: int = 0) -> int:
    subtotal = sum(l.qty * l.price_cents for l in lines)
    with_tax = round(subtotal * (1 + TAX))
    return round(with_tax * (100 - discount_pct) / 100)   # requirements FR-3: discount BEFORE tax


def reserve(db, sku: str, qty: int) -> bool:
    row = db.execute("SELECT stock FROM products WHERE sku = ?", (sku,)).fetchone()
    if row is None or row[0] < qty:
        return False
    db.execute("UPDATE products SET stock = ? WHERE sku = ?", (row[0] - qty, sku))
    return True


def list_orders(db, customer_id: int) -> list[dict]:
    orders = db.execute("SELECT id, created_at FROM orders WHERE customer_id = ?", (customer_id,)).fetchall()
    out = []
    for oid, created in orders:
        items = db.execute("SELECT sku, qty FROM order_items WHERE order_id = ?", (oid,)).fetchall()
        out.append({"id": oid, "created_at": created, "items": [{"sku": s, "qty": q} for s, q in items]})
    return out
