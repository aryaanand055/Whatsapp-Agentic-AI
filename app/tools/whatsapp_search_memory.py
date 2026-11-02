import logging
from typing import Optional, Any, List
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class SearchMemoryInput(BaseModel):
    query: str = Field(..., description="The semantic query to search for in memory (e.g. 'What food does this person like?')")
    contact: Optional[str] = Field(None, description="The specific contact to search memories for. If empty, searches global memories only.")
    limit: int = Field(5, description="Maximum number of memories to return.")

class SearchMemoryOutput(BaseModel):
    success: bool
    query: str
    results: List[dict] = Field(default_factory=list)
    error: Optional[str] = None

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "whatsapp_search_memory",
        "description": "Perform a semantic search over the agent's Vector Database to recall relevant facts or preferences based on meaning rather than exact keywords.",
        "parameters": SearchMemoryInput.model_json_schema(),
    },
}

async def execute(
    client: Any,
    args: dict,
    db: Any = None,
    genai_client: Any = None,
    model: str = "gemini-2.0-flash",
) -> SearchMemoryOutput:
    """Execute the whatsapp_search_memory tool."""
    try:
        input_data = SearchMemoryInput(**args)
        
        if not db:
            raise ValueError("Database connection is required for this tool.")

        if getattr(db, 'memory_collection', None) is None:
            raise ValueError("Vector Database (ChromaDB) is not initialized.")

        results = await db.search_memory(
            query=input_data.query, 
            contact=input_data.contact, 
            limit=input_data.limit
        )

        output = SearchMemoryOutput(
            success=True,
            query=input_data.query,
            results=results,
        )

        return output

    except Exception as e:
        logger.error(f"Error in whatsapp_search_memory: {e}")
        error_output = SearchMemoryOutput(
            success=False,
            query=args.get("query", ""),
            error=str(e)
        )
        return error_output
