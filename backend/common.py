"""Shared pieces for the agent team: the model, the MCP server, prompts, and team tools.

Every agent connects to the same MCP server (mcp_server/server.py, launched the way
hw5/.mcp.json says) and sees only the database tools its job needs. On top of that,
every agent gets `delegate`, which can hand a task to any other agent (full connectivity).
Draft tools (purchase orders, payment requests, customer messages) save drafts for a
human; nothing is sent, paid, or written to the database. They get every shop fact
from the MCP server too; nothing in the backend reads the database directly.

run_agent() runs an agent step by step and appends each loop step to
output/audit_trail.json (see audit.py).
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import replace
from pathlib import Path

import truststore
from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import RunUsage

from audit import append_event
from models import (
    MAX_AGENT_LOOPS,
    MAX_DELEGATION_DEPTH,
    AgentName,
    CustomerMessageDraft,
    DelegationRecord,
    PaymentRequestDraft,
    PurchaseOrderDraft,
    TeamDeps,
)

truststore.inject_into_ssl()  # use Windows' certificate store for HTTPS

BACKEND_DIR = Path(__file__).resolve().parent
HW5_DIR = BACKEND_DIR.parent
PROMPTS_DIR = BACKEND_DIR / "prompts"

# PORTKEY_API_KEY comes from hw5/.env (copy .env.example). On Joey's machine it lives
# one folder up, in the AI Class folder, so that's checked too.
load_dotenv(HW5_DIR / ".env")
load_dotenv(HW5_DIR.parent / ".env")
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

MODEL_NAME = "gpt-5.6-luna"
MODEL_TIMEOUT_SECONDS = 90
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# Filled in by team.py so `delegate` can find any agent by name.
AGENTS: dict[AgentName, Agent] = {}


def build_model() -> OpenAIResponsesModel:
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is missing from the .env file in the AI Class folder.")
    return OpenAIResponsesModel(
        MODEL_NAME,
        provider=OpenAIProvider(base_url=PORTKEY_BASE_URL, api_key=api_key),
        # A stuck model call gives up after this many seconds (the client retries twice)
        # instead of freezing the whole team.
        settings=ModelSettings(timeout=MODEL_TIMEOUT_SECONDS),
    )


MODEL = build_model()


def _build_mcp() -> MCPToolset:
    """Connect to the campus-customs server exactly as hw5/.mcp.json describes."""
    config = json.loads((HW5_DIR / ".mcp.json").read_text(encoding="utf-8"))
    server = config["mcpServers"]["campus-customs"]
    # .mcp.json says "python" and gives paths relative to hw5/, so it works on any machine.
    # Run the server with this same Python (the project's venv) and resolve the paths here.
    command = sys.executable if server["command"] == "python" else server["command"]
    args = [str(HW5_DIR / a) if a.endswith(".py") else a for a in server["args"]]
    return MCPToolset(Client(StdioTransport(command=command, args=args, cwd=str(HW5_DIR))))


MCP = _build_mcp()

# Every MCP tool some agent has been given; team.py checks they all exist on the server.
REQUESTED_MCP_TOOLS: set[str] = set()


def mcp_tools(*names: str):
    """The MCP server, narrowed to just the named tools."""
    allowed = frozenset(names)
    REQUESTED_MCP_TOOLS.update(allowed)
    return MCP.filtered(lambda ctx, tool_def: tool_def.name in allowed)


def load_prompt(name: str) -> str:
    """team.md (rules for everyone) followed by the agent's own prompt file."""
    team = (PROMPTS_DIR / "team.md").read_text(encoding="utf-8")
    own = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    return f"{team.strip()}\n\n{own.strip()}"


# ---------------------------------------------------------------------------
# Running an agent, one loop step at a time, into the audit trail
# ---------------------------------------------------------------------------


def _request_parts(request: ModelRequest) -> list[dict]:
    """What went to the model this step: the prompt, tool results, or retry notes."""
    parts = []
    for part in request.parts:
        if isinstance(part, UserPromptPart):
            parts.append({"type": "user_prompt", "content": part.content})
        elif isinstance(part, ToolReturnPart):
            parts.append({"type": "tool_result", "tool": part.tool_name, "tool_call_id": part.tool_call_id,
                          "content": part.content})
        elif isinstance(part, RetryPromptPart):
            parts.append({"type": "retry", "tool": part.tool_name, "content": part.content})
    return parts


def _response_parts(response: ModelResponse) -> list[dict]:
    """What the model sent back this step: tool calls and/or text."""
    parts = []
    for part in response.parts:
        if isinstance(part, ToolCallPart):
            parts.append({"type": "tool_call", "tool": part.tool_name, "tool_call_id": part.tool_call_id,
                          "args": part.args_as_dict()})
        elif isinstance(part, TextPart):
            parts.append({"type": "text", "content": part.content})
    return parts


class AgentLoopLimitExceeded(RuntimeError):
    """An agent hit MAX_AGENT_LOOPS model calls without finishing."""


class NotAuthorizedToRun(RuntimeError):
    """Someone tried to start an agent without the ask the safety rules require."""


def check_run_allowed(name: AgentName, deps: TeamDeps) -> None:
    """Agents only run when explicitly asked.

    The Boss must be asked by a human. Any other agent must be asked by a human
    directly, or be part of a chain the Boss started (the Boss, or a teammate the
    Boss brought in, delegated to it).
    """
    human_asked = deps.requested_by.startswith("human:") and len(deps.requested_by) > len("human:")
    if not human_asked:
        raise NotAuthorizedToRun(f"{name} can't run: no human asked for this run.")
    if name == "Boss":
        if deps.chain != ("Boss",):
            raise NotAuthorizedToRun("Only a human can start the Boss.")
    elif deps.chain[0] != "Boss" and deps.chain != (name,):
        raise NotAuthorizedToRun(f"{name} must be asked by the Boss or a human.")


async def run_agent(name: AgentName, prompt: str, deps: TeamDeps, usage: RunUsage | None = None):
    """Run one agent to completion, appending every loop step to output/audit_trail.json.

    A loop is one call to the model. The agent fails if it needs more than
    MAX_AGENT_LOOPS; when a delegated agent fails, its delegator is told and carries on.
    """
    base = {"run_id": deps.run_id, "ticket_id": deps.ticket_id, "agent": name, "chain": list(deps.chain),
            "requested_by": deps.requested_by}
    try:
        check_run_allowed(name, deps)
    except NotAuthorizedToRun as exc:
        append_event("agent_refused", **base, error=str(exc))
        raise
    step = 0
    loops = 0
    append_event("agent_start", **base, step=step, prompt=prompt)
    try:
        async with AGENTS[name].iter(prompt, deps=deps, usage=usage, usage_limits=deps.usage_limits) as run:
            async for node in run:
                step += 1
                if Agent.is_user_prompt_node(node):
                    append_event("loop_step", **base, step=step, node="user_prompt")
                elif Agent.is_model_request_node(node):
                    loops += 1
                    if loops > MAX_AGENT_LOOPS:
                        raise AgentLoopLimitExceeded(
                            f"{name} hit the {MAX_AGENT_LOOPS}-loop limit without finishing."
                        )
                    append_event("loop_step", **base, step=step, node="model_request", loop=loops,
                                 parts=_request_parts(node.request))
                elif Agent.is_call_tools_node(node):
                    resp = node.model_response
                    append_event("loop_step", **base, step=step, node="model_response",
                                 parts=_response_parts(resp),
                                 tokens={"input": resp.usage.input_tokens, "output": resp.usage.output_tokens})
                elif Agent.is_end_node(node):
                    append_event("loop_step", **base, step=step, node="end", output=node.data.output)
    except Exception as exc:
        append_event("agent_error", **base, step=step + 1, error=f"{type(exc).__name__}: {exc}")
        raise
    append_event("agent_end", **base, step=step + 1, output=run.result.output)
    return run.result


# ---------------------------------------------------------------------------
# delegate: any agent -> any other agent
# ---------------------------------------------------------------------------


async def delegate(ctx: RunContext[TeamDeps], to: AgentName, task: str) -> str:
    """Hand a task to another agent on the team and get their report back.

    Any agent can delegate to any other agent except the Boss, whom only a human can start. Write the task so it stands alone:
    say exactly what you need and include the facts you already have (SKUs,
    sizes, quantities, ids). The other agent can't see your conversation.

    Args:
        to: Inventory, Accounting, Facilities, or Customer Service.
        task: What you need them to do or find out.
    """
    deps = ctx.deps
    me = deps.current_agent
    if to == me:
        return f"You are {me}. Do this yourself instead of delegating to yourself."
    if to == "Boss":
        return (
            "Only a human can start the Boss. Don't delegate to the Boss; put the question "
            "in your report and set needs_boss_decision to true."
        )
    if to in deps.chain:
        return (
            f"{to} is already working on this ticket further up the chain "
            f"({' -> '.join(deps.chain)}) and is waiting on you. Don't send it back. "
            "Finish with what you have; put open questions in your report and set "
            "needs_boss_decision if a call has to be made."
        )
    if len(deps.chain) >= MAX_DELEGATION_DEPTH:
        return (
            f"Delegation limit reached ({' -> '.join(deps.chain)}). "
            "Finish with what you have and list anything still unknown in your report."
        )

    record = DelegationRecord(from_agent=me, to_agent=to, task=task, depth=len(deps.chain))
    deps.delegations.append(record)
    sub_deps = replace(deps, current_agent=to, chain=(*deps.chain, to))
    prompt = (
        f"Ticket {deps.ticket_id}. {me} delegated this to you "
        f"(chain: {' -> '.join(sub_deps.chain)}):\n\n{task}"
    )
    try:
        result = await run_agent(to, prompt, sub_deps, usage=ctx.usage)
    except UsageLimitExceeded:
        record.error = "The team's usage limit for this ticket was reached."
        raise
    except Exception as exc:  # report it to the delegating agent instead of crashing the team
        record.error = f"{type(exc).__name__}: {exc}"
        return f"{to} couldn't finish: {record.error}"
    record.result = result.output.model_dump_json()
    return f"Report from {to}:\n{result.output.model_dump_json(indent=2)}"


# ---------------------------------------------------------------------------
# Drafts for human approval
# ---------------------------------------------------------------------------


async def prepare_purchase_order(
    ctx: RunContext[TeamDeps], sku: str, size: str, qty: int, vendor_id: int, reason: str
) -> dict:
    """Prepare a restock purchase order for human approval. Nothing is sent to the vendor.

    Prices come from quote_purchase_order on the MCP server (qty x unit cost from
    the pricing table), so don't supply your own numbers. Preparing a PO again for
    the same SKU, size, and vendor replaces the earlier draft.

    Args:
        sku: Product SKU, e.g. "CC-HOOD-NAVY".
        size: Size, e.g. "M" or "OS".
        qty: Units to order.
        vendor_id: Vendor id from list_vendors.
        reason: One sentence on why, citing the ticket and stock numbers.
    """
    quote = await ctx.deps.mcp.direct_call_tool(
        "quote_purchase_order", {"sku": sku, "size": size, "qty": qty, "vendor_id": vendor_id}
    )
    if not quote.get("found"):
        return {"saved": False, **quote}
    draft = PurchaseOrderDraft(
        ticket_id=ctx.deps.ticket_id,
        prepared_by=ctx.deps.current_agent,
        sku=quote["sku"],
        name=quote["name"],
        size=quote["size"],
        order_qty=quote["order_qty"],
        vendor_id=quote["vendor_id"],
        vendor_name=quote["vendor_name"],
        lead_days=quote["lead_days"],
        expected_arrival=quote["expected_arrival"],
        unit_cost=quote["unit_cost"],
        estimated_total=quote["estimated_total"],
        cash_after_order=quote["cash_after_order"],
        cash_after_order_and_open_invoices=quote["cash_after_order_and_open_invoices"],
        reason=reason,
    )
    pos = ctx.deps.purchase_orders
    pos[:] = [p for p in pos if (p.sku, p.size, p.vendor_id) != (draft.sku, draft.size, draft.vendor_id)]
    pos.append(draft)
    append_event("draft_saved", run_id=ctx.deps.run_id, ticket_id=ctx.deps.ticket_id,
                 agent=ctx.deps.current_agent, draft_type="purchase_order", draft=draft)
    return {"saved": True, "note": "Saved for human approval. Not sent.", "purchase_order": draft.model_dump()}


async def prepare_payment_request(ctx: RunContext[TeamDeps], kind: str, ref_id: int, reason: str) -> dict:
    """Prepare a rent or invoice payment for human approval. Nothing is paid.

    Amount, payee, and due date come from quote_payment on the MCP server.
    Refuses if the invoice isn't open or a matching payment is already recorded.

    Args:
        kind: "rent" (ref_id is a lease id) or "invoice" (ref_id is an invoice id).
        ref_id: The lease or invoice id.
        reason: One sentence on why it should be paid now.
    """
    me = ctx.deps.current_agent
    kind = kind.strip().lower()
    if me == "Facilities" and kind != "rent":
        return {"saved": False, "message": "Facilities prepares rent payments only. Delegate invoices to Accounting."}
    quote = await ctx.deps.mcp.direct_call_tool("quote_payment", {"kind": kind, "ref_id": ref_id})
    if not quote.get("found"):
        return {"saved": False, **quote}
    if quote["matching_payments_recorded"]:
        return {"saved": False, "message": "A matching payment is already recorded.", **quote}
    if kind == "invoice" and quote["invoice_status"] != "open":
        return {"saved": False, "message": f"Invoice status is {quote['invoice_status']!r}, not open.", **quote}
    draft = PaymentRequestDraft(
        ticket_id=ctx.deps.ticket_id,
        prepared_by=me,
        kind=kind,
        ref_id=ref_id,
        payee=quote["payee"],
        description=quote["description"],
        amount=quote["amount"],
        due_date=quote["due_date"],
        days_until_due=quote["days_until_due"],
        overdue=quote["overdue"],
        cash_after_payment=quote["cash_after_payment"],
        reason=reason,
    )
    reqs = ctx.deps.payment_requests
    reqs[:] = [r for r in reqs if (r.kind, r.ref_id) != (kind, ref_id)]
    reqs.append(draft)
    append_event("draft_saved", run_id=ctx.deps.run_id, ticket_id=ctx.deps.ticket_id,
                 agent=me, draft_type="payment_request", draft=draft)
    return {"saved": True, "note": "Saved for human approval. Not paid.", "payment_request": draft.model_dump()}


async def draft_customer_message(ctx: RunContext[TeamDeps], subject: str, body: str) -> dict:
    """Save a message to this ticket's requester for a human to review. Nothing is sent.

    The recipient is always the ticket's requester from the database. Drafting
    again replaces the earlier draft.

    Args:
        subject: Short subject line.
        body: The full message. Only state facts from the tools; no promises about
            prices, dates, or stock that the data doesn't support.
    """
    ticket = await ctx.deps.mcp.direct_call_tool("get_ticket", {"ticket_id": ctx.deps.ticket_id})
    if not ticket.get("found"):
        return {"saved": False, **ticket}
    draft = CustomerMessageDraft(
        ticket_id=ctx.deps.ticket_id,
        prepared_by=ctx.deps.current_agent,
        to=ticket["requester"],
        subject=subject,
        body=body,
    )
    ctx.deps.customer_messages[:] = [draft]
    append_event("draft_saved", run_id=ctx.deps.run_id, ticket_id=ctx.deps.ticket_id,
                 agent=ctx.deps.current_agent, draft_type="customer_message", draft=draft)
    return {"saved": True, "note": "Saved for human review. Not sent.", "message": draft.model_dump()}
