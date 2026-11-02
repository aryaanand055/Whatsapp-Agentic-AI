"""Unit tests for WhatsApp tools using mocked WhatsApp client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.whatsapp.models import Contact, SearchResult, Message, ChatMessages, ConnectionStatus
from app.whatsapp.exceptions import ContactNotFound, MessageSendError
from app.tools import (
    whatsapp_search_contact,
    whatsapp_open_chat,
    whatsapp_read_messages,
    whatsapp_draft_message,
    whatsapp_send_message,
)


# ── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def mock_client():
    """Create a mock WhatsAppClient with default return values."""
    client = AsyncMock()
    client.search_contact.return_value = SearchResult(
        query="Rahul",
        matches=[Contact(name="Rahul Kumar", phone="+91XXXXXXXXXX")],
    )
    client.open_chat.return_value = True
    client.get_recent_messages.return_value = ChatMessages(
        contact="Rahul Kumar",
        messages=[
            Message(sender="Rahul Kumar", timestamp="14:32", text="Are you coming tomorrow?", is_from_me=False),
            Message(sender="Me", timestamp="14:35", text="Yes, I'll be there.", is_from_me=True),
        ],
    )
    client.send_message.return_value = True
    return client


@pytest.fixture
def mock_db():
    """Create a mock Database."""
    db = AsyncMock()
    db.log_tool_execution.return_value = 1
    db.create_pending_confirmation.return_value = "test-confirmation-id-1234"
    db.confirm_pending.return_value = {
        "confirmation_id": "test-confirmation-id-1234",
        "contact": "Rahul Kumar",
        "message": "I'll reach at 6.",
        "status": "confirmed",
    }
    return db


@pytest.fixture
def mock_llm_client():
    """Create a mock Google Gemini client."""
    genai_client = MagicMock()
    # Mock the async generate_content path: client.aio.models.generate_content()
    mock_response = MagicMock()
    mock_response.text = "Sure, I'll be there at 6!"
    genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    return genai_client


# ── Search Contact Tests ─────────────────────────────────


@pytest.mark.asyncio
async def test_search_contact_valid(mock_client, mock_db):
    """Search with a valid name returns matching contacts."""
    result = await whatsapp_search_contact.execute(
        mock_client, {"name": "Rahul"}, mock_db
    )
    assert result.success is True
    assert len(result.matches) == 1
    assert result.matches[0]["name"] == "Rahul Kumar"
    assert result.query == "Rahul"
    mock_client.search_contact.assert_awaited_once_with("Rahul")


@pytest.mark.asyncio
async def test_search_contact_multiple_matches(mock_client, mock_db):
    """Multiple matching contacts are all returned without guessing."""
    mock_client.search_contact.return_value = SearchResult(
        query="Rahul",
        matches=[
            Contact(name="Rahul Kumar"),
            Contact(name="Rahul Sharma"),
            Contact(name="Rahul Verma"),
        ],
    )
    result = await whatsapp_search_contact.execute(
        mock_client, {"name": "Rahul"}, mock_db
    )
    assert result.success is True
    assert len(result.matches) == 3


@pytest.mark.asyncio
async def test_search_contact_no_match(mock_client, mock_db):
    """Search with no matches returns empty list."""
    mock_client.search_contact.return_value = SearchResult(query="Nonexistent", matches=[])
    result = await whatsapp_search_contact.execute(
        mock_client, {"name": "Nonexistent"}, mock_db
    )
    assert result.success is True
    assert len(result.matches) == 0


@pytest.mark.asyncio
async def test_search_contact_error(mock_client, mock_db):
    """Search that raises an exception returns error output."""
    mock_client.search_contact.side_effect = Exception("Network error")
    result = await whatsapp_search_contact.execute(
        mock_client, {"name": "Rahul"}, mock_db
    )
    assert result.success is False
    assert "Network error" in result.error


# ── Open Chat Tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_open_chat_valid(mock_client, mock_db):
    """Opening a chat with a valid contact succeeds."""
    result = await whatsapp_open_chat.execute(
        mock_client, {"contact": "Rahul Kumar"}, mock_db
    )
    assert result.success is True
    assert result.contact == "Rahul Kumar"


@pytest.mark.asyncio
async def test_open_chat_not_found(mock_client, mock_db):
    """Opening a chat for an unknown contact returns error."""
    mock_client.open_chat.side_effect = ContactNotFound("Contact not found")
    result = await whatsapp_open_chat.execute(
        mock_client, {"contact": "Unknown Person"}, mock_db
    )
    assert result.success is False
    assert result.error is not None


# ── Read Messages Tests ──────────────────────────────────


@pytest.mark.asyncio
async def test_read_messages_valid(mock_client, mock_db):
    """Reading messages returns structured message list."""
    result = await whatsapp_read_messages.execute(
        mock_client, {"contact": "Rahul Kumar", "limit": 10}, mock_db
    )
    assert result.success is True
    assert result.contact == "Rahul Kumar"
    assert len(result.messages) == 2
    assert result.messages[0]["sender"] == "Rahul Kumar"
    assert result.messages[0]["is_from_me"] is False
    assert result.messages[1]["is_from_me"] is True


@pytest.mark.asyncio
async def test_read_messages_distinguishes_sender(mock_client, mock_db):
    """Messages correctly distinguish between sent and received."""
    result = await whatsapp_read_messages.execute(
        mock_client, {"contact": "Rahul Kumar"}, mock_db
    )
    received = [m for m in result.messages if not m["is_from_me"]]
    sent = [m for m in result.messages if m["is_from_me"]]
    assert len(received) == 1
    assert len(sent) == 1


@pytest.mark.asyncio
async def test_read_messages_error(mock_client, mock_db):
    """Read messages with error returns structured error."""
    mock_client.get_recent_messages.side_effect = Exception("Chat not found")
    result = await whatsapp_read_messages.execute(
        mock_client, {"contact": "Unknown"}, mock_db
    )
    assert result.success is False
    assert result.error is not None


# ── Draft Message Tests ──────────────────────────────────


@pytest.mark.asyncio
async def test_draft_message_valid(mock_client, mock_db, mock_llm_client):
    """Drafting a message returns LLM-generated text."""
    result = await whatsapp_draft_message.execute(
        mock_client,
        {"contact": "Rahul Kumar", "instruction": "Say I'll reach at 6"},
        mock_db,
        mock_llm_client,
        "gemini-2.0-flash",
    )
    assert result.success is True
    assert len(result.drafts) > 0
    assert result.contact == "Rahul Kumar"


@pytest.mark.asyncio
async def test_draft_message_no_llm(mock_client, mock_db):
    """Drafting without an LLM client returns an error."""
    result = await whatsapp_draft_message.execute(
        mock_client,
        {"contact": "Rahul Kumar", "instruction": "Say hello"},
        mock_db,
        None,
    )
    assert result.success is False
    assert "genai_client" in result.error.lower()


# ── Send Message Tests ───────────────────────────────────


@pytest.mark.asyncio
async def test_send_message_requires_confirmation(mock_client, mock_db):
    """Send without confirmed=True creates a pending confirmation."""
    result = await whatsapp_send_message.execute(
        mock_client,
        {"contact": "Rahul Kumar", "messages": ["I'll reach at 6."]},
        mock_db,
    )
    assert result.success is True
    assert result.requires_confirmation is True
    assert result.confirmation_id == "test-confirmation-id-1234"
    # Must NOT call client.send_message
    mock_client.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_message_with_confirmation(mock_client, mock_db):
    """Send with confirmed=True actually sends the message."""
    result = await whatsapp_send_message.execute(
        mock_client,
        {"contact": "Rahul Kumar", "messages": ["I'll reach at 6."], "confirmed": True},
        mock_db,
    )
    assert result.success is True
    assert result.requires_confirmation is False
    mock_client.send_message.assert_awaited_once_with("Rahul Kumar", ["I'll reach at 6."])


@pytest.mark.asyncio
async def test_send_message_failure(mock_client, mock_db):
    """Send that fails at the Playwright level returns error."""
    mock_client.send_message.side_effect = MessageSendError("Could not send")
    result = await whatsapp_send_message.execute(
        mock_client,
        {"contact": "Rahul Kumar", "messages": ["Test"], "confirmed": True},
        mock_db,
    )
    assert result.success is False
    assert result.error is not None


# ── Argument Validation Tests ────────────────────────────


@pytest.mark.asyncio
async def test_search_contact_missing_name(mock_client, mock_db):
    """Missing required 'name' field raises validation error."""
    result = await whatsapp_search_contact.execute(mock_client, {}, mock_db)
    assert result.success is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_send_message_missing_fields(mock_client, mock_db):
    """Missing required fields in send returns error."""
    result = await whatsapp_send_message.execute(mock_client, {}, mock_db)
    assert result.success is False
    assert result.error is not None
