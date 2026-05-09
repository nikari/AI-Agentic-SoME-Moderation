import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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


def _mock_raw_response(raw: str) -> MagicMock:
    m = MagicMock()
    m.choices[0].message.content = raw
    return m


def _flagged_result(post_id: str = "p1", severity: Severity = Severity.HIGH) -> ModerationResult:
    return ModerationResult(
        post_id=post_id,
        decision=ModerationDecision.FLAGGED,
        reasoning="Scam detected.",
        severity=severity,
        confidence=0.9,
    )


def _allowed_result(post_id: str = "p1") -> ModerationResult:
    return ModerationResult(
        post_id=post_id,
        decision=ModerationDecision.ALLOWED,
        reasoning="No violation.",
        confidence=0.95,
    )


@patch("moderation.agents.summarizer.litellm.acompletion", new_callable=AsyncMock)
async def test_summarize_flagged_post(mock_acompletion: AsyncMock) -> None:
    mock_acompletion.return_value = _mock_response({
        "verdict": "flagged",
        "reasoning": "Multiple scam indicators confirmed.",
        "severity": "high",
        "scam_category": "pump_and_dump",
        "recommended_action": "remove",
        "dsa_explanation": "Removed per DSA Art. 17.",
        "confidence": 0.93,
    })
    report = await summarize(Post(id="p1", content="BUY MOONTOKEN!"), [_flagged_result()])
    assert report.verdict == ModerationDecision.FLAGGED
    assert report.recommended_action == RecommendedAction.REMOVE
    assert report.dsa_explanation != ""


@patch("moderation.agents.summarizer.litellm.acompletion", new_callable=AsyncMock)
async def test_summarize_allowed_post(mock_acompletion: AsyncMock) -> None:
    mock_acompletion.return_value = _mock_response({
        "verdict": "allowed",
        "reasoning": "No violation found.",
        "severity": None,
        "scam_category": None,
        "recommended_action": "none",
        "dsa_explanation": "No action taken.",
        "confidence": 0.97,
    })
    report = await summarize(Post(id="p2", content="Normal post."), [_allowed_result("p2")])
    assert report.verdict == ModerationDecision.ALLOWED
    assert report.recommended_action == RecommendedAction.NONE
    assert report.severity is None


@patch("moderation.agents.summarizer.litellm.acompletion", new_callable=AsyncMock)
async def test_summarize_resolves_conflict(mock_acompletion: AsyncMock) -> None:
    # Two agents disagree — summarizer should resolve to flagged
    mock_acompletion.return_value = _mock_response({
        "verdict": "flagged",
        "reasoning": "One agent flagged; on balance the post is suspicious.",
        "severity": "medium",
        "scam_category": "other",
        "recommended_action": "flag",
        "dsa_explanation": "Flagged for review per DSA Art. 17.",
        "confidence": 0.7,
    })
    results = [_flagged_result(severity=Severity.MEDIUM), _allowed_result()]
    report = await summarize(Post(id="p3", content="Borderline post."), results)
    assert report.verdict == ModerationDecision.FLAGGED
    assert report.recommended_action == RecommendedAction.FLAG


@patch("moderation.agents.summarizer.litellm.acompletion", new_callable=AsyncMock)
async def test_summarize_handles_markdown_fenced_response(mock_acompletion: AsyncMock) -> None:
    payload = {
        "verdict": "flagged", "reasoning": "Scam.", "severity": "high",
        "scam_category": "fake_giveaway", "recommended_action": "remove",
        "dsa_explanation": "Removed.", "confidence": 0.9,
    }
    raw = f"```json\n{json.dumps(payload)}\n```"
    mock_acompletion.return_value = _mock_raw_response(raw)
    report = await summarize(Post(id="p4", content="Free crypto!"), [_flagged_result("p4")])
    assert report.verdict == ModerationDecision.FLAGGED


@patch("moderation.agents.summarizer.litellm.acompletion", new_callable=AsyncMock)
async def test_summarize_handles_newline_in_dsa_explanation(mock_acompletion: AsyncMock) -> None:
    raw = (
        '{"verdict": "flagged", "reasoning": "Scam.", "severity": "high", '
        '"scam_category": "other", "recommended_action": "remove", '
        '"dsa_explanation": "First sentence.\nSecond sentence.", "confidence": 0.88}'
    )
    mock_acompletion.return_value = _mock_raw_response(raw)
    report = await summarize(Post(id="p5", content="Scam post."), [_flagged_result("p5")])
    assert "First sentence." in report.dsa_explanation


@patch("moderation.agents.summarizer.litellm.acompletion", new_callable=AsyncMock)
async def test_summarize_raises_on_none_content(mock_acompletion: AsyncMock) -> None:
    m = MagicMock()
    m.choices[0].message.content = None
    mock_acompletion.return_value = m
    with pytest.raises(ValueError, match="no content"):
        await summarize(Post(id="p6", content="Post."), [_flagged_result("p6")])
