import logging
import asyncio
from typing import Optional, Any, List
from pydantic import BaseModel, Field
from google import genai

from app.whatsapp.client import WhatsAppClient

logger = logging.getLogger(__name__)


class AnalyzeUserStyleInput(BaseModel):
    contacts: List[str] = Field(..., description="List of contact names to analyze sent messages from")
    target_contact: Optional[str] = Field(None, description="If provided, the analyzed style will be saved as the specific writing style for this contact.")


class AnalyzeUserStyleOutput(BaseModel):
    success: bool
    style_profile: Optional[str] = None
    error: Optional[str] = None


TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "whatsapp_analyze_user_style",
        "description": "Analyze past sent messages from specified contacts to extract and save the user's personal writing style profile. If target_contact is provided, the style is saved for that specific contact. Otherwise, it is saved globally.",
        "parameters": AnalyzeUserStyleInput.model_json_schema(),
    },
}


async def execute(
    client: WhatsAppClient,
    args: dict,
    db: Any = None,
    genai_client: Optional[genai.Client] = None,
    model: str = "gemini-2.0-flash",
) -> AnalyzeUserStyleOutput:
    """Execute the whatsapp_analyze_user_style tool."""
    try:
        input_data = AnalyzeUserStyleInput(**args)
        sent_messages = []

        for contact in input_data.contacts:
            try:
                chat_msgs = await client.get_recent_messages(contact, limit=50, scroll_up=True)
                for msg in chat_msgs.messages:
                    if msg.is_from_me and msg.text and msg.text.strip():
                        sent_messages.append(msg.text.strip())
            except Exception as e:
                logger.warning(f"Could not fetch messages for style analysis from {contact}: {e}")

        if not sent_messages:
            raise ValueError("No sent messages found in the specified contacts to analyze.")

        if not genai_client:
            raise ValueError("genai_client is required for style analysis")

        sample_text = "\n".join([f"- {m}" for m in sent_messages[:50]])

        prompt = (
            "Analyze the following WhatsApp messages sent by the user to understand their personal texting style:\n\n"
            f"{sample_text}\n\n"
            "Provide a concise, bulleted writing style guide summarizing:\n"
            "1. Vocabulary & Slang (e.g. Tanglish/casual words like 'da', 'soltu', 'machan', 'nu').\n"
            "2. Capitalization & Punctuation (e.g. all lowercase, question mark usage, lack of periods).\n"
            "3. Emoji Usage (frequently used emojis or emojis style).\n"
            "4. Sentence Length & Structure.\n\n"
            "Keep the summary under 150 words."
        )

        response = await genai_client.aio.models.generate_content(
            model=model,
            contents=prompt,
        )

        style_profile = response.text.strip()

        if db:
            if input_data.target_contact:
                await db.save_contact_style(input_data.target_contact, style_profile)
            else:
                await db.save_user_style(style_profile)

        return AnalyzeUserStyleOutput(
            success=True,
            style_profile=style_profile,
        )
    except Exception as e:
        logger.error(f"Error in whatsapp_analyze_user_style: {e}")
        error_output = AnalyzeUserStyleOutput(
            success=False, error=str(e)
        )
        return error_output
