import logging
from typing import Optional, Any
from pydantic import BaseModel, Field

from app.whatsapp.client import WhatsAppClient

logger = logging.getLogger(__name__)

class SearchContactInput(BaseModel):
    name: str = Field(..., description="Contact name or phone number to search for")

class SearchContactOutput(BaseModel):
    success: bool
    matches: list[dict]
    query: str
    error: Optional[str] = None

# ════════════════════════════════════════════════════════════════════════════
# 🛠️ WORKSHOP EXERCISE #1: HOW GEMINI SELECTS TOOLS (THE DESCRIPTION)
# ════════════════════════════════════════════════════════════════════════════
# CONCEPT:
#   An LLM doesn't look at Python code. It ONLY looks at the English
#   "description" field below to decide when to call a tool!
#
# YOUR TASK:
#   Right now, the description is blank ("").
#   If you run the agent and ask "Find Rahul on WhatsApp", Gemini will ignore
#   this tool because it has no idea what it does!
#
#   Fill in a clear English description below, for example:
#   "Search for a contact on WhatsApp by name or phone number."
# ════════════════════════════════════════════════════════════════════════════
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "whatsapp_search_contact",
        # TODO (Exercise 1): Fill in the English description below:
        "description": "",
        "parameters": SearchContactInput.model_json_schema()
    }
}

async def execute(client: WhatsAppClient, args: dict, db: Any = None) -> SearchContactOutput:
    """Execute the whatsapp_search_contact tool."""
    try:
        input_data = SearchContactInput(**args)
        
        # The execution code is already wired up for you!
        # Once you provide the description above, Gemini will trigger this function:
        result = await client.search_contact(input_data.name)
        matches = [{"name": match.name, "phone": match.phone} for match in result.matches]
        
        return SearchContactOutput(
            success=True,
            matches=matches,
            query=result.query
        )
    except Exception as e:
        query_name = args.get("name", "Unknown")
        logger.error("Error in whatsapp_search_contact: Could not complete search for '%s': %s", query_name, e)
        return SearchContactOutput(
            success=False,
            matches=[],
            query=args.get("name", ""),
            error=str(e)
        )
