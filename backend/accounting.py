"""Accounting: cash, invoices, margins, and purchase orders for human approval."""

from pydantic_ai import Agent

from common import MODEL, delegate, load_prompt, mcp_tools, prepare_payment_request, prepare_purchase_order
from models import SpecialistReport, TeamDeps

agent = Agent(
    MODEL,
    name="Accounting",
    deps_type=TeamDeps,
    output_type=SpecialistReport,
    instructions=load_prompt("accounting"),
    toolsets=[
        mcp_tools(
            "get_ticket", "get_desk", "get_cash_accounts", "list_invoices", "get_invoice",
            "list_payments", "get_product_pricing", "calculate_margin", "list_vendors",
            "quote_purchase_order", "quote_payment",
        )
    ],
    tools=[delegate, prepare_purchase_order, prepare_payment_request],
)
