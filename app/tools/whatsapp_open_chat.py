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
    """
    Execute the whatsapp_open_chat tool.
    """
    try:
        input_data = OpenChatInput(**args)
        
        # ════════════════════════════════════════════════════════════════════════
        # 🛠️ HANDS-ON EXERCISE #2: OPEN A CHAT
        # ════════════════════════════════════════════════════════════════════════
        # GOAL: Make Playwright navigate to the specified contact's chat.
        #
        # HINT:
        #   - Call: `await client.open_chat(input_data.contact)`
        #   - It returns a boolean (`True` on success, `False` on failure)
        # ════════════════════════════════════════════════════════════════════════
        
        # TODO: Replace the line below with your implementation:
        success = await client.open_chat(input_data.contact)
        
        output = OpenChatOutput(
            success=success,
            contact=input_data.contact,
            error=None if success else "Failed to open chat."
        )
        return output
    except Exception as e:
        logger.error(f"Error in whatsapp_open_chat: {e}")
        error_output = OpenChatOutput(success=False, contact=args.get("contact", ""), error=str(e))
        return error_output
