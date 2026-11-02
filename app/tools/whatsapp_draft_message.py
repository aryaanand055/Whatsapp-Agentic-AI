import logging
from typing import Optional, Any
from pydantic import BaseModel, Field
from google import genai
import json

from app.whatsapp.client import WhatsAppClient

logger = logging.getLogger(__name__)


class DraftMessageInput(BaseModel):
    contact: str = Field(..., description="The contact to draft a message for")
    instruction: str = Field(..., description="Instructions on what the drafted message should say")


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

        # Fetch recent messages for context
        try:
            recent_msgs = await client.get_recent_messages(input_data.contact, limit=5)
            context = "\n".join(
                [f"{msg.sender}: {msg.text}" for msg in recent_msgs.messages]
            )
        except Exception as e:
            logger.warning(f"Could not fetch recent messages for context: {e}")
            context = "No recent context available."

        user_style = None
        memories = []
        if db:
            try:
                # First try to get contact-specific style
                user_style = await db.get_contact_style(input_data.contact)
                if not user_style:
                    # Fallback to global style
                    user_style = await db.get_user_style()
                
                # Fetch memories (global + contact specific)
                memories_records = await db.get_memories(input_data.contact)
                memories = [m['memory_text'] for m in memories_records]
            except Exception as e:
                logger.warning(f"Could not load user writing style or memories: {e}")

        style_prompt = ""
        if user_style:
            style_prompt = f"\nUSER'S PERSONAL WRITING STYLE PROFILE:\n{user_style}\nStrictly emulate the user's personal writing style profile above.\n\n"
            
        memory_prompt = ""
        if memories:
            memory_list = "\n".join([f"- {m}" for m in memories])
            memory_prompt = f"\nLONG-TERM MEMORY (Facts and preferences to remember):\n{memory_list}\nConsider these memories when crafting the message if they are relevant.\n\n"

        prompt = (
            f"Draft natural WhatsApp message(s) based on the following instruction: {input_data.instruction}\n\n"
            f"{style_prompt}"
            f"{memory_prompt}"
            f"Recent chat context:\n{context}\n\n"
            "RULES:\n"
            "1. Match the exact language, casual tone, and slang (e.g., Tanglish/casual English) from the chat context and the style profile.\n"
            "2. Send as many short messages as naturally required (could be 1, 2, 3, or 4). Do not force a fixed message count.\n"
            "3. CRITICAL: Every message MUST contain NEW information, a unique point, or a natural continuation. NEVER repeat or rephrase the same question/idea in multiple messages.\n"
            "4. Return ONLY a JSON array of strings, e.g. [\"Aah afternoon eh?\", \"Veetla enna vishesham?\"] or [\"Chumma veetuku poranu soltu ipdi oodura 🤣\"]."
        )

        if not genai_client:
            raise ValueError("genai_client is required for drafting messages.")

        response = await genai_client.aio.models.generate_content(
            model=model,
            contents=prompt,
        )

        drafts = []
        try:
            # Strip markdown codeblocks
            text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
            drafts = json.loads(text)
            if not isinstance(drafts, list):
                drafts = [str(drafts)]
        except Exception:
            drafts = [response.text.strip()]

        output = DraftMessageOutput(
            success=True,
            contact=input_data.contact,
            drafts=drafts,
        )

        return output
    except Exception as e:
        logger.error(f"Error in whatsapp_draft_message: {e}")
        error_output = DraftMessageOutput(
            success=False, contact=args.get("contact", ""), error=str(e)
        )
        return error_output
