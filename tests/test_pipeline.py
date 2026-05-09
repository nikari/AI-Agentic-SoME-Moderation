from unittest.mock import AsyncMock, patch

from moderation.pipeline import run_pipeline
from moderation.schemas import (
    ModerationDecision,
    ModerationReport,
    ModerationResult,
    Post,
    RecommendedAction,
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
