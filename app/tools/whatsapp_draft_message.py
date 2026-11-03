"""Tool to draft a message based on instruction and context."""

import logging
from typing import Optional, Any
from pydantic import BaseModel, Field
from google import genai

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

        # 1. Fetch recent messages so Gemini has conversation context
        try:
            recent_msgs = await client.get_recent_messages(input_data.contact, limit=5)
            context = "\n".join([f"{msg.sender}: {msg.text}" for msg in recent_msgs.messages])
        except Exception:
            context = "No recent context available."

        # ════════════════════════════════════════════════════════════════════════
        # 🛠️ EXERCISE 5: CONTEXTUAL PROMPT ENGINEERING
        # ════════════════════════════════════════════════════════════════════════
        # CONCEPT:
        #   An LLM needs clear ingredients to draft a realistic response.
        #   You need to provide:
        #     1. Recipient Name:   `input_data.contact`
        #     2. Chat Context:     `context` (what was said previously)
        #     3. User Instruction: `input_data.instruction` (what you want to say)
        #     4. Output Rule:      Ask Gemini to separate short message bubbles with '\n\n'
        #
        # YOUR TASK:
        #   Construct the `prompt` string below combining these elements.
        #   (Check solutions/SOLUTIONS.md for the reference prompt)
        # ════════════════════════════════════════════════════════════════════════
        
        # TODO: Construct your prompt string here:
        prompt = (
            f"You are drafting WhatsApp messages to {input_data.contact}.\n"
            f"Recent Conversation:\n{context}\n\n"
            f"User Instruction: {input_data.instruction}\n"
            f"Generate 1 to 3 short realistic WhatsApp messages separated by double newlines."
        )

        # ────────────────────────────────────────────────────────────────────────
        # 🤖 LLM Generation & Parsing (Pre-built for you):
        # Calls Gemini with your prompt, splits output into message bubbles,
        # and returns the DraftMessageOutput.
        # ────────────────────────────────────────────────────────────────────────
        if genai_client:
            res = await genai_client.aio.models.generate_content(model=model, contents=prompt)
            raw_text = res.text or ""
            drafts = [m.strip() for m in raw_text.split("\n\n") if m.strip()]
            return DraftMessageOutput(success=True, contact=input_data.contact, drafts=drafts)
        else:
            return DraftMessageOutput(
                success=False,
                contact=input_data.contact,
                drafts=[],
                error="genai_client is required for drafting messages"
            )

    except Exception as e:
        logger.error(f"Error in whatsapp_draft_message: {e}")
        return DraftMessageOutput(success=False, contact=args.get("contact", ""), drafts=[], error=str(e))
