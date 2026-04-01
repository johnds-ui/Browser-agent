"""BrowserState builder — assembles the full context snapshot each agent step."""

from __future__ import annotations

import base64
import logging

from browser_agent.browser.session import CDPSession
from browser_agent.dom.extractor import DOMExtractor
from browser_agent.models.browser_state import BrowserState
from browser_agent.models.cdp_action import CDPAction
from browser_agent.models.element import ElementFingerprint

logger = logging.getLogger(__name__)


class StateBuilder:
    """Constructs a ``BrowserState`` from the live browser after each action."""

    def __init__(
        self,
        session: CDPSession,
        extractor: DOMExtractor,
        capture_screenshots: bool = False,
    ) -> None:
        self._session = session
        self._extractor = extractor
        self._capture_screenshots = capture_screenshots
        self._step: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def build(
        self,
        task: str,
        elements: list[ElementFingerprint],
        last_action: CDPAction | None,
        last_action_result: str,
        retry_count: int,
        scope: str = "",
        next_plan: str = "",
    ) -> BrowserState:
        """Build and return a ``BrowserState`` for the current browser moment."""
        self._step += 1

        url, title = await self._get_url_and_title()
        dom_summary = await self._extractor.get_summary()
        screenshot_b64 = await self._maybe_screenshot()

        state = BrowserState(
            step=self._step,
            url=url,
            title=title,
            elements=elements,
            dom_summary=dom_summary,
            screenshot_b64=screenshot_b64,
            last_action=last_action,
            last_action_result=last_action_result,
            scope=scope,
            next_plan=next_plan,
            task=task,
            retry_count=retry_count,
        )

        logger.info(
            "State[%d] url=%s elements=%d result=%s",
            self._step,
            url,
            len(elements),
            last_action_result,
        )
        return state

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_url_and_title(self) -> tuple[str, str]:
        """Retrieve the current page URL and title via Runtime.evaluate."""
        result = await self._session.send_command(
            "Runtime.evaluate",
            {
                "expression": "({url: location.href, title: document.title})",
                "returnByValue": True,
            },
        )
        value = result.get("result", {}).get("value") or {}
        url = str(value.get("url", "about:blank"))
        title = str(value.get("title", ""))
        return url, title

    async def _maybe_screenshot(self) -> str | None:
        """Capture a base-64 PNG screenshot if screenshots are enabled."""
        if not self._capture_screenshots:
            return None
        try:
            result = await self._session.send_command(
                "Page.captureScreenshot",
                {"format": "png", "quality": 80},
            )
            return result.get("data")
        except Exception as exc:
            logger.warning("Screenshot capture failed: %s", exc)
            return None
