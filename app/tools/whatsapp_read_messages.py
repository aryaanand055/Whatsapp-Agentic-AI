import logging
from typing import Optional, Any
from pydantic import BaseModel, Field

from app.whatsapp.client import WhatsAppClient

logger = logging.getLogger(__name__)

class ReadMessagesInput(BaseModel):
    contact: str = Field(..., description="The contact name whose messages to read")
    limit: int = Field(default=10, description="Maximum number of messages to read")

class ReadMessagesOutput(BaseModel):
    success: bool
    contact: str
    messages: list[dict] = Field(default_factory=list)
    error: Optional[str] = None

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "whatsapp_read_messages",
        "description": "Read recent messages from a specific contact's chat.",
        "parameters": ReadMessagesInput.model_json_schema()
    }
}

async def execute(client: WhatsAppClient, args: dict, db: Any = None) -> ReadMessagesOutput:
    """
    Execute the whatsapp_read_messages tool.
    """
    try:
        input_data = ReadMessagesInput(**args)
        
        # ════════════════════════════════════════════════════════════════════════
        # 🛠️ WORKSHOP EXERCISE #3: READ MESSAGES (PERCEPTION)
        # ════════════════════════════════════════════════════════════════════════
        # GOAL:
        #   Scrape the recent messages from the active chat so Gemini has context.
        #
        # HINT:
        #   1. Call: chat_messages = await client.get_recent_messages(input_data.contact, input_data.limit)
        #   2. Build list of dicts with: sender, timestamp, text, is_from_me
        #
        # (See solutions/SOLUTIONS.md if you get stuck!)
        # ════════════════════════════════════════════════════════════════════════
        
        # YOUR CODE HERE:
        chat_messages = await client.get_recent_messages(input_data.contact, input_data.limit)
        messages = [
            {
                "sender": msg.sender,
                "timestamp": msg.timestamp,
                "text": msg.text,
                "is_from_me": msg.is_from_me
            } for msg in chat_messages.messages
        ]
        
        return ReadMessagesOutput(
            success=True,
            contact=input_data.contact,
            messages=messages
        )
    except Exception as e:
        logger.error(f"Error in whatsapp_read_messages: {e}")
        return ReadMessagesOutput(success=False, contact=args.get("contact", ""), error=str(e))
