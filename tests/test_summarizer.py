import json
from unittest.mock import AsyncMock, MagicMock, patch

from moderation.agents.summarizer import summarize
from moderation.schemas import (
    ModerationDecision,
    ModerationResult,
    Post,
    RecommendedAction,
    Severity,
)


def _mock_response(payload: dict) -> MagicMock:
    m = MagicMock()
    m.choices[0].message.content = json.dumps(payload)
    return m


@patch("moderation.agents.summarizer.litellm.acompletion", new_callable=AsyncMock)
async def test_summarize_flagged_post(mock_acompletion: AsyncMock) -> None:
    mock_acompletion.return_value = _mock_response({
        "verdict": "flagged",
        "reasoning": "Multiple scam indicators confirmed across agents.",
        "severity": "high",
        "scam_category": "pump_and_dump",
        "recommended_action": "remove",
        "dsa_explanation": (
            "The content was removed pursuant to DSA Art. 17 for promoting "
            "a financial scheme likely to cause consumer harm."
        ),
        "confidence": 0.93,
    })
    post = Post(id="p1", content="BUY MOONTOKEN NOW!")
    results = [
        ModerationResult(
            post_id="p1",
            decision=ModerationDecision.FLAGGED,
            reasoning="Pump-and-dump detected.",
            severity=Severity.HIGH,
            confidence=0.95,
        )
    ]
    report = await summarize(post, results)

    assert report.verdict == ModerationDecision.FLAGGED
    assert report.recommended_action == RecommendedAction.REMOVE
    assert report.dsa_explanation != ""
    assert report.post_id == "p1"


@patch("moderation.agents.summarizer.litellm.acompletion", new_callable=AsyncMock)
async def test_summarize_allowed_post(mock_acompletion: AsyncMock) -> None:
    mock_acompletion.return_value = _mock_response({
        "verdict": "allowed",
        "reasoning": "No violation found. Content is informational.",
        "severity": None,
        "scam_category": None,
        "recommended_action": "none",
        "dsa_explanation": "No action taken. Content does not violate platform rules.",
        "confidence": 0.97,
    })
    post = Post(id="p2", content="Here is a breakdown of Ethereum gas fees.")
    results = [
        ModerationResult(
            post_id="p2",
            decision=ModerationDecision.ALLOWED,
            reasoning="Educational content.",
            confidence=0.97,
        )
    ]
    report = await summarize(post, results)

    assert report.verdict == ModerationDecision.ALLOWED
    assert report.recommended_action == RecommendedAction.NONE
    assert report.severity is None
