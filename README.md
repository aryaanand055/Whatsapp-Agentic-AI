# WhatsApp Multi-Agent Autonomous Assistant

An intelligent, autonomous multi-agent assistant for WhatsApp built using **FastAPI**, **Playwright**, **Google Gemini LLM**, **SQLite**, and **ChromaDB**. It provides human-in-the-loop controls, autopilot modes, persistent semantic memory, style profiling, and real-time monitoring via an interactive Web UI and terminal CLI.

---

## 🌟 Key Features

- **Multi-Agent Coordination Architecture**:
  - **CoordinatorAgent**: Orchestrates requests, routes communications, and delegates tasks.
  - **Dedicated Worker Agents**: Spawns isolated worker agents tailored per contact when automated triggers or alerts fire.
- **WhatsApp Web Automation via Playwright**:
  - Headless or headful browser automation with persistent session storage.
  - Contact searching, opening chats by name or direct phone number (`https://web.whatsapp.com/send?phone=...`).
  - Reading conversations, tracking unread badges, and streaming live DOM mutations for new incoming messages.
- **Safety & Human-in-the-Loop Confirmation**:
  - Critical actions (e.g. sending outbound messages) require explicit user approval (`confirmation_id` flow) unless autopilot is actively authorized for that contact.
- **Autopilot Mode**:
  - Time-bounded goal-driven auto-responder (`whatsapp_manage_autopilot`).
  - Automatically handles conversations towards specific objectives and expires after a configured duration.
- **Smart Style Mimicking**:
  - Analyzes the user's historical writing style (`whatsapp_analyze_user_style`) to craft natural, contextually consistent draft responses.
- **Hybrid Memory & Knowledge Management**:
  - Relational storage via **SQLite (aiosqlite)** for audit logs, pending confirmations, contact profiles, tasks, and autopilot configs.
  - Vector database via **ChromaDB** for semantic search across past conversations and user facts (`whatsapp_search_memory`, `whatsapp_manage_memory`).
- **Interactive Web Interface & CLI**:
  - **Modern Web Dashboard**: Real-time server-sent event (SSE) updates, active sub-agent monitoring, task creation, chat interface, and approval dialogs.
  - **Audit Logs View** (`/audit`): Inspect tool execution traces, inputs, outputs, errors, and task IDs.
  - **Rich CLI**: Interactive command-line chat session powered by `prompt_toolkit` and `rich`.

---

## 🏗 System Architecture

```
                      +-----------------------------+
                      | User (CLI / Web Dashboard)  |
                      +--------------+--------------+
                                     |
                                     v
                       +---------------------------+
                       | FastAPI Server / CLI Core |
                       +-------------+-------------+
                                     |
                                     v
                       +---------------------------+
                       |     CoordinatorAgent      |
                       +-------------+-------------+
                                     |
                 +-------------------+-------------------+
                 |                                       |
                 v                                       v
         +---------------+                       +---------------+
         |  Main Worker  |                       | Contact Worker|
         |  (User Tasks) |                       |  (Autopilot)  |
         +-------+-------+                       +-------+-------+
                 |                                       |
                 +-------------------+-------------------+
                                     |
                                     v
                           +-------------------+
                           |    ToolRouter     |
                           +---------+---------+
                                     |
          +--------------------------+--------------------------+
          |                          |                          |
          v                          v                          v
+-------------------+      +-------------------+      +-------------------+
|  WhatsAppClient   |      |  SQLite Database  |      | ChromaDB (Vector) |
|   & Playwright    |      | (Tasks, Audits,   |      | (Semantic Memory, |
|   Browser Hub     |      |  Autopilot state) |      |   User Facts)     |
+-------------------+      +-------------------+      +-------------------+
```

---

## 🛠 Included Agent Tools

The agent leverages Google Gemini function calling connected through the `ToolRouter`:

| Tool                             | Description                                                                   |
| :------------------------------- | :---------------------------------------------------------------------------- |
| `whatsapp_search_contact`      | Searches WhatsApp contacts and chats matching a query.                        |
| `whatsapp_open_chat`           | Opens an existing chat conversation by contact/group name.                    |
| `whatsapp_open_chat_by_number` | Opens a chat directly using an international phone number.                    |
| `whatsapp_read_messages`       | Fetches the recent message history from the active conversation.              |
| `whatsapp_get_unread_chats`    | Identifies all chats with unread messages and extracts previews.              |
| `whatsapp_draft_message`       | Composes a tailored reply based on instructions and user style.               |
| `whatsapp_send_message`        | Requests confirmation or directly sends a message (if autopilot permitted).   |
| `whatsapp_manage_tasks`        | Creates, lists, updates, or completes agent background tasks.                 |
| `whatsapp_manage_memory`       | Stores or deletes persistent facts and memories (global or contact-specific). |
| `whatsapp_search_memory`       | Semantic vector search across stored memories using ChromaDB.                 |
| `whatsapp_analyze_user_style`  | Evaluates past outgoing messages to generate a style profile.                 |
| `whatsapp_manage_autopilot`    | Activates, inspects, or cancels autonomous response policies for a contact.   |

---

## 📋 Prerequisites

- **Python**: 3.11 or higher
- **Google Chrome** installed locally
- **Google Gemini API Key** (e.g. `gemini-2.0-flash` or `gemini-1.5-flash`)

---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone <repo-url>
cd Multiagent
```

### 2. Install Dependencies & Playwright

```bash
pip install -r requirements.txt
playwright install
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Gemini API Key
LLM_PROVIDER=gemini
LLM_API_KEY=your-gemini-api-key-here
LLM_MODEL=gemini-2.0-flash

# API Security & Server
API_KEY=your-secure-random-secret
API_HOST=127.0.0.1
API_PORT=8000

# WhatsApp Storage & Browser
WHATSAPP_PROFILE_DIR=storage/whatsapp_profile
WHATSAPP_HEADLESS=false

# Storage & Logging
LOG_LEVEL=INFO
DATABASE_URL=sqlite+aiosqlite:///storage/agent.db
```

> **Note on First Run**: Keep `WHATSAPP_HEADLESS=false` on initial launch so you can scan the WhatsApp Web QR code in the browser window. Once scanned, the session is saved in `storage/whatsapp_profile`.

---

## 💻 Running the Application

### Option A: Web Server & UI Dashboard (Recommended)

Start the FastAPI application:

```bash
python -m app.main --mode server
```

Open your browser to:

- **Chat Dashboard**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Audit Logs**: [http://127.0.0.1:8000/audit](http://127.0.0.1:8000/audit)
- **Interactive OpenAPI Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Option B: Interactive CLI Mode

Run directly in the console with interactive prompts:

```bash
python -m app.main --mode cli
```

CLI Commands:

- Type your natural language request directly (e.g., *"Check unread messages and draft a response to John"*).
- `status`: Show WhatsApp connection and login state.
- `/tasks`: List all managed tasks and their status.
- `quit` / `exit`: Safely shut down background listeners and browser session.

---

## 📡 REST API Reference

All protected endpoints require authentication via the `X-API-Key` header or `?api_key=` query parameter.

| Method   | Endpoint               | Description                                                                                 |
| :------- | :--------------------- | :------------------------------------------------------------------------------------------ |
| `GET`  | `/health`            | Unauthenticated server health probe.                                                        |
| `GET`  | `/agent/list`        | List all active coordinator and contact sub-agents.                                         |
| `POST` | `/agent/message`     | Send prompt to CoordinatorAgent (`{"message": "...", "session_id": "..."}`).              |
| `GET`  | `/notifications`     | Server-Sent Events (SSE) stream for live agent events and incoming alerts.                  |
| `GET`  | `/whatsapp/status`   | Current WhatsApp Web connection status.                                                     |
| `POST` | `/whatsapp/search`   | Search contacts (`{"name": "..."}`).                                                      |
| `POST` | `/whatsapp/read`     | Read messages (`{"contact": "...", "limit": 10}`).                                        |
| `POST` | `/whatsapp/draft`    | Draft message with style adaptation (`{"contact": "...", "instruction": "..."}`).         |
| `POST` | `/whatsapp/send`     | Stage or send message (`{"contact": "...", "message": "...", "confirmation_id": "..."}`). |
| `POST` | `/whatsapp/confirm`  | Confirm execution of staged send (`{"confirmation_id": "..."}`).                          |
| `GET`  | `/tasks`             | Retrieve all tasks from database.                                                           |
| `GET`  | `/autopilot/configs` | Retrieve all active autopilot configurations.                                               |
| `GET`  | `/audit/logs`        | Fetch paginated execution audit records (`?limit=100&offset=0`).                          |

---

## 🛡️ Security & Privacy

1. **Local Browser Isolation**: Playwright stores the WhatsApp session profile strictly on your local disk (`storage/whatsapp_profile`). No session tokens or cookies leave your machine.
2. **Action Confirmation**: Destructive or outbound actions require human confirmation by default unless explicitly delegated under a temporary Autopilot goal.
3. **Local Database & Vector Store**: Both SQLite and ChromaDB persist records on your filesystem.
4. **API Protection**: All REST endpoints are protected by `X-API-Key` validation.

---

## 🧪 Testing

Run unit and integration test suites:

```bash
pytest app/tests/
```

To run individual tests:

```bash
pytest app/tests/test_agent.py
pytest app/tests/test_tools.py
```

---

## 📁 Project Structure

```
Multiagent/
├── app/
│   ├── agent/                 # Agent loop, coordinator, router, and prompts
│   │   ├── agent.py           # CoordinatorAgent & WorkerAgent implementations
│   │   ├── prompts.py         # System prompt & tool JSON schema definitions
│   │   └── tool_router.py     # Tool dispatch and OpenAI -> Gemini schema conversion
│   ├── api/                   # FastAPI backend endpoints and static routing
│   │   └── server.py
│   ├── database/              # Persistence layer
│   │   ├── db.py              # SQLite & ChromaDB client wrapper
│   │   └── models.py          # SQL DDL schemas
│   ├── tools/                 # Atomic tool implementations for agent actions
│   │   ├── whatsapp_send_message.py
│   │   ├── whatsapp_manage_autopilot.py
│   │   ├── whatsapp_search_memory.py
│   │   └── ...
│   ├── whatsapp/              # Playwright automation engine
│   │   ├── browser.py         # Chromium lifecycle & persistent context
│   │   ├── client.py          # WhatsApp Web action wrappers
│   │   └── selectors.py       # Resilient DOM selectors
│   ├── config.py              # Pydantic environment configuration
│   └── main.py                # Application entrypoint (CLI / Server modes)
├── frontend/                  # Web dashboard & Audit UI
│   ├── index.html             # Main agent chat interface
│   ├── audit.html             # Tool execution audit explorer
│   ├── css/
│   └── js/
├── storage/                   # Database, vector stores, and browser profiles
├── requirements.txt           # Python package dependencies
└── README.md
```
