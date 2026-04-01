"""Entry point for the browser automation agent.

Usage
-----
  # Claude (default):
  python main.py "Go to https://news.ycombinator.com and find the top story"

  # Azure GPT-4o:
  python main.py --model azure-gpt-4o "Search for Python on https://pypi.org"

  # Gemini 2.0 Flash:
  python main.py --model gemini-2.0-flash "Open https://example.com"

  # Headful mode:
  python main.py --no-headless "..."

  # With screenshots:
  python main.py --screenshots "..."

Environment variables (put in .env or export directly)
------------------------------------------------------
  ANTHROPIC_API_KEY          — required for claude-sonnet-4-5
  AZURE_OPENAI_ENDPOINT      — required for azure-gpt-4o
  AZURE_OPENAI_API_KEY       — required for azure-gpt-4o
  AZURE_OPENAI_DEPLOYMENT    — optional (default: gpt-4o)
  GOOGLE_API_KEY             — required for gemini-2.0-flash
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; env vars can be exported directly


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quiet noisy third-party loggers in non-verbose mode
    if not verbose:
        for noisy in ("websockets", "asyncio", "anthropic", "httpx", "aiohttp"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


async def _run(args: argparse.Namespace) -> int:
    # Lazy import avoids module-level side-effects during --help
    from browser_agent.agent.orchestrator import AgentOrchestrator
    from browser_agent.browser.session import BrowserSession
    from browser_agent.llm.registry import MODEL_CHOICES

    model_key = args.model

    session = BrowserSession(headless=not args.no_headless)

    print(f"\n{'='*60}")
    print(f"  Browser Automation Agent")
    print(f"{'='*60}")
    print(f"  Task    : {args.task}")
    print(f"  Model   : {model_key}")
    print(f"  Headless: {not args.no_headless}")
    print(f"{'='*60}\n")

    try:
        await session.start()

        orchestrator = AgentOrchestrator(
            task=args.task,
            session=session,
            model_key=model_key,
            capture_screenshots=args.screenshots,
            max_retries=args.max_retries,
        )

        result = await orchestrator.run()

        print(f"\n{'='*60}")
        print(f"  Result : {result.status.upper()}")
        print(f"  Steps  : {len(result.history)}")
        print(f"  Reason : {result.reason}")
        if result.final_state:
            print(f"  URL    : {result.final_state.url}")
        print(f"{'='*60}\n")

        if args.output:
            history_data = [s.for_history() for s in result.history]
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "task": args.task,
                        "status": result.status,
                        "reason": result.reason,
                        "steps": len(result.history),
                        "history": history_data,
                    },
                    f,
                    indent=2,
                    default=str,
                )
            print(f"History saved to: {args.output}")

        return 0 if result.status == "done" else 1

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130
    except Exception as exc:
        logging.exception("Fatal agent error: %s", exc)
        return 1
    finally:
        await session.stop()


def main() -> None:
    from browser_agent.llm.registry import MODEL_CHOICES

    parser = argparse.ArgumentParser(
        description="AI-driven browser automation agent (Playwright + CDP + multi-LLM)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "task",
        help="Natural language task, e.g. 'Go to https://example.com and click Sign In'",
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-5",
        choices=MODEL_CHOICES,
        help="LLM backend to use (default: claude-sonnet-4-5)",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        default=False,
        help="Show the browser window instead of running headlessly",
    )
    parser.add_argument(
        "--screenshots",
        action="store_true",
        default=False,
        help="Capture a screenshot after each step",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Maximum unrecoverable failures before aborting (default: 5)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Save full run history to this JSON file",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=False,
        help="Enable DEBUG-level logging",
    )

    args = parser.parse_args()
    _setup_logging(args.verbose)

    exit_code = asyncio.run(_run(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
