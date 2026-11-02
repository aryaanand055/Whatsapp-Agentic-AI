# 🚀 1-Hour Agentic AI Workshop: Build an Autonomous WhatsApp Agent

Welcome to the **Agentic AI Workshop**! Today you will learn how to transition from building simple chatbots (*"brains in a jar"*) to building an **autonomous AI agent** that can perceive, reason, and act in the real world using **Google Gemini** and browser automation.

---

## 🧭 Workshop Overview & Roadmap

### What Makes an "AI Agent"?

$$\text{Agent} = \text{LLM Reasoning (Brain)} + \text{Tools (Hands)} + \text{Sensors (Perception)} + \text{Human-in-the-Loop (Safety Guardrails)}$$

In this workshop, you will follow the **ReAct (Reason + Act)** pattern:
1. **User Request**: *"Check what Rahul sent me and reply that I am running 10 minutes late."*
2. **Thought**: The agent decides which tools it needs to call and in what order.
3. **Action**: The agent executes a tool (e.g. `whatsapp_search_contact`).
4. **Observation**: The agent reads the result returned from the tool.
5. **Safety Gate**: Before sending any message out into the real world, the agent pauses and asks you for explicit confirmation!

---

## ⏱️ The 60-Minute Game Plan

```
[Level 1: The Brain] ──> [Level 2: The Hands] ──> [Level 3: Perception] ──> [Level 4: Safety & Autonomy]
    (Hello Gemini)           (Search & Open)           (Read & Draft)           (Send with Confirmation)
```

| Time | Milestone | Tools Explored / Implemented |
| :--- | :--- | :--- |
| **00:00 - 00:10** | **The Hook & Concepts** | Live demo: Agent checks unread WhatsApp messages & drafts replies. Core Agentic loops. |
| **00:10 - 00:22** | **Level 1: Finding & Opening Chats** | `whatsapp_search_contact` & `whatsapp_open_chat` |
| **00:22 - 00:35** | **Level 2: Reading & Context Perception** | `whatsapp_read_messages` & `whatsapp_get_unread_chats` |
| **00:35 - 00:45** | **Level 3: Context-Aware Drafting** | `whatsapp_draft_message` (feeding history into Gemini) |
| **00:45 - 00:55** | **Level 4: Human-in-the-Loop Safety** | `whatsapp_send_message` with confirmation gate |
| **00:55 - 01:00** | **Live Interactive Challenge** | Text each other! Let your agents detect, draft, and confirm replies. |

---

## 🛠️ Getting Started (Pre-Flight Setup)

### 1. Prerequisites
- **Python 3.11+** installed
- **Google Chrome** installed
- A **Gemini API Key** from [Google AI Studio](https://aistudio.google.com/)

### 2. Install Dependencies
```bash
pip install -r requirements.txt
playwright install
```

### 3. Setup Your `.env` File
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Open `.env` and insert your Gemini API Key:
```env
LLM_PROVIDER=gemini
LLM_API_KEY=your_actual_gemini_api_key_here
LLM_MODEL=gemini-2.0-flash
WHATSAPP_HEADLESS=false
```

### 4. Verify That Everything Runs
Run the test suite to make sure the environment is green:
```bash
pytest app/tests/test_tools.py
```
*(All tests should pass right out of the box!)*

---

## 🏃 Running the Workshop Agent

### Interactive Terminal Mode (CLI)
Start the agent in the command line:
```bash
python -m app.main --mode cli
```
1. On first run, a Chrome browser will open displaying the WhatsApp Web QR code.
2. Scan it with your phone's WhatsApp app (**Linked Devices** $\rightarrow$ **Link a Device**).
3. Once logged in, your terminal will show:
   ```
   WhatsApp Agent is ready!
   Type 'quit', 'exit', or 'status'.
   You: 
   ```

---

## 🧩 Workshop Exercises: Step-by-Step

In each of the files below, look for the banner:
```python
# ── WORKSHOP EXERCISE: TOOL #X ──────────────────────────────
```
The implementation is ready to run, but we will inspect the code, modify parameters, and see how Gemini responds to tool changes.

### Exercise 1: Contact Search (`whatsapp_search_contact.py`)
- **File**: [`app/tools/whatsapp_search_contact.py`](file:///D:/Desktop/Arya/Projects/Multiagent/app/tools/whatsapp_search_contact.py)
- **Concept**: Tool schemas. Notice how Pydantic's `SearchContactInput.model_json_schema()` tells Gemini what arguments are required.
- **Try it in CLI**:
  ```
  You: Search for my friend Rahul on WhatsApp
  ```

### Exercise 2: Navigating to Chats (`whatsapp_open_chat.py`)
- **File**: [`app/tools/whatsapp_open_chat.py`](file:///D:/Desktop/Arya/Projects/Multiagent/app/tools/whatsapp_open_chat.py)
- **Concept**: Translating natural intent into browser actions via `client.open_chat(contact)`.
- **Try it in CLI**:
  ```
  You: Open the chat with Rahul
  ```

### Exercise 3: Reading Recent Messages (`whatsapp_read_messages.py`)
- **File**: [`app/tools/whatsapp_read_messages.py`](file:///D:/Desktop/Arya/Projects/Multiagent/app/tools/whatsapp_read_messages.py)
- **Concept**: Perception. Scrapes messages from the DOM and categorizes them with `is_from_me` so the LLM understands who said what.
- **Try it in CLI**:
  ```
  You: Read the last 3 messages from Rahul
  ```

### Exercise 4: Reading Unread Badges (`whatsapp_get_unread_chats.py`)
- **File**: [`app/tools/whatsapp_get_unread_chats.py`](file:///D:/Desktop/Arya/Projects/Multiagent/app/tools/whatsapp_get_unread_chats.py)
- **Concept**: Event detection. Identifies chats that have unread notification badges.
- **Try it in CLI**:
  ```
  You: Do I have any unread WhatsApp messages right now?
  ```

### Exercise 5: Smart Drafting (`whatsapp_draft_message.py`)
- **File**: [`app/tools/whatsapp_draft_message.py`](file:///D:/Desktop/Arya/Projects/Multiagent/app/tools/whatsapp_draft_message.py)
- **Concept**: Contextual drafting. The agent pulls recent messages from the chat, feeds them as conversation context into Gemini, and produces natural, realistic text replies.
- **Try it in CLI**:
  ```
  You: Draft a polite response telling them I will call them back in an hour
  ```

### Exercise 6: Safe Sending with Human Confirmation (`whatsapp_send_message.py`)
- **File**: [`app/tools/whatsapp_send_message.py`](file:///D:/Desktop/Arya/Projects/Multiagent/app/tools/whatsapp_send_message.py)
- **Concept**: **Human-in-the-Loop Guardrail**. If `confirmed=False`, the message is saved as a *pending confirmation* in SQLite, returning a `confirmation_id`. The user must confirm before the message is dispatched.
- **Try it in CLI**:
  ```
  You: Send a message to Rahul saying "See you at the library"
  ```
  Watch the CLI intercept the call:
  ```
  Agent: I have drafted your message to Rahul: "See you at the library".
  Do you want to confirm this action? (y/n): 
  ```

---

## 🔮 What Comes Next? (Take-Home Advanced Roadmap)

Once you've mastered the 6 core tools today, the remaining half of the project introduces **Production-Grade Multi-Agent Architecture**:

1. **Direct Number Navigation (`whatsapp_open_chat_by_number.py`)**:
   Open conversations with unsaved numbers using international phone URLs.
2. **Writing Style Profiling (`whatsapp_analyze_user_style.py`)**:
   Analyzes your past sent messages to replicate your tone, emoji frequency, and vocabulary.
3. **Semantic Long-Term Memory with ChromaDB (`whatsapp_manage_memory.py` & `whatsapp_search_memory.py`)**:
   Store user facts (e.g. *"Mom's name is Priya"*, *"I prefer vegetarian food"*) into an embedded Vector Database so the agent remembers context across sessions.
4. **Task Management System (`whatsapp_manage_tasks.py`)**:
   Track long-running multi-step goals with state tracking in SQLite.
5. **Autopilot Mode (`whatsapp_manage_autopilot.py` & Multi-Agent Coordinator)**:
   Grant the agent temporary, time-bounded permission to negotiate or auto-reply to specific contacts autonomously!
6. **Web UI & Audit Dashboard**:
   Run `python -m app.main --mode server` and explore the real-time web dashboard at `http://localhost:8000/` and audit logs at `http://localhost:8000/audit`.

---

Happy Hacking! Build responsibly and have fun with Agentic AI! 🤖✨
