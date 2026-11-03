"""Tool to draft a message based on instruction and context."""

import logging
from typing import Optional, Any
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from app.whatsapp.client import WhatsAppClient

logger = logging.getLogger(__name__)


class DraftMessageInput(BaseModel):
    contact: str = Field(..., description="The contact name to draft a message for")
    instruction: str = Field(..., description="Instructions on what to say")


class DraftMessageOutput(BaseModel):
    success: bool
    contact: str
    drafts: list[str] = Field(default_factory=list)
    error: Optional[str] = None


TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "whatsapp_draft_message",
        "description": "Draft multiple sequential messages to a contact based on instructions and recent chat context.",
        "parameters": DraftMessageInput.model_json_schema(),
    },
}


async def execute(
    client: WhatsAppClient,
    args: dict,
    db: Any = None,
    genai_client: Optional[genai.Client] = None,
    model: str = "gemini-2.0-flash",
) -> DraftMessageOutput:
    """Execute the whatsapp_draft_message tool."""
    try:
        input_data = DraftMessageInput(**args)

        # ════════════════════════════════════════════════════════════════════════
        # 🛠️ WORKSHOP EXERCISE #6: CONTEXTUAL DRAFTING
        # ════════════════════════════════════════════════════════════════════════
        # GOAL:
        #   1. Fetch the last 5 messages from the chat as conversation context.
        #   2. Ask Gemini to draft a natural, human-sounding reply.
        #
        # (See solutions/SOLUTIONS.md if you get stuck!)
        # ════════════════════════════════════════════════════════════════════════

        # 1. Fetch recent messages for context
        try:
            recent_msgs = await client.get_recent_messages(input_data.contact, limit=5)
            context = "\n".join([f"{msg.sender}: {msg.text}" for msg in recent_msgs.messages])
        except Exception as e:
            logger.warning(f"Could not fetch recent messages for context: {e}")
            context = "No recent context available."

        # 2. Check for optional stored style/memory in DB
        user_style = None
        memories = []
        if db:
            try:
                user_style = await db.get_contact_style(input_data.contact) or await db.get_user_style()
                memories_records = await db.get_memories(input_data.contact)
                memories = [m['memory_text'] for m in memories_records]
            except Exception as e:
                logger.warning(f"Could not load writing style/memories: {e}")

        style_prompt = f"\nUSER'S STYLE PROFILE:\n{user_style}\n" if user_style else ""
        memory_prompt = f"\nRELEVANT MEMORIES:\n" + "\n".join([f"- {m}" for m in memories]) + "\n" if memories else ""

        prompt = (
            f"You are drafting WhatsApp messages on behalf of the user to {input_data.contact}.\n"
            f"Recent Conversation Context:\n{context}\n\n"
            f"{style_prompt}"
            f"{memory_prompt}"
            f"User's Instruction:\n{input_data.instruction}\n\n"
            f"Rules:\n"
            f"1. Generate 1 to 3 short sequential WhatsApp messages that sound completely natural.\n"
            f"2. Separate multiple messages with a double newline (\\n\\n).\n"
            f"3. Do not include quotes or conversational preamble — output ONLY the raw message texts."
        )

        if genai_client:
            response = await genai_client.aio.models.generate_content(
                model=model,
                contents=prompt
            )
            raw_text = response.text or ""
            # Split by double newline to get individual message bubbles
            drafts = [msg.strip() for msg in raw_text.split("\n\n") if msg.strip()]
        else:
            return DraftMessageOutput(
                success=False,
                contact=input_data.contact,
                drafts=[],
                error="genai_client is required for drafting messages"
            )

        return DraftMessageOutput(
            success=True,
            contact=input_data.contact,
            drafts=drafts,
        )

    except Exception as e:
        logger.error(f"Error in whatsapp_draft_message: {e}")
        return DraftMessageOutput(
            success=False,
            contact=args.get("contact", ""),
            drafts=[],
            error=str(e),
        )
