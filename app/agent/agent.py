"""
WhatsApp Agent — LLM conversation loop using Google Gemini.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from google import genai
from google.genai import types

from app.whatsapp.client import WhatsAppClient
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tool_router import ToolRouter

logger = logging.getLogger(__name__)


class AgentResponse(BaseModel):
    """Structured response from the agent."""
    response: str
    actions: List[Dict[str, Any]] = []
    requires_confirmation: bool = False
    confirmation_id: Optional[str] = None


class WorkerAgent:
    """AI agent that interacts with WhatsApp through structured tools.

    Uses Google Gemini for LLM reasoning and function calling.
    """

    def __init__(self, whatsapp_client: WhatsAppClient, db: Any, settings: Any):
        self.whatsapp_client = whatsapp_client
        self.db = db
        self.settings = settings
        self.genai_client: Optional[genai.Client] = None
        self.tool_router: Optional[ToolRouter] = None
        # In-memory conversation history keyed by session_id.
        # The Interactions API handles state server-side, so we only need to store the interaction ID.
        self._sessions: Dict[str, str] = {}
        self.is_thinking: bool = False

    async def initialize(self) -> None:
        """Set up the Gemini client and tool router."""
        self.genai_client = genai.Client(api_key=self.settings.llm_api_key)
        self.tool_router = ToolRouter(
            whatsapp_client=self.whatsapp_client,
            db=self.db,
            genai_client=self.genai_client,
            model=self.settings.llm_model,
        )
        logger.info("WhatsAppAgent initialized with Gemini model %s.", self.settings.llm_model)

    # ── public API ────────────────────────────────────────

    async def chat(self, user_message: str, session_id: str = "default", on_tool_call: Optional[Any] = None) -> AgentResponse:
        """Process a user message: reason, call tools, and return a response."""
        if not self.genai_client or not self.tool_router:
            raise RuntimeError("Agent not initialized. Call initialize() first.")

        self.is_thinking = True
        try:
            previous_interaction_id = self._sessions.get(session_id)
            
            kwargs = {
                "model": self.settings.llm_model,
                "input": user_message,
                "tools": self.tool_router.get_gemini_tools(),
                "system_instruction": SYSTEM_PROMPT,
            }
            if previous_interaction_id:
                kwargs["previous_interaction_id"] = previous_interaction_id

            try:
                interaction = await self.genai_client.aio.interactions.create(**kwargs)
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower() or "too_many_requests" in str(e).lower():
                    logger.warning("Rate limit hit, falling back to gemini-2.5-flash")
                    kwargs["model"] = "gemini-2.5-flash"
                    interaction = await self.genai_client.aio.interactions.create(**kwargs)
                else:
                    raise
            self._sessions[session_id] = interaction.id

            actions: List[Dict[str, Any]] = []
            requires_confirmation = False
            confirmation_id: Optional[str] = None

            # Agentic loop for function calls
            while True:
                # Find all function calls that do not have a corresponding function_result
                all_steps = getattr(interaction, "steps", []) or []
                function_calls = [s for s in all_steps if getattr(s, "type", "") == "function_call"]
                function_results = {getattr(s, "call_id", "") for s in all_steps if getattr(s, "type", "") == "function_result"}
                
                waiting_calls = [
                    step for step in function_calls
                    if getattr(step, "id", "") not in function_results
                ]

                if getattr(interaction, "status", "") != "requires_action" and not waiting_calls:
                    # If there are no waiting calls, the interaction is complete
                    break

                func_results_input = []
                
                for step in waiting_calls:
                    tool_name = getattr(step, "name", "")
                    arguments = getattr(step, "arguments", {})
                
                    logger.info("Executing tool %s with args %s", tool_name, arguments)
                    if on_tool_call:
                        import asyncio
                        if asyncio.iscoroutinefunction(on_tool_call):
                            await on_tool_call(tool_name, arguments)
                        else:
                            on_tool_call(tool_name, arguments)
                            
                    result = await self.tool_router.execute_tool(tool_name, arguments)

                    func_results_input.append({
                        "type": "function_result",
                        "call_id": getattr(step, "id", ""),
                        "name": tool_name,
                        "result": result,
                    })

                    actions.append({
                        "tool": tool_name,
                        "status": "success" if result.get("success", False) else "error",
                        "result": result,
                    })

                    if tool_name == "whatsapp_send_message" and result.get("requires_confirmation"):
                        requires_confirmation = True
                        confirmation_id = result.get("confirmation_id")

                if func_results_input:
                    kwargs["input"] = func_results_input
                    kwargs["previous_interaction_id"] = interaction.id
                    try:
                        interaction = await self.genai_client.aio.interactions.create(**kwargs)
                    except Exception as e:
                        if "429" in str(e) or "quota" in str(e).lower() or "too_many_requests" in str(e).lower():
                            logger.warning("Rate limit hit during function callback, falling back to gemini-2.5-flash")
                            kwargs["model"] = "gemini-2.5-flash"
                            interaction = await self.genai_client.aio.interactions.create(**kwargs)
                        else:
                            raise
                    self._sessions[session_id] = interaction.id
                else:
                    break

            final_response_text = getattr(interaction, "output_text", "")

            return AgentResponse(
                response=final_response_text,
                actions=actions,
                requires_confirmation=requires_confirmation,
                confirmation_id=confirmation_id,
            )

        finally:
            self.is_thinking = False

    async def confirm_send(self, confirmation_id: str) -> Dict[str, Any]:
        """Confirm and execute a pending message send."""
        pending = await self.db.confirm_pending(confirmation_id)
        if not pending:
            return {"success": False, "error": "Invalid or expired confirmation_id"}

        contact = pending.get("contact")
        message_str = pending.get("message")

        if not contact or not message_str:
            return {"success": False, "error": "Invalid pending message data"}
            
        import json
        try:
            message = json.loads(message_str)
            if not isinstance(message, list):
                message = [message]
        except Exception:
            # Fallback for old pending confirmations that might just be strings
            message = [message_str]

        success = await self.whatsapp_client.send_message(contact, message)
        return {
            "success": success,
            "contact": contact,
            "message": message,
            "error": None if success else "Failed to send message",
        }

class CoordinatorAgent:
    """Central coordinator that manages multiple WorkerAgents."""
    
    def __init__(self, whatsapp_client: WhatsAppClient, db: Any, settings: Any):
        self.whatsapp_client = whatsapp_client
        self.db = db
        self.settings = settings
        self.workers: Dict[str, WorkerAgent] = {}
        # Main agent for handling user commands directly
        self.main_agent = self._create_worker()

    def _create_worker(self) -> WorkerAgent:
        return WorkerAgent(self.whatsapp_client, self.db, self.settings)

    async def initialize(self) -> None:
        """Initialize the main agent."""
        await self.main_agent.initialize()
        logger.info("CoordinatorAgent initialized.")

    async def get_worker_for_contact(self, contact: str) -> WorkerAgent:
        """Get or create a dedicated worker agent for a specific contact."""
        if contact not in self.workers:
            worker = self._create_worker()
            await worker.initialize()
            self.workers[contact] = worker
            logger.info("Spawned new WorkerAgent for contact: %s", contact)
        return self.workers[contact]

    async def chat(self, user_message: str, session_id: str = "default", on_tool_call: Optional[Any] = None) -> AgentResponse:
        """
        Route chat messages. 
        If the message implies a background system alert (e.g. from a contact), route it to the specific worker.
        Otherwise, route it to the main agent.
        """
        import re
        
        # Check for system alert: "System Alert: New messages detected in the following chats: Contact Name."
        # or "System Alert: New unread messages detected:\n- Contact: 'Josana'..."
        if "System Alert: New unread messages detected" in user_message or "System Alert: New messages detected" in user_message:
            # Try to extract contact name
            match = re.search(r"Contact: '([^']+)'", user_message)
            if not match:
                match = re.search(r"following chats:\s*([^.]+)\.", user_message)
                
            if match:
                # If there are multiple names (comma separated), just take the first one for the agent spawn for simplicity
                contact_names = [name.strip() for name in match.group(1).split(",")]
                if contact_names:
                    contact = contact_names[0]
                    worker = await self.get_worker_for_contact(contact)
                    return await worker.chat(user_message, session_id, on_tool_call)
        
        return await self.main_agent.chat(user_message, session_id, on_tool_call)

    async def confirm_send(self, confirmation_id: str) -> Dict[str, Any]:
        """Delegate confirmation to the main agent."""
        return await self.main_agent.confirm_send(confirmation_id)

    def get_active_agents(self) -> List[Dict[str, str]]:
        """Return a list of all active agents for the web UI."""
        main_status = "Thinking..." if self.main_agent.is_thinking else "Idle"
        agents = [{"id": "main", "name": "Coordinator Agent", "status": main_status}]
        for contact, worker in self.workers.items():
            if worker.is_thinking:
                agents.append({"id": f"worker_{contact}", "name": f"Agent for {contact}", "status": "Thinking..."})
        return agents


# Backwards compatibility alias
WhatsAppAgent = WorkerAgent
