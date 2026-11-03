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
    """Execute the whatsapp_read_messages tool."""
    try:
        input_data = ReadMessagesInput(**args)
        
        # 1. Fetch recent messages using Playwright
        chat_messages = await client.get_recent_messages(input_data.contact, input_data.limit)

        # ════════════════════════════════════════════════════════════════════════
        # 🛠️ EXERCISE 3: PERCEPTION — "WHO SAID WHAT?"
        # ════════════════════════════════════════════════════════════════════════
        # CONCEPT:
        #   Raw HTML only gives us message text bubbles. But to give Gemini true
        #   perception, we MUST tell it WHO sent each message!
        #
        # YOUR TASK:
        #   Loop through `chat_messages.messages`.
        #   If `msg.is_from_me` is True, set sender to "Me".
        #   Otherwise, set sender to the friend's name (`input_data.contact`).
        # ════════════════════════════════════════════════════════════════════════
        
        # TODO: Format each message so Gemini knows the sender:
        formatted_messages = []
        for msg in chat_messages.messages:
            sender = "Me" if msg.is_from_me else input_data.contact
            formatted_messages.append({
                "sender": sender,
                "text": msg.text,
                "timestamp": msg.timestamp,
                "is_from_me": msg.is_from_me
            })

        return ReadMessagesOutput(
            success=True,
            contact=input_data.contact,
            messages=formatted_messages
        )

    except Exception as e:
        logger.error(f"Error in whatsapp_read_messages: {e}")
        return ReadMessagesOutput(success=False, contact=args.get("contact", ""), error=str(e))
