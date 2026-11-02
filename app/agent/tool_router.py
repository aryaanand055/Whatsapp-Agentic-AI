"""
Tool router — maps LLM function calls to tool implementations.

Converts OpenAI-style tool definitions (from each tool module) into
Gemini FunctionDeclaration format at runtime.
"""

import logging
from typing import Any, Dict, List, Optional
from google import genai
from google.genai import types

from app.whatsapp.client import WhatsAppClient
from app.agent.prompts import TOOL_DEFINITIONS
from app.tools import (
    whatsapp_search_contact,
    whatsapp_open_chat,
    whatsapp_read_messages,
    whatsapp_draft_message,
    whatsapp_send_message,
    whatsapp_manage_tasks,
    whatsapp_get_unread_chats,
    whatsapp_analyze_user_style,
    whatsapp_manage_memory,
    whatsapp_search_memory,
    whatsapp_open_chat_by_number,
    whatsapp_manage_autopilot,
)

logger = logging.getLogger(__name__)

def _openai_to_interactions_tool(tool_definitions: List[dict]) -> List[dict]:
    """Convert a list of OpenAI-format tool dicts into Gemini Interactions API format."""
    import copy
    declarations = []
    for tool_def in tool_definitions:
        if "function" in tool_def:
            func = copy.deepcopy(tool_def["function"])
            # Inject task_id into the schema dynamically
            if "parameters" in func and "properties" in func["parameters"]:
                func["parameters"]["properties"]["task_id"] = {
                    "type": "integer",
                    "description": "Optional: If this action is being performed as part of a tracked task from the Task Manager, provide the task ID here."
                }
            declarations.append({
                "type": "function",
                "name": func["name"],
                "description": func["description"],
                "parameters": func["parameters"]
            })
        else:
            declarations.append(tool_def)
    return declarations


# ── Router ────────────────────────────────────────────────


class ToolRouter:
    """Routes LLM tool calls to the correct Python function."""

    def __init__(
        self,
        whatsapp_client: WhatsAppClient,
        db: Any,
        genai_client: Optional[genai.Client] = None,
        model: str = "gemini-2.0-flash",
    ):
        self.whatsapp_client = whatsapp_client
        self.db = db
        self.genai_client = genai_client
        self.model = model
        self.tools = {
            "whatsapp_search_contact": whatsapp_search_contact.execute,
            "whatsapp_open_chat": whatsapp_open_chat.execute,
            "whatsapp_read_messages": whatsapp_read_messages.execute,
            "whatsapp_draft_message": whatsapp_draft_message.execute,
            "whatsapp_send_message": whatsapp_send_message.execute,
            "whatsapp_manage_tasks": whatsapp_manage_tasks.execute,
            "whatsapp_get_unread_chats": whatsapp_get_unread_chats.execute,
            "whatsapp_analyze_user_style": whatsapp_analyze_user_style.execute,
            "whatsapp_manage_memory": whatsapp_manage_memory.execute,
            "whatsapp_search_memory": whatsapp_search_memory.execute,
            "whatsapp_open_chat_by_number": whatsapp_open_chat_by_number.execute,
            "whatsapp_manage_autopilot": whatsapp_manage_autopilot.execute,
        }
        # Pre-compute Gemini tool objects once
        self._gemini_tools = _openai_to_interactions_tool(TOOL_DEFINITIONS)

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Return raw (OpenAI-style) tool definitions."""
        return TOOL_DEFINITIONS

    def get_gemini_tools(self) -> List[dict]:
        """Return Interactions API native Tool objects."""
        return self._gemini_tools

    async def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool by name with validated arguments."""
        # Extract task_id if present and remove it from arguments to avoid breaking strict Pydantic validation
        task_id = arguments.pop("task_id", None)
        
        if tool_name not in self.tools:
            error_msg = f"Unknown tool: {tool_name}"
            logger.error(error_msg)
            if self.db:
                await self.db.log_error(tool_name, "UnknownTool", error_msg)
                await self.db.log_tool_execution(tool_name, arguments, None, error_msg, task_id)
            return {"error": error_msg}

        tool_func = self.tools[tool_name]
        try:
            if tool_name in ["whatsapp_draft_message", "whatsapp_analyze_user_style"]:
                result = await tool_func(
                    self.whatsapp_client, arguments, self.db,
                    self.genai_client, self.model,
                )
            elif tool_name == "whatsapp_get_unread_chats":
                input_obj = whatsapp_get_unread_chats.GetUnreadChatsInput(**arguments)
                result = await whatsapp_get_unread_chats.execute(self.whatsapp_client, arguments, self.db)
            else:
                result = await tool_func(self.whatsapp_client, arguments, self.db)
                
            dumped_result = result.model_dump()
            if self.db:
                await self.db.log_tool_execution(tool_name, arguments, dumped_result, None, task_id)
            return dumped_result
        except Exception as e:
            error_msg = f"Error executing tool {tool_name}: {e}"
            logger.error(error_msg)
            if self.db:
                await self.db.log_error(tool_name, type(e).__name__, str(e))
                await self.db.log_tool_execution(tool_name, arguments, None, str(e), task_id)
            return {"error": error_msg}
