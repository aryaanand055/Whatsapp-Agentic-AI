"""Entry point for WhatsApp Agent."""

import argparse
import asyncio
import sys
import os
import uvicorn
import logging
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from prompt_toolkit import PromptSession, print_formatted_text
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.patch_stdout import patch_stdout
import io

from app.config import settings
from app.database.db import Database
from app.whatsapp.browser import WhatsAppBrowser
from app.whatsapp.client import WhatsAppClient
from app.agent.agent import CoordinatorAgent
from app.api.server import app as fastapi_app, setup_app

# We force terminal output and limit the color system to 'standard' (16 colors).
# This is crucial because prompt_toolkit's ANSI parser only supports standard ANSI codes,
# and will fail to parse Rich's advanced 256-color/truecolor RGB codes.
console = Console(force_terminal=True, color_system="standard")
logger = logging.getLogger(__name__)

def safe_print(*args, **kwargs):
    """Print with Rich formatting. Uses print_formatted_text(ANSI(...)) to safely clear, print, and redraw the active prompt."""
    buf = io.StringIO()
    temp_console = Console(file=buf, force_terminal=True, color_system="standard")
    temp_console.print(*args, **kwargs)
    print_formatted_text(ANSI(buf.getvalue()), end="", flush=True)

async def run_cli():
    """Run the agent in interactive CLI mode."""
    safe_print(Panel("[bold green]Starting WhatsApp Agent CLI...[/bold green]"))
    
    db = Database(settings.db_path, settings.chroma_db_dir)
    await db.initialize()
    
    browser = WhatsAppBrowser(settings.whatsapp_profile_dir, headless=settings.whatsapp_headless)
    await browser.start()
    
    safe_print("[yellow]Waiting for login... (Please scan QR code if not logged in)[/yellow]")
    await browser.wait_for_login()
    safe_print("[bold green]Successfully logged in![/bold green]")
    
    client = WhatsAppClient(browser)
    agent = CoordinatorAgent(client, db, settings)
    await agent.initialize()
    
    safe_print(Panel("[bold cyan]WhatsApp Agent is ready![/bold cyan]\nType 'quit', 'exit', or 'status'."))
    
    session = PromptSession()
    session_id = "cli_session"
    
    # Start background tasks for CLI mode
    listener_task, alert_bg_task = start_background_tasks(client, agent, mode="cli")
    
    # --- Main loop: only handles user input ---
    with patch_stdout():
        try:
            while True:
                try:
                    user_message = await session.prompt_async("You: ")
                except (EOFError, KeyboardInterrupt):
                    break
                except Exception:
                    break
                    
                if not user_message.strip():
                    continue
                elif user_message.strip().lower() in ['quit', 'exit']:
                    break
                elif user_message.strip().lower() == 'status':
                    status = await browser.check_connection()
                    safe_print(f"[bold magenta]Status:[/bold magenta] {status}")
                    continue
                elif user_message.strip().lower().startswith('/tasks'):
                    tasks = await db.get_tasks()
                    if not tasks:
                        safe_print("[yellow]No tasks found.[/yellow]")
                    else:
                        table = Table(title="Task List", title_style="bold magenta", border_style="cyan")
                        table.add_column("ID", style="cyan", justify="right")
                        table.add_column("Description", style="white")
                        table.add_column("Status", style="green")
                        table.add_column("Created", style="dim")
                        for t in tasks:
                            status_color = "green" if t['status'] == 'completed' else "yellow" if t['status'] == 'in_progress' else "white"
                            table.add_row(
                                str(t['id']), 
                                t['description'], 
                                f"[{status_color}]{t['status']}[/]", 
                                str(t['created_at']).split()[0] if t['created_at'] else ""
                            )
                        safe_print(table)
                    continue
                    
                async def print_tool(name, args):
                    safe_print(f"[cyan]➜ Calling tool:[/cyan] {name}")
                    
                safe_print("[bold green]Agent is thinking...[/bold green]")
                response = await agent.chat(user_message, session_id, on_tool_call=print_tool)
                    
                if response:
                    safe_print(f"\n[bold green]Agent:[/bold green]")
                    safe_print(Markdown(response.response))
                    
                    if getattr(response, "requires_confirmation", False) and getattr(response, "confirmation_id", None):
                        confirm = await session.prompt_async("Do you want to confirm this action? (y/n): ")
                        if confirm.strip().lower() == 'y':
                            result = await agent.confirm_send(response.confirmation_id)
                            if result.get("success"):
                                safe_print("[bold green]Message sent successfully.[/bold green]")
                            else:
                                safe_print(f"[bold red]Failed: {result.get('error', 'Unknown error')}[/bold red]")
                        else:
                            safe_print("[bold yellow]Action cancelled.[/bold yellow]")
        except KeyboardInterrupt:
            pass
        except Exception as e:
            safe_print(f"[bold red]Error:[/bold red] {e}")
    
    # Cleanup
    if 'alert_bg_task' in locals():
        alert_bg_task.cancel()
    if 'listener_task' in locals():
        listener_task.cancel()
    safe_print("[yellow]Cleaning up...[/yellow]")
    try:
        async with asyncio.timeout(3.0):
            if 'browser' in locals():
                await browser.stop()
            if 'db' in locals():
                await db.close()
    except Exception as e:
        safe_print(f"[red]Cleanup error: {e}[/red]")
    except KeyboardInterrupt:
        pass # Ignore second Ctrl+C during cleanup

async def run_server():
    """Run the agent as an API server."""
    safe_print(Panel("[bold green]Starting WhatsApp Agent Server...[/bold green]"))
    
    db = Database(settings.db_path, settings.chroma_db_dir)
    await db.initialize()
    
    browser = WhatsAppBrowser(settings.whatsapp_profile_dir, headless=settings.whatsapp_headless)
    await browser.start()
    
    safe_print("[yellow]Waiting for login... (Please scan QR code if not logged in)[/yellow]")
    await browser.wait_for_login()
    safe_print("[bold green]Successfully logged in![/bold green]")
    
    client = WhatsAppClient(browser)
    agent = CoordinatorAgent(client, db, settings)
    await agent.initialize()
    
    from app.api.server import app, setup_app
    setup_app(browser, client, agent, db)
    
    # Start background tasks for server mode
    listener_task, alert_bg_task = start_background_tasks(client, agent, mode="server", app=app)
    
    port = settings.api_port
    host = settings.api_host
    safe_print(f"[bold cyan]Starting server on {host}:{port}[/bold cyan]")
    
    config = uvicorn.Config(fastapi_app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    
    try:
        await server.serve()
    finally:
        safe_print("[yellow]Cancelling background tasks...[/yellow]")
        if 'alert_bg_task' in locals():
            alert_bg_task.cancel()
        if 'listener_task' in locals():
            listener_task.cancel()
            
        safe_print("[yellow]Cleaning up...[/yellow]")
        try:
            async with asyncio.timeout(3.0):
                if 'browser' in locals():
                    await browser.stop()
                if 'db' in locals():
                    await db.close()
        except Exception as e:
            safe_print(f"[red]Cleanup error: {e}[/red]")
        except KeyboardInterrupt:
            pass

def start_background_tasks(client, agent, mode="cli", app=None):
    """Starts the message listener and system alert loop in the background."""
    system_queue = asyncio.Queue()
    session_id = f"{mode}_session"
    
    async def broadcast_notification(event_type: str, data: dict):
        if mode == "server" and app:
            for q in app.state.notification_queues:
                try:
                    await q.put({"type": event_type, **data})
                except Exception:
                    pass

    async def on_new_message(triggered_chats):
        try:
            chats = triggered_chats if triggered_chats else await client.get_unread_chats()
            
            if chats:
                if isinstance(chats[0], dict):
                    details = "\n".join([f"- Contact: '{c.get('contact')}', Preview: '{c.get('preview')}'" for c in chats])
                    names = ", ".join([c.get('contact') for c in chats])
                    alert = f"System Alert: New unread messages detected:\n{details}\n\nCheck them and reply if you have autopilot permission for any of them. If the preview gives you enough context, you can skip reading the full chat and just use whatsapp_draft_message or whatsapp_send_message directly."
                else:
                    names = ", ".join(chats)
                    alert = f"System Alert: New messages detected in the following chats: {names}. Check them and reply if you have autopilot permission for any of them."
                
                if mode == "cli":
                    safe_print(f"\n[bold magenta][🔔 New message from {names}][/bold magenta]")
                await broadcast_notification("new_message", {"names": names})
                
                await system_queue.put(alert)
        except Exception as e:
            pass

    listener_task = asyncio.create_task(client.start_message_listener(on_new_message))

    async def system_alert_loop():
        while True:
            try:
                alert_content = await system_queue.get()
                
                async def on_tool_bg(name, args):
                    if mode == "cli":
                        safe_print(f"[cyan]➜ Calling tool:[/cyan] {name}")
                    await broadcast_notification("tool", {"name": name, "args": args})
                
                if mode == "cli":
                    safe_print("[bold green]Agent is checking system alerts...[/bold green]")
                await broadcast_notification("agent_thinking", {})
                
                response = await agent.chat(alert_content, session_id, on_tool_call=on_tool_bg)
                
                if response:
                    if mode == "cli":
                        safe_print(f"\n[bold green]Agent:[/bold green]")
                        safe_print(response.response)
                        if getattr(response, "requires_confirmation", False) and getattr(response, "confirmation_id", None):
                            safe_print("[dim](Auto-skipping confirmation for background alert)[/dim]")
                    
                    await broadcast_notification("agent_done", {"response": response.model_dump()})
            except asyncio.CancelledError:
                break
            except Exception as e:
                pass

    alert_bg_task = asyncio.create_task(system_alert_loop())
    return listener_task, alert_bg_task

def main():
    parser = argparse.ArgumentParser(description="WhatsApp Agent")
    parser.add_argument("--mode", choices=["cli", "server"], default="cli")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    
    if args.port is not None:
        settings.api_port = args.port
        
    try:
        if args.mode == "cli":
            asyncio.run(run_cli())
        else:
            asyncio.run(run_server())
    except KeyboardInterrupt:
        safe_print("\n[bold red]Exiting forcefully...[/bold red]")
        os._exit(0)

if __name__ == "__main__":
    main()
