#!/usr/bin/env python3
"""CLI: moderate a single social media post.

Usage:
    uv run python scripts/run_pipeline.py "Buy MOONTOKEN now — 100x guaranteed!"
    uv run python scripts/run_pipeline.py "..." --id post-123 --platform twitter
    uv run python scripts/run_pipeline.py "..." --appeal
"""

import argparse
import asyncio
import json

from dotenv import load_dotenv

load_dotenv()

from moderation.appeal import handle_appeal  # noqa: E402
from moderation.pipeline import run_pipeline_with_routing  # noqa: E402
from moderation.schemas import Case, Post, Route  # noqa: E402
from moderation.tracing import setup_tracing  # noqa: E402


async def _run(post: Post, appeal: bool) -> Case:
    case = await run_pipeline_with_routing(post)
    if appeal and case.route == Route.HOLD_AWAIT_APPEAL:
        return await handle_appeal(post, case)
    return case


def main() -> None:
    parser = argparse.ArgumentParser(description="Moderate a single social media post.")
    parser.add_argument("content", help="Text content of the post")
    parser.add_argument("--id", default="cli-post", dest="post_id")
    parser.add_argument("--platform", default=None)
    parser.add_argument(
        "--appeal",
        action="store_true",
        help="After initial moderation, attempt the appeal flow "
        "(fails with NotImplementedError until human stubs are wired).",
    )
    args = parser.parse_args()

    setup_tracing()
    post = Post(id=args.post_id, content=args.content, platform=args.platform)
    case = asyncio.run(_run(post, appeal=args.appeal))
    print(json.dumps(case.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
