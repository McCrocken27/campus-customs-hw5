"""Inventory: checks stock by SKU and size, spots low stock, picks the restock vendor."""

from pydantic_ai import Agent

from common import MODEL, delegate, load_prompt, mcp_tools
from models import SpecialistReport, TeamDeps

agent = Agent(
    MODEL,
    name="Inventory",
    deps_type=TeamDeps,
    output_type=SpecialistReport,
    instructions=load_prompt("inventory"),
    toolsets=[
        mcp_tools(
            "get_ticket", "get_desk", "check_inventory", "list_inventory",
            "find_low_stock", "list_vendors",
        )
    ],
    tools=[delegate],
)
