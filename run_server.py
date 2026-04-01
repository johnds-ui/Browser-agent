"""
Launcher for the Browser Agent API server.

Run with:
    python run_server.py

The WindowsProactorEventLoopPolicy MUST be set here — at the very first line
of the process — before uvicorn or anyio creates an event loop.
Playwright cannot spawn subprocesses on the default SelectorEventLoop on Windows.
"""
import sys

if sys.platform == "win32":
    import asyncio
    # ProactorEventLoop is required for Playwright subprocess spawning.
    # WindowsProactorEventLoopPolicy is deprecated in 3.14+ (Proactor is now
    # the default), so only set it on older Python versions.
    import sys as _sys
    if _sys.version_info < (3, 14):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    else:
        # Python 3.14+ defaults to ProactorEventLoop on Windows — nothing to do.
        pass

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "browser_agent.server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,   # reload mode resets the event loop policy — keep False
        log_level="info",
    )
