"""Data types shared by the Campus Customs agent team."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_ai.usage import UsageLimits

AgentName = Literal["Boss", "Inventory", "Accounting", "Facilities", "Customer Service"]
AGENT_NAMES: tuple[AgentName, ...] = ("Boss", "Inventory", "Accounting", "Facilities", "Customer Service")

# Guardrails so agents delegating to each other can't loop forever.
MAX_AGENT_LOOPS = 7  # model calls one agent run may make before it fails
MAX_DELEGATION_DEPTH = 4  # Boss -> A -> B -> C, and no further
TEAM_REQUEST_LIMIT = 80  # model calls per ticket, across the whole team
TEAM_TOOL_CALL_LIMIT = 150  # tool calls per ticket, across the whole team


# ---------------------------------------------------------------------------
# Drafts that need a human. Agents prepare them; nothing is sent or paid.
# ---------------------------------------------------------------------------


class PurchaseOrderDraft(BaseModel):
    """A restock order waiting for human approval. Numbers come from quote_purchase_order."""

    ticket_id: int
    prepared_by: AgentName
    sku: str
    name: str
    size: str
    order_qty: int
    vendor_id: int
    vendor_name: str
    lead_days: int
    expected_arrival: str
    unit_cost: float
    estimated_total: float
    cash_after_order: float
    cash_after_order_and_open_invoices: float
    reason: str
    status: Literal["pending_human_approval", "approved"] = "pending_human_approval"
    approved_by: str | None = None  # filled in when a human approves (Q7 backend)
    payment_id: int | None = None  # the payments row the approval created


class PaymentRequestDraft(BaseModel):
    """A rent or invoice payment waiting for human approval. Numbers come from quote_payment."""

    ticket_id: int
    prepared_by: AgentName
    kind: Literal["rent", "invoice"]
    ref_id: int
    payee: str
    description: str | None
    amount: float
    due_date: str
    days_until_due: int
    overdue: bool
    cash_after_payment: float
    reason: str
    status: Literal["pending_human_approval", "approved"] = "pending_human_approval"
    approved_by: str | None = None  # filled in when a human approves (Q7 backend)
    payment_id: int | None = None  # the payments row the approval created


class CustomerMessageDraft(BaseModel):
    """A message to a customer waiting for human review before it's sent."""

    ticket_id: int
    prepared_by: AgentName
    to: str = Field(description="The ticket's requester, exactly as in the database.")
    subject: str
    body: str
    status: Literal["pending_human_review"] = "pending_human_review"


class DelegationRecord(BaseModel):
    """One hand-off between agents, kept so a human can see who asked whom for what."""

    from_agent: AgentName
    to_agent: AgentName
    task: str
    depth: int
    result: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# What each agent returns.
# ---------------------------------------------------------------------------


class SpecialistReport(BaseModel):
    """What Inventory, Accounting, Facilities, or Customer Service hands back."""

    summary: str = Field(description="Two or three sentences answering the task you were given.")
    facts: list[str] = Field(
        default_factory=list,
        description="Each fact you relied on, with the tool it came from, e.g. "
        "'CC-TEE-WHITE size S qty 0 (check_inventory)'. Only tool data.",
    )
    recommendation: str = Field(description="What you think should happen next.")
    needs_boss_decision: bool = Field(
        default=False, description="True if there's a trade-off only the Boss should decide."
    )
    missing_data: list[str] = Field(
        default_factory=list,
        description="Anything you needed that isn't in the database. Never fill these in yourself.",
    )


TicketStatus = Literal["resolved", "waiting_on_human_approval", "waiting_on_vendor", "needs_more_info", "open"]


class BossDecision(BaseModel):
    """The Boss's final call on a ticket."""

    ticket_id: int
    decision: str = Field(description="The final call, in one or two sentences.")
    reasoning: str = Field(description="Why, citing the team's findings.")
    recommended_status: TicketStatus = Field(
        description="Suggested ticket status. It's a recommendation only; the database isn't changed."
    )
    next_steps: list[str] = Field(default_factory=list, description="Ordered steps for the humans.")
    missing_data: list[str] = Field(default_factory=list)


class TicketResolution(BaseModel):
    """Everything the team produced for one ticket."""

    ticket: dict[str, Any]
    decision: BossDecision
    purchase_orders: list[PurchaseOrderDraft]
    payment_requests: list[PaymentRequestDraft]
    customer_messages: list[CustomerMessageDraft]
    delegations: list[DelegationRecord]
    model_requests: int
    tool_calls: int


# ---------------------------------------------------------------------------
# Run state passed to every agent.
# ---------------------------------------------------------------------------


@dataclass
class TeamDeps:
    """Shared by every agent working on one ticket.

    Delegation makes a copy with a new current_agent and a longer chain; the lists
    are shared, so drafts and hand-offs from any agent end up in one place.
    """

    ticket_id: int
    mcp: Any  # the MCPToolset connected to mcp_server/server.py
    run_id: str  # ties this ticket run's audit events together
    requested_by: str  # the human who asked for this run, e.g. "human:jssim"
    current_agent: AgentName = "Boss"
    chain: tuple[AgentName, ...] = ("Boss",)
    usage_limits: UsageLimits = field(
        default_factory=lambda: UsageLimits(
            request_limit=TEAM_REQUEST_LIMIT, tool_calls_limit=TEAM_TOOL_CALL_LIMIT
        )
    )
    purchase_orders: list[PurchaseOrderDraft] = field(default_factory=list)
    payment_requests: list[PaymentRequestDraft] = field(default_factory=list)
    customer_messages: list[CustomerMessageDraft] = field(default_factory=list)
    delegations: list[DelegationRecord] = field(default_factory=list)
