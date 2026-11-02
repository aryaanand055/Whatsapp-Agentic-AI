"""
WhatsApp Browser — manages a Playwright persistent browser context
for connecting to WhatsApp Web.
"""

import logging
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext
from .models import ConnectionStatus
from .selectors import WhatsAppSelectors, is_authenticated

logger = logging.getLogger(__name__)


class WhatsAppBrowser:
    """Manages a persistent Chromium browser session for WhatsApp Web."""

    def __init__(self, profile_dir: str, headless: bool = False):
        self.profile_dir = str(Path(profile_dir).resolve())
        self.headless = headless
        self._playwright = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def start(self) -> None:
        """Launch the browser and navigate to WhatsApp Web."""
        self._playwright = await async_playwright().start()
        logger.info("Starting WhatsApp Browser (profile: %s)...", self.profile_dir)

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=self.profile_dir,
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
            ],
            viewport={'width': 1280, 'height': 800},
            locale='en-US',
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/131.0.0.0 Safari/537.36'
            ),
        )

        # Mask automation flags
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        pages = self._context.pages
        self._page = pages[0] if pages else await self._context.new_page()
        await self._page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
        logger.info("Navigated to web.whatsapp.com")

    async def stop(self) -> None:
        """Close the browser and save the session."""
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser stopped.")

    async def get_page(self) -> Page:
        """Return the active WhatsApp Web page."""
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first.")
        return self._page

    async def wait_for_login(self, timeout: int = 120) -> bool:
        """Wait for the user to authenticate (scan QR if needed).

        Returns True once the side panel is visible (= logged in).
        Polls every 2 seconds up to *timeout* seconds.
        """
        page = await self.get_page()

        # First, give WhatsApp Web a moment to render
        await asyncio.sleep(3)

        qr_prompted = False

        for elapsed in range(0, timeout, 2):
            # Check if already logged in
            if await is_authenticated(page):
                logger.info("WhatsApp authenticated successfully.")
                return True

            # Check for QR code
            if not qr_prompted:
                qr = page.locator(WhatsAppSelectors.QR_CANVAS)
                try:
                    if await qr.count() > 0 and await qr.first.is_visible():
                        print("\n📱  QR code visible — please scan it with your phone.")
                        print("    (WhatsApp → Settings → Linked Devices → Link a Device)\n")
                        qr_prompted = True
                except Exception:
                    pass

            # Also handle the case where there's no QR and no side panel yet
            # (WhatsApp may be syncing / loading messages)
            if elapsed > 0 and elapsed % 10 == 0:
                logger.debug("Still waiting for login... (%ds elapsed)", elapsed)

            await asyncio.sleep(2)

        logger.warning("Login timed out after %d seconds.", timeout)
        return False

    async def check_connection(self) -> ConnectionStatus:
        """Return the current connection/authentication status."""
        if not self._page:
            return ConnectionStatus(
                connected=False, authenticated=False,
                message="Browser not started",
            )

        is_auth = await is_authenticated(self._page)
        if is_auth:
            return ConnectionStatus(
                connected=True, authenticated=True,
                message="Connected and authenticated",
            )
        return ConnectionStatus(
            connected=True, authenticated=False,
            message="Browser open but not authenticated — scan QR code",
        )

    async def is_logged_in(self) -> bool:
        """Quick boolean check for authentication."""
        if not self._page:
            return False
        return await is_authenticated(self._page)
