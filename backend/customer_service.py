"""Customer Service: drafts messages to customers for human review."""

from pydantic_ai import Agent

from common import MODEL, delegate, draft_customer_message, load_prompt, mcp_tools
from models import SpecialistReport, TeamDeps

agent = Agent(
    MODEL,
    name="Customer Service",
    deps_type=TeamDeps,
    output_type=SpecialistReport,
    instructions=load_prompt("customer_service"),
    toolsets=[mcp_tools("get_ticket", "get_desk", "check_inventory", "list_inventory", "get_product_pricing")],
    tools=[delegate, draft_customer_message],
)
