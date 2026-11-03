import logging
from typing import Optional, Any
from pydantic import BaseModel, Field

from app.whatsapp.client import WhatsAppClient

logger = logging.getLogger(__name__)

class SendMessageInput(BaseModel):
    contact: str = Field(..., description="The contact name to send the message to")
    messages: list[str] = Field(..., description="List of messages to send sequentially")
    confirmed: bool = Field(default=False, description="Whether the user explicitly confirmed sending this message")

class SendMessageOutput(BaseModel):
    success: bool
    contact: str
    messages: list[str]
    requires_confirmation: bool = False
    confirmation_id: Optional[str] = None
    error: Optional[str] = None

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "whatsapp_send_message",
        "description": "Send a message to a contact. Requires confirmation to actually send. If not confirmed, returns a confirmation_id.",
        "parameters": SendMessageInput.model_json_schema()
    }
}

async def execute(client: WhatsAppClient, args: dict, db: Any = None) -> SendMessageOutput:
    """
    Execute the whatsapp_send_message tool.
    """
    try:
        input_data = SendMessageInput(**args)
        
        # ════════════════════════════════════════════════════════════════════════
        # 🛠️ WORKSHOP EXERCISE #4: SEND MESSAGE (HUMAN-IN-THE-LOOP SAFETY GATE)
        # ════════════════════════════════════════════════════════════════════════
        # GOAL:
        #   Never send an irreversible message without human approval!
        #
        # LOGIC:
        #   1. If `input_data.confirmed` is False:
        #      Stage the message in SQLite:
        #        confirmation_id = await db.create_pending_confirmation(input_data.contact, json.dumps(input_data.messages))
        #      Return SendMessageOutput with requires_confirmation=True and confirmation_id.
        #
        #   2. If `input_data.confirmed` is True:
        #      Dispatch the message:
        #        success = await client.send_message(input_data.contact, input_data.messages)
        #      Return SendMessageOutput with success=success.
        #
        # (See solutions/SOLUTIONS.md if you get stuck!)
        # ════════════════════════════════════════════════════════════════════════
        
        # YOUR CODE HERE:
        if not input_data.confirmed:
            if not db:
                raise ValueError("Database is required for pending confirmations")
            import json
            confirmation_id = await db.create_pending_confirmation(input_data.contact, json.dumps(input_data.messages))
            return SendMessageOutput(
                success=True,
                contact=input_data.contact,
                messages=input_data.messages,
                requires_confirmation=True,
                confirmation_id=confirmation_id
            )
        
        # When confirmed:
        success = await client.send_message(input_data.contact, input_data.messages)
        return SendMessageOutput(
            success=success,
            contact=input_data.contact,
            messages=input_data.messages,
            requires_confirmation=False,
            error=None if success else "Failed to send message via WhatsApp."
        )
    except Exception as e:
        logger.error(f"Error in whatsapp_send_message: {e}")
        return SendMessageOutput(
            success=False,
            contact=args.get("contact", ""),
            messages=args.get("messages", []),
            error=str(e)
        )
