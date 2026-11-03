# 📖 Workshop Solutions & Reference Guide

This file contains the complete reference solutions for the **6 Hands-On Workshop Exercises**.
If students get stuck or want to verify their logic, they can refer to the implementations below.

---

### Exercise 1: Search Contact
**File**: `app/tools/whatsapp_search_contact.py`

```python
async def execute(client: WhatsAppClient, args: dict, db: Any = None) -> SearchContactOutput:
    try:
        input_data = SearchContactInput(**args)
        
        # 1. Ask the client to search WhatsApp for the given name
        result = await client.search_contact(input_data.name)
        
        # 2. Extract matched contact objects into simple dictionaries
        matches = [{"name": match.name, "phone": match.phone} for match in result.matches]
        
        return SearchContactOutput(
            success=True,
            matches=matches,
            query=result.query
        )
    except Exception as e:
        logger.error(f"Error in whatsapp_search_contact: {e}")
        return SearchContactOutput(success=False, matches=[], query=args.get("name", ""), error=str(e))
```

---

### Exercise 2: Open Chat
**File**: `app/tools/whatsapp_open_chat.py`

```python
async def execute(client: WhatsAppClient, args: dict, db: Any = None) -> OpenChatOutput:
    try:
        input_data = OpenChatInput(**args)
        
        # 1. Ask Playwright to click into the chat
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

### Exercise 3: Read Recent Messages (Perception)
**File**: `app/tools/whatsapp_read_messages.py`

```python
async def execute(client: WhatsAppClient, args: dict, db: Any = None) -> ReadMessagesOutput:
    try:
        input_data = ReadMessagesInput(**args)
        
        # 1. Scrape the last N messages from the active chat
        chat_messages = await client.get_recent_messages(input_data.contact, input_data.limit)
        
        # 2. Format the messages so Gemini can distinguish who said what
        messages = [
            {
                "sender": msg.sender,
                "timestamp": msg.timestamp,
                "text": msg.text,
                "is_from_me": msg.is_from_me  # Critical for context!
            } for msg in chat_messages.messages
        ]
        
        return ReadMessagesOutput(
            success=True,
            contact=input_data.contact,
            messages=messages
        )
    except Exception as e:
        logger.error(f"Error in whatsapp_read_messages: {e}")
        return ReadMessagesOutput(success=False, contact=args.get("contact", ""), error=str(e))
```

---

### Exercise 4: Send Message (Human-in-the-Loop Safety Gate)
**File**: `app/tools/whatsapp_send_message.py`

```python
async def execute(client: WhatsAppClient, args: dict, db: Any = None) -> SendMessageOutput:
    try:
        input_data = SendMessageInput(**args)
        
        # STEP 1: Safety Check! If not explicitly confirmed, stage it in SQLite
        if not input_data.confirmed:
            if not db:
                raise ValueError("Database is required for pending confirmations")
            import json
            confirmation_id = await db.create_pending_confirmation(
                input_data.contact, 
                json.dumps(input_data.messages)
            )
            return SendMessageOutput(
                success=True,
                contact=input_data.contact,
                messages=input_data.messages,
                requires_confirmation=True,
                confirmation_id=confirmation_id
            )
        
        # STEP 2: When confirmed, dispatch through WhatsApp
        success = await client.send_message(input_data.contact, input_data.messages)
        return SendMessageOutput(
            success=success,
            contact=input_data.contact,
            messages=input_data.messages,
            requires_confirmation=False,
            error=None if success else "Failed to send message via WhatsApp."
        )
    except Exception as e:
        logger.error(f"Error in whatsapp_send_message: {e}")
        return SendMessageOutput(success=False, contact=args.get("contact", ""), messages=args.get("messages", []), error=str(e))
```

---

### Exercise 5: Detect Unread Messages (Event Detection)
**File**: `app/tools/whatsapp_get_unread_chats.py`

```python
async def execute(client: WhatsAppClient, args: dict[str, Any], db: Database | None = None) -> BaseModel:
    try:
        # 1. Ask Playwright to scan the contact list for unread badges
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

### Exercise 6: Contextual Message Drafting
**File**: `app/tools/whatsapp_draft_message.py`

```python
# 1. Read last 5 messages for context:
recent_msgs = await client.get_recent_messages(input_data.contact, limit=5)
context = "\n".join([f"{msg.sender}: {msg.text}" for msg in recent_msgs.messages])

# 2. Ask Gemini to generate natural WhatsApp message bubbles:
prompt = (
    f"Draft WhatsApp messages to {input_data.contact}.\n"
    f"Context:\n{context}\n\n"
    f"Instruction: {input_data.instruction}\n"
    f"Separate multiple short messages with a double newline."
)

response = await genai_client.aio.models.generate_content(model=model, contents=prompt)
drafts = [msg.strip() for msg in response.text.split("\n\n") if msg.strip()]
```
