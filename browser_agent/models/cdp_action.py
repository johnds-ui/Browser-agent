"""CDPAction model — the structured output the LLM must return each turn."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CDPAction(BaseModel):
    """A single browser action predicted by the LLM planner.

    The executor maps each ``action`` literal to one or more raw CDP commands.
    """

    action: Literal[
        "navigate",
        "click",
        "type",
        "scroll",
        "wait",
        "select",
        "key_press",
        "done",
    ] = Field(..., description="Action type to execute")

    element_index: int | None = Field(
        None,
        description="Index in the current state.elements list (required for click/type/select/scroll on element)",
    )

    value: str | None = Field(
        None,
        description="URL for 'navigate'; text for 'type'; option value for 'select'; key name for 'key_press'; summary for 'done'",
    )

    scroll_direction: Literal["up", "down", "left", "right"] | None = Field(
        None,
        description="Direction for scroll action",
    )

    scroll_amount: int | None = Field(
        None,
        description="Pixel delta per scroll step (default 300 if omitted)",
    )

    reason: str = Field(
        ...,
        description="LLM explanation of why this action was chosen — aids debugging and self-healing",
    )
