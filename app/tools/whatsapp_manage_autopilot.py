"""Tool for explicitly managing autopilot permissions in the SQL database."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from app.whatsapp.client import WhatsAppClient

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "whatsapp_manage_autopilot",
        "description": "CRITICAL: Use this tool to explicitly save, check, or disable Autopilot permissions for a specific contact in the SQL database. You MUST use this tool instead of the generic task manager when the user explicitly grants or revokes autopilot permission.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["enable", "disable", "check"],
                    "description": "Whether to enable, disable, or check the autopilot status."
                },
                "contact": {
                    "type": "string",
                    "description": "The exact contact name."
                },
                "duration_hours": {
                    "type": "number",
                    "description": "Required if action=enable. The number of hours autopilot should remain active."
                },
                "goal": {
                    "type": "string",
                    "description": "Required if action=enable. The specific objective you are trying to achieve while on autopilot."
                }
            },
            "required": ["action", "contact"]
        }
    }
}

class ManageAutopilotInput(BaseModel):
    action: str = Field(..., description="Action to perform: enable, disable, or check")
    contact: str = Field(..., description="The exact contact name")
    duration_hours: Optional[float] = Field(None, description="Duration in hours")
    goal: Optional[str] = Field(None, description="Autopilot goal")

async def execute(client: WhatsAppClient, args: dict, db: Any) -> Dict[str, Any]:
    """Execute the whatsapp_manage_autopilot tool."""
    try:
        input_data = ManageAutopilotInput(**args)
        
        if input_data.action == "enable":
            if not input_data.duration_hours or not input_data.goal:
                return {"success": False, "error": "duration_hours and goal are required to enable autopilot"}
            
            await db.set_autopilot(input_data.contact, input_data.duration_hours, input_data.goal)
            return {
                "success": True,
                "message": f"Autopilot successfully enabled for '{input_data.contact}' for {input_data.duration_hours} hours.",
                "goal": input_data.goal
            }
            
        elif input_data.action == "disable":
            await db.disable_autopilot(input_data.contact)
            return {
                "success": True,
                "message": f"Autopilot successfully disabled for '{input_data.contact}'."
            }
            
        elif input_data.action == "check":
            config = await db.get_active_autopilot(input_data.contact)
            if config:
                return {
                    "success": True,
                    "autopilot_active": True,
                    "config": config
                }
            else:
                return {
                    "success": True,
                    "autopilot_active": False,
                    "message": f"No active autopilot permission found for '{input_data.contact}'."
                }
                
    except Exception as e:
        return {"success": False, "error": str(e)}
