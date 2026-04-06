"""AgentOrchestrator — the main control loop.

Ties together all six modules:
  browser/session  →  dom/extractor  →  state/builder
  →  llm/planner  →  executor/cdp_executor
  →  executor/self_heal (on failure)

Data flow per iteration:
  1. extract DOM  →  ElementFingerprint list
  2. build state  →  BrowserState
  3. predict      →  CDPAction
  4. execute      →  result / optional failed fingerprint
  5. if failed: heal → retry action (no retry_count increment)
  6. append state to history; loop
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from browser_agent.browser.session import BrowserSession, CDPSession
from browser_agent.dom.extractor import DOMExtractor
from browser_agent.executor.cdp_executor import CDPExecutor
from browser_agent.executor.self_heal import SelfHealEngine
from browser_agent.llm.planner import LLMPlanner
from browser_agent.llm.registry import get_provider
from browser_agent.models.browser_state import BrowserState
from browser_agent.models.cdp_action import CDPAction
from browser_agent.models.element import ElementFingerprint
from browser_agent.state.builder import StateBuilder
from browser_agent.utils.direct_link import find_direct_link_for_task
from browser_agent.utils.url_detector import extract_url

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Return value of ``AgentOrchestrator.run()``."""

    status: str                          # "done" | "failed" | "max_retries"
    final_state: BrowserState | None
    history: list[BrowserState]
    reason: str = ""


class AgentOrchestrator:
    """Drives the full task-completion loop.

    Parameters
    ----------
    task:
        Free-text user instruction, e.g.
        "Go to https://example.com and click the Sign In button"
    session:
        An already-started ``BrowserSession`` (Playwright + CDP hybrid).
    model_key:
        Registry key selecting the LLM provider.  Defaults to Claude.
        Valid values: "claude-sonnet-4-5", "azure-gpt-4o", "gemini-2.0-flash".
    api_key:
        Forwarded to ``SelfHealEngine`` only (LLM providers read env vars).
    capture_screenshots:
        Set ``True`` to capture a PNG after every step.
    max_retries:
        Hard retry limit for *unrecoverable* failures (self-heal attempts do
        NOT count against this limit).
    """

    MAX_RETRIES: int = 5

    def __init__(
        self,
        task: str,
        session: BrowserSession,
        model_key: str = "claude-sonnet-4-5",
        api_key: str | None = None,
        capture_screenshots: bool = False,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self.task = task
        self._session = session
        self._max_retries = max_retries

        # Module instantiation
        self._extractor = DOMExtractor(session)
        self._builder = StateBuilder(session, self._extractor, capture_screenshots)
        self._planner = LLMPlanner(provider=get_provider(model_key))
        self._executor = CDPExecutor(session)
        self._healer = SelfHealEngine(api_key=api_key)

        # State
        self.history: list[BrowserState] = []
        self.retry_count: int = 0
        self._auto_redirected_urls: set[str] = set()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self) -> AgentResult:
        """Execute the agent loop until done, failure, or retry limit."""
        logger.info("Agent starting. Task: %s", self.task)

        # --- Step 0: auto-navigate if task contains a URL -----------------
        url = extract_url(self.task)
        if url:
            logger.info("Auto-navigating to URL detected in task: %s", url)
            first_action = CDPAction(
                action="navigate",
                value=url,
                element_index=None,
                scroll_direction=None,
                scroll_amount=None,
                reason="URL detected in task; navigating as first action",
            )
            try:
                await self._executor.execute(first_action, _empty_state(self.task))
            except Exception as exc:
                logger.error("Initial navigation failed: %s", exc)

        # --- Main loop ----------------------------------------------------
        last_action: CDPAction | None = None
        last_result: str = "success"
        scope: str = ""
        next_plan: str = ""
        _cached_elements: list[ElementFingerprint] = []

        while self.retry_count < self._max_retries:
            # 1. Extract DOM — skip if DOM unchanged (cheaper hash check first)
            if not _cached_elements or await self._extractor.dom_changed():
                elements = await self._extractor.extract()
                _cached_elements = elements
            else:
                elements = _cached_elements

            # 2. Build state
            state = await self._builder.build(
                task=self.task,
                elements=elements,
                last_action=last_action,
                last_action_result=last_result,
                retry_count=self.retry_count,
                scope=scope,
                next_plan=next_plan,
            )
            self.history.append(state)

            redirect_url = find_direct_link_for_task(
                task=self.task,
                state=state,
                attempted_urls=self._auto_redirected_urls,
            )
            if redirect_url:
                redirect_action = CDPAction(
                    action="navigate",
                    value=redirect_url,
                    element_index=None,
                    scroll_direction=None,
                    scroll_amount=None,
                    reason="Direct link matched the requested click target; navigating before planner inference",
                )
                logger.info("Auto-redirecting directly to matched link: %s", redirect_url)
                result_str, _ = await self._executor.execute(redirect_action, state)
                self._auto_redirected_urls.add(redirect_url)
                last_action = redirect_action
                last_result = result_str
                _cached_elements = []

                if result_str != "success":
                    self.retry_count += 1
                continue

            # 3. LLM prediction
            try:
                action = await self._planner.predict(self.history)
            except Exception as exc:
                logger.error("LLM planner error: %s", exc)
                self.retry_count += 1
                last_result = f"failed: LLM error — {exc}"
                continue

            logger.info(
                "LLM chose action=%s element=%s value=%r reason=%s",
                action.action, action.element_index, action.value, action.reason,
            )

            # Update scope/next_plan from LLM reasoning
            scope = action.reason
            next_plan = action.reason

            # 4. Check for completion
            if action.action == "done":
                logger.info("Task complete. Reason: %s", action.reason)
                return AgentResult(
                    status="done",
                    final_state=state,
                    history=self.history,
                    reason=action.reason,
                )

            # 5. Execute action
            result_str, failed_fp = await self._executor.execute(action, state)
            last_action = action

            # Invalidate DOM cache for actions that mutate the page
            if action.action in {"navigate", "click", "type", "select", "key_press"}:
                _cached_elements = []

            if result_str == "success":
                last_result = "success"
            else:
                logger.warning("Action failed: %s", result_str)

                # 6. Self-heal
                healed = None
                if failed_fp is not None:
                    logger.info("Attempting self-heal for element index %s", action.element_index)
                    healed = await self._healer.heal(failed_fp, elements)

                if healed is not None:
                    # Retry with the healed element (no retry_count increment)
                    healed_action = action.model_copy(
                        update={"element_index": healed.index}
                    )
                    logger.info("Self-heal succeeded → retrying with element index %d", healed.index)
                    heal_result, _ = await self._executor.execute(healed_action, state)
                    last_action = healed_action
                    last_result = heal_result

                    if heal_result != "success":
                        logger.warning("Healed action also failed: %s", heal_result)
                        self.retry_count += 1
                        last_result = f"failed: healed action still failed — {heal_result}"
                else:
                    # All heal strategies exhausted
                    self.retry_count += 1
                    last_result = result_str

                if self.retry_count >= self._max_retries:
                    break

        # Retry limit hit
        logger.error(
            "Agent reached max retries (%d). Last result: %s",
            self._max_retries, last_result,
        )
        return AgentResult(
            status="max_retries",
            final_state=self.history[-1] if self.history else None,
            history=self.history,
            reason=last_result,
        )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _empty_state(task: str) -> BrowserState:
    """Return a minimal BrowserState used during the pre-loop navigate step."""
    return BrowserState(
        step=0,
        url="about:blank",
        title="",
        elements=[],
        task=task,
    )
