"""Stub interfaces for human-in-the-loop review and sender notification.

`single_review` and `panel_review` raise NotImplementedError by default so that
silent fall-through is impossible — when the appeal flow reaches a human step
without a real implementation wired up, it fails loudly.

`notify_sender` prints to stdout for now so CLI runs are observable. Replace
with a real channel (email, in-app message) when one is available.

To plug in a real reviewer, reassign the function on this module:

    from moderation import review

    async def my_reviewer(post, report, allow_uncertain):
        ...

    review.single_review = my_reviewer

For tests, monkey-patch with `mocker.patch("moderation.review.single_review", ...)`
or patch where it's used in the appeal module.
"""

from moderation.schemas import ModerationReport, Post, ReviewerVerdict


async def single_review(
    post: Post,
    report: ModerationReport,
    allow_uncertain: bool,
) -> ReviewerVerdict:
    """One human reviews the post and returns APPROVE / DENY / UNCERTAIN.

    UNCERTAIN must only be returned when allow_uncertain=True (panel-eligible tier).
    """
    raise NotImplementedError("connect a reviewer UI")


async def panel_review(
    post: Post,
    report: ModerationReport,
) -> list[ReviewerVerdict]:
    """Three human reviewers each return APPROVE or DENY (no UNCERTAIN at panel)."""
    raise NotImplementedError("connect a reviewer UI")


def notify_sender(post: Post, message: str) -> None:
    """Notify the sender of the post about a moderation outcome."""
    print(f"[notify_sender] post={post.id}: {message}")
