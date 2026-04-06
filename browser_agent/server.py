"""FastAPI server — HTTP + WebSocket bridge between the React UI and the agent.

Endpoints
---------
POST  /api/task
    Body : { "task": str, "model_key": str }
    Returns : { "session_id": str }
    Starts the agent in a background asyncio task and opens a WebSocket stream.

WS    /api/task/{session_id}/stream
    Streams newline-delimited JSON (BrowserState snapshots) to the frontend.
    Final frame carries status "done" or "failed".

POST  /api/task/{session_id}/stop
    Cancels the running task for this session.

POST  /api/settings/env
    Body : { "key": str, "value": str }
    Writes / updates a key in the .env file next to this script.

POST  /api/settings/browser
    Body : { "headless": bool, "max_retries": int }
    Persists browser preferences in memory (reused by next task start).

GET   /api/health
    Returns { "status": "ok" }
"""

from __future__ import annotations

# WindowsProactorEventLoopPolicy is set in run_server.py (the process entry
# point) before uvicorn creates any event loop. Setting it here as well as a
# safety net for direct module imports.
import sys
if sys.platform == "win32":
    import asyncio as _asyncio
    _asyncio.set_event_loop_policy(_asyncio.WindowsProactorEventLoopPolicy())

import asyncio
import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# ---------------------------------------------------------------------------
# App + CORS
# ---------------------------------------------------------------------------

app = FastAPI(title="Browser Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Vite dev server on :3000
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory session registry
# ---------------------------------------------------------------------------

# session_id → asyncio.Task running the agent
_running_tasks: dict[str, asyncio.Task] = {}

# session_id → asyncio.Queue that feeds the WebSocket stream
_session_queues: dict[str, asyncio.Queue] = {}

# session_id → set of asyncio.Queue, one per connected screencast WebSocket
_screencast_subs: dict[str, set[asyncio.Queue]] = {}

# session_id → list of JPEG b64 frames for post-session replay (capped at 300)
_session_frames: dict[str, list[str]] = {}
_MAX_REPLAY_FRAMES = 300

# Global browser settings (mutated by /api/settings/browser)
_browser_settings: dict[str, Any] = {
    "headless": True,
    "max_retries": 5,
}

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class StartTaskRequest(BaseModel):
    task: str
    model_key: str = "claude-sonnet-4-5"


class EnvSettingRequest(BaseModel):
    key: str
    value: str


class BrowserSettingRequest(BaseModel):
    headless: bool = True
    max_retries: int = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ENV_FILE = Path(__file__).parent / ".env"


def _write_env_key(key: str, value: str) -> None:
    """Upsert a key=value pair in the .env file safely."""
    # Validate key name (alphanumeric + underscore only)
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
        raise ValueError(f"Invalid environment variable name: {key!r}")
    lines: list[str] = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    updated = False
    new_lines: list[str] = []
    for line in lines:
        if re.match(rf"^{re.escape(key)}\s*=", line):
            new_lines.append(f"{key}={value}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    os.environ[key] = value  # apply immediately for current process


def _serialize_state(state: Any, status: str = "running") -> str:
    """Convert a BrowserState (or any pydantic model) to a JSON string."""
    try:
        data = state.model_dump(exclude={"elements"})
        # Rename screenshot_b64 → screenshot for frontend compatibility
        screenshot = data.pop("screenshot_b64", None)
        if screenshot:
            data["screenshot"] = screenshot
        data["status"] = status
    except Exception:
        data = {"status": status}
    return json.dumps(data, default=str)


# ---------------------------------------------------------------------------
# Background agent runner
# ---------------------------------------------------------------------------

async def _run_agent(session_id: str, task: str, model_key: str) -> None:
    """Run the full agent loop and push BrowserState frames to the queue."""
    from browser_agent.browser.session import BrowserSession
    from browser_agent.agent.orchestrator import AgentOrchestrator

    queue: asyncio.Queue = _session_queues[session_id]
    headless: bool = _browser_settings["headless"]
    max_retries: int = _browser_settings["max_retries"]

    browser_session = BrowserSession(headless=headless)

    class _StreamingOrchestrator(AgentOrchestrator):
        """Subclass that pushes each BrowserState to the queue after build."""

        async def run(self):  # type: ignore[override]
            from browser_agent.utils.url_detector import extract_url
            from browser_agent.utils.direct_link import find_direct_link_for_task
            from browser_agent.models.cdp_action import CDPAction

            url = extract_url(self.task)
            if url:
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

            last_action = None
            last_result = "success"
            scope = ""
            next_plan = ""

            while self.retry_count < self._max_retries:
                elements = await self._extractor.extract()
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

                # Push state to WebSocket queue
                await queue.put(_serialize_state(state, "running"))

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

                    if result_str != "success":
                        self.retry_count += 1
                    continue

                try:
                    action = await self._planner.predict(self.history)
                except Exception as exc:
                    logger.error("LLM planner error: %s", exc)
                    self.retry_count += 1
                    last_result = f"failed: LLM error — {exc}"
                    continue

                scope = action.reason
                next_plan = action.reason

                if action.action == "done":
                    from browser_agent.agent.orchestrator import AgentResult
                    final_state = state
                    final_state_copy = final_state.model_copy(
                        update={"scope": action.reason}
                    )
                    await queue.put(_serialize_state(final_state_copy, "done"))
                    return AgentResult(
                        status="done",
                        final_state=final_state,
                        history=self.history,
                        reason=action.reason,
                    )

                result_str, failed_fp = await self._executor.execute(action, state)
                last_action = action

                if result_str == "success":
                    last_result = "success"
                else:
                    healed = None
                    if failed_fp is not None:
                        healed = await self._healer.heal(failed_fp, elements)

                    if healed is not None:
                        healed_action = action.model_copy(
                            update={"element_index": healed.index}
                        )
                        heal_result, _ = await self._executor.execute(healed_action, state)
                        last_action = healed_action
                        last_result = heal_result
                        if heal_result != "success":
                            self.retry_count += 1
                            last_result = f"failed: healed action still failed — {heal_result}"
                    else:
                        self.retry_count += 1
                        last_result = f"failed: {result_str}"

            from browser_agent.agent.orchestrator import AgentResult
            return AgentResult(
                status="max_retries",
                final_state=self.history[-1] if self.history else None,
                history=self.history,
                reason="Max retries reached",
            )

    async def _screencast_loop() -> None:
        """Capture JPEG frames every 300 ms and broadcast to all screencast subscribers."""
        import base64
        subs = _screencast_subs.setdefault(session_id, set())
        frames = _session_frames.setdefault(session_id, [])
        while True:
            await asyncio.sleep(0.3)
            page = browser_session.page
            if page is None:
                continue
            try:
                png = await page.screenshot(type="jpeg", quality=55, full_page=False)
                b64 = base64.b64encode(png).decode()
                # Store for replay (keep last N frames)
                if len(frames) < _MAX_REPLAY_FRAMES:
                    frames.append(b64)
                frame = json.dumps({"frame": b64})
                dead: set[asyncio.Queue] = set()
                for q in list(subs):
                    try:
                        q.put_nowait(frame)
                    except asyncio.QueueFull:
                        dead.add(q)
                subs -= dead
            except Exception:
                pass  # page may be navigating; skip this frame

    screencast_task: asyncio.Task | None = None
    try:
        await browser_session.start()
        screencast_task = asyncio.create_task(_screencast_loop())
        orchestrator = _StreamingOrchestrator(
            task=task,
            session=browser_session,
            model_key=model_key,
            capture_screenshots=True,
            max_retries=max_retries,
        )
        result = await orchestrator.run()

        if result is not None and result.status not in ("done",):
            # Push a final failed frame if we didn't already push "done"
            dummy = {"status": "failed", "step": len(result.history), "url": "", "task": task}
            await queue.put(json.dumps(dummy))

    except asyncio.CancelledError:
        logger.info("Session %s was cancelled.", session_id)
        await queue.put(json.dumps({"status": "failed", "reason": "cancelled"}))
    except Exception as exc:
        logger.exception("Agent error in session %s: %s", session_id, exc)
        await queue.put(json.dumps({"status": "failed", "reason": str(exc)}))
    finally:
        if screencast_task is not None:
            screencast_task.cancel()
        # Notify all screencast subscribers that the session ended
        for q in _screencast_subs.pop(session_id, set()):
            q.put_nowait(json.dumps({"done": True}))
        await browser_session.stop()
        # Sentinel so the WebSocket loop knows to close
        await queue.put(None)
        _running_tasks.pop(session_id, None)


def _empty_state(task: str):
    """Minimal placeholder BrowserState for the initial navigate step."""
    from browser_agent.models.browser_state import BrowserState
    return BrowserState(step=0, url="", title="", task=task)


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/task")
async def start_task(req: StartTaskRequest):
    if not req.task.strip():
        raise HTTPException(status_code=400, detail="task must not be empty")

    session_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    _session_queues[session_id] = queue

    task_coro = _run_agent(session_id, req.task, req.model_key)
    bg_task = asyncio.create_task(task_coro)
    _running_tasks[session_id] = bg_task

    logger.info("Started session %s — task: %s | model: %s", session_id, req.task[:60], req.model_key)
    return {"session_id": session_id}


@app.post("/api/task/{session_id}/stop")
async def stop_task(session_id: str):
    task = _running_tasks.get(session_id)
    if task and not task.done():
        task.cancel()
        return {"status": "stopping"}
    return {"status": "not_running"}


@app.websocket("/api/task/{session_id}/stream")
async def stream_task(websocket: WebSocket, session_id: str):
    await websocket.accept()

    queue = _session_queues.get(session_id)
    if queue is None:
        await websocket.send_text(json.dumps({"status": "failed", "reason": "unknown session"}))
        await websocket.close()
        return

    try:
        while True:
            try:
                frame = await asyncio.wait_for(queue.get(), timeout=120.0)
            except asyncio.TimeoutError:
                # Keep-alive ping
                await websocket.send_text(json.dumps({"ping": True}))
                continue

            if frame is None:
                # Sentinel — agent finished
                break

            await websocket.send_text(frame)

            # Stop streaming once terminal status is sent
            try:
                data = json.loads(frame)
                if data.get("status") in ("done", "failed"):
                    break
            except Exception:
                pass

    except (WebSocketDisconnect, Exception) as exc:
        logger.info("WebSocket for session %s closed: %s", session_id, exc)
    finally:
        await websocket.close(code=1000)
        _session_queues.pop(session_id, None)


@app.websocket("/api/task/{session_id}/screencast")
async def screencast_task_ws(websocket: WebSocket, session_id: str):
    """Stream live JPEG frames from the agent's browser page."""
    await websocket.accept()

    subs = _screencast_subs.setdefault(session_id, set())
    q: asyncio.Queue = asyncio.Queue(maxsize=5)
    subs.add(q)

    try:
        while True:
            try:
                frame = await asyncio.wait_for(q.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # Keep-alive ping
                await websocket.send_text(json.dumps({"ping": True}))
                continue

            await websocket.send_text(frame)

            try:
                data = json.loads(frame)
                if data.get("done"):
                    break
            except Exception:
                pass

    except (WebSocketDisconnect, Exception) as exc:
        logger.info("Screencast WebSocket for session %s closed: %s", session_id, exc)
    finally:
        subs.discard(q)
        await websocket.close(code=1000)


@app.get("/api/task/{session_id}/replay")
async def get_replay(session_id: str):
    """Return all stored JPEG frames for replay playback."""
    frames = _session_frames.get(session_id, [])
    return {"session_id": session_id, "frames": frames, "fps": 3}


@app.post("/api/settings/env")
async def save_env(req: EnvSettingRequest):
    try:
        _write_env_key(req.key, req.value)
        return {"status": "saved", "key": req.key}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"File write error: {exc}")


@app.post("/api/settings/browser")
async def save_browser_settings(req: BrowserSettingRequest):
    _browser_settings["headless"] = req.headless
    _browser_settings["max_retries"] = req.max_retries
    return {"status": "saved", **_browser_settings}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "browser_agent.server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,   # reload mode resets the event loop policy on Windows
        log_level="info",
    )
