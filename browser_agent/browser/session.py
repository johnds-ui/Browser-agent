"""Playwright + CDP hybrid browser session.

Playwright manages: browser launch, context, page, navigation (goto with
networkidle), screenshots, and keyboard input.

Raw CDP (via Playwright's CDPSession) handles: Input.dispatchMouseEvent,
Runtime.evaluate, DOM.*, Network.enable.
"""

from __future__ import annotations

import logging
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    async_playwright,
)
from playwright.async_api import CDPSession as PlaywrightCDPSession

logger = logging.getLogger(__name__)

# CDP domains to enable on connect
_ENABLE_DOMAINS = ["DOM", "Runtime", "Network", "Page"]


class BrowserSession:
    """Playwright-managed browser with a raw CDP overlay.

    Attributes
    ----------
    page : Page
        The active Playwright Page.  Exposed so executors and extractors
        can call page.goto(), page.keyboard, page.evaluate(), etc.
    """

    def __init__(self, headless: bool = True) -> None:
        self._headless = headless
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._cdp_session: PlaywrightCDPSession | None = None
        self.page: Page | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Launch Chromium via Playwright and attach a CDP session."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._headless,
            args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-extensions",
                "--disable-popup-blocking",
                "--disable-translate",
                "--disable-background-networking",
                "--disable-sync",
                "--password-store=basic",
                "--use-mock-keychain",
            ],
        )
        self._context = await self._browser.new_context()
        self.page = await self._context.new_page()

        # Attach raw CDP session to the page
        self._cdp_session = await self._context.new_cdp_session(self.page)

        # Enable required CDP domains
        for domain in _ENABLE_DOMAINS:
            await self.send_cdp(f"{domain}.enable", {})

        logger.info("BrowserSession ready (Playwright + raw CDP).")

    async def stop(self) -> None:
        """Close the browser and stop the Playwright driver."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("BrowserSession stopped.")

    # ------------------------------------------------------------------
    # Raw CDP access
    # ------------------------------------------------------------------

    async def send_cdp(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a raw CDP command via Playwright's CDP session.

        Returns the response ``result`` dict from Chrome DevTools Protocol.
        """
        if self._cdp_session is None:
            raise RuntimeError("BrowserSession is not started — call start() first.")
        logger.debug("CDP ► %s", method)
        result = await self._cdp_session.send(method, params)
        return result or {}

    # Backward-compatibility alias used by state/builder.py
    async def send_command(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Alias for send_cdp; preserves API compatibility with state/builder."""
        return await self.send_cdp(method, params)


# Alias so existing imports (`from browser_agent.browser.session import CDPSession`)
# continue to work without changes in files outside the update scope.
CDPSession = BrowserSession
