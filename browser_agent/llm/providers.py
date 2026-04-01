"""LLM provider implementations — abstract base + Claude, Azure GPT-4o, Gemini.

All providers:
  - Implement ``predict(system, messages) -> CDPAction``
  - Force JSON output via provider-native mechanisms
  - Cap max_tokens at 1024
  - Parse the response into a CDPAction via model_validate_json or robust parsing
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from abc import ABC, abstractmethod

from browser_agent.models.cdp_action import CDPAction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared JSON parser (handles markdown fences + partial JSON)
# ---------------------------------------------------------------------------

def _parse_cdp_action(raw: str) -> CDPAction:
    """Extract and validate a CDPAction from an LLM text response.

    Strips optional markdown code fences, locates the first ``{...}`` block,
    decodes the JSON, and validates it against the CDPAction schema.
    """
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()

    brace_start = cleaned.find("{")
    brace_end = cleaned.rfind("}")
    if brace_start == -1 or brace_end == -1:
        raise ValueError(f"No JSON object found in LLM response: {raw[:300]}")

    json_str = cleaned[brace_start : brace_end + 1]
    try:
        return CDPAction.model_validate_json(json_str)
    except Exception as exc:
        # Try a permissive parse + model construction as fallback
        try:
            data = json.loads(json_str)
            return CDPAction(**data)
        except Exception:
            raise ValueError(
                f"CDPAction validation failed: {exc}\n\nJSON: {json_str[:400]}"
            ) from exc


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class LLMProvider(ABC):
    """Abstract interface for an LLM backend that predicts the next CDPAction."""

    model_id: str
    display_name: str

    @abstractmethod
    async def predict(
        self,
        system: str,
        messages: list[dict],
    ) -> CDPAction:
        """Call the LLM with *system* + *messages* and return a CDPAction."""


# ---------------------------------------------------------------------------
# Provider 1 — Anthropic Claude
# ---------------------------------------------------------------------------

class _ClaudeBase(LLMProvider):
    """Shared Anthropic Claude implementation."""

    model_id: str = "claude-sonnet-4-5"
    display_name: str = "Anthropic Claude"

    def __init__(self) -> None:
        import anthropic  # noqa: PLC0415

        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Add it to your .env file or export it before running."
            )
        self._client = anthropic.Anthropic(api_key=key)

    async def predict(self, system: str, messages: list[dict]) -> CDPAction:
        response = await asyncio.to_thread(
            lambda: self._client.messages.create(
                model=self.model_id,
                max_tokens=1024,
                system=system,
                messages=messages,
            )
        )
        raw = response.content[0].text.strip()
        logger.debug("Claude raw response: %s", raw[:300])
        return _parse_cdp_action(raw)


class ClaudeProvider(_ClaudeBase):
    """Anthropic Claude Sonnet 4.5."""

    model_id = "claude-sonnet-4-5"
    display_name = "Anthropic Claude Sonnet 4.5"


class ClaudeOpusProvider(_ClaudeBase):
    """Anthropic Claude Opus 4.5."""

    model_id = "claude-opus-4-5"
    display_name = "Anthropic Claude Opus 4.5"


# ---------------------------------------------------------------------------
# Provider 2 — Azure OpenAI GPT-4o
# ---------------------------------------------------------------------------

class AzureGPTProvider(LLMProvider):
    """Azure-hosted OpenAI GPT-4o via the ``openai`` SDK with JSON mode."""

    model_id = "gpt-4o"
    display_name = "Azure OpenAI GPT-4o"

    def __init__(self) -> None:
        from openai import AsyncAzureOpenAI  # noqa: PLC0415

        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        key = os.environ.get("AZURE_OPENAI_API_KEY")
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

        if not endpoint or not key:
            raise ValueError(
                "AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY must be set. "
                "Add them to your .env file."
            )

        self._client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=key,
            api_version="2024-02-01",
        )
        self._deployment = deployment

    async def predict(self, system: str, messages: list[dict]) -> CDPAction:
        oai_messages = [{"role": "system", "content": system}, *messages]
        response = await self._client.chat.completions.create(
            model=self._deployment,
            max_tokens=1024,
            response_format={"type": "json_object"},  # forces JSON output
            messages=oai_messages,
        )
        raw = (response.choices[0].message.content or "").strip()
        logger.debug("Azure GPT-4o raw response: %s", raw[:300])
        return _parse_cdp_action(raw)


# ---------------------------------------------------------------------------
# Shared Gemini base — uses the new ``google-genai`` SDK (google.genai)
# ---------------------------------------------------------------------------

class _GeminiBase(LLMProvider):
    """Base for all Gemini providers using the new google-genai SDK."""

    model_id: str = "gemini-2.0-flash"
    display_name: str = "Google Gemini"

    def __init__(self) -> None:
        from google import genai  # noqa: PLC0415
        from google.genai import types as genai_types  # noqa: PLC0415

        key = os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise ValueError(
                "GOOGLE_API_KEY environment variable is not set. "
                "Add it to your .env file."
            )
        self._client = genai.Client(api_key=key)
        self._config = genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            max_output_tokens=1024,
        )

    async def predict(self, system: str, messages: list[dict]) -> CDPAction:
        user_content = messages[-1]["content"] if messages else ""
        full_prompt = f"{system}\n\n{user_content}"

        response = await asyncio.to_thread(
            lambda: self._client.models.generate_content(
                model=self.model_id,
                contents=full_prompt,
                config=self._config,
            )
        )
        raw = response.text.strip()
        logger.debug("%s raw response: %s", self.display_name, raw[:300])
        return _parse_cdp_action(raw)


# ---------------------------------------------------------------------------
# Provider 3 — Google Gemini 2.0 Flash
# ---------------------------------------------------------------------------

class GeminiFlashProvider(_GeminiBase):
    """Google Gemini 2.0 Flash."""

    model_id = "gemini-2.0-flash"
    display_name = "Google Gemini 2.0 Flash"


# ---------------------------------------------------------------------------
# Shared Groq base — OpenAI-compatible API
# ---------------------------------------------------------------------------

class _GroqBase(LLMProvider):
    """Base for all Groq providers using the OpenAI-compatible endpoint."""

    model_id: str = "llama-3.3-70b-versatile"
    display_name: str = "Groq"

    def __init__(self) -> None:
        from openai import AsyncOpenAI  # noqa: PLC0415

        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise ValueError(
                "GROQ_API_KEY environment variable is not set. "
                "Add it to your .env file."
            )
        self._client = AsyncOpenAI(
            api_key=key,
            base_url="https://api.groq.com/openai/v1",
        )

    async def predict(self, system: str, messages: list[dict]) -> CDPAction:
        oai_messages = [{"role": "system", "content": system}, *messages]
        response = await self._client.chat.completions.create(
            model=self.model_id,
            max_tokens=1024,
            response_format={"type": "json_object"},
            messages=oai_messages,
        )
        raw = (response.choices[0].message.content or "").strip()
        logger.debug("%s raw response: %s", self.display_name, raw[:300])
        return _parse_cdp_action(raw)


# ---------------------------------------------------------------------------
# Provider 4 — Groq Llama 3.3 70B Versatile
# ---------------------------------------------------------------------------

class GroqLlama33_70BProvider(_GroqBase):
    """Groq — Llama 3.3 70B Versatile (30 RPM, 12K TPM)."""

    model_id = "llama-3.3-70b-versatile"
    display_name = "Groq Llama 3.3 70B"


# ---------------------------------------------------------------------------
# Provider 5 — Groq Llama 4 Scout 17B
# ---------------------------------------------------------------------------

class GroqLlama4ScoutProvider(_GroqBase):
    """Groq — Llama 4 Scout 17B 16E Instruct (30 RPM, 30K TPM)."""

    model_id = "meta-llama/llama-4-scout-17b-16e-instruct"
    display_name = "Groq Llama 4 Scout 17B"


# ---------------------------------------------------------------------------
# Provider 6 — Groq Kimi K2
# ---------------------------------------------------------------------------

class GroqKimiK2Provider(_GroqBase):
    """Groq — Moonshot Kimi K2 Instruct (60 RPM, 10K TPM)."""

    model_id = "moonshotai/kimi-k2-instruct"
    display_name = "Groq Kimi K2"
