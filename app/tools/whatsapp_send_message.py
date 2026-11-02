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
        
        # ── WORKSHOP EXERCISE: TOOL #5 (Human-In-The-Loop Safety Gate) ──────────
        # CRITICAL AGENTIC PRINCIPLE:
        # Never perform external destructive actions (like sending texts) without 
        # explicit approval! If `confirmed` is False, stage it in SQLite and ask.
        #
        # If confirmed is False:
        #   confirmation_id = await db.create_pending_confirmation(...)
        # If confirmed is True:
        #   success = await client.send_message(input_data.contact, input_data.messages)
        # ────────────────────────────────────────────────────────────────────────
        if not input_data.confirmed:
            if not db:
                raise ValueError("Database is required for pending confirmations")
                
            import json
            confirmation_id = await db.create_pending_confirmation(input_data.contact, json.dumps(input_data.messages))
            
            output = SendMessageOutput(
                success=True,
                contact=input_data.contact,
                messages=input_data.messages,
                requires_confirmation=True,
                confirmation_id=confirmation_id
            )
            return output
        
        # If explicitly confirmed:
        success = await client.send_message(input_data.contact, input_data.messages)
        
        output = SendMessageOutput(
            success=success,
            contact=input_data.contact,
            messages=input_data.messages,
            requires_confirmation=False,
            error=None if success else "Failed to send message via WhatsApp."
        )
        return output
    except Exception as e:
        logger.error(f"Error in whatsapp_send_message: {e}")
        error_output = SendMessageOutput(
            success=False,
            contact=args.get("contact", ""),
            messages=args.get("messages", []),
            error=str(e)
        )
        return error_output
