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
    """Execute the whatsapp_send_message tool."""
    try:
        input_data = SendMessageInput(**args)
        
        # ════════════════════════════════════════════════════════════════════════
        # 🛠️ WORKSHOP EXERCISE #6: HUMAN-IN-THE-LOOP (HITL) SAFETY GATE
        # ════════════════════════════════════════════════════════════════════════
        # CRITICAL PRINCIPLE:
        #   Never allow an autonomous agent to execute irreversible outward 
        #   actions (like dispatching WhatsApp messages) without human consent!
        #
        # YOUR TASK:
        #   1. If `input_data.confirmed` is False:
        #      Stage the message in SQLite so the CLI/UI can ask the user for approval.
        #   2. If `input_data.confirmed` is True:
        #      Dispatch the message through WhatsApp via `client.send_message(...)`.
        # ════════════════════════════════════════════════════════════════════════
        
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
        
        # If explicitly confirmed by human:
        success = await client.send_message(input_data.contact, input_data.messages)
        return SendMessageOutput(
            success=success,
            contact=input_data.contact,
            messages=input_data.messages,
            requires_confirmation=False,
            error=None if success else "Failed to send message via WhatsApp."
        )

        # ────────────────────────────────────────────────────────────────────────
        # ⚠️ CRITICAL AGENTIC AI TAKEAWAY:
        # Notice that in this implementation, the `confirmed` flag is passed as an 
        # argument that the LLM generates! That means this Human-in-the-Loop (HITL) 
        # system is ultimately decided by the model's output itself. If a model 
        # hallucinates or a prompt injection forces `confirmed=True`, the guardrail 
        # could be bypassed. In production systems, we need stronger hard guards: 
        # deterministic backend verification, cryptographically signed approval tokens, 
        # or enforcing confirmation strictly outside the LLM's parameter space.
        # ────────────────────────────────────────────────────────────────────────

    except Exception as e:
        logger.error(f"Error in whatsapp_send_message: {e}")
        return SendMessageOutput(success=False, contact=args.get("contact", ""), messages=args.get("messages", []), error=str(e))
