# 📖 Workshop Solutions & Reference Guide

This file contains the complete reference solutions for the **Workshop Exercises**.
Students can refer to these exact snippets if they get stuck or want to verify their code.

---

### Exercise 1: How Gemini Selects Tools (The Description)
**File**: `app/tools/whatsapp_search_contact.py`

* **Goal**: Provide the natural language description so Gemini knows when to trigger the tool.
* **Solution**:
```python
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "whatsapp_search_contact",
        # Added description:
        "description": "Search for a contact on WhatsApp by name or phone number.",
        "parameters": SearchContactInput.model_json_schema()
    }
}
```

---

### Exercise 2: Browser Automation (Opening a Chat Window)
**File**: `app/tools/whatsapp_open_chat.py`

* **Goal**: Call Playwright to navigate to the contact's chat.
* **Solution**:
```python
async def execute(client: WhatsAppClient, args: dict, db: Any = None) -> OpenChatOutput:
    try:
        input_data = OpenChatInput(**args)
        
        # Call client to open chat:
        success = await client.open_chat(input_data.contact)

        return OpenChatOutput(
            success=success,
            contact=input_data.contact,
            error=None if success else "Failed to open chat."
        )
    except Exception as e:
        logger.error(f"Error in whatsapp_open_chat: {e}")
        return OpenChatOutput(success=False, contact=args.get("contact", ""), error=str(e))
```

---

### Exercise 3: Perception — "Who Said What?"
**File**: `app/tools/whatsapp_read_messages.py`

* **Goal**: Scrape recent text bubbles and label `sender` as `"Me"` if `is_from_me` is True, otherwise use the friend's name.
* **Solution**:
```python
async def execute(client: WhatsAppClient, args: dict, db: Any = None) -> ReadMessagesOutput:
    try:
        input_data = ReadMessagesInput(**args)
        
        # 1. Fetch recent messages
        chat_messages = await client.get_recent_messages(input_data.contact, input_data.limit)

        # 2. Format with sender semantic perception:
        formatted_messages = []
        for msg in chat_messages.messages:
            sender = "Me" if msg.is_from_me else input_data.contact
            formatted_messages.append({
                "sender": sender,
                "text": msg.text,
                "timestamp": msg.timestamp,
                "is_from_me": msg.is_from_me
            })

        return ReadMessagesOutput(
            success=True,
            contact=input_data.contact,
            messages=formatted_messages
        )
    except Exception as e:
        logger.error(f"Error in whatsapp_read_messages: {e}")
        return ReadMessagesOutput(success=False, contact=args.get("contact", ""), error=str(e))
```

---

### Exercise 4: Event Sensing (Scanning for Unread Badges)
**File**: `app/tools/whatsapp_get_unread_chats.py`

* **Goal**: Scan the WhatsApp sidebar for unread count badges.
* **Solution**:
```python
async def execute(client: WhatsAppClient, args: dict[str, Any], db: Database | None = None) -> BaseModel:
    try:
        # Call client to find chats with unread badges:
        chats = await client.get_unread_chats()

        return GetUnreadChatsOutput(
            success=True,
            unread_chats=chats
        )
    except Exception as e:
        logger.error(f"Error in whatsapp_get_unread_chats: {e}")
        return GetUnreadChatsOutput(success=False, unread_chats=[], error=str(e))
```

---

### Exercise 5: Contextual Prompt Engineering
**File**: `app/tools/whatsapp_draft_message.py`

* **Goal**: Combine the 4 key ingredients (recipient, context, instruction, formatting rules) into an LLM prompt.
* **Solution**:
```python
# Construct the prompt combining all 4 elements:
prompt = (
    f"You are drafting WhatsApp messages to {input_data.contact}.\n"
    f"Recent Conversation:\n{context}\n\n"
    f"User Instruction: {input_data.instruction}\n"
    f"Generate 1 to 3 short realistic WhatsApp messages separated by double newlines."
)
```

---

### Exercise 6: Send Message (Human-in-the-Loop Safety Gate)
**File**: `app/tools/whatsapp_send_message.py`

* **Goal**: Never send an outward message without human approval.
* **Solution**:
```python
if not input_data.confirmed:
    if not db:
        raise ValueError("Database is required for pending confirmations")
    import json
    confirmation_id = await db.create_pending_confirmation(input_data.contact, json.dumps(input_data.messages))
    return SendMessageOutput(
        success=True,
        contact=input_data.contact,
        messages=input_data.messages,
        requires_confirmation=True,
        confirmation_id=confirmation_id
    )

# When explicitly confirmed:
success = await client.send_message(input_data.contact, input_data.messages)
return SendMessageOutput(success=success, contact=input_data.contact, messages=input_data.messages)
```
