from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from moderation.pipeline import run_pipeline, run_pipeline_with_routing
from moderation.schemas import (
    CaseStatus,
    ModerationDecision,
    ModerationReport,
    ModerationResult,
    Post,
    RecommendedAction,
    ReviewerVerdict,
    Route,
)


@patch("moderation.pipeline.summarize", new_callable=AsyncMock)
@patch("moderation.pipeline.moderate", new_callable=AsyncMock)
async def test_pipeline_calls_agents_in_order(
    mock_moderate: AsyncMock, mock_summarize: AsyncMock
) -> None:
    post = Post(id="p1", content="Free crypto giveaway — click here!")
    mock_moderate.return_value = [
        ModerationResult(
            post_id="p1",
            decision=ModerationDecision.FLAGGED,
            reasoning="Fake giveaway detected.",
            confidence=0.9,
        )
    ]
    mock_summarize.return_value = ModerationReport(
        post_id="p1",
        verdict=ModerationDecision.FLAGGED,
        reasoning="Confirmed fake giveaway scam.",
        recommended_action=RecommendedAction.REMOVE,
        dsa_explanation="Removed per DSA Art. 17.",
        confidence=0.9,
    )

    report = await run_pipeline(post)

    mock_moderate.assert_called_once_with(post)
    mock_summarize.assert_called_once()
    assert report.verdict == ModerationDecision.FLAGGED
    assert report.recommended_action == RecommendedAction.REMOVE


def _allowed_report(post_id: str = "p1") -> ModerationReport:
    return ModerationReport(
        post_id=post_id,
        verdict=ModerationDecision.ALLOWED,
        recommended_action=RecommendedAction.NONE,
    )


def _flagged_report(post_id: str = "p1", confidence: float = 0.8) -> ModerationReport:
    return ModerationReport(
        post_id=post_id,
        verdict=ModerationDecision.FLAGGED,
        recommended_action=RecommendedAction.REMOVE,
        dsa_explanation="Removed per DSA Art. 17.",
        confidence=confidence,
    )


@patch("moderation.pipeline.notify_sender")
@patch("moderation.pipeline.single_review", new_callable=AsyncMock)
@patch("moderation.pipeline.route_initial")
@patch("moderation.pipeline.run_pipeline", new_callable=AsyncMock)
async def test_routing_auto_publish(
    mock_run: AsyncMock,
    mock_route: MagicMock,
    mock_review: AsyncMock,
    mock_notify: MagicMock,
) -> None:
    post = Post(id="p1", content="Hello world")
    mock_run.return_value = _allowed_report()
    mock_route.return_value = Route.AUTO_PUBLISH

    case = await run_pipeline_with_routing(post)

    assert case.status == CaseStatus.PUBLISHED
    assert any("auto-published" in h for h in case.history)
    mock_review.assert_not_called()
    mock_notify.assert_not_called()


@patch("moderation.pipeline.notify_sender")
@patch("moderation.pipeline.single_review", new_callable=AsyncMock)
@patch("moderation.pipeline.route_initial")
@patch("moderation.pipeline.run_pipeline", new_callable=AsyncMock)
async def test_routing_single_review_approve(
    mock_run: AsyncMock,
    mock_route: MagicMock,
    mock_review: AsyncMock,
    mock_notify: MagicMock,
) -> None:
    post = Post(id="p1", content="Borderline post")
    mock_run.return_value = _flagged_report(confidence=0.2)
    mock_route.return_value = Route.SINGLE_REVIEW_FINAL
    mock_review.return_value = ReviewerVerdict.APPROVE

    case = await run_pipeline_with_routing(post)

    assert case.status == CaseStatus.PUBLISHED
    mock_notify.assert_called_once()


@patch("moderation.pipeline.notify_sender")
@patch("moderation.pipeline.single_review", new_callable=AsyncMock)
@patch("moderation.pipeline.route_initial")
@patch("moderation.pipeline.run_pipeline", new_callable=AsyncMock)
async def test_routing_single_review_deny(
    mock_run: AsyncMock,
    mock_route: MagicMock,
    mock_review: AsyncMock,
    mock_notify: MagicMock,
) -> None:
    post = Post(id="p1", content="Scam post")
    mock_run.return_value = _flagged_report(confidence=0.2)
    mock_route.return_value = Route.SINGLE_REVIEW_FINAL
    mock_review.return_value = ReviewerVerdict.DENY

    case = await run_pipeline_with_routing(post)

    assert case.status == CaseStatus.BLOCKED
    mock_notify.assert_called_once()


@patch("moderation.pipeline.notify_sender")
@patch("moderation.pipeline.single_review", new_callable=AsyncMock)
@patch("moderation.pipeline.route_initial")
@patch("moderation.pipeline.run_pipeline", new_callable=AsyncMock)
async def test_routing_single_review_uncertain_raises(
    mock_run: AsyncMock,
    mock_route: MagicMock,
    mock_review: AsyncMock,
    mock_notify: MagicMock,
) -> None:
    post = Post(id="p1", content="Ambiguous post")
    mock_run.return_value = _flagged_report(confidence=0.2)
    mock_route.return_value = Route.SINGLE_REVIEW_FINAL
    mock_review.return_value = ReviewerVerdict.UNCERTAIN

    with pytest.raises(ValueError, match="UNCERTAIN"):
        await run_pipeline_with_routing(post)


@patch("moderation.pipeline.notify_sender")
@patch("moderation.pipeline.single_review", new_callable=AsyncMock)
@patch("moderation.pipeline.route_initial")
@patch("moderation.pipeline.run_pipeline", new_callable=AsyncMock)
async def test_routing_hold_await_appeal(
    mock_run: AsyncMock,
    mock_route: MagicMock,
    mock_review: AsyncMock,
    mock_notify: MagicMock,
) -> None:
    post = Post(id="p1", content="High-confidence scam")
    mock_run.return_value = _flagged_report(confidence=0.85)
    mock_route.return_value = Route.HOLD_AWAIT_APPEAL

    case = await run_pipeline_with_routing(post)

    assert case.status == CaseStatus.PENDING
    mock_review.assert_not_called()
    mock_notify.assert_called_once()
    assert "appeal" in (case.final_message_to_sender or "").lower()
