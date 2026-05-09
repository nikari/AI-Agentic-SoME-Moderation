import json
from unittest.mock import AsyncMock, MagicMock, patch

from moderation.agents.moderator import moderate
from moderation.schemas import ModerationDecision, Post, Severity


def _mock_response(payload: dict) -> MagicMock:
    m = MagicMock()
    m.choices[0].message.content = json.dumps(payload)
    return m


@patch("moderation.agents.moderator.litellm.acompletion", new_callable=AsyncMock)
async def test_moderate_flags_scam(mock_acompletion: AsyncMock) -> None:
    mock_acompletion.return_value = _mock_response({
        "decision": "flagged",
        "reasoning": "Classic pump-and-dump language.",
        "severity": "high",
        "scam_category": "pump_and_dump",
        "confidence": 0.95,
    })
    results = await moderate(Post(id="p1", content="BUY MOONTOKEN NOW 100X GUARANTEED!"))

    assert len(results) == 1
    r = results[0]
    assert r.decision == ModerationDecision.FLAGGED
    assert r.severity == Severity.HIGH
    assert r.confidence == 0.95
    assert r.post_id == "p1"


@patch("moderation.agents.moderator.litellm.acompletion", new_callable=AsyncMock)
async def test_moderate_allows_clean_post(mock_acompletion: AsyncMock) -> None:
    mock_acompletion.return_value = _mock_response({
        "decision": "allowed",
        "reasoning": "No scam indicators detected.",
        "severity": None,
        "scam_category": None,
        "confidence": 0.98,
    })
    results = await moderate(Post(id="p2", content="Bitcoin had an interesting week."))

    r = results[0]
    assert r.decision == ModerationDecision.ALLOWED
    assert r.severity is None
    assert r.scam_category is None
