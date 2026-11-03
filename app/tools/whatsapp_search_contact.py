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
        # Validate arguments using Pydantic
        input_data = SearchContactInput(**args)
        
        # ════════════════════════════════════════════════════════════════════════
        # 🛠️ HANDS-ON EXERCISE #1: SEARCH FOR A CONTACT
        # ════════════════════════════════════════════════════════════════════════
        # GOAL: Use the `client` object to search WhatsApp for the given name.
        # 
        # HINT: 
        #   - The contact query is in `input_data.name`
        #   - Call: `result = await client.search_contact(input_data.name)`
        #   - `result.matches` is a list of contacts with `.name` and `.phone`
        # ════════════════════════════════════════════════════════════════════════
        
        # TODO: Replace the line below with your implementation:
        result = await client.search_contact(input_data.name)
        
        output = SearchContactOutput(
            success=True,
            matches=[{"name": match.name, "phone": match.phone} for match in result.matches],
            query=result.query
        )
        return output
    except Exception as e:
        query_name = args.get("name", "Unknown")
        logger.error("Error in whatsapp_search_contact: Could not complete search for '%s': %s", query_name, e)
        error_output = SearchContactOutput(
            success=False,
            matches=[],
            query=args.get("name", ""),
            error=str(e)
        )
        return error_output
