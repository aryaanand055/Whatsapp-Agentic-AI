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
    whatsapp_get_unread_chats,
)

logger = logging.getLogger(__name__)

def _openai_to_interactions_tool(tool_definitions: List[dict]) -> List[dict]:
    """Convert a list of OpenAI-format tool dicts into Gemini Interactions API format."""
    import copy
    declarations = []
    for tool_def in tool_definitions:
        if "function" in tool_def:
            func = copy.deepcopy(tool_def["function"])
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
            "whatsapp_get_unread_chats": whatsapp_get_unread_chats.execute,
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
        if tool_name not in self.tools:
            logger.error("Unknown tool requested: %s", tool_name)
            return {"success": False, "error": f"Unknown tool: {tool_name}"}

        func = self.tools[tool_name]
        logger.info("Calling tool %s with args %s", tool_name, arguments)

        try:
            # Special case tools that need extra dependencies
            if tool_name == "whatsapp_draft_message":
                output = await func(
                    self.whatsapp_client,
                    arguments,
                    db=self.db,
                    genai_client=self.genai_client,
                    model=self.model,
                )
            else:
                output = await func(self.whatsapp_client, arguments, db=self.db)

            # Output is a Pydantic model; convert to dict
            result = output.model_dump()
            logger.info("Tool %s finished. Success: %s", tool_name, result.get("success"))

            if self.db:
                await self.db.log_tool_execution(tool_name, arguments, result, None)

            return result

        except Exception as e:
            logger.exception("Error executing tool %s: %s", tool_name, e)
            if self.db:
                await self.db.log_tool_execution(tool_name, arguments, None, str(e))
            return {"success": False, "error": str(e)}
