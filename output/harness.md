# Campus Customs Agent Harness

## Database tables

The database has nine tables that AI agents can use to understand and work with Campus Customs. The cash accounts table includes name, balance, and date, and it matters because it tells agents how much money is available in each account and when that balance was recorded. The desk table includes today’s date and notes, and it gives agents the current date and any general notes they should know before making decisions. The inventory table includes SKU, product name, size, quantity, and location, and it matters because it tells agents what products are available, how many are in stock, their sizes, and where they are located. The invoices table includes invoice ID, vendor ID, amount, due date, status, and description, and it lets agents see what the company owes vendors, when payments are due, and whether they have already been paid. The leases table includes lease ID, space name, landlord, monthly rent, next due date, and notes, and it gives agents information about the company’s rented spaces, including how much rent costs and when it is due. The payments table includes payment ID, type, reference ID, amount, account, payment date, and approved by, and it gives agents a record of payments that have been made, including what was paid, which account was used, when it was paid, and who approved it. The pricing table includes SKU, unit cost, and list price, and it matters because it tells agents how much each product costs the company and how much the company sells it for. The tickets table includes ticket ID, type, requester, subject, SKU, size, quantity, lease ID, invoice ID, status, notes, and creation date, and it gives agents the requests or tasks they may need to handle while connecting those requests to products, leases, or invoices when necessary. Finally, the vendors table includes vendor ID, name, specialty, and lead time in days, and it tells agents who the company buys from, what each vendor specializes in, and how long they usually take to deliver.

Quick reference (`data/campus_customs_new.db`, with real column names):

| Table | Columns | Rows in original data |
|---|---|---|
| `cash_accounts` | name, balance, date | 1 |
| `desk` | date_today, notes | 1 |
| `inventory` | sku, name, size, qty, location | 10 |
| `invoices` | id, vendor_id, amount, due_date, status, description | 1 |
| `leases` | id, space_name, landlord, monthly_rent, next_due, notes | 1 |
| `payments` | id, kind, ref_id, amount, account, paid_at, approved_by | 0 |
| `pricing` | sku, unit_cost, list_price | 4 |
| `tickets` | id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, notes, created_at | 3 |
| `vendors` | id, name, specialty, lead_days | 3 |

`data/campus_customs.db` is an untouched copy of the original. The backend's reset copies it back over `campus_customs_new.db`.

## MCP tools

The **check_inventory** tool reads the **inventory table** and helps unlock **tickets 101 and 103**. It checks how many units of a specific product and size are currently in stock so the agent can determine whether there is enough inventory to fulfill the request. The **get_product_pricing** tool reads the **pricing table** and helps unlock **ticket 103**. It returns the unit cost and list price for a specific product so the agent has the pricing information needed to evaluate the requested bulk discount. The **get_lease_details** tool reads the **leases table** and helps unlock **ticket 102**. It returns the relevant information about a specific lease, including the landlord, rent amount, and due date, so the agent can understand and respond to the rent notice.

### Every tool and who can use it

All shop facts come from the campus-customs MCP server (`mcp_server/server.py`) over `data/campus_customs_new.db`, connected through `hw5/.mcp.json`. Every tool an agent can use only reads the database. Each agent gets only the tools its job needs.

### MCP server tools

| Tool | What it does | Agents |
|---|---|---|
| `check_inventory` | Units in stock for one SKU and size, with product name and location | Inventory, Customer Service |
| `get_product_pricing` | A product's unit cost and list price | Accounting, Customer Service |
| `get_lease_details` | One lease: space, landlord, monthly rent, next due date, notes | Facilities |
| `get_ticket` | Every field of one ticket | All agents |
| `get_desk` | The shop's current date and desk notes | All agents |
| `list_tickets` | All tickets, or those with a given status | Boss |
| `list_inventory` | Every stock row, or every size of one SKU | Inventory, Customer Service |
| `find_low_stock` | Items at or below a reorder point (default 5), or where open tickets ask for more than is on hand, with the shortfall | Inventory |
| `list_vendors` | Vendors with specialty and lead time in days | Inventory, Accounting |
| `get_cash_accounts` | Cash account balances and the total | Accounting, Facilities |
| `list_invoices` | Vendor invoices with vendor name, days until due, and an overdue flag | Accounting |
| `get_invoice` | One invoice with vendor name, days until due, and an overdue flag | Accounting |
| `list_payments` | Payments already made | Accounting, Facilities |
| `list_leases` | All leases, with days until rent is due | Facilities |
| `calculate_margin` | Profit per unit, margin %, and totals at list price or a proposed discount price | Accounting |
| `quote_purchase_order` | Prices a restock order: estimated cost (qty × unit cost), vendor lead time, expected arrival, cash left afterward | Accounting |
| `quote_payment` | Looks up a rent or invoice payment: payee, amount, due date, whether already paid, cash left afterward | Accounting, Facilities |
| `record_approved_payment` | Pays rent or an invoice after a human clicks approve: records a `payments` row, takes it out of checking, and marks an invoice paid. The amount comes from the database. | No agent (the backend calls it for a human) |
| `record_approved_purchase_order` | Places a restock PO after a human clicks approve: re-prices it from `pricing`, records a `payments` row, and takes it out of checking | No agent (the backend calls it for a human) |

The two `record_approved_*` tools are the only writes to the database. They require an approver named `human:<name>`, and they refuse double payments, closed invoices, and anything checking can't cover.

### Team tools

These tools don't read the database themselves. Any shop facts they need come from the MCP tools above.

| Tool | What it does | Agents |
|---|---|---|
| `delegate` | Hands a task to another agent and returns their report. Any agent can reach any teammate; nobody can delegate to the Boss, whom only a human can start. | All agents |
| `prepare_purchase_order` | Saves a purchase order draft for human approval, priced by `quote_purchase_order` | Accounting |
| `prepare_payment_request` | Saves a rent or invoice payment draft for human approval, priced by `quote_payment` | Accounting, Facilities (rent only) |
| `draft_customer_message` | Saves a message to the ticket's requester for human review | Customer Service |

## The 5 agents

Built with PydanticAI on `gpt-5.6-luna` through Portkey. Each agent has its own file in `backend/` and its own prompt in `backend/prompts/`. Every prompt starts with the shared rules in `team.md`. Data types are in `backend/models.py`.

| Agent | Job | Tools (besides `get_ticket`, `get_desk`, `delegate`) | Returns |
|---|---|---|---|
| 🐶 Boss (`boss.py`) | Reads the ticket, delegates it, and makes the final call | `list_tickets` | `BossDecision`: decision, reasoning, recommended status, next steps, missing data |
| 📦 Inventory (`inventory.py`) | Checks stock by SKU and size, spots low stock, and picks the restock vendor | `check_inventory`, `list_inventory`, `find_low_stock`, `list_vendors` | `SpecialistReport` |
| 💰 Accounting (`accounting.py`) | Looks over cash and invoices, checks margins, and prepares purchase orders and payments for human approval | `get_cash_accounts`, `list_invoices`, `get_invoice`, `list_payments`, `get_product_pricing`, `calculate_margin`, `list_vendors`, `quote_purchase_order`, `quote_payment`, `prepare_purchase_order`, `prepare_payment_request` | `SpecialistReport` |
| 🔧 Facilities (`facilities.py`) | Shop upkeep: leases and rent | `get_lease_details`, `list_leases`, `get_cash_accounts`, `list_payments`, `quote_payment`, `prepare_payment_request` (rent only) | `SpecialistReport` |
| 💌 Customer Service (`customer_service.py`) | Drafts messages to customers for human review | `check_inventory`, `list_inventory`, `get_product_pricing`, `draft_customer_message` | `SpecialistReport` |

A `SpecialistReport` has a summary, the facts used (each with the tool it came from), a recommendation, a `needs_boss_decision` flag, and missing data.

How a ticket runs (`backend/team.py`, `backend/common.py`):
1. A human asks, through the dashboard or `run_ticket.py`, and the Boss starts.
2. The Boss reads the ticket and delegates. Teammates can delegate to each other, so the hand-offs form a chain like Boss → Inventory → Accounting.
3. Drafts go into a shared list. The Boss's decision plus every draft is saved to `output/ticket_runs/ticket_<id>.json`.
4. Every agent shares one MCP server process for the whole run.

## API routes

FastAPI app in `backend/main.py`. Start it from `backend/` with `uvicorn main:app --reload --port 8000`. CORS allows the dashboard at `http://localhost:5173`. All shop data comes through the MCP server; the backend never opens the database itself.

| Method and route | What it does |
|---|---|
| `GET /api/tickets` | Every ticket with its resolve status: `not_run`, `running`, `failed`, `awaiting_approval`, or `resolved` |
| `GET /api/tickets/{id}` | One ticket, its resolve status, and the team's full latest result (decision, drafts, hand-offs) |
| `POST /api/tickets/{id}/run` | Starts the agent team on a ticket. The body must name the human asking (`requested_by`). Only one run at a time. Returns right away; progress shows up in events. |
| `GET /api/events?ticket_id=&run_id=&after=` | Agent events from `output/audit_trail.json`, each with an index, so the dashboard can poll for new ones |
| `POST /api/tickets/{id}/approve` | A human approves one drafted payment or purchase order (`kind`, `index`, `approved_by`). Calls the MCP server's `record_approved_*` tool. |
| `GET /api/cash` | Current checking balance from `cash_accounts` |
| `POST /api/reset` | Restores the database to its original values (`requested_by`, `confirm: true`). Clears saved team results; the audit trail is kept and the reset is logged. |
| `GET /api/scores` | Real Yale Athletics scores for the dashboard ticker, from the yalebulldogs.com calendar feed (cached 15 minutes). Not shop data. |

## Dashboard

React + Vite + TypeScript in `frontend/`. Start it with `npm run dev` (port 5173, fixed so it always matches the backend's CORS setting). It only talks to the backend at `http://localhost:8000`. The design notes are in `output/design.md`.

- **Ticket desk:** the 3 tickets down the left side, each with a status badge (Not started, Agents working, Needs you, Resolved) and a "🚀 Send in the team" button.
- **Agent stage:** the Boss above the four teammates, each with an emoji avatar.
  - Each speech bubble says what the agent is doing right now, in plain words.
  - The agent working right now bounces and lights up. One waiting on a teammate gets a dashed border, and finished ones get a ✔.
  - A strip shows the live hand-off chain.
  - Seven dots per agent show how many of its 7 loops it has used.
- **Live feed:** every step, with a time, like a Twitter feed.
- **Permission slips:** drafted payments and purchase orders with Pay / Approve buttons, which send the "Human on duty" name as the approver. Approved slips get stamped. Draft customer messages are shown as "not sent".
- **Who did what:** the Boss's call and next steps, plus a card per agent with its summary, drafts, and tools used.
- **Checking balance:** a piggy bank in the header that rolls to the new balance after each approval. A "↺ Fresh run" button resets the database, after asking for confirmation.
- **Yale theme:** Yale blue and white with varsity fonts, a real Yale sports ticker, a Rivalry Row of Bulldogs fighting the Princeton Tiger, Columbia Lion, and Brown Bear, and a bulldog that peeks up from the corner.

## Safety guidelines

Agents should never make a payment, refund, or any customer communication without human approval. Each agent should loop a maximum of 7 times before it fails. Agents should not run unless explicitly asked. The boss must be asked by a human, and the others by either the boss or a human.

How the code enforces them:
- **Human approval:** no agent tool can pay, refund, or send anything. Agents can only save drafts marked `pending_human_approval` or `pending_human_review`. A payment or purchase happens only when a human clicks approve on the dashboard. That calls `POST /api/tickets/{id}/approve`, which calls the MCP server's `record_approved_*` tools with `approved_by = human:<name>`. Those tools are never given to an agent. There is no refund tool, and customer messages are never sent by the system.
- **7-loop limit:** a loop is one call to the model. If an agent tries an 8th loop, it fails with `AgentLoopLimitExceeded` (`MAX_AGENT_LOOPS = 7` in `backend/models.py`). When a delegated agent fails, the agent that delegated to it is told and carries on. If the Boss fails, the ticket run fails.
- **Only run when asked:** nothing starts the agents on its own. On the dashboard, a run starts only when a human clicks "Send in the team", and their name is sent as `requested_by`. `run_ticket.py` does nothing unless a human names the tickets or passes `--all-open`. Either way, the person who asked is recorded in the audit trail. Before any agent makes a model call, `check_run_allowed` (in `backend/common.py`) checks who asked:
  - **The Boss** must be started by a human. No agent can delegate to the Boss; teammates set `needs_boss_decision` instead.
  - **Every other agent** must be asked by a human directly, or be part of a chain the Boss started. Teammates can still hand work to each other inside a Boss-started chain.
  - A refused run fails before reaching the model, and it's logged as `agent_refused`.
- **Audit trail:** every loop step is added to `output/audit_trail.json`, which is never cleared. That includes each prompt, tool call, tool result, and answer, plus agent starts and ends, drafts, errors, human approvals, and database resets. If the backend restarts mid-run, the unfinished run is logged as `ticket_run_abandoned`.
- **Never invent data:** every prompt tells agents to state only numbers that come from a tool result, and to list anything missing instead of guessing. Money math comes from tools (`calculate_margin`, `quote_purchase_order`, `quote_payment`), not from the model.
- **No runaway runs:** each model call times out after 90 seconds. Each ticket run is capped at 80 model calls and 150 tool calls in total, delegation chains stop at 4 agents deep, and only one ticket runs at a time.
- **Resets are deliberate:** `POST /api/reset` requires a human's name and `confirm: true`, and is refused while a run is in progress.
