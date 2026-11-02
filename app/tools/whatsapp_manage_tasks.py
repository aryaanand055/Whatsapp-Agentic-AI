import logging
from typing import Any, Optional, List
from pydantic import BaseModel, Field

from app.whatsapp.client import WhatsAppClient

logger = logging.getLogger(__name__)

class ManageTasksInput(BaseModel):
    action: str = Field(..., description="Action to perform: 'add', 'update', or 'delete'")
    description: Optional[str] = Field(None, description="Description of the task (required for 'add')")
    task_id: Optional[int] = Field(None, description="ID of the task (required for 'update' and 'delete')")
    status: Optional[str] = Field(None, description="Status of the task ('pending', 'in_progress', 'completed') (required for 'update')")

class ManageTasksOutput(BaseModel):
    success: bool
    action: str
    task_id: Optional[int] = None
    error: Optional[str] = None

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "whatsapp_manage_tasks",
        "description": "Add, update, or delete tasks in the task manager. Use this to keep track of conversational goals or pending actions.",
        "parameters": ManageTasksInput.model_json_schema()
    }
}

async def execute(client: WhatsAppClient, args: dict, db: Any = None) -> ManageTasksOutput:
    """Execute the whatsapp_manage_tasks tool."""
    try:
        input_data = ManageTasksInput(**args)
        
        if not db:
            raise ValueError("Database is required to manage tasks.")
            
        action = input_data.action.lower()
        task_id = None
        
        if action == "add":
            if not input_data.description:
                raise ValueError("description is required for 'add' action.")
            task_id = await db.add_task(input_data.description)
            
        elif action == "update":
            if input_data.task_id is None or not input_data.status:
                raise ValueError("task_id and status are required for 'update' action.")
            success = await db.update_task_status(input_data.task_id, input_data.status)
            if not success:
                raise ValueError(f"Task with ID {input_data.task_id} not found.")
            task_id = input_data.task_id
            
        elif action == "delete":
            if input_data.task_id is None:
                raise ValueError("task_id is required for 'delete' action.")
            success = await db.delete_task(input_data.task_id)
            if not success:
                raise ValueError(f"Task with ID {input_data.task_id} not found.")
            task_id = input_data.task_id
            
        else:
            raise ValueError(f"Invalid action '{action}'. Must be 'add', 'update', or 'delete'.")
            
        output = ManageTasksOutput(
            success=True,
            action=action,
            task_id=task_id
        )
        
        return output
        
    except Exception as e:
        logger.error(f"Error in whatsapp_manage_tasks: {e}")
        error_output = ManageTasksOutput(
            success=False,
            action=args.get("action", "unknown"),
            error=str(e)
        )
        return error_output
