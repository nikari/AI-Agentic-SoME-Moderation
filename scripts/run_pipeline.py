#!/usr/bin/env python3
"""CLI: moderate a single social media post.

Usage:
    uv run python scripts/run_pipeline.py "Buy MOONTOKEN now — 100x guaranteed!"
    uv run python scripts/run_pipeline.py "..." --id post-123 --platform twitter
"""

import argparse
import asyncio
import json

from dotenv import load_dotenv

load_dotenv()

from moderation.pipeline import run_pipeline  # noqa: E402
from moderation.schemas import Post  # noqa: E402
from moderation.tracing import setup_tracing  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Moderate a single social media post.")
    parser.add_argument("content", help="Text content of the post")
    parser.add_argument("--id", default="cli-post", dest="post_id")
    parser.add_argument("--platform", default=None)
    args = parser.parse_args()

    setup_tracing()
    post = Post(id=args.post_id, content=args.content, platform=args.platform)
    report = asyncio.run(run_pipeline(post))
    print(json.dumps(report.model_dump(), indent=2))


if __name__ == "__main__":
    main()
