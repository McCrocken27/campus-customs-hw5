# Campus Customs HQ: HW5 agent team 🐶

A team of five AI agents (Boss, Inventory, Accounting, Facilities, Customer Service) that responds to Campus Customs desk tickets. Every shop fact comes from an MCP server over a SQLite database. A FastAPI backend runs the team, and a Yale-themed React dashboard lets a human watch the agents work and approve payments and purchases.

- **Agents:** PydanticAI on `gpt-5.6-luna` through Portkey (`backend/`)
- **Shop data:** FastMCP server over `data/campus_customs_new.db` (`mcp_server/`)
- **API:** FastAPI (`backend/main.py`)
- **Dashboard:** React + Vite + TypeScript (`frontend/`)
- **Full write-up:** `output/harness.md` (tables, MCP tools, agents, API routes, dashboard, safety rules)

## Layout

```
hw5/
├── AI_prompts.md          every prompt given to the AI assistant, by problem
├── requirements.txt       Python packages for the backend, agents, and MCP server
├── .env.example           copy to .env and add your Portkey key
├── .mcp.json              how Claude Code (and the backend) start the MCP server
├── data/
│   ├── campus_customs.db       untouched original (used by reset)
│   └── campus_customs_new.db   working copy the agents use
├── mcp_server/            server.py (FastMCP tools) and README.md
├── backend/               main.py (API), models.py, one file per agent, prompts/
├── frontend/              the React dashboard
└── output/                harness, smoke test, desk tickets, design notes, results, audit trail
```

## Setup

You need Python 3.12+ and Node.js 20+.

1. Clone the repo and open a terminal in it:
   ```bash
   git clone https://github.com/McCrocken27/campus-customs-hw5.git
   cd campus-customs-hw5
   ```
2. Make a Python environment and install the packages:
   ```bash
   python -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   ```
   (On Mac/Linux use `.venv/bin/python` instead of `.venv\Scripts\python`.)
3. Add your API key: copy `.env.example` to `.env` and put your Portkey key after `PORTKEY_API_KEY=`.
4. Install the dashboard's packages:
   ```bash
   cd frontend
   npm install
   cd ..
   ```

## Run it

1. Start the backend from the `backend` folder:
   ```bash
   cd backend
   ..\.venv\Scripts\uvicorn main:app --reload --port 8000
   ```
   It starts the MCP server for you, using the same Python. API docs: http://localhost:8000/docs
2. In a second terminal, start the dashboard from the `frontend` folder:
   ```bash
   cd frontend
   npm run dev
   ```
3. Open http://localhost:5173. Type your name under "Human on duty", then click **Send in the team** on a ticket.

To run a ticket from the command line instead, run this from `backend/`: `..\.venv\Scripts\python run_ticket.py 101`

## Safety

- Agents never pay, refund, or message anyone. They only save drafts. A payment or purchase happens only when a human clicks approve on the dashboard.
- Each agent may make at most 7 model calls per run, and each model call times out after 90 seconds.
- Agents only run when a human asks. Only a human can start the Boss.
- Every agent step is appended to `output/audit_trail.json`, which is never cleared.
- **↺ Fresh run** on the dashboard (or `POST /api/reset`) copies `data/campus_customs.db` back over the working database.

The committed `campus_customs_new.db`, `output/ticket_runs/`, and `output/audit_trail.json` show the state after the HW5 runs. All 3 tickets are resolved, and checking went from $3,400.00 to $728.00. Reset to start over.
