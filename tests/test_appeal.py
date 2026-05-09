from unittest.mock import AsyncMock, patch

import pytest

from moderation.appeal import handle_appeal
from moderation.schemas import (
    Case,
    CaseStatus,
    ModerationDecision,
    ModerationReport,
    ModerationResult,
    Post,
    RecommendedAction,
    ReviewerVerdict,
    Route,
)


def _post() -> Post:
    return Post(id="p1", content="suspicious post")


def _report(confidence: float) -> ModerationReport:
    return ModerationReport(
        post_id="p1",
        verdict=ModerationDecision.FLAGGED,
        reasoning="x",
        recommended_action=RecommendedAction.FLAG,
        dsa_explanation="DSA reasons.",
        confidence=confidence,
    )


def _case(confidence: float) -> Case:
    return Case(post_id="p1", report=_report(confidence), route=Route.HOLD_AWAIT_APPEAL)


def _moderation_result(confidence: float) -> ModerationResult:
    return ModerationResult(
        post_id="p1",
        decision=ModerationDecision.FLAGGED,
        reasoning="re-eval reasoning",
        confidence=confidence,
    )


@patch("moderation.appeal.notify_sender")
@patch("moderation.appeal._ai_reevaluate", new_callable=AsyncMock)
async def test_high_confidence_reeval_upholds_blocks(mock_reeval: AsyncMock, _mock_notify) -> None:
    mock_reeval.return_value = _moderation_result(0.95)
    case = await handle_appeal(_post(), _case(0.95))
    assert case.status == CaseStatus.BLOCKED
    mock_reeval.assert_awaited_once()


@patch("moderation.appeal.notify_sender")
@patch("moderation.appeal.single_review", new_callable=AsyncMock)
@patch("moderation.appeal._ai_reevaluate", new_callable=AsyncMock)
async def test_high_confidence_reeval_drops_to_human_review_approve_publishes(
    mock_reeval: AsyncMock, mock_single: AsyncMock, _mock_notify
) -> None:
    mock_reeval.return_value = _moderation_result(0.85)
    mock_single.return_value = ReviewerVerdict.APPROVE
    case = await handle_appeal(_post(), _case(0.95))
    assert case.status == CaseStatus.PUBLISHED
    # single_review at HUMAN_REVIEW tier must NOT allow uncertain
    _, kwargs = mock_single.call_args
    assert kwargs["allow_uncertain"] is False


@patch("moderation.appeal.notify_sender")
@patch("moderation.appeal.panel_review", new_callable=AsyncMock)
@patch("moderation.appeal.single_review", new_callable=AsyncMock)
@patch("moderation.appeal._ai_reevaluate", new_callable=AsyncMock)
async def test_high_confidence_reeval_drops_to_panel_majority_publishes(
    mock_reeval: AsyncMock,
    mock_single: AsyncMock,
    mock_panel: AsyncMock,
    _mock_notify,
) -> None:
    mock_reeval.return_value = _moderation_result(0.50)
    mock_single.return_value = ReviewerVerdict.UNCERTAIN
    mock_panel.return_value = [
        ReviewerVerdict.APPROVE,
        ReviewerVerdict.APPROVE,
        ReviewerVerdict.DENY,
    ]
    case = await handle_appeal(_post(), _case(0.95))
    assert case.status == CaseStatus.PUBLISHED
    # single_review at panel-eligible tier must allow uncertain
    _, kwargs = mock_single.call_args
    assert kwargs["allow_uncertain"] is True


@patch("moderation.appeal.notify_sender")
@patch("moderation.appeal.panel_review", new_callable=AsyncMock)
@patch("moderation.appeal.single_review", new_callable=AsyncMock)
async def test_panel_minority_approve_blocks(
    mock_single: AsyncMock,
    mock_panel: AsyncMock,
    _mock_notify,
) -> None:
    mock_single.return_value = ReviewerVerdict.UNCERTAIN
    mock_panel.return_value = [
        ReviewerVerdict.APPROVE,
        ReviewerVerdict.DENY,
        ReviewerVerdict.DENY,
    ]
    # confidence 0.50 → starts directly in HUMAN_REVIEW_WITH_PANEL (no AI re-eval)
    case = await handle_appeal(_post(), _case(0.50))
    assert case.status == CaseStatus.BLOCKED


@patch("moderation.appeal.notify_sender")
@patch("moderation.appeal.single_review", new_callable=AsyncMock)
async def test_uncertain_at_human_review_tier_raises(mock_single: AsyncMock, _mock_notify) -> None:
    mock_single.return_value = ReviewerVerdict.UNCERTAIN
    with pytest.raises(ValueError, match="UNCERTAIN"):
        await handle_appeal(_post(), _case(0.80))


@patch("moderation.appeal.notify_sender")
@patch("moderation.appeal.single_review", new_callable=AsyncMock)
async def test_human_review_deny_blocks(mock_single: AsyncMock, _mock_notify) -> None:
    mock_single.return_value = ReviewerVerdict.DENY
    case = await handle_appeal(_post(), _case(0.80))
    assert case.status == CaseStatus.BLOCKED


async def test_appeal_rejects_non_held_case() -> None:
    bad = Case(post_id="p1", report=_report(0.95), route=Route.AUTO_PUBLISH)
    with pytest.raises(ValueError, match="HOLD_AWAIT_APPEAL"):
        await handle_appeal(_post(), bad)


async def test_appeal_rejects_already_terminal_case() -> None:
    held = _case(0.50)
    held.status = CaseStatus.PUBLISHED
    with pytest.raises(ValueError, match="terminal"):
        await handle_appeal(_post(), held)
