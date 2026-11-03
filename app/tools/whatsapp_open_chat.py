import logging
from typing import Optional, Any
from pydantic import BaseModel, Field

from app.whatsapp.client import WhatsAppClient

logger = logging.getLogger(__name__)

class OpenChatInput(BaseModel):
    contact: str = Field(..., description="The name or phone number of the contact to open chat with")

class OpenChatOutput(BaseModel):
    success: bool
    contact: str
    error: Optional[str] = None

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "whatsapp_open_chat",
        "description": "Open a WhatsApp chat with a specific contact.",
        "parameters": OpenChatInput.model_json_schema()
    }
}

async def execute(client: WhatsAppClient, args: dict, db: Any = None) -> OpenChatOutput:
    """Execute the whatsapp_open_chat tool."""
    try:
        input_data = OpenChatInput(**args)
        
        # ════════════════════════════════════════════════════════════════════════
        # 🛠️ EXERCISE 2: OPEN A CHAT WINDOW
        # ════════════════════════════════════════════════════════════════════════
        # TASK:
        #   Make the browser open the chat for `input_data.contact`.
        #
        # HINT:
        #   Call: await client.open_chat(input_data.contact)
        # ════════════════════════════════════════════════════════════════════════
        
        # TODO: Replace False with the client call above:
        success = False  # <-- Change this to: await client.open_chat(input_data.contact)

        return OpenChatOutput(
            success=success,
            contact=input_data.contact,
            error=None if success else "Chat not opened yet (Complete Exercise 2)."
        )

    except Exception as e:
        logger.error(f"Error in whatsapp_open_chat: {e}")
        return OpenChatOutput(success=False, contact=args.get("contact", ""), error=str(e))
