"""Facilities: shop upkeep, including leases and rent."""

from pydantic_ai import Agent

from common import MODEL, delegate, load_prompt, mcp_tools, prepare_payment_request
from models import SpecialistReport, TeamDeps

agent = Agent(
    MODEL,
    name="Facilities",
    deps_type=TeamDeps,
    output_type=SpecialistReport,
    instructions=load_prompt("facilities"),
    toolsets=[
        mcp_tools(
            "get_ticket", "get_desk", "get_lease_details", "list_leases",
            "get_cash_accounts", "list_payments", "quote_payment",
        )
    ],
    tools=[delegate, prepare_payment_request],
)
