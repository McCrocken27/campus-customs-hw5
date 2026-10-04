"""Boss: reads the ticket, delegates it, and makes the final call."""

from pydantic_ai import Agent

from common import MODEL, delegate, load_prompt, mcp_tools
from models import BossDecision, TeamDeps

agent = Agent(
    MODEL,
    name="Boss",
    deps_type=TeamDeps,
    output_type=BossDecision,
    instructions=load_prompt("boss"),
    toolsets=[mcp_tools("get_ticket", "list_tickets", "get_desk")],
    tools=[delegate],
)
