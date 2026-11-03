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
        # 🛠️ HANDS-ON EXERCISE #3: PERCEPTION & READING MESSAGES
        # ════════════════════════════════════════════════════════════════════════
        # GOAL: Read recent messages so the agent can perceive context.
        #
        # HINT:
        #   - Call: `chat_messages = await client.get_recent_messages(input_data.contact, input_data.limit)`
        #   - Each item in `chat_messages.messages` has:
        #       - msg.sender (str)
        #       - msg.text (str)
        #       - msg.timestamp (str)
        #       - msg.is_from_me (bool) -> Tells the LLM who sent it!
        # ════════════════════════════════════════════════════════════════════════
        
        # TODO: Replace the line below with your implementation:
        chat_messages = await client.get_recent_messages(input_data.contact, input_data.limit)
        
        messages = [
            {
                "sender": msg.sender,
                "timestamp": msg.timestamp,
                "text": msg.text,
                "is_from_me": msg.is_from_me
            } for msg in chat_messages.messages
        ]
        
        output = ReadMessagesOutput(
            success=True,
            contact=input_data.contact,
            messages=messages
        )
        return output
    except Exception as e:
        logger.error(f"Error in whatsapp_read_messages: {e}")
        error_output = ReadMessagesOutput(success=False, contact=args.get("contact", ""), error=str(e))
        return error_output
