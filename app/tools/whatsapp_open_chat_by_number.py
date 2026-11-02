"""Tool to open a WhatsApp chat with any phone number (saved or unsaved)."""

import logging
from typing import Optional, Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class OpenChatByNumberInput(BaseModel):
    phone_number: str = Field(
        ...,
        description=(
            "The phone number to message, including the country code. "
            "Examples: '+919876543210', '919876543210', '+1 555-123-4567'. "
            "Spaces, dashes, and parentheses are stripped automatically."
        ),
    )


class OpenChatByNumberOutput(BaseModel):
    success: bool
    phone_number: str
    display_name: Optional[str] = None
    error: Optional[str] = None


TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "whatsapp_open_chat_by_number",
        "description": (
            "Open a WhatsApp chat with any phone number — even if the number is NOT saved in contacts. "
            "This uses WhatsApp Web's native URL scheme to navigate directly to the conversation. "
            "After calling this tool, you can use the normal whatsapp_read_messages, whatsapp_draft_message, "
            "and whatsapp_send_message tools to converse with this person. "
            "The phone number MUST include the country code (e.g. +91 for India, +1 for US)."
        ),
        "parameters": OpenChatByNumberInput.model_json_schema(),
    },
}


async def execute(
    client: Any,
    args: dict,
    db: Any = None,
    genai_client: Any = None,
    model: str = "gemini-2.0-flash",
) -> OpenChatByNumberOutput:
    """Execute the whatsapp_open_chat_by_number tool."""
    try:
        input_data = OpenChatByNumberInput(**args)

        display_name = await client.open_chat_by_number(input_data.phone_number)

        output = OpenChatByNumberOutput(
            success=True,
            phone_number=input_data.phone_number,
            display_name=display_name,
        )

        return output

    except Exception as e:
        logger.error(f"Error in whatsapp_open_chat_by_number: {e}")
        error_output = OpenChatByNumberOutput(
            success=False,
            phone_number=args.get("phone_number", ""),
            error=str(e),
        )
        return error_output
