"""LLM provider registry — maps model-key strings to provider classes.

Usage
-----
    from browser_agent.llm.registry import get_provider

    provider = get_provider("claude-sonnet-4-5")
    action   = await provider.predict(system_prompt, messages)
"""

from __future__ import annotations

from browser_agent.llm.providers import (
    AzureGPTProvider,
    ClaudeOpusProvider,
    ClaudeProvider,
    GeminiFlashProvider,
    GroqLlama33_70BProvider,
    GroqLlama4ScoutProvider,
    GroqKimiK2Provider,
    LLMProvider,
)

# Map CLI/config key → provider class
REGISTRY: dict[str, type[LLMProvider]] = {
    "claude-sonnet-4-5":                       ClaudeProvider,
    "claude-opus-4-5":                         ClaudeOpusProvider,
    "azure-gpt-4o":                            AzureGPTProvider,
    "gemini-2.0-flash":                        GeminiFlashProvider,
    "llama-3.3-70b-versatile":                 GroqLlama33_70BProvider,
    "meta-llama/llama-4-scout-17b-16e-instruct": GroqLlama4ScoutProvider,
    "moonshotai/kimi-k2-instruct":             GroqKimiK2Provider,
}

# Human-readable names (for display in main.py)
MODEL_CHOICES: list[str] = list(REGISTRY)


def get_provider(key: str) -> LLMProvider:
    """Instantiate and return the provider registered under *key*.

    Raises ``ValueError`` with the list of valid keys if *key* is unknown.
    """
    cls = REGISTRY.get(key)
    if cls is None:
        raise ValueError(
            f"Unknown model key {key!r}. "
            f"Available choices: {MODEL_CHOICES}"
        )
    return cls()
