"""Campus Customs MCP server.

Shared by every agent in HW5. Agent tools only read data/campus_customs_new.db.
The two record_approved_* tools at the bottom write to it, and only when a
human approves something through the backend; no agent is given them.

Run it:  .venv\\Scripts\\python.exe server.py
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

from fastmcp import FastMCP

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db"

mcp = FastMCP(
    "campus-customs",
    instructions=(
        "Tools for the Campus Customs database. Never invent data: only report "
        "what these tools return. If a tool finds nothing, say so instead of guessing."
    ),
)


def get_connection() -> sqlite3.Connection:
    """Open the Campus Customs database. Rows come back as dict-like objects."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@mcp.tool
def check_inventory(sku: str, size: str) -> dict:
    """Get how many units of one product in one size are in stock.

    sku is like "CC-TEE-WHITE"; size is like "S", "M", "L", "XL", or "OS"
    (one size). Returns {"found": False, ...} if that SKU and size aren't in
    inventory.
    """
    with closing(get_connection()) as conn:
        row = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory"
            " WHERE sku = ? COLLATE NOCASE AND size = ? COLLATE NOCASE",
            (sku.strip(), size.strip()),
        ).fetchone()
    if row is None:
        return {"found": False, "message": f"No inventory record for SKU {sku!r} in size {size!r}."}
    return {"found": True, **dict(row)}


@mcp.tool
def get_product_pricing(sku: str) -> dict:
    """Get a product's unit cost (what Campus Customs pays) and list price (what it charges).

    Returns {"found": False, ...} if the SKU has no pricing record.
    """
    with closing(get_connection()) as conn:
        row = conn.execute(
            "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ? COLLATE NOCASE",
            (sku.strip(),),
        ).fetchone()
    if row is None:
        return {"found": False, "message": f"No pricing record for SKU {sku!r}."}
    return {"found": True, **dict(row)}


@mcp.tool
def get_lease_details(lease_id: int) -> dict:
    """Get one lease: space name, landlord, monthly rent, next due date, and notes.

    Returns {"found": False, ...} if no lease has that id.
    """
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone()
    if row is None:
        return {"found": False, "message": f"No lease with id {lease_id}."}
    return {"found": True, **dict(row)}


# ---------------------------------------------------------------------------
# Tools for the Q5 agent team. All of them only read the database; drafts
# (purchase orders, payment requests) are computed here but never saved.
# ---------------------------------------------------------------------------


def _desk_date(conn: sqlite3.Connection) -> date:
    """The shop's "today", from the desk table (not the computer's clock)."""
    return date.fromisoformat(conn.execute("SELECT date_today FROM desk").fetchone()[0])


def _total_cash(conn: sqlite3.Connection) -> float:
    return conn.execute("SELECT COALESCE(SUM(balance), 0) FROM cash_accounts").fetchone()[0]


def _open_demand(conn: sqlite3.Connection) -> dict[tuple[str, str], list[dict]]:
    """Units requested by open tickets, keyed by (sku, size)."""
    demand: dict[tuple[str, str], list[dict]] = {}
    for row in conn.execute(
        "SELECT id, sku, size, qty FROM tickets"
        " WHERE status = 'open' AND sku IS NOT NULL AND qty IS NOT NULL"
    ):
        demand.setdefault((row["sku"], row["size"]), []).append({"ticket_id": row["id"], "qty": row["qty"]})
    return demand


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Get every field of one ticket: type, requester, subject, sku, size, qty,
    lease_id, invoice_id, status, notes, created_at."""
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if row is None:
        return {"found": False, "message": f"No ticket with id {ticket_id}."}
    return {"found": True, **dict(row)}


@mcp.tool
def list_tickets(status: str | None = None) -> dict:
    """List tickets, oldest first. Pass status (e.g. "open") to filter."""
    sql, params = "SELECT * FROM tickets", ()
    if status:
        sql, params = sql + " WHERE status = ? COLLATE NOCASE", (status.strip(),)
    with closing(get_connection()) as conn:
        tickets = [dict(r) for r in conn.execute(sql + " ORDER BY created_at", params)]
    return {"count": len(tickets), "tickets": tickets}


@mcp.tool
def get_desk() -> dict:
    """Get the shop's current date (date_today) and any desk notes. Use this
    date, not your own, for anything due or overdue."""
    with closing(get_connection()) as conn:
        return dict(conn.execute("SELECT * FROM desk").fetchone())


@mcp.tool
def list_inventory(sku: str | None = None) -> dict:
    """List inventory rows (sku, name, size, qty, location). Pass sku to see
    every size of one product."""
    sql, params = "SELECT * FROM inventory", ()
    if sku:
        sql, params = sql + " WHERE sku = ? COLLATE NOCASE", (sku.strip(),)
    with closing(get_connection()) as conn:
        rows = [dict(r) for r in conn.execute(sql + " ORDER BY sku, size", params)]
    if sku and not rows:
        return {"found": False, "message": f"No inventory records for SKU {sku!r}."}
    return {"found": True, "count": len(rows), "items": rows}


@mcp.tool
def find_low_stock(threshold: int = 5) -> dict:
    """Find stock that's low. An item is flagged if its qty is at or below
    threshold, or if open tickets ask for more units than are on hand.

    threshold is the team's reorder point, not a number from the database;
    5 is the default. Each item shows open-ticket demand and the shortfall.
    """
    with closing(get_connection()) as conn:
        demand = _open_demand(conn)
        flagged = []
        for row in conn.execute("SELECT * FROM inventory ORDER BY sku, size"):
            requests = demand.get((row["sku"], row["size"]), [])
            requested = sum(r["qty"] for r in requests)
            reasons = []
            if row["qty"] <= threshold:
                reasons.append(f"qty {row['qty']} is at or below threshold {threshold}")
            if requested > row["qty"]:
                reasons.append(f"open tickets request {requested}, only {row['qty']} on hand")
            if reasons:
                flagged.append({
                    **dict(row),
                    "open_ticket_requests": requests,
                    "units_requested": requested,
                    "shortfall": max(requested - row["qty"], 0),
                    "reasons": reasons,
                })
    return {"threshold": threshold, "count": len(flagged), "items": flagged}


@mcp.tool
def list_vendors(specialty: str | None = None) -> dict:
    """List vendors (id, name, specialty, lead_days). Pass specialty to match
    part of the specialty text, e.g. "apparel"."""
    sql, params = "SELECT * FROM vendors", ()
    if specialty:
        sql, params = sql + " WHERE specialty LIKE ?", (f"%{specialty.strip()}%",)
    with closing(get_connection()) as conn:
        vendors = [dict(r) for r in conn.execute(sql + " ORDER BY id", params)]
    return {"count": len(vendors), "vendors": vendors}


@mcp.tool
def get_cash_accounts() -> dict:
    """List cash accounts (name, balance, date the balance was recorded) and the total."""
    with closing(get_connection()) as conn:
        accounts = [dict(r) for r in conn.execute("SELECT * FROM cash_accounts ORDER BY name")]
        return {"accounts": accounts, "total_balance": _total_cash(conn)}


def _invoice_rows(conn: sqlite3.Connection, where: str = "", params: tuple = ()) -> list[dict]:
    today = _desk_date(conn)
    rows = []
    for r in conn.execute(
        "SELECT i.*, v.name AS vendor_name FROM invoices i"
        f" LEFT JOIN vendors v ON v.id = i.vendor_id {where} ORDER BY i.due_date",
        params,
    ):
        days = (date.fromisoformat(r["due_date"]) - today).days
        rows.append({**dict(r), "days_until_due": days, "overdue": r["status"] == "open" and days < 0})
    return rows


@mcp.tool
def list_invoices(status: str | None = None) -> dict:
    """List vendor invoices with vendor name, days until due (negative means
    past due, measured from the desk date), and an overdue flag. Pass status
    (e.g. "open") to filter."""
    with closing(get_connection()) as conn:
        if status:
            rows = _invoice_rows(conn, "WHERE i.status = ? COLLATE NOCASE", (status.strip(),))
        else:
            rows = _invoice_rows(conn)
    return {
        "count": len(rows),
        "total_amount": sum(r["amount"] for r in rows),
        "invoices": rows,
    }


@mcp.tool
def get_invoice(invoice_id: int) -> dict:
    """Get one invoice with its vendor name, days until due, and overdue flag."""
    with closing(get_connection()) as conn:
        rows = _invoice_rows(conn, "WHERE i.id = ?", (invoice_id,))
    if not rows:
        return {"found": False, "message": f"No invoice with id {invoice_id}."}
    return {"found": True, **rows[0]}


@mcp.tool
def list_payments() -> dict:
    """List payments already made (kind, ref_id, amount, account, paid_at, approved_by)."""
    with closing(get_connection()) as conn:
        payments = [dict(r) for r in conn.execute("SELECT * FROM payments ORDER BY paid_at")]
    return {"count": len(payments), "payments": payments}


@mcp.tool
def list_leases() -> dict:
    """List every lease (space name, landlord, monthly rent, next due date, notes)."""
    with closing(get_connection()) as conn:
        today = _desk_date(conn)
        leases = [
            {**dict(r), "days_until_due": (date.fromisoformat(r["next_due"]) - today).days}
            for r in conn.execute("SELECT * FROM leases ORDER BY id")
        ]
    return {"count": len(leases), "leases": leases}


@mcp.tool
def calculate_margin(sku: str, unit_price: float | None = None, qty: int = 1) -> dict:
    """Work out the margin on selling qty units of a product.

    Uses unit_cost and list_price from the pricing table. Pass unit_price to
    test a discounted price; leave it out to use the list price. Returns per-unit
    and total profit, margin percent, and the discount off list.
    """
    if qty <= 0:
        return {"found": False, "message": "qty must be at least 1."}
    pricing = get_product_pricing(sku)
    if not pricing["found"]:
        return pricing
    cost, list_price = pricing["unit_cost"], pricing["list_price"]
    price = list_price if unit_price is None else unit_price
    profit = price - cost
    return {
        "found": True,
        "sku": pricing["sku"],
        "qty": qty,
        "unit_cost": cost,
        "list_price": list_price,
        "unit_price": round(price, 2),
        "discount_off_list_pct": round((list_price - price) / list_price * 100, 2),
        "profit_per_unit": round(profit, 2),
        "margin_pct": round(profit / price * 100, 2) if price else None,
        "total_revenue": round(price * qty, 2),
        "total_cost": round(cost * qty, 2),
        "total_profit": round(profit * qty, 2),
        "below_cost": price < cost,
    }


@mcp.tool
def quote_purchase_order(sku: str, size: str, qty: int, vendor_id: int) -> dict:
    """Price a restock order. Nothing is saved or sent.

    Checks that the SKU/size is a stocked item and the vendor exists, estimates
    cost as qty x pricing.unit_cost, and adds the vendor's lead time, expected
    arrival (desk date + lead_days), cash on hand, open invoices, and cash left
    after paying this order and open invoices.
    """
    if qty <= 0:
        return {"found": False, "message": "qty must be at least 1."}
    with closing(get_connection()) as conn:
        item = conn.execute(
            "SELECT sku, name, size, qty FROM inventory"
            " WHERE sku = ? COLLATE NOCASE AND size = ? COLLATE NOCASE",
            (sku.strip(), size.strip()),
        ).fetchone()
        if item is None:
            return {"found": False, "message": f"No inventory record for SKU {sku!r} in size {size!r}."}
        vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if vendor is None:
            return {"found": False, "message": f"No vendor with id {vendor_id}."}
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (item["sku"],)).fetchone()
        if price is None:
            return {"found": False, "message": f"No pricing record for SKU {item['sku']!r}."}
        today = _desk_date(conn)
        cash = _total_cash(conn)
        open_invoices = sum(r["amount"] for r in _invoice_rows(conn, "WHERE i.status = 'open'"))
    total = round(price["unit_cost"] * qty, 2)
    return {
        "found": True,
        "sku": item["sku"],
        "name": item["name"],
        "size": item["size"],
        "qty_on_hand": item["qty"],
        "order_qty": qty,
        "vendor_id": vendor["id"],
        "vendor_name": vendor["name"],
        "vendor_specialty": vendor["specialty"],
        "lead_days": vendor["lead_days"],
        "expected_arrival": (today + timedelta(days=vendor["lead_days"])).isoformat(),
        "unit_cost": price["unit_cost"],
        "estimated_total": total,
        "cost_basis": "qty x pricing.unit_cost (estimate; vendor's actual quote may differ)",
        "cash_on_hand": cash,
        "open_invoices_total": open_invoices,
        "cash_after_order": round(cash - total, 2),
        "cash_after_order_and_open_invoices": round(cash - total - open_invoices, 2),
    }


@mcp.tool
def quote_payment(kind: str, ref_id: int) -> dict:
    """Look up what a payment would be. Nothing is paid or saved.

    kind is "rent" (ref_id = lease id) or "invoice" (ref_id = invoice id).
    Returns payee, amount, due date, days until due, whether a matching payment
    is already recorded, cash on hand, and cash left after paying.
    """
    kind = kind.strip().lower()
    with closing(get_connection()) as conn:
        today = _desk_date(conn)
        if kind == "rent":
            row = conn.execute("SELECT * FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if row is None:
                return {"found": False, "message": f"No lease with id {ref_id}."}
            payee, amount, due = row["landlord"], row["monthly_rent"], row["next_due"]
            what = f"Rent for {row['space_name']}"
            status = None
        elif kind == "invoice":
            row = conn.execute(
                "SELECT i.*, v.name AS vendor_name FROM invoices i"
                " LEFT JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
                (ref_id,),
            ).fetchone()
            if row is None:
                return {"found": False, "message": f"No invoice with id {ref_id}."}
            payee, amount, due = row["vendor_name"], row["amount"], row["due_date"]
            what = row["description"]
            status = row["status"]
        else:
            return {"found": False, "message": 'kind must be "rent" or "invoice".'}
        already_paid = [
            dict(r) for r in conn.execute(
                "SELECT * FROM payments WHERE kind = ? AND ref_id = ?", (kind, ref_id)
            )
        ]
        cash = _total_cash(conn)
    days = (date.fromisoformat(due) - today).days
    return {
        "found": True,
        "kind": kind,
        "ref_id": ref_id,
        "description": what,
        "payee": payee,
        "amount": amount,
        "due_date": due,
        "days_until_due": days,
        "overdue": days < 0,
        "invoice_status": status,
        "matching_payments_recorded": already_paid,
        "cash_on_hand": cash,
        "cash_after_payment": round(cash - amount, 2),
    }


# ---------------------------------------------------------------------------
# Human approval (Q7). These are the only tools that write to the database.
# The backend calls them when a human clicks approve; no agent is given them.
# ---------------------------------------------------------------------------


def _check_approver(approved_by: str) -> str | None:
    """Return an error message unless approved_by names a human, e.g. "human:Joey"."""
    if not approved_by.startswith("human:") or not approved_by[len("human:"):].strip():
        return 'approved_by must name the human who approved, like "human:Joey".'
    return None


def _debit(conn: sqlite3.Connection, account: str, amount: float, today: date) -> dict | None:
    """Take amount out of account. Returns an error dict if it can't."""
    row = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()
    if row is None:
        return {"approved": False, "message": f"No cash account named {account!r}."}
    if row["balance"] < amount:
        return {
            "approved": False,
            "message": f"{account} has ${row['balance']:,.2f}, not enough for ${amount:,.2f}.",
        }
    conn.execute(
        "UPDATE cash_accounts SET balance = balance - ?, date = ? WHERE name = ?",
        (amount, today.isoformat(), account),
    )
    return None


@mcp.tool
def record_approved_payment(kind: str, ref_id: int, approved_by: str, account: str = "checking") -> dict:
    """Pay rent or an invoice that a human approved. HUMAN APPROVAL ONLY; agents never get this tool.

    Amount and payee come from the database, not the caller. Records the payment,
    takes it out of the cash account, and marks an invoice paid. Refuses if it's
    already paid, the invoice isn't open, or there isn't enough cash.
    """
    if err := _check_approver(approved_by):
        return {"approved": False, "message": err}
    quote = quote_payment(kind, ref_id)
    if not quote["found"]:
        return {"approved": False, "message": quote["message"]}
    if quote["matching_payments_recorded"]:
        return {"approved": False, "message": "A matching payment is already recorded."}
    if quote["kind"] == "invoice" and quote["invoice_status"] != "open":
        return {"approved": False, "message": f"Invoice status is {quote['invoice_status']!r}, not open."}

    with closing(get_connection()) as conn, conn:
        today = _desk_date(conn)
        if err := _debit(conn, account, quote["amount"], today):
            return err
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (quote["kind"], ref_id, quote["amount"], account, today.isoformat(), approved_by),
        )
        if quote["kind"] == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (ref_id,))
        balance = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()[0]
    return {
        "approved": True,
        "payment_id": cur.lastrowid,
        "kind": quote["kind"],
        "ref_id": ref_id,
        "payee": quote["payee"],
        "amount": quote["amount"],
        "account": account,
        "paid_at": today.isoformat(),
        "approved_by": approved_by,
        "balance_after": balance,
    }


@mcp.tool
def record_approved_purchase_order(
    ticket_id: int, sku: str, size: str, qty: int, vendor_id: int, approved_by: str, account: str = "checking"
) -> dict:
    """Place a restock purchase order that a human approved. HUMAN APPROVAL ONLY; agents never get this tool.

    Cost is re-priced from the database (qty x pricing.unit_cost). Records it in
    payments as kind "purchase_order" with ref_id = the ticket id, and takes it out
    of the cash account. Inventory doesn't change until the goods arrive.
    """
    if err := _check_approver(approved_by):
        return {"approved": False, "message": err}
    if not get_ticket(ticket_id)["found"]:
        return {"approved": False, "message": f"No ticket with id {ticket_id}."}
    quote = quote_purchase_order(sku, size, qty, vendor_id)
    if not quote["found"]:
        return {"approved": False, "message": quote["message"]}

    with closing(get_connection()) as conn, conn:
        today = _desk_date(conn)
        if err := _debit(conn, account, quote["estimated_total"], today):
            return err
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            ("purchase_order", ticket_id, quote["estimated_total"], account, today.isoformat(), approved_by),
        )
        balance = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()[0]
    return {
        "approved": True,
        "payment_id": cur.lastrowid,
        "ticket_id": ticket_id,
        "sku": quote["sku"],
        "size": quote["size"],
        "order_qty": quote["order_qty"],
        "vendor_name": quote["vendor_name"],
        "amount": quote["estimated_total"],
        "expected_arrival": quote["expected_arrival"],
        "account": account,
        "paid_at": today.isoformat(),
        "approved_by": approved_by,
        "balance_after": balance,
    }


if __name__ == "__main__":
    mcp.run(show_banner=False)
