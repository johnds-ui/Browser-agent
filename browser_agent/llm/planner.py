"""LLM planner — predicts the next CDP action from browser history.

Prompt construction lives here; actual LLM I/O is delegated to an
``LLMProvider`` instance (Claude, Azure GPT-4o, or Gemini Flash).
"""

from __future__ import annotations

import json
import logging

from browser_agent.llm.providers import LLMProvider
from browser_agent.models.browser_state import BrowserState
from browser_agent.models.cdp_action import CDPAction

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a browser automation agent that controls a real web browser via the \
Chrome DevTools Protocol.

Each turn you receive:
1. The original user task (as a reminder)
2. The full current browser state JSON (URL, title, interactive elements \
   indexed [0]..[N], visible DOM text, last action + result)
3. The last few historical states for context

Your job: return the single NEXT action to make progress toward the task.

OUTPUT FORMAT — return ONLY a valid JSON object matching this schema:
{
  "action": one of ["navigate","click","type","scroll","wait","select","key_press","done"],
  "element_index": <integer index from elements[] or null>,
  "value": <string: URL for navigate | text for type | option for select | key name for key_press | summary for done | null>,
  "scroll_direction": <"up"|"down"|"left"|"right"|null>,
  "scroll_amount": <integer pixels or null>,
  "reason": "<brief explanation of why this action>"
}

RULES:
- Return ONLY the JSON object — no markdown fences, no extra prose.
- If the task is fully complete, return {"action":"done","reason":"<summary>", \
  "element_index":null,"value":null,"scroll_direction":null,"scroll_amount":null}.
- Reference elements ONLY by their index numbers from the current state's \
  elements list.  Never invent selectors.
- If the last action failed, try a DIFFERENT approach — do not repeat the \
  same failed action.
- Always include a "reason" explaining your decision.
- For type actions, set element_index to the input field's index and value to \
  the text to enter.
- For navigate actions, set value to the full URL (include https://).
- For key_press, use standard key names: "Enter", "Tab", "Escape", \
  "ArrowDown", "ArrowUp", etc.

FIELD IDENTIFICATION (critical for forms):
- Each element includes: tag, type, label_text, placeholder, aria_label, value, name, id.
- Match form fields to task requirements using label_text FIRST, then placeholder, \
  then aria_label — these uniquely identify what each field expects.
- If an element's "value" field is non-empty, that field is ALREADY FILLED — \
  do NOT type into it again; move on to the next unfilled field.
- Carefully distinguish fields: "First Name" vs "City" vs "Email" are all \
  different input fields — match each piece of data to the correct field label.

AVOIDING DUPLICATES:
- Before issuing a "type" action, check the history to confirm you have not \
  already successfully typed into that element.
- If a field's current "value" in the state is already set to the correct data, \
  skip it entirely.
- Never re-execute an action that already succeeded in a prior step.
"""


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(history: list[BrowserState]) -> str:
    """Construct the user-turn message from the history window."""
    recent = history[-6:]   # keep last 6 steps — enough context, fewer tokens
    current = recent[-1]

    # Current state — include full elements list
    current_json = json.dumps(current.for_current(), indent=2)

    # Historical states — slim elements, no screenshots
    history_parts = [json.dumps(s.for_history(), indent=2) for s in recent[:-1]]
    history_json = "[\n" + ",\n".join(history_parts) + "\n]" if history_parts else "[]"

    return (
        f"Task: {history[0].task}\n\n"
        f"Current state (step {current.step}):\n{current_json}\n\n"
        f"History (last {len(recent) - 1} previous steps):\n{history_json}\n\n"
        "Return next CDPAction JSON:"
    )


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

class LLMPlanner:
    """Predicts the next ``CDPAction`` by querying the configured LLM provider."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def predict(self, history: list[BrowserState]) -> CDPAction:
        """Build the prompt from *history* and delegate to the provider."""
        prompt = build_prompt(history)
        logger.debug(
            "LLM prompt length: %d chars (provider: %s)",
            len(prompt),
            self._provider.display_name,
        )
        return await self._provider.predict(
            _SYSTEM_PROMPT,
            [{"role": "user", "content": prompt}],
        )
