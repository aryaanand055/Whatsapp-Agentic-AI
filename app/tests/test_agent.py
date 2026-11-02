"""Tests for the agent, API authentication, and confirmation flow."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.database.db import Database
from app.agent.agent import WhatsAppAgent, AgentResponse


# ── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def mock_settings():
    """Mock settings object."""
    s = MagicMock()
    s.llm_api_key = "test-key"
    s.llm_model = "gemini-2.0-flash"
    s.api_key = "test-api-key"
    return s


@pytest.fixture
def mock_client():
    """Mock WhatsApp client."""
    return AsyncMock()


@pytest.fixture
def mock_db():
    """Mock database with all required methods."""
    db = AsyncMock()
    db.get_session_state.return_value = None
    db.save_session_state.return_value = None
    db.create_pending_confirmation.return_value = "confirm-123"
    db.confirm_pending.return_value = {
        "confirmation_id": "confirm-123",
        "contact": "Rahul Kumar",
        "message": '["I\'ll reach at 6."]',
        "status": "confirmed",
    }
    db.log_tool_execution.return_value = 1
    return db


# ── Confirmation Flow Tests ──────────────────────────────


@pytest.mark.asyncio
async def test_confirm_send_valid(mock_client, mock_db, mock_settings):
    """Confirming a valid pending confirmation sends the message."""
    mock_client.send_message.return_value = True
    agent = WhatsAppAgent(mock_client, mock_db, mock_settings)

    result = await agent.confirm_send("confirm-123")

    assert result["success"] is True
    assert result["contact"] == "Rahul Kumar"
    assert result["message"] == ["I'll reach at 6."]
    mock_client.send_message.assert_awaited_once_with("Rahul Kumar", ["I'll reach at 6."])


@pytest.mark.asyncio
async def test_confirm_send_invalid(mock_client, mock_db, mock_settings):
    """Confirming an invalid/expired ID returns error."""
    mock_db.confirm_pending.return_value = None
    agent = WhatsAppAgent(mock_client, mock_db, mock_settings)

    result = await agent.confirm_send("invalid-id")

    assert result["success"] is False
    assert "Invalid" in result["error"] or "expired" in result["error"]
    mock_client.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirm_send_message_failure(mock_client, mock_db, mock_settings):
    """If send_message fails after confirmation, error is returned."""
    mock_client.send_message.return_value = False
    agent = WhatsAppAgent(mock_client, mock_db, mock_settings)

    result = await agent.confirm_send("confirm-123")

    assert result["success"] is False


# ── Database Confirmation Flow ───────────────────────────


@pytest.mark.asyncio
async def test_db_create_and_confirm_pending():
    """Integration test: create → confirm flow using real Database."""
    import os
    import tempfile

    db_path = os.path.join(tempfile.gettempdir(), "test_agent.db")
    db = Database(db_path)
    await db.initialize()

    try:
        # Create a pending confirmation
        cid = await db.create_pending_confirmation("Rahul Kumar", "Hello!")
        assert cid is not None

        # Retrieve it
        pending = await db.get_pending_confirmation(cid)
        assert pending is not None
        assert pending["status"] == "pending"
        assert pending["contact"] == "Rahul Kumar"

        # Confirm it
        confirmed = await db.confirm_pending(cid)
        assert confirmed is not None
        assert confirmed["status"] == "confirmed"

        # Try to confirm again — should not change (already confirmed)
        re_confirmed = await db.confirm_pending(cid)
        # Status is already 'confirmed', so the UPDATE WHERE status='pending' won't match
        assert re_confirmed["status"] == "confirmed"
    finally:
        await db.close()
        if os.path.exists(db_path):
            os.remove(db_path)


@pytest.mark.asyncio
async def test_db_cancel_pending():
    """Integration test: create → cancel flow."""
    import os
    import tempfile

    db_path = os.path.join(tempfile.gettempdir(), "test_agent_cancel.db")
    db = Database(db_path)
    await db.initialize()

    try:
        cid = await db.create_pending_confirmation("Test Contact", "Test message")
        cancelled = await db.cancel_pending(cid)
        assert cancelled is True

        # Verify status
        pending = await db.get_pending_confirmation(cid)
        assert pending["status"] == "cancelled"
    finally:
        await db.close()
        if os.path.exists(db_path):
            os.remove(db_path)


# ── API Authentication Tests ────────────────────────────


@pytest.mark.asyncio
async def test_api_health_no_auth():
    """Health endpoint works without authentication."""
    import httpx
    from app.api.server import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_api_requires_auth():
    """Protected endpoints reject requests without API key."""
    import httpx
    from app.api.server import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/whatsapp/status")
        assert response.status_code in (403, 422)  # Missing header


@pytest.mark.asyncio
async def test_api_wrong_key():
    """Protected endpoints reject requests with wrong API key."""
    import httpx
    from app.api.server import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/whatsapp/status",
            headers={"X-API-Key": "wrong-key-here"}
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_api_validation_error():
    """POST endpoints reject requests with missing required fields."""
    import httpx
    from app.api.server import app
    from app.config import settings

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/whatsapp/search",
            json={},
            headers={"X-API-Key": settings.api_key},
        )
        assert response.status_code == 422
