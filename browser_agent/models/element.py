"""ElementFingerprint model — rich descriptor for a single interactive DOM element."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ElementFingerprint(BaseModel):
    """Uniquely describes an interactive element and provides multiple
    redundant identifiers so the self-heal engine can re-locate it after
    DOM mutations."""

    index: int = Field(..., description="Sequential index in the current elements list")
    tag: str = Field(..., description="Lowercase HTML tag name, e.g. 'button', 'a'")
    type: str | None = Field(None, description="<input type=...> value if applicable")
    text: str | None = Field(None, description="innerText trimmed to 80 chars")
    placeholder: str | None = Field(None, description="placeholder attribute value")
    aria_label: str | None = Field(None, description="aria-label attribute value")
    css_selector: str = Field(..., description="Unique CSS selector computed by JS")
    xpath: str = Field(..., description="Full XPath computed by JS")
    bbox: dict[str, float] = Field(
        default_factory=dict,
        description="Bounding box {x, y, width, height} from getBoundingClientRect()",
    )
    attributes: dict[str, str] = Field(
        default_factory=dict,
        description="All HTML attributes: id, class, name, data-*, etc.",
    )
    parent_text: str | None = Field(
        None,
        description="innerText of the nearest ancestor element that has non-empty text",
    )

    value: str | None = Field(
        None,
        description="Current value of input/textarea/select — shows what is already filled",
    )

    label_text: str | None = Field(
        None,
        description="Text of the associated <label> element for this field",
    )

    # ------------------------------------------------------------------ helpers

    @property
    def center_x(self) -> float:
        """Horizontal center of the element's bounding box."""
        return self.bbox.get("x", 0) + self.bbox.get("width", 0) / 2

    @property
    def center_y(self) -> float:
        """Vertical center of the element's bounding box."""
        return self.bbox.get("y", 0) + self.bbox.get("height", 0) / 2

    @property
    def is_visible(self) -> bool:
        """Return True when the element has a non-zero bounding box."""
        return self.bbox.get("width", 0) > 0 and self.bbox.get("height", 0) > 0

    def slim(self) -> dict[str, Any]:
        """Return a token-efficient subset for LLM history context."""
        return {
            "index": self.index,
            "tag": self.tag,
            "type": self.type,
            "text": self.text,
            "label_text": self.label_text,
            "aria_label": self.aria_label,
            "placeholder": self.placeholder,
            "value": self.value,
            "name": self.attributes.get("name"),
            "id": self.attributes.get("id"),
        }
