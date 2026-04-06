"""DOM extractor — injects JS into the browser to produce ElementFingerprints.

Uses Playwright's ``page.evaluate()`` for all JS injection.  A single call
per extraction cycle keeps latency and DevTools traffic minimal.
"""

from __future__ import annotations

import logging
from typing import Any

from browser_agent.browser.session import BrowserSession
from browser_agent.models.element import ElementFingerprint
from browser_agent.utils.dom_js import DOM_EXTRACT_JS, DOM_SUMMARY_JS, DOM_HASH_JS

logger = logging.getLogger(__name__)


class DOMExtractor:
    """Extracts interactive elements and visible text from the live DOM."""

    def __init__(self, session: BrowserSession) -> None:
        self._session = session
        self._page = session.page
        self._last_hash: str = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def extract(self) -> list[ElementFingerprint]:
        """Return a flat, indexed list of interactive ElementFingerprints."""
        raw = await self._evaluate(DOM_EXTRACT_JS)

        if not isinstance(raw, list):
            logger.warning("DOM extraction returned non-list: %s", type(raw))
            return []

        elements: list[ElementFingerprint] = []
        for item in raw:
            try:
                fp = self._parse_fingerprint(item)
                elements.append(fp)
            except Exception as exc:
                logger.debug("Skipping malformed element: %s — %s", item, exc)

        logger.info("Extracted %d interactive elements.", len(elements))
        return elements

    async def get_summary(self) -> str:
        """Return visible-text summary of the page (max 2 000 chars)."""
        result = await self._evaluate(DOM_SUMMARY_JS)
        return str(result)[:2000] if result else ""

    async def get_dom_hash(self) -> str:
        """Return a lightweight hash of the current DOM for change detection."""
        result = await self._evaluate(DOM_HASH_JS)
        return str(result) if result else ""

    async def dom_changed(self) -> bool:
        """Return True if the DOM has changed since the last call."""
        new_hash = await self.get_dom_hash()
        changed = new_hash != self._last_hash
        self._last_hash = new_hash
        return changed

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _evaluate(self, expression: str) -> Any:
        """Run a JS expression via Playwright and return the value directly.

        Playwright's page.evaluate() unwraps the CDP result automatically and
        raises a PlaywrightError on JavaScript exceptions.
        """
        return await self._page.evaluate(expression)

    @staticmethod
    def _parse_fingerprint(raw: dict) -> ElementFingerprint:
        """Convert a raw JS object dict to an ElementFingerprint."""
        # Normalise bbox — JS may return a DOMRect-like object
        bbox_raw = raw.get("bbox") or {}
        if isinstance(bbox_raw, dict):
            bbox = {
                "x": float(bbox_raw.get("x", 0)),
                "y": float(bbox_raw.get("y", 0)),
                "width": float(bbox_raw.get("width", 0)),
                "height": float(bbox_raw.get("height", 0)),
            }
        else:
            bbox = {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0}

        # Sanitise attributes — must be dict[str, str]
        attrs_raw = raw.get("attributes") or {}
        attributes: dict[str, str] = {
            str(k): str(v) for k, v in attrs_raw.items() if v is not None
        }

        return ElementFingerprint(
            index=int(raw.get("index", 0)),
            tag=str(raw.get("tag", "unknown")).lower(),
            type=raw.get("type"),
            text=raw.get("text") or None,
            placeholder=raw.get("placeholder") or None,
            aria_label=raw.get("aria_label") or None,
            label_text=raw.get("label_text") or None,
            value=raw.get("value") or None,
            link_url=raw.get("link_url") or None,
            css_selector=str(raw.get("css_selector", "unknown")),
            xpath=str(raw.get("xpath", "/unknown")),
            bbox=bbox,
            attributes=attributes,
            parent_text=raw.get("parent_text") or None,
        )
