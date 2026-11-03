from pydantic import BaseModel, Field
from typing import Any
import logging

from app.whatsapp.client import WhatsAppClient
from app.database.db import Database

logger = logging.getLogger(__name__)

class GetUnreadChatsInput(BaseModel):
    pass  # No parameters needed

class GetUnreadChatsOutput(BaseModel):
    success: bool
    unread_chats: list[str] = Field(default_factory=list)
    error: str | None = None

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "whatsapp_get_unread_chats",
        "description": "Gets a list of all visible chats that currently have unread messages.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

async def execute(
    client: WhatsAppClient, 
    args: dict[str, Any], 
    db: Database | None = None
) -> BaseModel:
    """Gets a list of all visible chats that currently have unread messages."""
    try:
        # ════════════════════════════════════════════════════════════════════════
        # 🛠️ EXERCISE 4: EVENT SENSING (SCANNING FOR UNREAD BADGES)
        # ════════════════════════════════════════════════════════════════════════
        # CONCEPT:
        #   An agent should know when someone is waiting for a reply.
        #   In WhatsApp Web, unread chats display green notification badges.
        #
        # YOUR TASK:
        #   Call `await client.get_unread_chats()` to scan the sidebar!
        # ════════════════════════════════════════════════════════════════════════
        
        # TODO: Call client.get_unread_chats() to get the list:
        chats = await client.get_unread_chats()

        return GetUnreadChatsOutput(
            success=True,
            unread_chats=chats
        )

    except Exception as e:
        logger.error(f"Error in whatsapp_get_unread_chats: {e}")
        return GetUnreadChatsOutput(success=False, unread_chats=[], error=str(e))
