"""Run the agent team on tickets from the command line.

    .venv\\Scripts\\python.exe run_ticket.py 101        one ticket
    .venv\\Scripts\\python.exe run_ticket.py 101 102    several
    .venv\\Scripts\\python.exe run_ticket.py --all-open every open ticket

Agents only run when a human explicitly asks: with no ticket ids and no
--all-open, nothing runs. The person running the command is recorded as the
human who asked.

Prints what the team decided and saves the full result (decision, drafts,
hand-offs) to output/ticket_runs/ticket_<id>.json. Every agent step is also
appended to output/audit_trail.json. The database isn't changed.
"""

from __future__ import annotations

import asyncio
import getpass
import sys

from common import HW5_DIR
from team import open_ticket_ids, run_ticket, save_resolution


def print_resolution(res) -> None:
    t, d = res.ticket, res.decision
    print(f"\n=== Ticket {t['id']}: {t['subject']} ({t['type']}, from {t['requester']}) ===")
    print("Hand-offs:")
    for h in res.delegations:
        note = f"  [error: {h.error}]" if h.error else ""
        print(f"  {'  ' * (h.depth - 1)}{h.from_agent} -> {h.to_agent}{note}")
    print(f"Decision: {d.decision}")
    print(f"Why: {d.reasoning}")
    print(f"Recommended status: {d.recommended_status}")
    for i, step in enumerate(d.next_steps, 1):
        print(f"  {i}. {step}")
    for po in res.purchase_orders:
        print(f"PO draft: {po.order_qty} x {po.sku} {po.size} from {po.vendor_name}, "
              f"est. ${po.estimated_total:,.2f}, arrives {po.expected_arrival} (needs approval)")
    for p in res.payment_requests:
        print(f"Payment draft: ${p.amount:,.2f} to {p.payee} ({p.kind} {p.ref_id}), due {p.due_date} (needs approval)")
    for m in res.customer_messages:
        print(f"Message draft to {m.to}: {m.subject}\n" + "\n".join(f"    {line}" for line in m.body.splitlines()))
    if d.missing_data:
        print("Missing data: " + "; ".join(d.missing_data))
    print(f"({res.model_requests} model calls, {res.tool_calls} tool calls)")


sys.stdout.reconfigure(encoding="utf-8")  # so curly quotes print correctly on Windows


async def main(args: list[str]) -> None:
    if args == ["--all-open"]:
        ids = await open_ticket_ids()
    elif args and all(a.isdigit() for a in args):
        ids = [int(a) for a in args]
    else:
        print(__doc__)
        print("Nothing was run. Name the tickets to run, or pass --all-open.")
        return
    requested_by = f"human:{getpass.getuser()}"
    for ticket_id in ids:
        res = await run_ticket(ticket_id, requested_by=requested_by)
        print_resolution(res)
        path = save_resolution(res)
        print(f"Saved {path.relative_to(HW5_DIR)}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
