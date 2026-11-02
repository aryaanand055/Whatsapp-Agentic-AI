import logging
from typing import Optional, Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class ManageMemoryInput(BaseModel):
    action: str = Field(..., description="The action to perform: 'add', 'get', or 'delete'")
    contact: Optional[str] = Field(None, description="The contact this memory is about. Leave empty for global memories.")
    memory_text: Optional[str] = Field(None, description="The fact or preference to remember. Required for 'add'.")
    memory_id: Optional[int] = Field(None, description="The ID of the memory to delete. Required for 'delete'.")

class ManageMemoryOutput(BaseModel):
    success: bool
    action: str
    memories: list[dict] = Field(default_factory=list)
    memory_id: Optional[int] = None
    error: Optional[str] = None

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "whatsapp_manage_memory",
        "description": "Manage the agent's long-term memory. Use 'add' to save a fact/preference (globally or for a specific contact). Use 'get' to retrieve memories for a contact. Use 'delete' to remove an outdated memory.",
        "parameters": ManageMemoryInput.model_json_schema(),
    },
}

async def execute(
    client: Any,
    args: dict,
    db: Any = None,
    genai_client: Any = None,
    model: str = "gemini-2.0-flash",
) -> ManageMemoryOutput:
    """Execute the whatsapp_manage_memory tool."""
    try:
        input_data = ManageMemoryInput(**args)
        
        if not db:
            raise ValueError("Database connection is required for this tool.")

        if input_data.action == "add":
            if not input_data.memory_text:
                raise ValueError("memory_text is required for action 'add'")
            memory_id = await db.add_memory(input_data.memory_text, input_data.contact)
            output = ManageMemoryOutput(
                success=True,
                action="add",
                memory_id=memory_id,
            )
        elif input_data.action == "get":
            memories = await db.get_memories(input_data.contact)
            output = ManageMemoryOutput(
                success=True,
                action="get",
                memories=memories,
            )
        elif input_data.action == "delete":
            if input_data.memory_id is None:
                raise ValueError("memory_id is required for action 'delete'")
            deleted = await db.delete_memory(input_data.memory_id)
            if not deleted:
                raise ValueError(f"Memory with ID {input_data.memory_id} not found.")
            output = ManageMemoryOutput(
                success=True,
                action="delete",
                memory_id=input_data.memory_id,
            )
        else:
            raise ValueError(f"Invalid action: {input_data.action}")

        return output

    except Exception as e:
        logger.error(f"Error in whatsapp_manage_memory: {e}")
        error_output = ManageMemoryOutput(
            success=False,
            action=args.get("action", "unknown"),
            error=str(e)
        )
        return error_output
