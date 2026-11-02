"""FastAPI server for the WhatsApp Agent."""

from fastapi import FastAPI, Depends, HTTPException, Security, Request
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os

from app.config import settings
from app.whatsapp.models import ConnectionStatus, SearchResult, ChatMessages
from app.agent.agent import AgentResponse, CoordinatorAgent

app = FastAPI(title="WhatsApp Agent API", version="1.0.0")

# Mount frontend static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/css", StaticFiles(directory=os.path.join(frontend_dir, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(frontend_dir, "js")), name="js")

# API key auth middleware
from fastapi import Query
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(
    api_key_h: Optional[str] = Security(api_key_header),
    api_key_q: Optional[str] = Query(None, alias="api_key")
) -> str:
    api_key = api_key_h or api_key_q
    if api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

def setup_app(browser, client, agent, db):
    """Setup FastAPI app with global dependencies."""
    app.state.browser = browser
    app.state.client = client
    app.state.agent = agent
    app.state.db = db
    app.state.notification_queues = []

# Request Models
class AgentMessageRequest(BaseModel):
    message: str
    session_id: str = "default"

class SearchRequest(BaseModel):
    name: str

class ReadRequest(BaseModel):
    contact: str
    limit: int = 10

class DraftRequest(BaseModel):
    contact: str
    instruction: str

class SendRequest(BaseModel):
    contact: str
    message: str
    confirmation_id: Optional[str] = None

class ConfirmRequest(BaseModel):
    confirmation_id: str

@app.get("/")
async def serve_frontend():
    """Serve the main frontend HTML."""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend not found"}

@app.get("/audit")
async def serve_audit():
    """Serve the audit logs frontend HTML."""
    audit_path = os.path.join(frontend_dir, "audit.html")
    if os.path.exists(audit_path):
        return FileResponse(audit_path)
    return {"message": "Audit frontend not found"}

@app.get("/audit/logs")
async def get_audit_logs(limit: int = 100, offset: int = 0, request: Request = None, api_key: str = Security(verify_api_key)):
    """Get the audit logs."""
    db = request.app.state.db
    return await db.get_tool_executions(limit=limit, offset=offset)

@app.get("/health")
async def health_check():
    """Health check endpoint, no auth required."""
    return {"status": "ok"}

@app.get("/agent/list")
async def list_agents(request: Request, api_key: str = Security(verify_api_key)):
    """List all active sub-agents from Coordinator."""
    agent: CoordinatorAgent = request.app.state.agent
    return {
        "agents": agent.get_active_agents()
    }

@app.get("/whatsapp/status", response_model=ConnectionStatus)
async def get_whatsapp_status(request: Request, api_key: str = Security(verify_api_key)):
    """Get WhatsApp connection status."""
    browser = request.app.state.browser
    return await browser.check_connection()

@app.post("/agent/message", response_model=AgentResponse)
async def agent_message(req: AgentMessageRequest, request: Request, api_key: str = Security(verify_api_key)):
    """Send a message to the agent."""
    agent = request.app.state.agent
    return await agent.chat(req.message, req.session_id)

class AutopilotDisableRequest(BaseModel):
    contact: str

@app.get("/autopilot/list")
async def list_active_autopilots(request: Request, api_key: str = Security(verify_api_key)):
    """Get all active autopilots."""
    db = request.app.state.db
    return {"autopilots": await db.get_all_active_autopilots()}

@app.post("/autopilot/disable")
async def disable_autopilot(req: AutopilotDisableRequest, request: Request, api_key: str = Security(verify_api_key)):
    """Disable autopilot for a specific contact."""
    db = request.app.state.db
    await db.disable_autopilot(req.contact)
    return {"success": True}

import json
import asyncio
from fastapi.responses import StreamingResponse

@app.post("/agent/stream")
async def stream_agent_message(req: AgentMessageRequest, request: Request, api_key: str = Security(verify_api_key)):
    """Stream tool calls and the final response via Server-Sent Events."""
    agent = request.app.state.agent
    
    async def event_generator():
        queue = asyncio.Queue()
        
        async def on_tool(name, args):
            await queue.put({"type": "tool", "name": name})
            
        async def run_chat():
            try:
                res = await agent.chat(req.message, req.session_id, on_tool_call=on_tool)
                await queue.put({"type": "done", "response": res.model_dump()})
            except Exception as e:
                await queue.put({"type": "error", "error": str(e)})
                
        task = asyncio.create_task(run_chat())
        
        while True:
            item = await queue.get()
            yield f"data: {json.dumps(item)}\n\n"
            if item["type"] in ["done", "error"]:
                break
                
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/notifications/stream")
async def stream_notifications(request: Request, api_key: str = Security(verify_api_key)):
    """Stream background notifications to the web UI."""
    queue = asyncio.Queue()
    request.app.state.notification_queues.append(queue)
    
    async def notification_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    # Wait for a new notification in the queue with a timeout
                    item = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {json.dumps(item)}\n\n"
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            pass
        finally:
            if queue in request.app.state.notification_queues:
                request.app.state.notification_queues.remove(queue)
                
    return StreamingResponse(notification_generator(), media_type="text/event-stream")

@app.post("/whatsapp/search", response_model=SearchResult)
async def search_whatsapp(req: SearchRequest, request: Request, api_key: str = Security(verify_api_key)):
    """Search for a contact."""
    client = request.app.state.client
    return await client.search_contact(req.name)

@app.post("/whatsapp/read", response_model=ChatMessages)
async def read_whatsapp_messages(req: ReadRequest, request: Request, api_key: str = Security(verify_api_key)):
    """Read recent messages from a contact."""
    client = request.app.state.client
    return await client.get_recent_messages(req.contact, limit=req.limit)

@app.post("/whatsapp/draft")
async def draft_whatsapp_message(req: DraftRequest, request: Request, api_key: str = Security(verify_api_key)):
    """Draft a message for a contact."""
    client = request.app.state.client
    draft = await client.draft_message(req.contact, req.instruction)
    return {"draft": draft}

@app.post("/whatsapp/send")
async def send_whatsapp_message(req: SendRequest, request: Request, api_key: str = Security(verify_api_key)):
    """Send a message to a contact. Requires a valid confirmation_id from a prior draft/confirm flow."""
    agent = request.app.state.agent
    if req.confirmation_id:
        result = await agent.confirm_send(req.confirmation_id)
        return result
    # Create a pending confirmation if no confirmation_id provided
    db = request.app.state.db
    confirmation_id = await db.create_pending_confirmation(req.contact, req.message)
    return {"success": True, "requires_confirmation": True, "confirmation_id": confirmation_id}

@app.post("/whatsapp/confirm")
async def confirm_whatsapp_message(req: ConfirmRequest, request: Request, api_key: str = Security(verify_api_key)):
    """Confirm a pending send."""
    agent = request.app.state.agent
    result = await agent.confirm_send(req.confirmation_id)
    return result
