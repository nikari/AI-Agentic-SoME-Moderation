import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from moderation.agents.moderator import moderate
from moderation.schemas import (
    ModerationDecision,
    ModerationResult,
    Post,
    Severity,
    ViolationCategory,
)


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
            "violations": [
                {"category": "crypto_scam", "score": 0.95, "reasoning": "Pump-and-dump."}
            ],
            "confidence": 0.95,
        }
    )
    results = await moderate(Post(id="p1", content="BUY MOONTOKEN NOW 100X GUARANTEED!"))

    assert len(results) == 1
    r = results[0]
    assert r.decision == ModerationDecision.FLAGGED
    assert r.severity == Severity.HIGH
    assert len(r.violations) == 1
    assert r.violations[0].category == ViolationCategory.CRYPTO_SCAM
    assert r.violations[0].score == 0.95
    assert r.confidence == 0.95
    assert r.post_id == "p1"


@patch("moderation.agents.moderator.litellm.acompletion", new_callable=AsyncMock)
async def test_moderate_returns_multiple_violations(mock_acompletion: AsyncMock) -> None:
    mock_acompletion.return_value = _mock_response(
        {
            "decision": "flagged",
            "reasoning": "Crypto giveaway scam impersonating a celebrity, plus mass-marketed.",
            "severity": "critical",
            "violations": [
                {"category": "crypto_scam", "score": 0.98, "reasoning": "Fake giveaway."},
                {"category": "spam", "score": 0.6, "reasoning": "Mass-marketed."},
            ],
            "confidence": 0.96,
        }
    )
    results = await moderate(Post(id="p-multi", content="Free ETH for first 1000!"))

    r = results[0]
    assert len(r.violations) == 2
    categories = {v.category for v in r.violations}
    assert ViolationCategory.CRYPTO_SCAM in categories
    assert ViolationCategory.SPAM in categories


@patch("moderation.agents.moderator.litellm.acompletion", new_callable=AsyncMock)
async def test_moderate_allows_clean_post(mock_acompletion: AsyncMock) -> None:
    mock_acompletion.return_value = _mock_response({"decision": "allowed"})
    results = await moderate(Post(id="p2", content="Bitcoin had an interesting week."))

    r = results[0]
    assert r.decision == ModerationDecision.ALLOWED
    assert r.severity is None
    assert r.violations == []
    assert r.confidence is None


@patch("moderation.agents.moderator.litellm.acompletion", new_callable=AsyncMock)
async def test_moderate_drops_confidence_from_allowed_responses(
    mock_acompletion: AsyncMock,
) -> None:
    # Defensive: even if the LLM emits confidence on an allowed response,
    # the parser must strip it before constructing ModerationResult.
    mock_acompletion.return_value = _mock_response({"decision": "allowed", "confidence": 0.98})
    results = await moderate(Post(id="p-drift", content="clean"))
    assert results[0].confidence is None


def test_moderation_result_validator_rejects_allowed_with_confidence() -> None:
    with pytest.raises(ValidationError):
        ModerationResult(
            post_id="t",
            decision=ModerationDecision.ALLOWED,
            confidence=0.9,
        )


def test_moderation_result_validator_rejects_flagged_without_confidence() -> None:
    with pytest.raises(ValidationError):
        ModerationResult(
            post_id="t",
            decision=ModerationDecision.FLAGGED,
            reasoning="x",
        )


@patch("moderation.agents.moderator.litellm.acompletion", new_callable=AsyncMock)
async def test_moderate_handles_markdown_fenced_response(mock_acompletion: AsyncMock) -> None:
    raw = (
        '```json\n{"decision": "flagged", "reasoning": "Scam.", "severity": "high", '
        '"violations": [{"category": "crypto_scam", "score": 0.9}], "confidence": 0.9}\n```'
    )
    mock_acompletion.return_value = _mock_raw_response(raw)
    results = await moderate(Post(id="p3", content="Free ETH giveaway!"))
    assert results[0].decision == ModerationDecision.FLAGGED
    assert results[0].violations[0].category == ViolationCategory.CRYPTO_SCAM


@patch("moderation.agents.moderator.litellm.acompletion", new_callable=AsyncMock)
async def test_moderate_handles_newline_in_reasoning(mock_acompletion: AsyncMock) -> None:
    # Literal newline inside the reasoning string — the real-world bug we hit
    raw = (
        '{"decision": "flagged", "reasoning": "Line one\nLine two.", "severity": "medium", '
        '"violations": [{"category": "other", "score": 0.5}], "confidence": 0.8}'
    )
    mock_acompletion.return_value = _mock_raw_response(raw)
    results = await moderate(Post(id="p4", content="Some suspicious post."))
    assert results[0].decision == ModerationDecision.FLAGGED
    assert "Line one" in results[0].reasoning


@patch("moderation.agents.moderator.litellm.acompletion", new_callable=AsyncMock)
async def test_moderate_handles_post_with_special_chars(mock_acompletion: AsyncMock) -> None:
    mock_acompletion.return_value = _mock_response(
        {
            "decision": "flagged",
            "reasoning": "Investment scam.",
            "severity": "high",
            "violations": [{"category": "other", "score": 0.85}],
            "confidence": 0.95,
        }
    )
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


@patch("moderation.agents.moderator.litellm.acompletion", new_callable=AsyncMock)
async def test_moderate_combined_agent_for_text_and_image(mock_acompletion: AsyncMock) -> None:
    mock_acompletion.return_value = _mock_response(
        {
            "decision": "flagged",
            "reasoning": "Caption combined with fake profit screenshot indicates crypto scam.",
            "severity": "high",
            "violations": [
                {"category": "crypto_scam", "score": 0.93, "reasoning": "Fake screenshot."}
            ],
            "confidence": 0.93,
        }
    )
    fake_image = b"\x89PNG\r\n\x1a\n"  # minimal PNG-like header
    post = Post(
        id="img-p1",
        content="Check out my gains!",
        image_data=fake_image,
        image_media_type="image/png",
    )
    results = await moderate(post)

    assert len(results) == 1
    assert results[0].decision == ModerationDecision.FLAGGED
    assert results[0].violations[0].category == ViolationCategory.CRYPTO_SCAM
    # Single call includes both text and image parts
    mock_acompletion.assert_called_once()
    user_message = mock_acompletion.call_args.kwargs["messages"][1]
    content_types = [part["type"] for part in user_message["content"]]
    assert "text" in content_types
    assert "image_url" in content_types


@patch("moderation.agents.moderator.litellm.acompletion", new_callable=AsyncMock)
async def test_moderate_skips_image_agent_without_image(mock_acompletion: AsyncMock) -> None:
    mock_acompletion.return_value = _mock_response({"decision": "allowed", "confidence": 0.95})
    results = await moderate(Post(id="text-only", content="Normal post."))
    assert len(results) == 1
    mock_acompletion.assert_called_once()
