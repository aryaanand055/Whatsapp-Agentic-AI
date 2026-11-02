"""
Centralized WhatsApp Web CSS selectors and Playwright helper functions.

All UI element lookups go through this module so that selector changes
only need to be updated in one place.
"""

from playwright.async_api import Page, Locator
import asyncio
import logging

logger = logging.getLogger(__name__)


class WhatsAppSelectors:
    """All WhatsApp Web CSS selectors in one place."""

    # QR / Auth — multiple fallbacks
    QR_CANVAS = 'canvas[aria-label="Scan me!"], [data-testid="qrcode"], canvas'

    # Side panel — multiple fallbacks to detect successful login
    SIDE_PANEL = '#pane-side, [data-testid="pane-side"]'

    # Search
    SEARCH_BOX = (
        '[data-testid="chat-list-search"], '
        '[data-testid="chat-list-search-container"] input, '
        'input[placeholder="Search or start a new chat"], '
        'input[aria-label="Search or start a new chat"], '
        'div[contenteditable="true"][data-tab="3"], '
        'div[aria-label="Search input textbox"], '
        'div[aria-label="Search or start new chat"], '
        'div[title="Search input textbox"], '
        '#side div[contenteditable="true"]'
    )
    SEARCH_RESULT_ITEM = '[data-testid="cell-frame-container"], #pane-side div[role="listitem"]'
    SEARCH_RESULT_TITLE = 'span[title]'

    # Chat List
    CHAT_LIST_ITEM = '[data-testid="cell-frame-container"], #pane-side div[role="listitem"]'
    UNREAD_BADGE = '[data-testid="icon-unread-count"], span[aria-label*="unread message"]'
    GROUP_ICON = '[data-icon="default-group"], [data-icon="avatar-group"], [data-testid="avatar-group"], [data-icon="community-outline"], span[aria-label*="Community"], span[aria-label*="Group"]'

    # Chat header
    CHAT_HEADER_TITLE = (
        '[data-testid="conversation-info-header"] span[title], '
        'header span[title]'
    )

    # Messages
    MESSAGE_CONTAINER = 'div[role="row"]'
    MESSAGE_IN = 'div[role="row"]:has([data-icon="tail-in"])'
    MESSAGE_OUT = 'div[role="row"]:has([data-icon="tail-out"])'
    MESSAGE_TEXT = '[data-testid="msg-text"], span.selectable-text.copyable-text, .copyable-text'
    MESSAGE_META = '[data-testid="msg-meta"]'
    MESSAGE_PRE_PLAIN_TEXT = 'data-pre-plain-text'

    # Compose
    MESSAGE_INPUT = (
        '[data-testid="conversation-compose-box-input"], '
        'div[contenteditable="true"][data-tab="10"], '
        'footer div[contenteditable="true"], '
        'footer p[contenteditable="true"], '
        'footer [contenteditable="true"]'
    )
    SEND_BUTTON = '[data-testid="send"], button[aria-label="Send"], span[data-icon="send"], button span[data-icon="send"]'


# ── Helper functions ──────────────────────────────────────


async def _try_selectors(page: Page, combined_selector: str, timeout: int = 5000) -> bool:
    """Try a CSS selector (may contain commas for fallbacks) and return True if any match."""
    try:
        element = await page.wait_for_selector(combined_selector, timeout=timeout)
        return element is not None
    except Exception:
        return False


async def wait_for_whatsapp_ready(page: Page, timeout: int = 60000) -> bool:
    """Wait until WhatsApp Web is fully loaded and authenticated."""
    try:
        await page.wait_for_selector(WhatsAppSelectors.SIDE_PANEL, timeout=timeout)
        return True
    except Exception:
        return False


async def is_authenticated(page: Page) -> bool:
    """Quick check whether the user is logged in."""
    return await _try_selectors(page, WhatsAppSelectors.SIDE_PANEL, timeout=5000)


async def find_search_box(page: Page) -> Locator:
    """Locate the search / new-chat input box."""
    locator = page.locator(WhatsAppSelectors.SEARCH_BOX).first
    await locator.wait_for(state="visible", timeout=10000)
    return locator


async def find_chat_by_name(page: Page, name: str) -> Locator | None:
    """Find a chat entry matching *name* in the current search results."""
    locators = page.locator(WhatsAppSelectors.SEARCH_RESULT_ITEM)
    count = await locators.count()
    for i in range(count):
        locator = locators.nth(i)
        title_locator = locator.locator(WhatsAppSelectors.SEARCH_RESULT_TITLE)
        if await title_locator.count() > 0:
            title = await title_locator.first.get_attribute('title')
            if title and name.lower() in title.lower():
                return locator
    return None


async def find_message_elements(page: Page, limit: int) -> list[Locator]:
    """Return the last *limit* message containers visible in the chat pane."""
    locators = page.locator(WhatsAppSelectors.MESSAGE_CONTAINER)
    count = await locators.count()
    elements = []
    start = max(0, count - limit)
    for i in range(start, count):
        elements.append(locators.nth(i))
    return elements


async def find_message_input(page: Page) -> Locator:
    """Locate the message compose box."""
    locator = page.locator(WhatsAppSelectors.MESSAGE_INPUT).first
    await locator.wait_for(state="visible", timeout=10000)
    return locator


async def find_send_button(page: Page) -> Locator:
    """Locate the send button."""
    locator = page.locator(WhatsAppSelectors.SEND_BUTTON).first
    await locator.wait_for(state="visible", timeout=5000)
    return locator
