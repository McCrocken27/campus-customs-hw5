"""The Campus Customs agent team. run_ticket() hands one ticket to the Boss.

The Boss delegates to teammates, who can delegate to each other. Every agent
uses the shared MCP server for database facts. The result collects the Boss's
decision plus every draft (purchase orders, payments, customer messages) for
humans to approve. Every step is appended to output/audit_trail.json.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import accounting
import boss
import customer_service
import facilities
import inventory
from audit import append_event
from common import AGENTS, HW5_DIR, MCP, REQUESTED_MCP_TOOLS, run_agent
from models import TeamDeps, TicketResolution

RUNS_DIR = HW5_DIR / "output" / "ticket_runs"

AGENTS.update({
    "Boss": boss.agent,
    "Inventory": inventory.agent,
    "Accounting": accounting.agent,
    "Facilities": facilities.agent,
    "Customer Service": customer_service.agent,
})


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def save_resolution(res: TicketResolution) -> Path:
    """Save the latest result for a ticket to output/ticket_runs/ticket_<id>.json."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"ticket_{res.ticket['id']}.json"
    path.write_text(res.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_resolution(ticket_id: int) -> TicketResolution | None:
    path = RUNS_DIR / f"ticket_{ticket_id}.json"
    if not path.exists():
        return None
    return TicketResolution.model_validate_json(path.read_text(encoding="utf-8"))


async def _check_server_tools() -> None:
    available = {tool.name for tool in await MCP.list_tools()}
    missing = REQUESTED_MCP_TOOLS - available
    if missing:
        raise RuntimeError(f"MCP server is missing tools: {sorted(missing)}")


async def open_ticket_ids() -> list[int]:
    """Ids of open tickets, from the MCP server."""
    async with MCP:
        result = await MCP.direct_call_tool("list_tickets", {"status": "open"})
    return [t["id"] for t in result["tickets"]]


async def run_ticket(ticket_id: int, requested_by: str, run_id: str | None = None) -> TicketResolution:
    """Have the team respond to one ticket. requested_by names the human who asked, e.g. "human:jssim"."""
    run_id = run_id or new_run_id()
    append_event("ticket_run_start", run_id=run_id, ticket_id=ticket_id, requested_by=requested_by)
    try:
        async with MCP:  # one server process shared by every agent for this ticket
            await _check_server_tools()
            ticket = await MCP.direct_call_tool("get_ticket", {"ticket_id": ticket_id})
            if not ticket.get("found"):
                raise ValueError(ticket["message"])

            deps = TeamDeps(ticket_id=ticket_id, mcp=MCP, run_id=run_id, requested_by=requested_by)
            result = await run_agent("Boss", f"Respond to ticket {ticket_id}.", deps)
            usage = result.usage
    except Exception as exc:
        append_event("ticket_run_error", run_id=run_id, ticket_id=ticket_id, error=f"{type(exc).__name__}: {exc}")
        raise

    ticket.pop("found")
    resolution = TicketResolution(
        ticket=ticket,
        decision=result.output,
        purchase_orders=deps.purchase_orders,
        payment_requests=deps.payment_requests,
        customer_messages=deps.customer_messages,
        delegations=deps.delegations,
        model_requests=usage.requests,
        tool_calls=usage.tool_calls,
    )
    append_event("ticket_run_end", run_id=run_id, ticket_id=ticket_id,
                 model_requests=usage.requests, tool_calls=usage.tool_calls,
                 decision=resolution.decision,
                 drafts={"purchase_orders": len(deps.purchase_orders),
                         "payment_requests": len(deps.payment_requests),
                         "customer_messages": len(deps.customer_messages)})
    return resolution
