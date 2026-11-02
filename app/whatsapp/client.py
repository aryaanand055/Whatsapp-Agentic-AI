import logging
import asyncio
from playwright.async_api import Page
from .browser import WhatsAppBrowser
from .models import Contact, SearchResult, Message, ChatMessages
from .exceptions import (
    ContactNotFound, ElementNotFound, 
    MessageSendError, AuthenticationRequired
)
from .selectors import (
    WhatsAppSelectors, wait_for_whatsapp_ready, find_search_box,
    find_chat_by_name, find_message_elements, find_message_input,
    find_send_button
)

logger = logging.getLogger(__name__)

class WhatsAppClient:
    def __init__(self, browser: WhatsAppBrowser):
        self.browser = browser
        self._lock = asyncio.Lock()

    async def _get_page(self) -> Page:
        page = await self.browser.get_page()
        if not await wait_for_whatsapp_ready(page):
            raise AuthenticationRequired("WhatsApp is not authenticated or not ready.")
        return page

    async def search_contact(self, name: str) -> SearchResult:
        async with self._lock:
            page = await self._get_page()
        for attempt in range(3):
            try:
                search_box = await find_search_box(page)
                await search_box.click()
                await search_box.fill("")
                await search_box.type(name, delay=100)
                
                await asyncio.sleep(2) # wait for results
                
                locators = page.locator(WhatsAppSelectors.SEARCH_RESULT_ITEM)
                count = await locators.count()
                
                matches = []
                for i in range(count):
                    locator = locators.nth(i)
                    title_loc = locator.locator(WhatsAppSelectors.SEARCH_RESULT_TITLE)
                    if await title_loc.count() > 0:
                        title = await title_loc.first.get_attribute("title")
                        if title:
                            matches.append(Contact(name=title))
                
                # Clear search
                await search_box.fill("")
                await page.keyboard.press("Escape")
                
                return SearchResult(query=name, matches=matches)
            except Exception as e:
                logger.warning(f"Search attempt {attempt+1} failed: {e}")
                await asyncio.sleep(1)
        
        raise ElementNotFound(f"Could not complete search for '{name}'")

    async def _open_chat(self, page: Page, contact: str) -> bool:
        """Internal method to open a chat, assumes caller holds the lock and provides the page."""
        
        # 1. Fast path: Check if the chat is already open
        try:
            header = page.locator(WhatsAppSelectors.CHAT_HEADER_TITLE).first
            if await header.count() > 0:
                title = await header.get_attribute("title")
                if title:
                    title_clean = title.strip().lower()
                    contact_clean = contact.strip().lower()
                    if title_clean == contact_clean:
                        logger.info(f"Chat '{contact}' is already active, skipping search.")
                        return True
                    
                    import re
                    # Fallback for phone numbers (compare digits and plus sign)
                    title_digits = re.sub(r'[^\d+]', '', title)
                    contact_digits = re.sub(r'[^\d+]', '', contact)
                    if title_digits and contact_digits and title_digits == contact_digits:
                        logger.info(f"Chat '{contact}' is already active (number match), skipping search.")
                        return True
        except Exception:
            pass
            
        # 2. Slow path: Search for the contact
        for attempt in range(3):
            try:
                search_box = await find_search_box(page)
                await search_box.click()
                await search_box.fill("")
                await search_box.type(contact, delay=100)
                
                await asyncio.sleep(2)
                
                chat_locator = await find_chat_by_name(page, contact)
                if chat_locator:
                    await chat_locator.click()
                    await asyncio.sleep(1)
                    return True
                
                # clear search
                await search_box.fill("")
                await page.keyboard.press("Escape")
                
                logger.warning(f"Chat '{contact}' not found in search results on attempt {attempt+1}")
            except Exception as e:
                logger.warning(f"Open chat attempt {attempt+1} failed: {e}")
                await asyncio.sleep(1)
                
        raise ContactNotFound(f"Contact '{contact}' not found.")

    async def open_chat(self, contact: str) -> bool:
        async with self._lock:
            page = await self._get_page()
            return await self._open_chat(page, contact)

    async def open_chat_by_number(self, phone_number: str) -> str:
        """Open a chat with any phone number (saved or unsaved) using WhatsApp Web's URL scheme.
        Returns the display name shown in the chat header after opening."""
        import re
        async with self._lock:
            page = await self._get_page()
            
            # Strip everything except digits and leading +
            cleaned = re.sub(r'[^\d+]', '', phone_number)
            # Remove leading + if present (WhatsApp URL expects digits only)
            digits_only = cleaned.lstrip('+')
            
            if len(digits_only) < 7:
                raise ContactNotFound(f"Phone number '{phone_number}' is too short.")
            
            # 1. Fast path: Check if the chat is already open
            try:
                header = page.locator(WhatsAppSelectors.CHAT_HEADER_TITLE).first
                if await header.count() > 0:
                    title = await header.get_attribute("title")
                    # The title might be the formatted phone number e.g., "+91 98765 43210"
                    if title:
                        title_digits = re.sub(r'[^\d]', '', title)
                        if digits_only in title_digits or title_digits in digits_only:
                            logger.info(f"Chat for number '{phone_number}' is already active, skipping reload.")
                            return title
            except Exception:
                pass

            # 2. Try standard search first to avoid a heavy page reload
            try:
                # If we use _open_chat with the phone number, it might find it in recents
                success = await self._open_chat(page, phone_number)
                if success:
                    # Get the display name
                    header = page.locator(WhatsAppSelectors.CHAT_HEADER_TITLE).first
                    if await header.count() > 0:
                        return await header.get_attribute("title") or digits_only
            except ContactNotFound:
                pass
            
            # 3. Slow path: Reload the page with the URL scheme
            url = f"https://web.whatsapp.com/send?phone={digits_only}"
        await page.goto(url)
        
        # Wait for the chat to load (the compose box appearing means the chat is ready)
        try:
            await page.wait_for_selector(
                WhatsAppSelectors.MESSAGE_INPUT, timeout=15000
            )
        except Exception:
            raise ContactNotFound(
                f"Could not open chat with number '{phone_number}'. "
                "Make sure the number includes the country code (e.g. +91...)."
            )
        
        await asyncio.sleep(1)
        
        # Read the chat header to get the display name (could be a saved name or just the number)
        display_name = digits_only
        try:
            header = page.locator(WhatsAppSelectors.CHAT_HEADER_TITLE).first
            if await header.count() > 0:
                display_name = await header.get_attribute("title") or digits_only
        except Exception:
            pass
        
        return display_name

    async def get_recent_messages(self, contact: str, limit: int = 10, scroll_up: bool = False) -> ChatMessages:
        async with self._lock:
            page = await self._get_page()
            await self._open_chat(page, contact)
        
        if scroll_up:
            try:
                chat_pane = page.locator('#main, [data-testid="conversation-panel-wrapper"]').first
                if await chat_pane.count() > 0:
                    await chat_pane.click()
                for _ in range(5):
                    await page.keyboard.press("PageUp")
                    await asyncio.sleep(0.3)
            except Exception:
                pass

        messages = []
        msg_elements = await find_message_elements(page, limit)
        
        for msg_el in msg_elements:
            try:
                # Skip non-message rows (like date dividers)
                if await msg_el.locator('[data-testid="msg-container"]').count() == 0:
                    continue

                is_from_me = False
                class_name = await msg_el.get_attribute("class") or ""
                data_id = await msg_el.get_attribute("data-id") or ""
                parent_data_id = ""
                try:
                    parent_data_id = await msg_el.evaluate("el => el.closest('[data-id]')?.getAttribute('data-id') || ''")
                except Exception:
                    pass

                if "message-out" in class_name or "true_" in data_id or "true_" in parent_data_id:
                    is_from_me = True
                
                text = ""
                text_loc = msg_el.locator(WhatsAppSelectors.MESSAGE_TEXT)
                if await text_loc.count() > 0:
                    text = await text_loc.first.inner_text()
                
                if not text:
                    try:
                        raw_text = await msg_el.inner_text()
                        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
                        valid_lines = [line for line in lines if not any(kw in line.lower() for kw in ["pm", "am", "edited", "read", "delivered"])]
                        if valid_lines:
                            text = "\n".join(valid_lines)
                    except Exception:
                        pass
                
                meta_loc = msg_el.locator(f"div[{WhatsAppSelectors.MESSAGE_PRE_PLAIN_TEXT}]")
                timestamp = ""
                sender = "Me" if is_from_me else contact
                if await meta_loc.count() > 0:
                    meta_str = await meta_loc.first.get_attribute(WhatsAppSelectors.MESSAGE_PRE_PLAIN_TEXT)
                    if meta_str:
                        parts = meta_str.split("] ", 1)
                        if len(parts) > 1:
                            timestamp = parts[0].strip("[")
                            sender_name = parts[1].strip(": ")
                            
                            # If we still haven't detected it's from me, check if the sender_name isn't the contact
                            if not is_from_me and sender_name.lower() != contact.lower() and sender_name != "":
                                is_from_me = True
                            
                            sender = "Me" if is_from_me else sender_name
                            
                messages.append(Message(
                    sender=sender,
                    timestamp=timestamp,
                    text=text,
                    is_from_me=is_from_me
                ))
            except Exception as e:
                logger.warning(f"Failed to parse a message: {e}")
                
        return ChatMessages(contact=contact, messages=messages)

    async def draft_message(self, contact: str, message: str) -> str:
        return message

    async def send_message(self, contact: str, messages: list[str]) -> bool:
        async with self._lock:
            page = await self._get_page()
            await self._open_chat(page, contact)
            
            for msg in messages:
                for attempt in range(3):
                    try:
                        input_box = await find_message_input(page)
                        await input_box.click()
                        # WhatsApp Web can sometimes drop characters with pure fill() or fail to register state.
                        # However, fill() usually works if followed by an Enter key.
                        # If fill() doesn't register, we might need a fallback, but let's try fill + Enter.
                        await input_box.fill(msg)
                        await input_box.press("Enter")
                        
                        await asyncio.sleep(0.5)
                        break
                    except Exception as e:
                        logger.warning(f"Send message attempt {attempt+1} failed: {e}")
                        await asyncio.sleep(1)
                        if attempt == 2:
                            raise MessageSendError(f"Failed to send message to {contact}")
                            
        return True

    async def get_unread_chats(self) -> list[dict]:
        async with self._lock:
            page = await self._get_page()
            try:
                search_box = await find_search_box(page)
                await search_box.click()
                await search_box.fill("")
                await page.keyboard.press("Escape")
                await asyncio.sleep(1)
            except Exception:
                pass
            
        unread_chats = []
        try:
            chat_items = page.locator(WhatsAppSelectors.CHAT_LIST_ITEM)
            count = await chat_items.count()
            
            for i in range(count):
                item = chat_items.nth(i)
                
                # Skip group chats
                group_icon = item.locator(WhatsAppSelectors.GROUP_ICON)
                if await group_icon.count() > 0:
                    continue
                    
                unread_badge = item.locator(WhatsAppSelectors.UNREAD_BADGE)
                if await unread_badge.count() > 0:
                    title_loc = item.locator(WhatsAppSelectors.SEARCH_RESULT_TITLE)
                    if await title_loc.count() > 0:
                        title = await title_loc.first.get_attribute("title")
                        
                        # Extract the message preview by parsing inner_text
                        preview_text = ""
                        try:
                            inner_text = await item.inner_text()
                            lines = [line.strip() for line in inner_text.split('\n') if line.strip()]
                            # Format typically is:
                            # 0: Name
                            # 1: Time
                            # 2: Preview Message (or "typing...", or "Photo", etc.)
                            # 3: Unread Count
                            if len(lines) >= 3:
                                # We assume the preview is the line before the unread count
                                preview_text = lines[-2]
                        except Exception as parse_e:
                            logger.warning(f"Failed to parse preview text for {title}: {parse_e}")

                        if title and not any(c.get("contact") == title for c in unread_chats):
                            unread_chats.append({"contact": title, "preview": preview_text})
        except Exception as e:
            logger.error(f"Error finding unread chats: {e}")
            
        return unread_chats

    async def start_message_listener(self, callback) -> None:
        page = await self._get_page()
        
        async def binding_callback(source, triggered_chats=None):
            try:
                chats = triggered_chats if isinstance(triggered_chats, list) else []
                if asyncio.iscoroutinefunction(callback):
                    await callback(chats)
                else:
                    callback(chats)
            except Exception as e:
                logger.error(f"Listener callback error: {e}")
                
        try:
            await page.expose_binding("onWhatsAppMessage", binding_callback)
        except Exception:
            pass # Already bound
            
        js_code = """
        () => {
            if (window._waObserverInterval) {
                clearInterval(window._waObserverInterval);
            }
            let lastUnreadChats = {};
            let lastActiveChatTitle = null;
            let lastActiveChatMessageId = null;
            
            window._waObserverInterval = setInterval(() => {
                const triggeredChats = [];
                
                // 1. Check Visible Chat Bubbles for increments (Ignore Group Chats)
                const currentChats = {};
                const chatItems = document.querySelectorAll('[data-testid="cell-frame-container"], #pane-side div[role="listitem"]');
                chatItems.forEach(chat => {
                    const isGroup = chat.querySelector('[data-icon="default-group"], [data-icon="avatar-group"], [data-testid="avatar-group"], [data-icon="community-outline"]');
                    if (isGroup) return;
                    
                    const titleNode = chat.querySelector('span[title]');
                    const unreadNode = chat.querySelector('[data-testid="icon-unread-count"], span[aria-label*="unread message"]');
                    
                    if (titleNode && unreadNode) {
                        const title = titleNode.getAttribute('title');
                        const text = unreadNode.innerText || unreadNode.getAttribute('aria-label') || "";
                        const match = text.match(/\\d+/);
                        const count = match ? parseInt(match[0]) : 1;
                        
                        currentChats[title] = count;
                        
                        if (lastUnreadChats[title] !== undefined && currentChats[title] > lastUnreadChats[title]) {
                            let previewText = "";
                            try {
                                const lines = chat.innerText.split('\\n').map(l => l.trim()).filter(l => l);
                                if (lines.length >= 3) {
                                    previewText = lines[lines.length - 2];
                                }
                            } catch(e) {}
                            
                            // Check if already in array
                            if (!triggeredChats.some(c => c.contact === title)) {
                                triggeredChats.push({contact: title, preview: previewText});
                            }
                        }
                    } else if (titleNode) {
                        const title = titleNode.getAttribute('title');
                        currentChats[title] = 0;
                    }
                });
                
                for (const [title, count] of Object.entries(currentChats)) {
                    lastUnreadChats[title] = count;
                }
                
                // 2. Check Active Chat (even if it doesn't show an unread badge because it is already open)
                const headerTitleNode = document.querySelector('[data-testid="conversation-info-header"] span[title], header span[title]');
                if (headerTitleNode) {
                    const currentActiveChatTitle = headerTitleNode.getAttribute('title');
                    
                    // Check if it is a group chat
                    const isGroupChat = document.querySelector('header [data-icon="default-group"], header [data-icon="avatar-group"], header [data-testid="avatar-group"], header [data-icon="community-outline"]');
                    
                    if (!isGroupChat) {
                        const allRows = document.querySelectorAll('div[role="row"]');
                        const msgRows = Array.from(allRows).filter(row => row.querySelector('[data-testid="msg-container"]'));
                        
                        if (msgRows.length > 0) {
                            const lastRow = msgRows[msgRows.length - 1];
                            const msgContainer = lastRow.querySelector('[data-id]');
                            const data_id = msgContainer ? msgContainer.getAttribute('data-id') : '';
                            const class_name = msgContainer ? msgContainer.getAttribute('class') : (lastRow.getAttribute('class') || '');
                            
                            const isOutgoing = class_name.includes('message-out') || data_id.includes('true_');
                            const messageId = data_id || lastRow.innerText;
                            
                            if (currentActiveChatTitle === lastActiveChatTitle) {
                                if (lastActiveChatMessageId && messageId !== lastActiveChatMessageId) {
                                    if (!isOutgoing) {
                                        if (!triggeredChats.some(c => c.contact === currentActiveChatTitle)) {
                                            let previewText = "";
                                            try {
                                                const txtEl = lastRow.querySelector('[data-testid="msg-text"] span, span.selectable-text, .copyable-text span');
                                                previewText = txtEl ? txtEl.innerText : lastRow.innerText;
                                            } catch(e) {}
                                            triggeredChats.push({contact: currentActiveChatTitle, preview: previewText});
                                        }
                                    }
                                }
                            }
                            lastActiveChatMessageId = messageId;
                        } else {
                            lastActiveChatMessageId = null;
                        }
                        lastActiveChatTitle = currentActiveChatTitle;
                    } else {
                        lastActiveChatTitle = null;
                        lastActiveChatMessageId = null;
                    }
                } else {
                    lastActiveChatTitle = null;
                    lastActiveChatMessageId = null;
                }
                
                if (triggeredChats.length > 0) {
                    window.onWhatsAppMessage(triggeredChats);
                }
            }, 1500);
        }
        """
        await page.evaluate(js_code)
        logger.info("WhatsApp message listener started.")
