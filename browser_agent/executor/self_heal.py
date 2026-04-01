"""Self-healing engine — re-locates elements after DOM mutations.

When a CDP action fails (element not found, stale bbox, etc.) the engine
attempts 6 strategies in order of confidence:

  1. EXACT MATCH     — same css_selector exists in re-queried DOM
  2. TEXT MATCH      — innerText fuzzy-matches (≥ 80 % difflib ratio)
  3. ARIA MATCH      — aria-label matches exactly
  4. ATTRIBUTE MATCH — id / name / placeholder / data-testid match
  5. STRUCTURAL MATCH— same tag + same parent_text context
  6. LLM FALLBACK    — send DOM + fingerprint to Claude, ask it to pick

Only unrecoverable failures (all six strategies exhausted) increment the
caller's retry_count — healing attempts are free.
"""

from __future__ import annotations

import asyncio
import difflib
import json
import logging
import os
import re

import anthropic

from browser_agent.models.element import ElementFingerprint

logger = logging.getLogger(__name__)

# Minimum fuzzy-match ratio to accept a TEXT MATCH hit
_TEXT_SIMILARITY_THRESHOLD = 0.80


class SelfHealEngine:
    """Cascading element re-location engine."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = anthropic.Anthropic(api_key=key) if key else None
        self._model = model or "claude-sonnet-4-5"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def heal(
        self,
        failed: ElementFingerprint,
        current_elements: list[ElementFingerprint],
    ) -> ElementFingerprint | None:
        """Try all healing strategies in order and return the first match.

        Returns ``None`` when all strategies fail.
        """
        strategies = [
            ("EXACT",     self._exact_match),
            ("TEXT",      self._text_match),
            ("ARIA",      self._aria_match),
            ("ATTRIBUTE", self._attribute_match),
            ("STRUCTURAL",self._structural_match),
            ("LLM",       self._llm_fallback),
        ]

        for name, strategy in strategies:
            try:
                result = await strategy(failed, current_elements)
                if result is not None:
                    logger.info(
                        "Self-heal SUCCESS via %s strategy → new index %d",
                        name,
                        result.index,
                    )
                    return result
                logger.debug("Self-heal %s strategy: no match.", name)
            except Exception as exc:
                logger.warning("Self-heal %s strategy raised: %s", name, exc)

        logger.warning("Self-heal EXHAUSTED for element: %s", failed.css_selector)
        return None

    # ------------------------------------------------------------------
    # Strategy 1 — exact CSS selector match
    # ------------------------------------------------------------------

    async def _exact_match(
        self,
        failed: ElementFingerprint,
        current: list[ElementFingerprint],
    ) -> ElementFingerprint | None:
        for el in current:
            if el.css_selector == failed.css_selector:
                return el
        return None

    # ------------------------------------------------------------------
    # Strategy 2 — fuzzy text match (difflib)
    # ------------------------------------------------------------------

    async def _text_match(
        self,
        failed: ElementFingerprint,
        current: list[ElementFingerprint],
    ) -> ElementFingerprint | None:
        if not failed.text:
            return None

        best: ElementFingerprint | None = None
        best_ratio = 0.0

        for el in current:
            if not el.text:
                continue
            ratio = difflib.SequenceMatcher(None, failed.text, el.text).ratio()
            if ratio >= _TEXT_SIMILARITY_THRESHOLD and ratio > best_ratio:
                best = el
                best_ratio = ratio
                logger.debug(
                    "TEXT match candidate: index=%d ratio=%.2f text=%r",
                    el.index, ratio, el.text,
                )

        return best

    # ------------------------------------------------------------------
    # Strategy 3 — aria-label match
    # ------------------------------------------------------------------

    async def _aria_match(
        self,
        failed: ElementFingerprint,
        current: list[ElementFingerprint],
    ) -> ElementFingerprint | None:
        if not failed.aria_label:
            return None
        for el in current:
            if el.aria_label and el.aria_label.strip() == failed.aria_label.strip():
                return el
        return None

    # ------------------------------------------------------------------
    # Strategy 4 — attribute match (id / name / placeholder / data-testid)
    # ------------------------------------------------------------------

    async def _attribute_match(
        self,
        failed: ElementFingerprint,
        current: list[ElementFingerprint],
    ) -> ElementFingerprint | None:
        priority_attrs = ("id", "name", "placeholder", "data-testid")

        for attr in priority_attrs:
            wanted = failed.attributes.get(attr) or getattr(failed, attr, None)
            if not wanted:
                continue
            for el in current:
                candidate = el.attributes.get(attr) or getattr(el, attr, None)
                if candidate and str(candidate).strip() == str(wanted).strip():
                    logger.debug("ATTRIBUTE match on %s=%r", attr, wanted)
                    return el

        return None

    # ------------------------------------------------------------------
    # Strategy 5 — structural match (tag + parent_text)
    # ------------------------------------------------------------------

    async def _structural_match(
        self,
        failed: ElementFingerprint,
        current: list[ElementFingerprint],
    ) -> ElementFingerprint | None:
        if not failed.parent_text:
            return None

        candidates = [
            el for el in current
            if el.tag == failed.tag and el.parent_text
        ]
        if not candidates:
            return None

        best: ElementFingerprint | None = None
        best_ratio = 0.0

        for el in candidates:
            ratio = difflib.SequenceMatcher(
                None, failed.parent_text, el.parent_text
            ).ratio()
            if ratio >= _TEXT_SIMILARITY_THRESHOLD and ratio > best_ratio:
                best = el
                best_ratio = ratio

        return best

    # ------------------------------------------------------------------
    # Strategy 6 — LLM fallback
    # ------------------------------------------------------------------

    async def _llm_fallback(
        self,
        failed: ElementFingerprint,
        current: list[ElementFingerprint],
    ) -> ElementFingerprint | None:
        if self._client is None:
            logger.warning("LLM fallback skipped — no API key configured.")
            return None

        slim_elements = [el.slim() for el in current]
        prompt = (
            "A browser automation agent tried to interact with this element but it "
            "is no longer found in the DOM:\n\n"
            f"FAILED ELEMENT:\n{json.dumps(failed.model_dump(), indent=2)}\n\n"
            f"CURRENT ELEMENTS (indexed list):\n{json.dumps(slim_elements, indent=2)}\n\n"
            "Which element index (integer) best matches the failed element?\n"
            "Respond with ONLY a JSON object: {\"index\": <int>, \"reason\": \"<why>\"}\n"
            "If no suitable match exists respond with {\"index\": null, \"reason\": \"<why>\"}."
        )

        response = await asyncio.to_thread(
            lambda: self._client.messages.create(
                model=self._model,
                max_tokens=128,
                messages=[{"role": "user", "content": prompt}],
            )
        )

        raw = response.content[0].text.strip()
        logger.debug("LLM fallback raw response: %s", raw)

        # Parse index from response
        try:
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
            cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()
            data = json.loads(cleaned[cleaned.find("{"):cleaned.rfind("}") + 1])
            index = data.get("index")
            if index is None:
                return None
            for el in current:
                if el.index == int(index):
                    return el
        except Exception as exc:
            logger.warning("LLM fallback parse error: %s", exc)

        return None
