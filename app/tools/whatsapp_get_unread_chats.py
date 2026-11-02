from pydantic import BaseModel, Field
from typing import Any
import logging

from app.whatsapp.client import WhatsAppClient
from app.database.db import Database

logger = logging.getLogger(__name__)

class GetUnreadChatsInput(BaseModel):
    pass # No input required

class GetUnreadChatsOutput(BaseModel):
    success: bool
    unread_chats: list[str] = Field(default_factory=list)
    error: str | None = None

async def execute(
    client: WhatsAppClient, 
    args: dict[str, Any], 
    db: Database | None = None
) -> BaseModel:
    """Gets a list of all visible chats that currently have unread messages."""
    try:
        chats = await client.get_unread_chats()
        
        output = GetUnreadChatsOutput(
            success=True,
            unread_chats=chats
        )
        
            
        return output
    except Exception as e:
        logger.error(f"Error in whatsapp_get_unread_chats: {e}")
        error_output = GetUnreadChatsOutput(success=False, unread_chats=[], error=str(e))
        return error_output

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
