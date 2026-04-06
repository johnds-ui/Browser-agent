"""Helpers for short-circuiting click tasks into direct navigations."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from browser_agent.models.browser_state import BrowserState

_CLICK_TARGET_RE = re.compile(
    r"(?:click|tap|press|open)\s+(?:on\s+)?(.+?)(?=(?:,|\band then\b|\bthen\b|\bafter that\b|$))",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[a-z0-9]+")
_IGNORED_SCHEMES = ("javascript:", "mailto:", "tel:", "#")


def find_direct_link_for_task(
    task: str,
    state: BrowserState,
    attempted_urls: set[str] | None = None,
) -> str | None:
    """Return a matching direct link from the current DOM for the task, if any."""
    attempted_urls = attempted_urls or set()
    targets = _extract_click_targets(task)
    if not targets:
        return None

    current_url = (state.url or "").strip()
    best_url: str | None = None
    best_score = 0.0

    for element in state.elements:
        raw_url = (element.link_url or element.attributes.get("href") or "").strip()
        if not raw_url or raw_url.startswith(_IGNORED_SCHEMES):
            continue

        resolved_url = urljoin(current_url or "about:blank", raw_url)
        if not resolved_url or resolved_url == current_url or resolved_url in attempted_urls:
            continue

        label = " ".join(
            part.strip()
            for part in [
                element.text or "",
                element.aria_label or "",
                element.label_text or "",
                element.parent_text or "",
                element.attributes.get("title", ""),
            ]
            if part and part.strip()
        )
        if not label:
            continue

        score = max((_match_score(target, label) for target in targets), default=0.0)
        if element.tag == "a":
            score += 0.05

        if score > best_score:
            best_score = score
            best_url = resolved_url

    return best_url if best_score >= 0.6 else None


def _extract_click_targets(task: str) -> list[str]:
    targets = [match.group(1).strip(" .,:;\"'") for match in _CLICK_TARGET_RE.finditer(task)]
    if not targets:
        return []
    return [target for target in targets if len(_normalize_text(target)) >= 3]


def _match_score(target: str, label: str) -> float:
    normalized_target = _normalize_text(target)
    normalized_label = _normalize_text(label)
    if not normalized_target or not normalized_label:
        return 0.0

    if normalized_target in normalized_label or normalized_label in normalized_target:
        return 1.0

    target_words = set(_WORD_RE.findall(normalized_target))
    label_words = set(_WORD_RE.findall(normalized_label))
    if not target_words or not label_words:
        return 0.0

    overlap = target_words & label_words
    return len(overlap) / max(len(target_words), 1)


def _normalize_text(value: str) -> str:
    return " ".join(_WORD_RE.findall(value.lower()))