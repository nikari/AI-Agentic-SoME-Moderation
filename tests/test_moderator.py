import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from moderation.agents.moderator import moderate
from moderation.schemas import ModerationDecision, Post, ScamCategory, Severity


def _mock_response(payload: dict) -> MagicMock:
    m = MagicMock()
    m.choices[0].message.content = json.dumps(payload)
    return m


def _mock_raw_response(raw: str) -> MagicMock:
    m = MagicMock()
    m.choices[0].message.content = raw
    return m


@patch("moderation.agents.moderator.litellm.acompletion", new_callable=AsyncMock)
async def test_moderate_flags_scam(mock_acompletion: AsyncMock) -> None:
    mock_acompletion.return_value = _mock_response(
        {
            "decision": "flagged",
            "reasoning": "Classic pump-and-dump language.",
            "severity": "high",
            "scam_category": "pump_and_dump",
            "confidence": 0.95,
        }
    )
    results = await moderate(Post(id="p1", content="BUY MOONTOKEN NOW 100X GUARANTEED!"))

    assert len(results) == 1
    r = results[0]
    assert r.decision == ModerationDecision.FLAGGED
    assert r.severity == Severity.HIGH
    assert r.scam_category == ScamCategory.PUMP_AND_DUMP
    assert r.confidence == 0.95
    assert r.post_id == "p1"


@patch("moderation.agents.moderator.litellm.acompletion", new_callable=AsyncMock)
async def test_moderate_allows_clean_post(mock_acompletion: AsyncMock) -> None:
    mock_acompletion.return_value = _mock_response(
        {
            "decision": "allowed",
            "reasoning": "No scam indicators detected.",
            "severity": None,
            "scam_category": None,
            "confidence": 0.98,
        }
    )
    results = await moderate(Post(id="p2", content="Bitcoin had an interesting week."))

    r = results[0]
    assert r.decision == ModerationDecision.ALLOWED
    assert r.severity is None
    assert r.scam_category is None


@patch("moderation.agents.moderator.litellm.acompletion", new_callable=AsyncMock)
async def test_moderate_handles_markdown_fenced_response(mock_acompletion: AsyncMock) -> None:
    raw = '```json\n{"decision": "flagged", "reasoning": "Scam.", "severity": "high", "scam_category": "fake_giveaway", "confidence": 0.9}\n```'
    mock_acompletion.return_value = _mock_raw_response(raw)
    results = await moderate(Post(id="p3", content="Free ETH giveaway!"))
    assert results[0].decision == ModerationDecision.FLAGGED


@patch("moderation.agents.moderator.litellm.acompletion", new_callable=AsyncMock)
async def test_moderate_handles_newline_in_reasoning(mock_acompletion: AsyncMock) -> None:
    # Literal newline inside the reasoning string — the real-world bug we hit
    raw = '{"decision": "flagged", "reasoning": "Line one\nLine two.", "severity": "medium", "scam_category": "other", "confidence": 0.8}'
    mock_acompletion.return_value = _mock_raw_response(raw)
    results = await moderate(Post(id="p4", content="Some suspicious post."))
    assert results[0].decision == ModerationDecision.FLAGGED
    assert "Line one" in results[0].reasoning


@patch("moderation.agents.moderator.litellm.acompletion", new_callable=AsyncMock)
async def test_moderate_handles_post_with_special_chars(mock_acompletion: AsyncMock) -> None:
    mock_acompletion.return_value = _mock_response({
        "decision": "flagged",
        "reasoning": "Investment scam.",
        "severity": "high",
        "scam_category": "other",
        "confidence": 0.95,
    })
    post = Post(id="p5", content="I make $8,000/week 😴 Pay $149. Link in bio 🔗")
    results = await moderate(post)
    assert results[0].decision == ModerationDecision.FLAGGED


@patch("moderation.agents.moderator.litellm.acompletion", new_callable=AsyncMock)
async def test_moderate_raises_on_none_content(mock_acompletion: AsyncMock) -> None:
    m = MagicMock()
    m.choices[0].message.content = None
    mock_acompletion.return_value = m
    with pytest.raises(ValueError, match="no content"):
        await moderate(Post(id="p6", content="Some post."))
