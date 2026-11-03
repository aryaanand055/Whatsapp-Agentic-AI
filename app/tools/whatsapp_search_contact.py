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

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "whatsapp_search_contact",
        "description": "Search for a contact on WhatsApp by name or phone number. Returns matching contacts. If multiple matches are found, the user must select the correct one.",
        "parameters": SearchContactInput.model_json_schema()
    }
}

async def execute(client: WhatsAppClient, args: dict, db: Any = None) -> SearchContactOutput:
    """
    Execute the whatsapp_search_contact tool.
    """
    try:
        input_data = SearchContactInput(**args)
        
        # ════════════════════════════════════════════════════════════════════════
        # 🛠️ WORKSHOP EXERCISE #1: SEARCH CONTACT
        # ════════════════════════════════════════════════════════════════════════
        # GOAL:
        #   Use `client` to search for the contact on WhatsApp Web.
        #
        # HINT:
        #   1. Call: result = await client.search_contact(input_data.name)
        #   2. Populate matches from result.matches
        #
        # (See solutions/SOLUTIONS.md if you get stuck!)
        # ════════════════════════════════════════════════════════════════════════
        
        # YOUR CODE HERE:
        result = await client.search_contact(input_data.name)
        matches = [{"name": match.name, "phone": match.phone} for match in result.matches]
        query = result.query
        
        return SearchContactOutput(
            success=True,
            matches=matches,
            query=query
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
