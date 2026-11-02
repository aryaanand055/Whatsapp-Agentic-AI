"""Database manager using aiosqlite."""

import aiosqlite
import json
import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.database.models import CREATE_TABLES_SQL

logger = logging.getLogger(__name__)

class Database:
    """Async SQLite database manager."""

    def __init__(self, db_path: str, chroma_db_dir: Optional[str] = None):
        self.db_path = db_path
        self.chroma_db_dir = chroma_db_dir
        self._conn: Optional[aiosqlite.Connection] = None
        self.chroma_client = None
        self.memory_collection = None

    async def initialize(self) -> None:
        """Create tables and initialize the database."""
        self._conn = await aiosqlite.connect(self.db_path)
        for statement in CREATE_TABLES_SQL.split(";"):
            if statement.strip():
                await self._conn.execute(statement)
                
        # Migration: Add task_id to tool_executions if it doesn't exist
        try:
            await self._conn.execute("ALTER TABLE tool_executions ADD COLUMN task_id INTEGER")
        except Exception:
            pass # Column already exists
            
        await self._conn.commit()

        # Initialize ChromaDB if dir is provided
        if self.chroma_db_dir:
            import chromadb
            import os
            os.makedirs(self.chroma_db_dir, exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(path=self.chroma_db_dir)
            self.memory_collection = self.chroma_client.get_or_create_collection(name="memories")
            
            # Migration/Sync Step: Make sure all SQLite memories are loaded into ChromaDB
            # under the corrected metadata tags (e.g. '__global__' sentinels)
            try:
                # Retrieve all memories directly from SQLite
                async with self._conn.execute("SELECT id, contact, memory_text FROM memories") as cursor:
                    rows = await cursor.fetchall()
                    if rows:
                        documents = [row[2] for row in rows]
                        metadatas = [{"contact": row[1] if row[1] else "__global__"} for row in rows]
                        ids = [str(row[0]) for row in rows]
                        
                        # Upsert them directly to sync everything cleanly
                        self.memory_collection.upsert(
                            documents=documents,
                            metadatas=metadatas,
                            ids=ids
                        )
            except Exception as e:
                logger.error(f"Failed to sync SQLite memories to ChromaDB on init: {e}")

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def log_tool_execution(
        self, tool_name: str, arguments: Dict[str, Any], result: Optional[Dict[str, Any]] = None, error: Optional[str] = None, task_id: Optional[int] = None
    ) -> int:
        """Log a tool execution."""
        cursor = await self._conn.execute(
            """
            INSERT INTO tool_executions (tool_name, arguments, result, error, task_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                tool_name,
                json.dumps(arguments),
                json.dumps(result) if result is not None else None,
                error,
                task_id,
            ),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def get_tool_executions(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieve tool execution logs."""
        async with self._conn.execute(
            """
            SELECT id, tool_name, arguments, result, error, task_id, created_at
            FROM tool_executions
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "tool_name": row[1],
                    "arguments": json.loads(row[2]) if row[2] else None,
                    "result": json.loads(row[3]) if row[3] else None,
                    "error": row[4],
                    "task_id": row[5],
                    "created_at": row[6],
                }
                for row in rows
            ]

    async def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session state by session_id."""
        async with self._conn.execute(
            "SELECT state FROM sessions WHERE session_id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
            return None

    async def save_session_state(self, session_id: str, state: Dict[str, Any]) -> None:
        """Save session state."""
        await self._conn.execute(
            """
            INSERT INTO sessions (session_id, state)
            VALUES (?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                state = excluded.state,
                updated_at = CURRENT_TIMESTAMP
            """,
            (session_id, json.dumps(state)),
        )
        await self._conn.commit()

    async def cache_contact(self, name: str, phone: Optional[str] = None) -> None:
        """Cache a contact's information."""
        await self._conn.execute(
            """
            INSERT INTO contacts_cache (name, phone)
            VALUES (?, ?)
            """,
            (name, phone),
        )
        await self._conn.commit()

    async def get_cached_contacts(self, name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve cached contacts, optionally filtering by name."""
        query = "SELECT id, name, phone, discovered_at FROM contacts_cache"
        params = []
        if name:
            query += " WHERE name LIKE ?"
            params.append(f"%{name}%")
            
        async with self._conn.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "phone": row[2],
                    "discovered_at": row[3],
                }
                for row in rows
            ]

    async def create_pending_confirmation(self, contact: str, message: str) -> str:
        """Create a pending confirmation and return the confirmation_id."""
        confirmation_id = str(uuid.uuid4())
        await self._conn.execute(
            """
            INSERT INTO pending_confirmations (confirmation_id, contact, message, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (confirmation_id, contact, message),
        )
        await self._conn.commit()
        return confirmation_id

    async def get_pending_confirmation(self, confirmation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a pending confirmation by ID."""
        async with self._conn.execute(
            "SELECT confirmation_id, contact, message, status, created_at, confirmed_at FROM pending_confirmations WHERE confirmation_id = ?",
            (confirmation_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "confirmation_id": row[0],
                    "contact": row[1],
                    "message": row[2],
                    "status": row[3],
                    "created_at": row[4],
                    "confirmed_at": row[5]
                }
            return None

    async def confirm_pending(self, confirmation_id: str) -> Optional[Dict[str, Any]]:
        """Confirm a pending request."""
        await self._conn.execute(
            """
            UPDATE pending_confirmations
            SET status = 'confirmed', confirmed_at = CURRENT_TIMESTAMP
            WHERE confirmation_id = ? AND status = 'pending'
            """,
            (confirmation_id,)
        )
        await self._conn.commit()
        return await self.get_pending_confirmation(confirmation_id)

    async def cancel_pending(self, confirmation_id: str) -> bool:
        """Cancel a pending request."""
        cursor = await self._conn.execute(
            """
            UPDATE pending_confirmations
            SET status = 'cancelled'
            WHERE confirmation_id = ? AND status = 'pending'
            """,
            (confirmation_id,)
        )
        await self._conn.commit()
        return cursor.rowcount > 0

    async def log_error(self, tool_name: str, error_type: str, error_message: str) -> None:
        """Log an error."""
        await self._conn.execute(
            """
            INSERT INTO errors (tool_name, error_type, error_message)
            VALUES (?, ?, ?)
            """,
            (tool_name, error_type, error_message),
        )
        await self._conn.commit()

    async def save_user_style(self, style_text: str) -> None:
        """Save user's writing style profile."""
        await self._conn.execute(
            """
            INSERT INTO settings (key, value)
            VALUES ('user_writing_style', ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (style_text,),
        )
        await self._conn.commit()

    async def get_user_style(self) -> Optional[str]:
        """Get stored user writing style profile."""
        async with self._conn.execute(
            "SELECT value FROM settings WHERE key = 'user_writing_style'"
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return row[0]
            return None

    # --- Memory and Contact Profile Helpers ---

    async def add_memory(self, memory_text: str, contact: Optional[str] = None) -> int:
        """Add a memory (global if contact is None, otherwise specific to contact)."""
        cursor = await self._conn.execute(
            """
            INSERT INTO memories (contact, memory_text)
            VALUES (?, ?)
            """,
            (contact, memory_text),
        )
        await self._conn.commit()
        memory_id = cursor.lastrowid

        # Sync to ChromaDB
        if self.memory_collection is not None:
            metadata = {"contact": contact if contact else "__global__"}
            self.memory_collection.add(
                documents=[memory_text],
                metadatas=[metadata],
                ids=[str(memory_id)]
            )
            
        return memory_id

    async def get_memories(self, contact: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve memories. If contact is provided, returns global + contact-specific memories."""
        query = "SELECT id, contact, memory_text, created_at FROM memories WHERE contact IS NULL"
        params = []
        
        if contact:
            query += " OR contact = ?"
            params.append(contact)
            
        query += " ORDER BY created_at DESC"
        
        async with self._conn.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "contact": row[1],
                    "memory_text": row[2],
                    "created_at": row[3],
                }
                for row in rows
            ]

    async def delete_memory(self, memory_id: int) -> bool:
        """Delete a specific memory by ID."""
        cursor = await self._conn.execute(
            "DELETE FROM memories WHERE id = ?",
            (memory_id,)
        )
        await self._conn.commit()
        
        # Sync to ChromaDB
        if self.memory_collection is not None and cursor.rowcount > 0:
            self.memory_collection.delete(ids=[str(memory_id)])
            
        return cursor.rowcount > 0

    async def search_memory(self, query: str, contact: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Search ChromaDB for semantically similar memories."""
        if self.memory_collection is None:
            return []
            
        where = None
        if contact:
            # Search both the specific contact's memories and global memories
            where = {"contact": {"$in": [contact, "__global__"]}}
        else:
            # Search only global memories
            where = {"contact": "__global__"}
            
        results = self.memory_collection.query(
            query_texts=[query],
            n_results=limit,
            where=where
        )
        
        memories = []
        if results and results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                memories.append({
                    "id": int(results['ids'][0][i]),
                    "memory_text": doc,
                    "metadata": results['metadatas'][0][i] if results['metadatas'] else {}
                })
        return memories

    async def save_contact_style(self, contact: str, style_text: str) -> None:
        """Save a specific contact's conversational style profile."""
        await self._conn.execute(
            """
            INSERT INTO contact_profiles (contact, writing_style)
            VALUES (?, ?)
            ON CONFLICT(contact) DO UPDATE SET
                writing_style = excluded.writing_style,
                updated_at = CURRENT_TIMESTAMP
            """,
            (contact, style_text),
        )
        await self._conn.commit()

    async def get_contact_style(self, contact: str) -> Optional[str]:
        """Get a specific contact's conversational style profile."""
        async with self._conn.execute(
            "SELECT writing_style FROM contact_profiles WHERE contact = ?",
            (contact,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return row[0]
            return None

    # --- Task Management ---

    async def add_task(self, description: str) -> int:
        """Add a new task."""
        cursor = await self._conn.execute(
            """
            INSERT INTO tasks (description)
            VALUES (?)
            """,
            (description,),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def get_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve tasks, optionally filtered by status."""
        query = "SELECT id, description, status, created_at, updated_at FROM tasks"
        params = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at ASC"
        
        async with self._conn.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "description": row[1],
                    "status": row[2],
                    "created_at": row[3],
                    "updated_at": row[4],
                }
                for row in rows
            ]

    async def update_task_status(self, task_id: int, status: str) -> bool:
        """Update a task's status."""
        cursor = await self._conn.execute(
            """
            UPDATE tasks
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, task_id)
        )
        await self._conn.commit()
        return cursor.rowcount > 0

    async def delete_task(self, task_id: int) -> bool:
        """Delete a task."""
        cursor = await self._conn.execute(
            "DELETE FROM tasks WHERE id = ?",
            (task_id,)
        )
        await self._conn.commit()
        return cursor.rowcount > 0

    async def set_autopilot(self, contact: str, duration_hours: float, goal: str) -> None:
        """Enable autopilot for a contact for a specific duration."""
        from datetime import datetime, timedelta
        active_until = datetime.utcnow() + timedelta(hours=duration_hours)
        await self._conn.execute(
            """
            INSERT INTO autopilot_configs (contact, duration_hours, goal, active_until)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(contact) DO UPDATE SET
                duration_hours = excluded.duration_hours,
                goal = excluded.goal,
                active_until = excluded.active_until
            """,
            (contact, duration_hours, goal, active_until.isoformat()),
        )
        await self._conn.commit()

    async def get_active_autopilot(self, contact: str) -> Optional[Dict[str, Any]]:
        """Get the active autopilot configuration for a contact, if valid."""
        async with self._conn.execute(
            """
            SELECT duration_hours, goal, active_until, created_at
            FROM autopilot_configs
            WHERE contact = ? AND datetime(active_until) > datetime('now')
            """,
            (contact,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "duration_hours": row[0],
                    "goal": row[1],
                    "active_until": row[2],
                    "created_at": row[3],
                }
            return None

    async def get_all_active_autopilots(self) -> List[Dict[str, Any]]:
        """Get all active autopilot configurations."""
        async with self._conn.execute(
            """
            SELECT contact, duration_hours, goal, active_until, created_at
            FROM autopilot_configs
            WHERE datetime(active_until) > datetime('now')
            """
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "contact": row[0],
                    "duration_hours": row[1],
                    "goal": row[2],
                    "active_until": row[3],
                    "created_at": row[4],
                }
                for row in rows
            ]

    async def disable_autopilot(self, contact: str) -> None:
        """Disable autopilot for a contact."""
        await self._conn.execute(
            "DELETE FROM autopilot_configs WHERE contact = ?",
            (contact,),
        )
        await self._conn.commit()
