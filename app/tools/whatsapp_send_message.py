import logging
from typing import Optional, Any
from pydantic import BaseModel, Field

from app.whatsapp.client import WhatsAppClient

logger = logging.getLogger(__name__)

class SendMessageInput(BaseModel):
    contact: str = Field(..., description="The contact to send the messages to")
    messages: list[str] = Field(..., description="A list of messages to send sequentially")
    confirmed: bool = Field(False, description="Whether the user has explicitly confirmed sending these messages")

class SendMessageOutput(BaseModel):
    success: bool
    contact: str
    messages: list[str]
    requires_confirmation: bool
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
            
        success = await client.send_message(input_data.contact, input_data.messages)
        
        output = SendMessageOutput(
            success=success,
            contact=input_data.contact,
            messages=input_data.messages,
            requires_confirmation=False,
            error=None if success else "Failed to send message."
        )
        
            
        return output
    except Exception as e:
        logger.error(f"Error in whatsapp_send_message: {e}")
        error_output = SendMessageOutput(
            success=False, 
            contact=args.get("contact", ""), 
            messages=args.get("messages", []), 
            requires_confirmation=False, 
            error=str(e)
        )
        return error_output
