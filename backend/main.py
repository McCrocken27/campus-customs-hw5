"""Campus Customs backend (Q7): FastAPI routes over the agent team and the MCP server.

Start it from this folder:
    .venv\\Scripts\\uvicorn.exe main:app --reload --port 8000

Routes (all under /api):
    GET  /tickets                    the tickets and their resolve status
    GET  /tickets/{id}               one ticket with its latest team result
    POST /tickets/{id}/run           run the agent team on a ticket (a human must ask)
    GET  /events                     agent events from output/audit_trail.json
    POST /tickets/{id}/approve       a human approves a drafted payment or purchase order
    GET  /cash                       current checking balance from cash_accounts
    POST /reset                      restore the database to its original values
    GET  /scores                     Yale Athletics scores for the dashboard ticker

Every shop fact comes from the MCP server. Approving a draft calls the MCP
server's record_approved_* tools; this file never opens the database. Reset
copies the untouched original (data/campus_customs.db) over the working copy.
"""

from __future__ import annotations

import asyncio
import hashlib
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from audit import append_event, read_events
from scores import Scoreboard, get_scoreboard
from common import HW5_DIR, MCP
from team import RUNS_DIR, _check_server_tools, load_resolution, new_run_id, run_ticket, save_resolution

DB_PATH = HW5_DIR / "data" / "campus_customs_new.db"
ORIGINAL_DB_PATH = HW5_DIR / "data" / "campus_customs.db"

# In-memory state of runs started by this server, keyed by ticket id.
RUN_STATE: dict[int, dict] = {}
_tasks: set[asyncio.Task] = set()


def _mark_abandoned_runs() -> None:
    """Add a ticket_run_abandoned event for any run that started but never ended.

    Runs live inside this server process, so a restart stops them mid-way. This keeps
    the audit trail honest about it; nothing is removed.
    """
    started, ended = {}, set()
    for e in read_events():
        if e.get("event") == "ticket_run_start":
            started[e["run_id"]] = e
        elif e.get("event") in ("ticket_run_end", "ticket_run_error", "ticket_run_abandoned"):
            ended.add(e.get("run_id"))
    for run_id, start in started.items():
        if run_id not in ended:
            append_event("ticket_run_abandoned", run_id=run_id, ticket_id=start.get("ticket_id"),
                         error="The backend restarted before this run finished.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _mark_abandoned_runs()
    async with MCP:  # keep one MCP server process open while the API is up
        await _check_server_tools()
        yield


app = FastAPI(title="Campus Customs backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class HumanRequest(BaseModel):
    requested_by: str = Field(min_length=1, description="Name of the human asking, e.g. 'Joey'.")


class ApprovalRequest(BaseModel):
    kind: Literal["payment", "purchase_order"]
    index: int = Field(ge=0, description="Which draft, counting from 0, in the ticket's latest result.")
    approved_by: str = Field(min_length=1, description="Name of the human approving, e.g. 'Joey'.")


class ResetRequest(BaseModel):
    requested_by: str = Field(min_length=1)
    confirm: bool = Field(description="Must be true. Resetting wipes payments and approvals.")


def _human(name: str) -> str:
    name = name.strip()
    if not name:
        raise HTTPException(422, "A human's name is required.")
    return f"human:{name}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _mcp(tool: str, args: dict | None = None) -> dict:
    return await MCP.direct_call_tool(tool, args or {})


def _any_run_active() -> bool:
    return any(s["status"] == "running" for s in RUN_STATE.values())


def _resolve_status(ticket_id: int) -> dict:
    """Combine this server's run state with the ticket's latest saved team result."""
    state = RUN_STATE.get(ticket_id, {})
    res = load_resolution(ticket_id)
    drafts = (res.payment_requests + res.purchase_orders) if res else []
    pending = sum(d.status == "pending_human_approval" for d in drafts)
    approved = sum(d.status == "approved" for d in drafts)

    if state.get("status") == "running":
        status = "running"
    elif state.get("status") == "failed":
        status = "failed"
    elif res is None:
        status = "not_run"
    elif pending:
        status = "awaiting_approval"  # finished, but a human still has to approve something
    else:
        status = "resolved"  # finished, and nothing is waiting on a human

    return {
        "resolve_status": status,
        "run_id": state.get("run_id"),
        "run_error": state.get("error"),
        "recommended_status": res.decision.recommended_status if res else None,
        "decision": res.decision.decision if res else None,
        "pending_approvals": pending,
        "approved_drafts": approved,
        "customer_messages": len(res.customer_messages) if res else 0,
    }


async def _run_in_background(ticket_id: int, requested_by: str, run_id: str) -> None:
    try:
        res = await run_ticket(ticket_id, requested_by=requested_by, run_id=run_id)
        save_resolution(res)
        RUN_STATE[ticket_id].update(status="done", finished_at=_now())
    except Exception as exc:
        RUN_STATE[ticket_id].update(status="failed", error=f"{type(exc).__name__}: {exc}", finished_at=_now())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/docs")


@app.get("/api/tickets")
async def list_tickets():
    """Every ticket from the database, with its resolve status."""
    result = await _mcp("list_tickets")
    return {"tickets": [{**t, **_resolve_status(t["id"])} for t in result["tickets"]]}


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: int):
    """One ticket, its resolve status, and the team's full latest result (drafts, hand-offs)."""
    ticket = await _mcp("get_ticket", {"ticket_id": ticket_id})
    if not ticket.get("found"):
        raise HTTPException(404, ticket["message"])
    ticket.pop("found")
    res = load_resolution(ticket_id)
    return {**ticket, **_resolve_status(ticket_id), "result": res.model_dump() if res else None}


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_team(ticket_id: int, body: HumanRequest):
    """Start the agent team on a ticket. Returns right away; follow progress with /api/events."""
    requested_by = _human(body.requested_by)
    ticket = await _mcp("get_ticket", {"ticket_id": ticket_id})
    if not ticket.get("found"):
        raise HTTPException(404, ticket["message"])
    if _any_run_active():
        raise HTTPException(409, "The team is already working on a ticket. Wait for it to finish.")

    run_id = new_run_id()
    RUN_STATE[ticket_id] = {"status": "running", "run_id": run_id, "requested_by": requested_by,
                            "started_at": _now(), "error": None}
    task = asyncio.create_task(_run_in_background(ticket_id, requested_by, run_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {"ticket_id": ticket_id, "run_id": run_id, "status": "running", "requested_by": requested_by}


@app.get("/api/events")
async def events(
    ticket_id: int | None = None,
    run_id: str | None = None,
    after: int = Query(-1, description="Only events with an index greater than this (for polling)."),
):
    """Agent events from the audit trail, oldest first. Each has an index for polling."""
    out = []
    for i, e in enumerate(read_events()):
        if i <= after:
            continue
        if ticket_id is not None and e.get("ticket_id") != ticket_id:
            continue
        if run_id is not None and e.get("run_id") != run_id:
            continue
        out.append({"index": i, **e})
    return {"events": out, "last_index": out[-1]["index"] if out else after}


@app.post("/api/tickets/{ticket_id}/approve")
async def approve(ticket_id: int, body: ApprovalRequest):
    """A human approves one drafted payment or purchase order from the ticket's latest result.

    The MCP server re-prices it from the database, records the payment, and takes it
    out of checking.
    """
    approved_by = _human(body.approved_by)
    if RUN_STATE.get(ticket_id, {}).get("status") == "running":
        raise HTTPException(409, "The team is still working on this ticket.")
    res = load_resolution(ticket_id)
    if res is None:
        raise HTTPException(404, f"Ticket {ticket_id} has no team result to approve yet.")

    drafts = res.payment_requests if body.kind == "payment" else res.purchase_orders
    if body.index >= len(drafts):
        raise HTTPException(404, f"Ticket {ticket_id} has no {body.kind} draft #{body.index}.")
    draft = drafts[body.index]
    if draft.status == "approved":
        raise HTTPException(409, f"Already approved by {draft.approved_by}.")

    if body.kind == "payment":
        outcome = await _mcp("record_approved_payment",
                             {"kind": draft.kind, "ref_id": draft.ref_id, "approved_by": approved_by})
    else:
        outcome = await _mcp("record_approved_purchase_order", {
            "ticket_id": ticket_id, "sku": draft.sku, "size": draft.size, "qty": draft.order_qty,
            "vendor_id": draft.vendor_id, "approved_by": approved_by,
        })
    append_event("human_approval", run_id=None, ticket_id=ticket_id, approved_by=approved_by,
                 draft_type=body.kind, index=body.index, draft=draft, outcome=outcome)
    if not outcome.get("approved"):
        raise HTTPException(400, outcome["message"])

    draft.status, draft.approved_by, draft.payment_id = "approved", approved_by, outcome["payment_id"]
    save_resolution(res)
    return {"ticket_id": ticket_id, **outcome, **_resolve_status(ticket_id)}


@app.get("/api/cash")
async def cash():
    """Current checking balance from the cash_accounts table."""
    result = await _mcp("get_cash_accounts")
    checking = next((a for a in result["accounts"] if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(404, "No checking account in cash_accounts.")
    return {"account": "checking", "balance": checking["balance"], "as_of": checking["date"]}


@app.get("/api/scores", response_model=Scoreboard)
def yale_scores():
    """Latest Yale Athletics results and upcoming games, from yalebulldogs.com (cached 15 min)."""
    return get_scoreboard()


@app.post("/api/reset")
async def reset(body: ResetRequest):
    """Restore the database to its original values for a fresh run.

    Copies data/campus_customs.db over data/campus_customs_new.db and clears the saved
    team results. The audit trail is never cleared; the reset is added to it.
    """
    requested_by = _human(body.requested_by)
    if not body.confirm:
        raise HTTPException(422, "Set confirm to true to reset the database.")
    if _any_run_active():
        raise HTTPException(409, "The team is working on a ticket. Wait for it to finish.")
    if not ORIGINAL_DB_PATH.exists():
        raise HTTPException(500, f"Original database not found at {ORIGINAL_DB_PATH}.")

    shutil.copyfile(ORIGINAL_DB_PATH, DB_PATH)
    cleared = [p.name for p in RUNS_DIR.glob("ticket_*.json")] if RUNS_DIR.exists() else []
    for name in cleared:
        (RUNS_DIR / name).unlink()
    RUN_STATE.clear()
    matches = _sha256(DB_PATH) == _sha256(ORIGINAL_DB_PATH)
    append_event("database_reset", run_id=None, ticket_id=None, requested_by=requested_by,
                 cleared_results=cleared, matches_original=matches)
    return {"reset": True, "matches_original": matches, "cleared_results": cleared, "requested_by": requested_by}
