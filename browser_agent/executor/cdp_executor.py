"""CDP action executor — maps CDPAction objects to Playwright + raw CDP calls.

Routing per action type:
  navigate  → page.goto()               (Playwright — networkidle wait)
  click     → Input.dispatchMouseEvent  (raw CDP — mouseMoved/Pressed/Released)
  type      → focus via CDP click, then page.keyboard.type()  (Playwright)
  scroll    → Input.dispatchMouseEvent mouseWheel  (raw CDP)
  key_press → page.keyboard.press()     (Playwright)
  select    → Runtime.evaluate          (raw CDP — set .value + dispatch change)
  wait      → page.wait_for_load_state("networkidle")  (Playwright)
  done      → no-op
"""

from __future__ import annotations

import asyncio
import logging

from browser_agent.browser.session import BrowserSession
from browser_agent.models.browser_state import BrowserState
from browser_agent.models.cdp_action import CDPAction
from browser_agent.models.element import ElementFingerprint
from browser_agent.utils.dom_js import SELECT_OPTION_JS

logger = logging.getLogger(__name__)

# Seconds to wait after an interaction when Playwright load-state times out
_DEFAULT_SETTLE_TIMEOUT = 0.8
# Pixel delta used when scroll_amount is not specified
_DEFAULT_SCROLL_PX = 300


def _result(ok: bool, detail: str = "") -> str:
    return "success" if ok else f"failed: {detail}"


class CDPExecutor:
    """Translates high-level CDPAction objects into Playwright + CDP commands."""

    def __init__(self, session: BrowserSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute(
        self, action: CDPAction, state: BrowserState
    ) -> tuple[str, ElementFingerprint | None]:
        """Execute *action* against the current browser state.

        Returns (result_str, failed_fingerprint).
        ``result_str`` is "success" or "failed: <reason>".
        ``failed_fingerprint`` is the element that caused the failure (for
        self-healing), or None when not element-related.
        """
        handler = {
            "navigate": self._navigate,
            "click":    self._click,
            "type":     self._type,
            "scroll":   self._scroll,
            "wait":     self._wait,
            "select":   self._select,
            "key_press":self._key_press,
            "done":     self._done,
        }.get(action.action)

        if handler is None:
            return _result(False, f"unknown action '{action.action}'"), None

        try:
            result, fingerprint = await handler(action, state)
            logger.info("Action '%s' → %s", action.action, result)
            return result, fingerprint
        except Exception as exc:
            logger.error("Action '%s' raised: %s", action.action, exc)
            fp = self._get_fingerprint(action, state)
            return _result(False, str(exc)), fp

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    async def _navigate(
        self, action: CDPAction, state: BrowserState
    ) -> tuple[str, None]:
        url = (action.value or "").strip()
        if not url:
            return _result(False, "navigate action missing value/URL"), None
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        # Use 'load' event — fires after DOM + critical resources, faster than networkidle
        try:
            await self._session.page.goto(url, wait_until="load", timeout=30_000)
        except Exception:
            # If load event times out (some pages never fire it), proceed anyway
            pass
        # Brief settle for SPA JS rendering
        await asyncio.sleep(0.8)
        return "success", None

    async def _click(
        self, action: CDPAction, state: BrowserState
    ) -> tuple[str, ElementFingerprint | None]:
        fp = self._get_fingerprint(action, state)
        if fp is None:
            return _result(False, f"element_index {action.element_index} not found"), None

        await self._scroll_into_view(fp)

        if not fp.is_visible:
            return _result(False, "element has zero-size bounding box"), fp

        x, y = fp.center_x, fp.center_y
        # Raw CDP mouse events: mouseMoved → mousePressed → mouseReleased
        for event_type in ("mouseMoved", "mousePressed", "mouseReleased"):
            await self._session.send_cdp(
                "Input.dispatchMouseEvent",
                {"type": event_type, "x": x, "y": y, "button": "left", "clickCount": 1},
            )

        await self._wait_for_load(_DEFAULT_SETTLE_TIMEOUT)
        return "success", None

    async def _type(
        self, action: CDPAction, state: BrowserState
    ) -> tuple[str, ElementFingerprint | None]:
        fp = self._get_fingerprint(action, state)
        if fp is None:
            return _result(False, f"element_index {action.element_index} not found"), None

        text = action.value or ""

        # Primary path: page.fill() clears existing value then types — handles React/Vue
        try:
            await self._session.page.fill(fp.css_selector, text, timeout=3_000)
            await asyncio.sleep(0.1)
            return "success", None
        except Exception:
            pass

        # Fallback: scroll into view, CDP click to focus, select-all, then type
        await self._scroll_into_view(fp)
        x, y = fp.center_x, fp.center_y
        for event_type in ("mouseMoved", "mousePressed", "mouseReleased"):
            await self._session.send_cdp(
                "Input.dispatchMouseEvent",
                {"type": event_type, "x": x, "y": y, "button": "left", "clickCount": 1},
            )
        # Select all existing text so new text replaces it (prevents appending duplicates)
        await self._session.page.keyboard.press("Control+a")
        await self._session.page.keyboard.type(text, delay=20)
        await asyncio.sleep(0.1)
        return "success", None

    async def _scroll(
        self, action: CDPAction, state: BrowserState
    ) -> tuple[str, ElementFingerprint | None]:
        direction = action.scroll_direction or "down"
        amount = action.scroll_amount or _DEFAULT_SCROLL_PX

        delta_x = delta_y = 0
        if direction == "down":
            delta_y = amount
        elif direction == "up":
            delta_y = -amount
        elif direction == "right":
            delta_x = amount
        elif direction == "left":
            delta_x = -amount

        fp = self._get_fingerprint(action, state) if action.element_index is not None else None
        x = fp.center_x if fp else 640
        y = fp.center_y if fp else 400

        # Raw CDP mouseWheel event
        await self._session.send_cdp(
            "Input.dispatchMouseEvent",
            {"type": "mouseWheel", "x": x, "y": y, "deltaX": delta_x, "deltaY": delta_y},
        )
        await asyncio.sleep(0.2)
        return "success", None

    async def _wait(
        self, action: CDPAction, state: BrowserState
    ) -> tuple[str, None]:
        seconds = min(float(action.value or 1.0), 10.0)
        # Playwright handles network-idle detection
        try:
            await self._session.page.wait_for_load_state(
                "networkidle", timeout=int(seconds * 1000)
            )
        except Exception:
            await asyncio.sleep(seconds)
        return "success", None

    async def _select(
        self, action: CDPAction, state: BrowserState
    ) -> tuple[str, ElementFingerprint | None]:
        fp = self._get_fingerprint(action, state)
        if fp is None:
            return _result(False, f"element_index {action.element_index} not found"), None

        option_value = action.value or ""
        result = await self._session.send_cdp(
            "Runtime.evaluate",
            {
                "expression": (
                    f"({SELECT_OPTION_JS})({json_str(fp.css_selector)}, {json_str(option_value)})"
                ),
                "returnByValue": True,
            },
        )
        # Playwright's CDP send returns the CDP result dict directly
        success_val = result.get("result", {}).get("value", False)
        if not success_val:
            return _result(False, "select: element not found or option not available"), fp

        await asyncio.sleep(0.1)
        return "success", None

    async def _key_press(
        self, action: CDPAction, state: BrowserState
    ) -> tuple[str, None]:
        key = action.value or "Enter"
        # Playwright keyboard for high-level key names ("Enter", "Tab", etc.)
        await self._session.page.keyboard.press(key)
        await self._wait_for_load(_DEFAULT_SETTLE_TIMEOUT)
        return "success", None

    async def _done(
        self, action: CDPAction, state: BrowserState
    ) -> tuple[str, None]:
        logger.info("Task marked done by LLM. Reason: %s", action.reason)
        return "success", None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_fingerprint(
        action: CDPAction, state: BrowserState
    ) -> ElementFingerprint | None:
        if action.element_index is None:
            return None
        for el in state.elements:
            if el.index == action.element_index:
                return el
        return None

    async def _scroll_into_view(self, fp: ElementFingerprint) -> None:
        """Scroll element into the viewport using Playwright page.evaluate()."""
        try:
            await self._session.page.evaluate(
                f"document.querySelector({json_str(fp.css_selector)})"
                f"?.scrollIntoView({{behavior:'instant',block:'center'}})"
            )
            await asyncio.sleep(0.05)
        except Exception as exc:
            logger.debug("scrollIntoView failed for %s: %s", fp.css_selector, exc)

    async def _wait_for_load(self, timeout: float = 5.0) -> None:
        """Wait for Playwright 'load' state; fall back to debounce on timeout."""
        try:
            await self._session.page.wait_for_load_state(
                "load", timeout=int(timeout * 1000)
            )
            logger.debug("Page load state reached.")
        except Exception:
            await asyncio.sleep(min(timeout, _DEFAULT_SETTLE_TIMEOUT))


# ---------------------------------------------------------------------------
# Tiny JSON-string helper
# ---------------------------------------------------------------------------
import json as _json


def json_str(value: str) -> str:
    """Return *value* as a JSON-encoded string literal (with quotes)."""
    return _json.dumps(value)
