"""Pipeline: Post → moderation agents → summarizer → ModerationReport."""

from moderation.agents.moderator import moderate
from moderation.agents.summarizer import summarize
from moderation.schemas import ModerationReport, Post


async def run_pipeline(post: Post) -> ModerationReport:
    """Run the full moderation pipeline on a single post."""
    results = await moderate(post)
    return await summarize(post, results)
