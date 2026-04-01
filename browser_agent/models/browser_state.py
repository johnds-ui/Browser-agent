"""BrowserState model — full snapshot of the browser at one agent step."""

from __future__ import annotations

from pydantic import BaseModel, Field

from browser_agent.models.cdp_action import CDPAction
from browser_agent.models.element import ElementFingerprint


class BrowserState(BaseModel):
    """Complete context captured after each action.

    The full list of ``BrowserState`` objects (history) is passed to the LLM
    each turn.  To keep token counts manageable:

    * ``screenshot_b64`` is always excluded from history serialisation.
    * ``elements`` is excluded from *historical* steps; only the current step's
      elements list is included.
    """

    step: int = Field(..., description="1-based step counter")
    url: str = Field(..., description="Current page URL")
    title: str = Field(..., description="Current page <title>")

    elements: list[ElementFingerprint] = Field(
        default_factory=list,
        description="All interactive elements found in the current DOM snapshot",
    )

    dom_summary: str = Field(
        "",
        description="Visible text nodes extracted from the DOM, max 2 000 chars",
    )

    screenshot_b64: str | None = Field(
        None,
        description="Base-64 PNG screenshot (optional, excluded from LLM history)",
    )

    last_action: CDPAction | None = Field(
        None,
        description="The CDPAction that was executed to reach this state",
    )

    last_action_result: str = Field(
        "success",
        description="'success' or 'failed: <reason>'",
    )

    scope: str = Field(
        "",
        description="LLM-written one-line description of the current page context",
    )

    next_plan: str = Field(
        "",
        description="LLM-written intent for the immediately next step",
    )

    task: str = Field(
        ...,
        description="Original user task string — repeated for LLM grounding",
    )

    retry_count: int = Field(0, description="Number of unrecoverable failures so far")

    def for_history(self) -> dict:
        """Slim representation used for older steps in the history window.

        Drops ``screenshot_b64`` and full ``elements`` list; replaces elements
        with a lean list so the LLM still knows *what* was on the page.
        """
        d = self.model_dump(exclude={"screenshot_b64", "elements"})
        d["elements_slim"] = [el.slim() for el in self.elements]
        return d

    def for_current(self) -> dict:
        """Full representation for the *current* (most recent) step."""
        return self.model_dump(exclude={"screenshot_b64"})
